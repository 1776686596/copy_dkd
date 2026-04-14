from __future__ import annotations

import sqlalchemy
import uuid

from ....core import app
from ....entity.persistence import rag as persistence_rag
from ....rag.knowledge.builtin_local_faq import (
    BUILTIN_LOCAL_FAQ_PLUGIN_ID,
    get_builtin_local_faq_engine,
)


class KnowledgeService:
    """知识库服务"""

    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    async def get_knowledge_bases(self) -> list[dict]:
        """获取所有知识库"""
        return await self.ap.rag_mgr.get_all_knowledge_base_details()

    async def get_knowledge_base(self, kb_uuid: str) -> dict | None:
        """获取知识库"""
        return await self.ap.rag_mgr.get_knowledge_base_details(kb_uuid)

    async def create_knowledge_base(self, kb_data: dict) -> str:
        """创建知识库"""
        # In new architecture, we delegate entirely to RAGManager which uses plugins.
        # Legacy internal KB creation is removed.

        knowledge_engine_plugin_id = kb_data.get('knowledge_engine_plugin_id')
        if not knowledge_engine_plugin_id:
            raise ValueError('knowledge_engine_plugin_id is required')

        kb = await self.ap.rag_mgr.create_knowledge_base(
            name=kb_data.get('name', 'Untitled'),
            knowledge_engine_plugin_id=knowledge_engine_plugin_id,
            creation_settings=kb_data.get('creation_settings', {}),
            retrieval_settings=kb_data.get('retrieval_settings', {}),
            description=kb_data.get('description', ''),
        )
        return kb.uuid

    async def update_knowledge_base(self, kb_uuid: str, kb_data: dict) -> None:
        """更新知识库"""
        # Filter to only mutable fields
        filtered_data = {k: v for k, v in kb_data.items() if k in persistence_rag.KnowledgeBase.MUTABLE_FIELDS}

        if not filtered_data:
            return

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_rag.KnowledgeBase)
            .values(filtered_data)
            .where(persistence_rag.KnowledgeBase.uuid == kb_uuid)
        )
        await self.ap.rag_mgr.remove_knowledge_base_from_runtime(kb_uuid)

        kb = await self.get_knowledge_base(kb_uuid)
        if kb is None:
            raise Exception('Knowledge base not found after update')

        await self.ap.rag_mgr.load_knowledge_base(kb)

    async def _check_doc_capability(self, kb_uuid: str, operation: str) -> None:
        """Check if the KB's Knowledge Engine supports document operations.

        Args:
            kb_uuid: Knowledge base UUID.
            operation: Human-readable operation name for error messages.

        Raises:
            Exception: If the KB does not support doc_ingestion.
        """
        kb_info = await self.ap.rag_mgr.get_knowledge_base_details(kb_uuid)
        if not kb_info:
            raise Exception('Knowledge base not found')
        capabilities = kb_info.get('knowledge_engine', {}).get('capabilities', [])
        if 'doc_ingestion' not in capabilities:
            raise Exception(f'This knowledge base does not support {operation}')

    async def store_file(self, kb_uuid: str, file_id: str, parser_plugin_id: str | None = None) -> str:
        """存储文件"""
        runtime_kb = await self.ap.rag_mgr.get_knowledge_base_by_uuid(kb_uuid)
        if runtime_kb is None:
            raise Exception('Knowledge base not found')

        await self._check_doc_capability(kb_uuid, 'document upload')

        result = await runtime_kb.store_file(file_id, parser_plugin_id=parser_plugin_id)

        # Update the KB's updated_at timestamp
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_rag.KnowledgeBase)
            .values(updated_at=sqlalchemy.func.now())
            .where(persistence_rag.KnowledgeBase.uuid == kb_uuid)
        )

        return result

    async def retrieve_knowledge_base(
        self, kb_uuid: str, query: str, retrieval_settings: dict | None = None
    ) -> list[dict]:
        """检索知识库"""
        runtime_kb = await self.ap.rag_mgr.get_knowledge_base_by_uuid(kb_uuid)
        if runtime_kb is None:
            raise Exception('Knowledge base not found')

        # Pass retrieval_settings
        results = await runtime_kb.retrieve(query, settings=retrieval_settings)

        return [result.model_dump() for result in results]

    async def get_files_by_knowledge_base(self, kb_uuid: str) -> list[dict]:
        """获取知识库文件"""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_rag.File).where(persistence_rag.File.kb_id == kb_uuid)
        )
        files = result.all()
        return [self.ap.persistence_mgr.serialize_model(persistence_rag.File, file) for file in files]

    async def delete_file(self, kb_uuid: str, file_id: str) -> None:
        """删除文件"""
        runtime_kb = await self.ap.rag_mgr.get_knowledge_base_by_uuid(kb_uuid)
        if runtime_kb is None:
            raise Exception('Knowledge base not found')

        await self._check_doc_capability(kb_uuid, 'document deletion')

        await runtime_kb.delete_file(file_id)

        # Update the KB's updated_at timestamp
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_rag.KnowledgeBase)
            .values(updated_at=sqlalchemy.func.now())
            .where(persistence_rag.KnowledgeBase.uuid == kb_uuid)
        )

    async def delete_knowledge_base(self, kb_uuid: str) -> None:
        """删除知识库"""
        # Delete from DB first to commit the deletion, then clean up runtime/plugin (best-effort)
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_rag.KnowledgeBase).where(persistence_rag.KnowledgeBase.uuid == kb_uuid)
        )
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_rag.LocalFAQEntry).where(persistence_rag.LocalFAQEntry.kb_id == kb_uuid)
        )

        # delete files
        # NOTE: Chunk cleanup is for legacy (pre-plugin) KBs that stored chunks locally.
        # For plugin-based Knowledge Engines, the Chunk table is not populated, so this is a no-op.
        files = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_rag.File).where(persistence_rag.File.kb_id == kb_uuid)
        )
        for file in files:
            # delete chunks
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.delete(persistence_rag.Chunk).where(persistence_rag.Chunk.file_id == file.uuid)
            )
            # delete file
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.delete(persistence_rag.File).where(persistence_rag.File.uuid == file.uuid)
            )

        # Remove from runtime and notify plugin (best-effort, DB is already cleaned up)
        await self.ap.rag_mgr.delete_knowledge_base(kb_uuid)

    # ================= Knowledge Engine Discovery =================

    async def list_knowledge_engines(self) -> list[dict]:
        """List all available Knowledge Engines from plugins."""
        engines = [get_builtin_local_faq_engine()]

        if not self.ap.plugin_connector.is_enable_plugin:
            return engines

        # Get KnowledgeEngine plugins
        try:
            knowledge_engines = await self.ap.plugin_connector.list_knowledge_engines()
            engines.extend(knowledge_engines)
        except Exception as e:
            self.ap.logger.warning(f'Failed to list Knowledge Engines from plugins: {e}')

        return engines

    async def list_parsers(self, mime_type: str | None = None) -> list[dict]:
        """List available parsers, optionally filtered by MIME type."""
        if not self.ap.plugin_connector.is_enable_plugin:
            return []
        try:
            parsers = await self.ap.plugin_connector.list_parsers()
            if mime_type:
                parsers = [p for p in parsers if mime_type in p.get('supported_mime_types', [])]
            return parsers
        except Exception as e:
            self.ap.logger.warning(f'Failed to list parsers: {e}')
            return []

    async def get_engine_creation_schema(self, plugin_id: str) -> dict:
        """Get creation settings schema for a specific Knowledge Engine."""
        if plugin_id == BUILTIN_LOCAL_FAQ_PLUGIN_ID:
            return get_builtin_local_faq_engine().get('creation_schema', [])
        try:
            return await self.ap.plugin_connector.get_rag_creation_schema(plugin_id)
        except Exception as e:
            self.ap.logger.warning(f'Failed to get creation schema for {plugin_id}: {e}')
            return {}

    async def get_engine_retrieval_schema(self, plugin_id: str) -> dict:
        """Get retrieval settings schema for a specific Knowledge Engine."""
        if plugin_id == BUILTIN_LOCAL_FAQ_PLUGIN_ID:
            return get_builtin_local_faq_engine().get('retrieval_schema', [])
        try:
            return await self.ap.plugin_connector.get_rag_retrieval_schema(plugin_id)
        except Exception as e:
            self.ap.logger.warning(f'Failed to get retrieval schema for {plugin_id}: {e}')
            return {}

    async def _ensure_local_faq_kb(self, kb_uuid: str) -> dict:
        kb_info = await self.ap.rag_mgr.get_knowledge_base_details(kb_uuid)
        if not kb_info:
            raise Exception('Knowledge base not found')
        if kb_info.get('knowledge_engine_plugin_id') != BUILTIN_LOCAL_FAQ_PLUGIN_ID:
            raise Exception('This knowledge base is not a local FAQ knowledge base')
        return kb_info

    async def get_local_faq_entries(self, kb_uuid: str) -> list[dict]:
        await self._ensure_local_faq_kb(kb_uuid)
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_rag.LocalFAQEntry)
            .where(persistence_rag.LocalFAQEntry.kb_id == kb_uuid)
            .order_by(
                persistence_rag.LocalFAQEntry.sort_order.asc(),
                persistence_rag.LocalFAQEntry.created_at.asc(),
            )
        )
        rows = result.all()
        return [self.ap.persistence_mgr.serialize_model(persistence_rag.LocalFAQEntry, row) for row in rows]

    async def create_local_faq_entry(self, kb_uuid: str, payload: dict) -> dict:
        await self._ensure_local_faq_kb(kb_uuid)
        questions = self._normalize_questions(payload.get('questions'))
        answer = str(payload.get('answer', '')).strip()
        if not questions or not answer:
            raise ValueError('questions and answer are required')

        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_rag.LocalFAQEntry).where(persistence_rag.LocalFAQEntry.kb_id == kb_uuid)
        )
        next_sort_order = max((entry.sort_order for entry in result.all()), default=-1) + 1

        entry_data = {
            'uuid': str(uuid.uuid4()),
            'kb_id': kb_uuid,
            'questions': questions,
            'answer': answer,
            'source_file_id': payload.get('source_file_id'),
            'enabled': bool(payload.get('enabled', True)),
            'sort_order': int(payload.get('sort_order', next_sort_order)),
        }
        await self.ap.persistence_mgr.execute_async(sqlalchemy.insert(persistence_rag.LocalFAQEntry).values(entry_data))
        await self._touch_knowledge_base(kb_uuid)
        return entry_data

    async def update_local_faq_entry(self, kb_uuid: str, entry_uuid: str, payload: dict) -> dict:
        await self._ensure_local_faq_kb(kb_uuid)
        update_data: dict = {}

        if 'questions' in payload:
            questions = self._normalize_questions(payload.get('questions'))
            if not questions:
                raise ValueError('questions cannot be empty')
            update_data['questions'] = questions
        if 'answer' in payload:
            answer = str(payload.get('answer', '')).strip()
            if not answer:
                raise ValueError('answer cannot be empty')
            update_data['answer'] = answer
        if 'enabled' in payload:
            update_data['enabled'] = bool(payload.get('enabled'))
        if 'sort_order' in payload:
            update_data['sort_order'] = int(payload.get('sort_order'))

        if not update_data:
            return {'uuid': entry_uuid}

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_rag.LocalFAQEntry)
            .where(persistence_rag.LocalFAQEntry.uuid == entry_uuid)
            .where(persistence_rag.LocalFAQEntry.kb_id == kb_uuid)
            .values(update_data)
        )
        await self._touch_knowledge_base(kb_uuid)
        return {'uuid': entry_uuid}

    async def delete_local_faq_entry(self, kb_uuid: str, entry_uuid: str) -> None:
        await self._ensure_local_faq_kb(kb_uuid)
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_rag.LocalFAQEntry)
            .where(persistence_rag.LocalFAQEntry.uuid == entry_uuid)
            .where(persistence_rag.LocalFAQEntry.kb_id == kb_uuid)
        )
        await self._touch_knowledge_base(kb_uuid)

    async def _touch_knowledge_base(self, kb_uuid: str) -> None:
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_rag.KnowledgeBase)
            .values(updated_at=sqlalchemy.func.now())
            .where(persistence_rag.KnowledgeBase.uuid == kb_uuid)
        )

    @staticmethod
    def _normalize_questions(raw_questions: object) -> list[str]:
        if raw_questions is None:
            return []

        if isinstance(raw_questions, list):
            parts = raw_questions
        else:
            parts = [raw_questions]

        questions: list[str] = []
        for part in parts:
            for segment in str(part).replace('；', ';').replace('\n', ';').split(';'):
                normalized = segment.strip()
                if normalized:
                    questions.append(normalized)

        return questions
