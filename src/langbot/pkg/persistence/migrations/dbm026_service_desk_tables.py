import sqlalchemy

from .. import migration


@migration.migration_class(26)
class DBMigrateServiceDeskTables(migration.DBMigration):
    """Add service desk tables"""

    async def upgrade(self):
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(
                """
                CREATE TABLE service_desk_bot_configs (
                    bot_uuid VARCHAR(255) PRIMARY KEY,
                    version_label VARCHAR(255) NOT NULL,
                    handoff_keywords JSON NOT NULL DEFAULT '[]',
                    fallback_unresolved_count INTEGER NOT NULL DEFAULT 2,
                    manual_timeout_seconds INTEGER NOT NULL DEFAULT 900,
                    enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(
                """
                CREATE TABLE service_desk_materials (
                    uuid VARCHAR(255) PRIMARY KEY,
                    bot_uuid VARCHAR(255) NOT NULL,
                    material_type VARCHAR(50) NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    trigger_keywords JSON NOT NULL DEFAULT '[]',
                    reply_text TEXT NOT NULL,
                    payload JSON NOT NULL DEFAULT '{}',
                    priority INTEGER NOT NULL DEFAULT 100,
                    enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(
                """
                CREATE TABLE service_desk_sessions (
                    session_id VARCHAR(255) PRIMARY KEY,
                    bot_uuid VARCHAR(255) NOT NULL,
                    pipeline_uuid VARCHAR(255) NOT NULL,
                    mode VARCHAR(50) NOT NULL DEFAULT 'ai_hosted',
                    queue_status VARCHAR(50) NOT NULL DEFAULT 'ai',
                    handoff_reason VARCHAR(255),
                    source_entry_id VARCHAR(255) NOT NULL,
                    external_user_id VARCHAR(255) NOT NULL,
                    last_message_id VARCHAR(255),
                    claimed_by_user_uuid VARCHAR(255),
                    claimed_by_user_name VARCHAR(255),
                    manual_claimed_at TIMESTAMP,
                    silent_since TIMESTAMP,
                    last_customer_message_at TIMESTAMP,
                    last_manual_reply_at TIMESTAMP,
                    unresolved_count INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )

    async def downgrade(self):
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text('DROP TABLE service_desk_sessions'))
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text('DROP TABLE service_desk_materials'))
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text('DROP TABLE service_desk_bot_configs'))
