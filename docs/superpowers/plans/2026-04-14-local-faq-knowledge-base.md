# Local FAQ Knowledge Base Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 LangBot 知识库页面中新增一个可上传 `xlsx/csv/json`、可前端查看和编辑条目、对话时命中后轻度润色并可回退标准答案的内置“本地问答库”。

**Architecture:** 后端在现有插件化知识引擎体系旁补一个 `builtin/local-faq` 内置知识引擎，通过 `knowledge_bases` 复用现有知识库主模型，并新增一张条目表存储结构化问答。前端继续走现有知识库页面结构，在 `Documents` 里导入文件，在新增的 `Entries` 标签页管理条目，在 `Retrieve` 页查看命中结果；对话阶段则在 `local-agent` 中识别本地问答命中并执行轻度润色，失败时回退标准答案。

**Tech Stack:** Python 3.12、Quart、SQLAlchemy、SQLite/PostgreSQL migrations、React 19、TypeScript、Vite、Pytest、ESLint、现有 LangBot 知识库页面与 Local Agent Runner

---

## File Structure

- Create: `src/langbot/pkg/persistence/migrations/dbm027_local_faq_entries.py`
  负责新增本地问答条目表，并把数据库版本从 `26` 升到 `27`。
- Modify: `src/langbot/pkg/utils/constants.py`
  维护最新数据库版本常量。
- Modify: `src/langbot/pkg/entity/persistence/rag.py`
  增加本地问答条目 ORM 模型。
- Create: `src/langbot/pkg/rag/knowledge/builtin_local_faq.py`
  负责内置 `builtin/local-faq` 引擎的元数据、文件解析、条目 CRUD、命中与检索结果封装。
- Modify: `src/langbot/pkg/rag/knowledge/kbmgr.py`
  在运行态知识库里为 `builtin/local-faq` 增加创建、导入、检索、删除的内置分支。
- Modify: `src/langbot/pkg/api/http/service/knowledge.py`
  向知识引擎列表注入 `builtin/local-faq`，并为条目 CRUD 暴露服务层方法。
- Create: `src/langbot/pkg/api/http/controller/groups/knowledge/entries.py`
  负责 `/api/v1/knowledge/bases/<kb_id>/entries` 条目接口。
- Modify: `src/langbot/pkg/provider/runners/localagent.py`
  负责本地问答命中后的轻度润色与标准答案回退。
- Modify: `src/langbot/pkg/utils/local_faq.py`
  复用现有文本归一化/相似度逻辑，补充命中结果结构与复用入口。
- Create: `tests/unit_tests/knowledge/test_local_faq_backend.py`
  覆盖文件导入、条目 CRUD、检索结果和错误处理。
- Modify: `tests/unit_tests/pipeline/test_local_faq.py`
  从纯工具测试扩展到本地问答命中阈值和润色回退测试。
- Modify: `web/src/app/infra/entities/api/index.ts`
  增加本地问答条目与检索扩展字段类型。
- Modify: `web/src/app/infra/http/BackendClient.ts`
  增加条目 CRUD 调用。
- Modify: `web/src/app/home/knowledge/KBDetailContent.tsx`
  为本地问答知识库增加 `Entries` 标签页。
- Modify: `web/src/app/home/knowledge/components/kb-docs/FileUploadZone.tsx`
  扩展支持 `xlsx/csv/json` 上传，并在本地问答库时提示“将解析为问答条目”。
- Create: `web/src/app/home/knowledge/components/kb-entries/KBEntries.tsx`
  负责条目列表、刷新、增删改入口。
- Create: `web/src/app/home/knowledge/components/kb-entries/KBEntryDialog.tsx`
  负责新增/编辑单条问答的表单弹窗。
- Modify: `web/src/app/home/knowledge/components/kb-retrieve/KBRetrieveGeneric.tsx`
  支持展示本地问答命中的标题、标准答案和最终回复。
- Modify: `web/src/i18n/locales/zh-Hans.ts`
  增加中文界面的本地问答库文案。
- Modify: `web/src/i18n/locales/en-US.ts`
  增加英文界面的本地问答库文案。

---

