import sqlalchemy

from .. import migration


@migration.migration_class(27)
class DBMigrateLocalFAQEntries(migration.DBMigration):
    """Add local FAQ entry table for builtin knowledge base"""

    async def upgrade(self):
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(
                """
                CREATE TABLE IF NOT EXISTS knowledge_base_local_faq_entries (
                    uuid VARCHAR(255) PRIMARY KEY,
                    kb_id VARCHAR(255) NOT NULL,
                    questions JSON NOT NULL,
                    answer TEXT NOT NULL,
                    source_file_id VARCHAR(255),
                    enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(
                'CREATE INDEX IF NOT EXISTS idx_local_faq_entries_kb_id '
                'ON knowledge_base_local_faq_entries (kb_id)'
            )
        )
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(
                'CREATE INDEX IF NOT EXISTS idx_local_faq_entries_source_file_id '
                'ON knowledge_base_local_faq_entries (source_file_id)'
            )
        )

    async def downgrade(self):
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text('DROP INDEX IF EXISTS idx_local_faq_entries_source_file_id')
        )
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text('DROP INDEX IF EXISTS idx_local_faq_entries_kb_id')
        )
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text('DROP TABLE IF EXISTS knowledge_base_local_faq_entries')
        )