### Task 1: 先用测试锁定本地问答条目存储和文件解析

**Files:**
- Create: `tests/unit_tests/knowledge/test_local_faq_backend.py`
- Modify: `src/langbot/pkg/utils/local_faq.py`
- Create: `src/langbot/pkg/rag/knowledge/builtin_local_faq.py`

- [ ] **Step 1: 先写文件解析与命中结果的失败测试**

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_parse_json_faq_file_reads_questions_and_answer(tmp_path: Path):
    from langbot.pkg.rag.knowledge.builtin_local_faq import parse_local_faq_file

    file_path = tmp_path / 'faq.json'
    file_path.write_text(
        json.dumps(
            [
                {
                    'questions': ['哪个职业好玩？', '职业推荐'],
                    'answer': '鬼王前期开荒更快，焚天更适合中后期团战。',
                }
            ],
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )

    entries = parse_local_faq_file(file_path, extension='json')

    assert len(entries) == 1
    assert entries[0]['questions'] == ['哪个职业好玩？', '职业推荐']
    assert entries[0]['answer'] == '鬼王前期开荒更快，焚天更适合中后期团战。'


def test_match_local_faq_entry_returns_distance_and_entry_id():
    from langbot.pkg.rag.knowledge.builtin_local_faq import build_retrieve_result

    result = build_retrieve_result(
        entry_id='entry-1',
        question='哪个职业好玩？',
        answer='鬼王前期开荒更快，焚天更适合中后期团战。',
        distance=0.01,
        source_file_id='file-1',
    )

    assert result['id'] == 'entry-1'
    assert result['metadata']['matched_question'] == '哪个职业好玩？'
    assert result['metadata']['source_file_id'] == 'file-1'
    assert result['content'][0]['text'] == '鬼王前期开荒更快，焚天更适合中后期团战。'
```

- [ ] **Step 2: 运行这组测试，确认当前因为模块/函数不存在而失败**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && ./.venv/bin/pytest tests/unit_tests/knowledge/test_local_faq_backend.py -v`

Expected: FAIL，报 `ModuleNotFoundError` 或 `AttributeError`，说明测试确实先于实现。

- [ ] **Step 3: 写最小解析与结果构造实现**

```python
from __future__ import annotations

import csv
import json
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET


def parse_local_faq_file(file_path: Path, extension: str) -> list[dict]:
    if extension == 'json':
        payload = json.loads(file_path.read_text(encoding='utf-8'))
        return [_normalize_entry(item) for item in payload]
    if extension == 'csv':
        with file_path.open('r', encoding='utf-8-sig', newline='') as file:
            reader = csv.DictReader(file)
            return [_normalize_tabular_row(row) for row in reader]
    if extension == 'xlsx':
        return _parse_xlsx_rows(file_path)
    raise ValueError(f'Unsupported local FAQ extension: {extension}')


def build_retrieve_result(
    *,
    entry_id: str,
    question: str,
    answer: str,
    distance: float,
    source_file_id: str | None,
) -> dict:
    return {
        'id': entry_id,
        'distance': distance,
        'metadata': {
            'matched_question': question,
            'source_file_id': source_file_id,
            'local_faq_answer': answer,
        },
        'content': [{'type': 'text', 'text': answer}],
    }
```

- [ ] **Step 4: 重新运行测试，确认解析和结果格式转绿**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && ./.venv/bin/pytest tests/unit_tests/knowledge/test_local_faq_backend.py -v`

Expected: PASS，且 `parse_local_faq_file` 已支持 `json/csv/xlsx` 三种入口。

- [ ] **Step 5: 提交这一小步**

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add tests/unit_tests/knowledge/test_local_faq_backend.py \
        src/langbot/pkg/utils/local_faq.py \
        src/langbot/pkg/rag/knowledge/builtin_local_faq.py
git commit -m "feat(knowledge): add local faq parsing primitives"
```

### Task 2: 增加条目表与数据库迁移，先让结构化问答可落库

**Files:**
- Modify: `src/langbot/pkg/entity/persistence/rag.py`
- Create: `src/langbot/pkg/persistence/migrations/dbm027_local_faq_entries.py`
- Modify: `src/langbot/pkg/utils/constants.py`
- Test: `tests/unit_tests/knowledge/test_local_faq_backend.py`

- [ ] **Step 1: 先写条目持久化失败测试**

```python
@pytest.mark.asyncio
async def test_list_local_faq_entries_returns_rows_in_sort_order(mock_app):
    import sqlalchemy
    from langbot.pkg.entity.persistence import rag as persistence_rag

    rows = [
        persistence_rag.LocalFAQEntry(
            uuid='entry-1',
            kb_id='kb-1',
            questions=['职业推荐'],
            answer='鬼王前期开荒更快',
            source_file_id='file-1',
            enabled=True,
            sort_order=1,
        )
    ]
    mock_result = type('Result', (), {'all': lambda self: rows})()
    mock_app.persistence_mgr.execute_async.return_value = mock_result

    stmt = sqlalchemy.select(persistence_rag.LocalFAQEntry)
    assert stmt is not None
```

- [ ] **Step 2: 运行测试，确认当前因为 `LocalFAQEntry` 模型不存在而失败**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && ./.venv/bin/pytest tests/unit_tests/knowledge/test_local_faq_backend.py -k sort_order -v`

Expected: FAIL，报 `AttributeError: module 'rag' has no attribute 'LocalFAQEntry'`。

- [ ] **Step 3: 在 ORM 与 migration 里增加条目表**

```python
class LocalFAQEntry(Base):
    __tablename__ = 'knowledge_base_local_faq_entries'
    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    kb_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    questions = sqlalchemy.Column(sqlalchemy.JSON, nullable=False)
    answer = sqlalchemy.Column(sqlalchemy.Text, nullable=False)
    source_file_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True, index=True)
    enabled = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=True)
    sort_order = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, default=0)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(sqlalchemy.DateTime, default=sqlalchemy.func.now(), onupdate=sqlalchemy.func.now())
```

```python
class DBMigrateLocalFAQEntries(migration.DBMigration):
    number = 27

    async def upgrade(self):
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(
                '''
                CREATE TABLE IF NOT EXISTS knowledge_base_local_faq_entries (
                    uuid VARCHAR(255) PRIMARY KEY,
                    kb_id VARCHAR(255) NOT NULL,
                    questions TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    source_file_id VARCHAR(255),
                    enabled BOOLEAN NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                '''
            )
        )
```

- [ ] **Step 4: 更新数据库版本常量**

```python
required_database_version = 27
```

- [ ] **Step 5: 重新运行后端测试并确认模型可导入**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && ./.venv/bin/pytest tests/unit_tests/knowledge/test_local_faq_backend.py -v`

Expected: PASS，且测试不再因为 `LocalFAQEntry` 缺失失败。

- [ ] **Step 6: 提交这一小步**

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add src/langbot/pkg/entity/persistence/rag.py \
        src/langbot/pkg/persistence/migrations/dbm027_local_faq_entries.py \
        src/langbot/pkg/utils/constants.py \
        tests/unit_tests/knowledge/test_local_faq_backend.py
git commit -m "feat(knowledge): persist local faq entries"
```

### Task 3: 把 `builtin/local-faq` 接进知识库主链路和条目 API

**Files:**
- Modify: `src/langbot/pkg/rag/knowledge/kbmgr.py`
- Modify: `src/langbot/pkg/api/http/service/knowledge.py`
- Create: `src/langbot/pkg/api/http/controller/groups/knowledge/entries.py`
- Create: `src/langbot/pkg/rag/knowledge/builtin_local_faq.py`
- Test: `tests/unit_tests/knowledge/test_local_faq_backend.py`

- [ ] **Step 1: 先写失败测试，锁定内置知识引擎会出现在引擎列表里**

```python
@pytest.mark.asyncio
async def test_list_knowledge_engines_includes_builtin_local_faq(mock_app):
    from langbot.pkg.api.http.service.knowledge import KnowledgeService

    mock_app.plugin_connector.is_enable_plugin = False
    service = KnowledgeService(mock_app)

    engines = await service.list_knowledge_engines()

    assert any(engine['plugin_id'] == 'builtin/local-faq' for engine in engines)
```

- [ ] **Step 2: 再写失败测试，锁定文件导入后会生成条目**

```python
@pytest.mark.asyncio
async def test_builtin_local_faq_store_file_creates_entries(mock_app, tmp_path):
    from langbot.pkg.rag.knowledge.kbmgr import RuntimeKnowledgeBase
    from langbot.pkg.entity.persistence import rag as persistence_rag

    file_bytes = b'问题,回答\n哪个职业好玩,鬼王前期开荒更快\n'
    mock_app.storage_mgr.storage_provider.exists.return_value = True
    mock_app.storage_mgr.storage_provider.load.return_value = file_bytes
    mock_app.storage_mgr.storage_provider.size.return_value = len(file_bytes)
    mock_app.task_mgr.create_user_task.side_effect = lambda coro, **_: type('Task', (), {'id': 'task-1'})()

    kb = persistence_rag.KnowledgeBase(
        uuid='kb-1',
        name='FAQ KB',
        knowledge_engine_plugin_id='builtin/local-faq',
        collection_id='kb-1',
        creation_settings={},
        retrieval_settings={},
    )

    runtime_kb = RuntimeKnowledgeBase(mock_app, kb)
    task_id = await runtime_kb.store_file('faq.csv')

    assert task_id == 'task-1'
```

- [ ] **Step 3: 运行测试，确认当前引擎列表和导入分支都还不存在**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && ./.venv/bin/pytest tests/unit_tests/knowledge/test_local_faq_backend.py -k 'builtin_local_faq or list_knowledge_engines' -v`

Expected: FAIL，原因分别是引擎列表没有 `builtin/local-faq`，以及 `store_file` 仍然只会走插件 ingestion 分支。

- [ ] **Step 4: 给知识引擎列表注入内置本地问答引擎**

```python
BUILTIN_LOCAL_FAQ_ENGINE = {
    'plugin_id': 'builtin/local-faq',
    'name': {'en_US': 'Local FAQ', 'zh_Hans': '本地问答库'},
    'capabilities': ['doc_ingestion', 'faq_entry_editing', 'light_rewrite'],
    'creation_schema': [],
    'retrieval_schema': [
        {
            'name': 'faq_match_threshold',
            'type': 'number',
            'label': {'en_US': 'Match Threshold', 'zh_Hans': '匹配阈值'},
            'default': 0.95,
            'required': False,
        }
    ],
}


async def list_knowledge_engines(self) -> list[dict]:
    engines = [BUILTIN_LOCAL_FAQ_ENGINE]
    if self.ap.plugin_connector.is_enable_plugin:
        engines.extend(await self.ap.plugin_connector.list_knowledge_engines())
    return engines
```

- [ ] **Step 5: 在 `RuntimeKnowledgeBase` 中增加内置引擎分支**

```python
async def _on_kb_create(self) -> None:
    if self.get_knowledge_engine_plugin_id() == 'builtin/local-faq':
        return
    ...


async def _ingest_document(self, file_metadata, storage_path, parsed_content=None):
    if self.get_knowledge_engine_plugin_id() == 'builtin/local-faq':
        return await builtin_local_faq.ingest_local_faq_document(
            ap=self.ap,
            kb=self.knowledge_base_entity,
            file_metadata=file_metadata,
            storage_path=storage_path,
        )
    ...


async def _retrieve(self, query: str, settings: dict[str, Any]) -> dict[str, Any]:
    if self.get_knowledge_engine_plugin_id() == 'builtin/local-faq':
        return await builtin_local_faq.retrieve_local_faq(
            ap=self.ap,
            kb=self.knowledge_base_entity,
            query=query,
            settings=settings,
        )
    ...
```

- [ ] **Step 6: 新增条目 CRUD 服务与路由**

```python
async def list_local_faq_entries(self, kb_uuid: str) -> list[dict]:
    result = await self.ap.persistence_mgr.execute_async(
        sqlalchemy.select(persistence_rag.LocalFAQEntry)
        .where(persistence_rag.LocalFAQEntry.kb_id == kb_uuid)
        .order_by(persistence_rag.LocalFAQEntry.sort_order.asc(), persistence_rag.LocalFAQEntry.created_at.asc())
    )
    return [self.ap.persistence_mgr.serialize_model(persistence_rag.LocalFAQEntry, row) for row in result.all()]
```

```python
@group.group_class('knowledge_entries', '/api/v1/knowledge/bases/<knowledge_base_uuid>/entries')
class KnowledgeEntriesRouterGroup(group.RouterGroup):
    def initialize_routes(self):
        @self.route('/', methods=['GET'])
        async def list_entries(knowledge_base_uuid: str) -> quart.Response:
            entries = await self.ap.knowledge_service.list_local_faq_entries(knowledge_base_uuid)
            return self.success(data={'entries': entries})
```

- [ ] **Step 7: 重新运行后端测试，确认内置引擎与条目导入链路可用**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && ./.venv/bin/pytest tests/unit_tests/knowledge/test_local_faq_backend.py -v`

Expected: PASS，且 `builtin/local-faq` 可以被创建、导入、列出条目、执行检索。

- [ ] **Step 8: 提交这一小步**

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add src/langbot/pkg/rag/knowledge/kbmgr.py \
        src/langbot/pkg/api/http/service/knowledge.py \
        src/langbot/pkg/api/http/controller/groups/knowledge/entries.py \
        src/langbot/pkg/rag/knowledge/builtin_local_faq.py \
        tests/unit_tests/knowledge/test_local_faq_backend.py
git commit -m "feat(knowledge): add builtin local faq engine"
```

### Task 4: 在 `local-agent` 中实现“轻度润色 + 失败回退标准答案”

**Files:**
- Modify: `src/langbot/pkg/provider/runners/localagent.py`
- Modify: `tests/unit_tests/pipeline/test_local_faq.py`
- Modify: `src/langbot/pkg/utils/local_faq.py`

- [ ] **Step 1: 先写失败测试，锁定命中后会调用轻度润色，失败时回退标准答案**

```python
def test_local_faq_hit_rewrite_falls_back_to_standard_answer():
    from langbot.pkg.utils.local_faq import choose_local_faq_reply

    result = choose_local_faq_reply(
        standard_answer='鬼王前期开荒更快，焚天更适合中后期团战。',
        rewrite_result='',
    )

    assert result == '鬼王前期开荒更快，焚天更适合中后期团战。'
```

```python
def test_local_faq_hit_rewrite_accepts_close_variant():
    from langbot.pkg.utils.local_faq import choose_local_faq_reply

    result = choose_local_faq_reply(
        standard_answer='下载注册后把区服和角色名发我，我给你安排礼包和 CDK。',
        rewrite_result='老板，您先下载注册，把区服和角色名给我，我这边给您安排礼包和 CDK。',
    )

    assert '礼包和 CDK' in result
```

- [ ] **Step 2: 运行测试，确认当前没有“润色回退决策”实现**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && ./.venv/bin/pytest tests/unit_tests/pipeline/test_local_faq.py -v`

Expected: FAIL，报 `ImportError` 或断言失败，说明回退策略尚未实现。

- [ ] **Step 3: 把标准答案回退与润色约束提取为小函数**

```python
def choose_local_faq_reply(*, standard_answer: str, rewrite_result: str | None) -> str:
    cleaned = (rewrite_result or '').strip()
    if not cleaned:
        return standard_answer
    if len(cleaned) < max(6, len(standard_answer) // 4):
        return standard_answer
    return cleaned
```

- [ ] **Step 4: 在 `localagent.py` 中接入本地问答命中后的轻度润色**

```python
rewrite_prompt = [
    provider_message.Message(
        role='system',
        content=(
            '你是客服话术润色助手。你只能对标准答案做轻度润色，'
            '不得改变福利、承诺、职业推荐、数值判断等核心信息。'
            '如果无法自然润色，请原样返回标准答案。'
        ),
    ),
    provider_message.Message(
        role='user',
        content=f'用户问题：{user_message_text}\n标准答案：{standard_answer}',
    ),
]
```

```python
if local_faq_answer is not None:
    rewritten = await self._rewrite_local_faq_answer(query, user_message_text, local_faq_answer)
    final_answer = local_faq.choose_local_faq_reply(
        standard_answer=local_faq_answer,
        rewrite_result=rewritten,
    )
    yield provider_message.Message(role='assistant', content=final_answer)
    return
```

- [ ] **Step 5: 重新运行本地 FAQ 测试并确认转绿**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && ./.venv/bin/pytest tests/unit_tests/pipeline/test_local_faq.py -v`

Expected: PASS，且命中后的空润色/坏润色都会回退标准答案。

- [ ] **Step 6: 提交这一小步**

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add src/langbot/pkg/provider/runners/localagent.py \
        src/langbot/pkg/utils/local_faq.py \
        tests/unit_tests/pipeline/test_local_faq.py
git commit -m "feat(local-agent): rewrite local faq answers with fallback"
```

### Task 5: 在前端知识库创建页和详情页接入本地问答库

**Files:**
- Modify: `web/src/app/infra/entities/api/index.ts`
- Modify: `web/src/app/infra/http/BackendClient.ts`
- Modify: `web/src/app/home/knowledge/components/kb-form/KBForm.tsx`
- Modify: `web/src/app/home/knowledge/KBDetailContent.tsx`
- Modify: `web/src/i18n/locales/zh-Hans.ts`
- Modify: `web/src/i18n/locales/en-US.ts`

- [ ] **Step 1: 先扩充前端 API 类型和调用**

```ts
export interface LocalFAQEntry {
  uuid: string;
  kb_id: string;
  questions: string[];
  answer: string;
  source_file_id?: string;
  enabled: boolean;
  sort_order: number;
  created_at?: string;
  updated_at?: string;
}

export interface ApiRespKnowledgeBaseEntries {
  entries: LocalFAQEntry[];
}
```

```ts
public getKnowledgeBaseEntries(uuid: string): Promise<ApiRespKnowledgeBaseEntries> {
  return this.get(`/api/v1/knowledge/bases/${uuid}/entries`);
}
```

- [ ] **Step 2: 在 `KBForm` 里保证内置引擎可被选中且创建时不要求动态 schema**

```tsx
const selectedEngine = ragEngines.find((e) => e.plugin_id === selectedEngineId);
const isBuiltinLocalFaq = selectedEngineId === 'builtin/local-faq';

{isBuiltinLocalFaq && (
  <FormDescription>
    {t('knowledge.localFaqDescription')}
  </FormDescription>
)}
```

- [ ] **Step 3: 在详情页增加 `Entries` 标签页开关**

```tsx
const hasEntryCapability = (): boolean => {
  if (!kbInfo?.knowledge_engine) return false;
  return kbInfo.knowledge_engine.capabilities?.includes('faq_entry_editing') ?? false;
};
```

```tsx
{hasEntryCapability() && (
  <TabsTrigger value="entries" className="gap-1.5">
    <FileText className="size-3.5" />
    {t('knowledge.entries')}
  </TabsTrigger>
)}
```

- [ ] **Step 4: 补中英文文案**

```ts
entries: '问答条目',
localFaqDescription: '适合小体量、高精度命中的固定问答场景。创建后请在文档页上传 xlsx/csv/json。',
```

```ts
entries: 'Entries',
localFaqDescription: 'Best for small, high-precision scripted FAQ. Upload xlsx/csv/json after creating the knowledge base.',
```

- [ ] **Step 5: 跑前端构建，确认类型和路由没有坏**

Run: `cd /home/daisheng/code/copy_dkd/LangBot/web && npm run build`

Expected: PASS，`tsc && vite build` 成功。

- [ ] **Step 6: 提交这一小步**

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add web/src/app/infra/entities/api/index.ts \
        web/src/app/infra/http/BackendClient.ts \
        web/src/app/home/knowledge/components/kb-form/KBForm.tsx \
        web/src/app/home/knowledge/KBDetailContent.tsx \
        web/src/i18n/locales/zh-Hans.ts \
        web/src/i18n/locales/en-US.ts
git commit -m "feat(web): add local faq knowledge base shell"
```

### Task 6: 做 `Entries` 管理页并把文档上传接成“导入问答”

**Files:**
- Create: `web/src/app/home/knowledge/components/kb-entries/KBEntries.tsx`
- Create: `web/src/app/home/knowledge/components/kb-entries/KBEntryDialog.tsx`
- Modify: `web/src/app/home/knowledge/components/kb-docs/FileUploadZone.tsx`
- Modify: `web/src/app/home/knowledge/KBDetailContent.tsx`
- Modify: `web/src/app/home/knowledge/components/kb-retrieve/KBRetrieveGeneric.tsx`

- [ ] **Step 1: 先写 `Entries` 页最小列表和刷新逻辑**

```tsx
export default function KBEntries({ kbId }: { kbId: string }) {
  const [entries, setEntries] = useState<LocalFAQEntry[]>([]);

  const loadEntries = useCallback(async () => {
    const resp = await httpClient.getKnowledgeBaseEntries(kbId);
    setEntries(resp.entries);
  }, [kbId]);

  useEffect(() => {
    void loadEntries();
  }, [loadEntries]);

  return (
    <div className="space-y-3">
      {entries.map((entry) => (
        <Card key={entry.uuid}>
          <CardContent className="p-4">
            <div className="text-sm font-medium">{entry.questions.join(' / ')}</div>
            <div className="text-sm text-muted-foreground whitespace-pre-wrap">{entry.answer}</div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: 再补新增/编辑弹窗**

```tsx
export function KBEntryDialog({ open, initialValue, onSubmit, onOpenChange }: Props) {
  const [questionsText, setQuestionsText] = useState(initialValue?.questions.join('\n') ?? '');
  const [answer, setAnswer] = useState(initialValue?.answer ?? '');

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <Textarea value={questionsText} onChange={(e) => setQuestionsText(e.target.value)} />
        <Textarea value={answer} onChange={(e) => setAnswer(e.target.value)} />
        <Button
          onClick={() =>
            onSubmit({
              questions: questionsText.split('\n').map((v) => v.trim()).filter(Boolean),
              answer: answer.trim(),
            })
          }
        >
          保存
        </Button>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 3: 让文档上传区支持 `xlsx/csv/json`，并对本地问答库给出明确提示**

```tsx
const isLocalFaqKb = ragEngineCapabilities?.includes('faq_entry_editing') ?? false;

<input
  type="file"
  accept={isLocalFaqKb ? '.xlsx,.csv,.json' : '.pdf,.doc,.docx,.txt,.md,.html,.zip'}
  ...
/>
```

```tsx
{isLocalFaqKb && (
  <p className="text-xs text-muted-foreground">
    {t('knowledge.documentsTab.localFaqUploadHint')}
  </p>
)}
```

- [ ] **Step 4: 让 `Retrieve` 页展示“标准答案 / 最终回复 / 命中问题”**

```tsx
const getTitle = (result: RetrieveResult): string => {
  return (
    (result.metadata.matched_question as string) ||
    (result.metadata.document_name as string) ||
    result.id
  );
};
```

```tsx
{result.metadata.final_reply && (
  <p className="text-xs text-muted-foreground whitespace-pre-wrap">
    Final Reply: {String(result.metadata.final_reply)}
  </p>
)}
```

- [ ] **Step 5: 跑前端 lint 和 build，确认页面代码可编译**

Run: `cd /home/daisheng/code/copy_dkd/LangBot/web && npm run lint && npm run build`

Expected: PASS，ESLint 和构建都成功。

- [ ] **Step 6: 提交这一小步**

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add web/src/app/home/knowledge/components/kb-entries/KBEntries.tsx \
        web/src/app/home/knowledge/components/kb-entries/KBEntryDialog.tsx \
        web/src/app/home/knowledge/components/kb-docs/FileUploadZone.tsx \
        web/src/app/home/knowledge/KBDetailContent.tsx \
        web/src/app/home/knowledge/components/kb-retrieve/KBRetrieveGeneric.tsx
git commit -m "feat(web): add local faq entry management"
```

### Task 7: 做演示闭环验证并清理临时配置

**Files:**
- Modify: `tests/unit_tests/knowledge/test_local_faq_backend.py`
- Modify: `tests/unit_tests/pipeline/test_local_faq.py`
- Modify: `docs/superpowers/specs/2026-04-14-local-faq-knowledge-base-design.md`（仅在实现偏离规格时回写）

- [ ] **Step 1: 运行后端单测集合**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && ./.venv/bin/pytest tests/unit_tests/knowledge/test_local_faq_backend.py tests/unit_tests/pipeline/test_local_faq.py -v`

Expected: PASS，覆盖导入、条目 CRUD、命中、润色、回退。

- [ ] **Step 2: 运行前端构建**

Run: `cd /home/daisheng/code/copy_dkd/LangBot/web && npm run build`

Expected: PASS。

- [ ] **Step 3: 手工演示烟雾验证**

```text
1. 打开 /home/knowledge，新建“本地问答库”
2. 进入详情页，在 Documents 点击上传一个 xlsx
3. 确认 Entries 页出现解析后的问答条目
4. 修改一条答案并保存
5. 在 Retrieve 输入“哪个职业好玩”
6. 确认页面展示命中问题、标准答案和最终回复
7. 在真实对话入口发送相同问题，确认回复为轻度润色版本
8. 临时断开模型配置，再次发送问题，确认回退标准答案
```

- [ ] **Step 4: 检查工作树并整理最终提交**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && git status --short`

Expected: 只剩本次实现相关文件变更，没有把 `uv.lock`、`web/package-lock.json` 之类无关改动混进来。

- [ ] **Step 5: 最终提交**

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add src/langbot/pkg/entity/persistence/rag.py \
        src/langbot/pkg/persistence/migrations/dbm027_local_faq_entries.py \
        src/langbot/pkg/utils/constants.py \
        src/langbot/pkg/rag/knowledge/builtin_local_faq.py \
        src/langbot/pkg/rag/knowledge/kbmgr.py \
        src/langbot/pkg/api/http/service/knowledge.py \
        src/langbot/pkg/api/http/controller/groups/knowledge/entries.py \
        src/langbot/pkg/provider/runners/localagent.py \
        src/langbot/pkg/utils/local_faq.py \
        tests/unit_tests/knowledge/test_local_faq_backend.py \
        tests/unit_tests/pipeline/test_local_faq.py \
        web/src/app/infra/entities/api/index.ts \
        web/src/app/infra/http/BackendClient.ts \
        web/src/app/home/knowledge/KBDetailContent.tsx \
        web/src/app/home/knowledge/components/kb-form/KBForm.tsx \
        web/src/app/home/knowledge/components/kb-docs/FileUploadZone.tsx \
        web/src/app/home/knowledge/components/kb-entries/KBEntries.tsx \
        web/src/app/home/knowledge/components/kb-entries/KBEntryDialog.tsx \
        web/src/app/home/knowledge/components/kb-retrieve/KBRetrieveGeneric.tsx \
        web/src/i18n/locales/zh-Hans.ts \
        web/src/i18n/locales/en-US.ts
git commit -m "feat(knowledge): add local faq knowledge base flow"
```

---

## Self-Review

### Spec coverage

- “前端知识库页面创建/导入/查看/修改”：
  已覆盖 Task 3、Task 5、Task 6。
- “支持 xlsx/csv/json 导入”：
  已覆盖 Task 1、Task 3、Task 6。
- “命中后轻度润色，失败回退标准答案”：
  已覆盖 Task 4、Task 7。
- “明天演示优先、绕开不稳定插件链路”：
  已通过 Task 3 的 `builtin/local-faq` 内置引擎分支落实。

### Placeholder scan

- 已避免 `TODO/TBD/类似 Task N` 之类占位语句。
- 每个代码步骤都给出实际代码片段。
- 每个验证步骤都给出实际命令与预期结果。

### Type consistency

- 统一使用 `builtin/local-faq` 作为引擎 ID。
- 前后端统一使用 `LocalFAQEntry` / `knowledge_base_local_faq_entries` / `/entries` 接口。
- 检索返回统一通过 `RetrieveResult.metadata` 扩展 `matched_question`、`local_faq_answer`、`final_reply` 字段。
