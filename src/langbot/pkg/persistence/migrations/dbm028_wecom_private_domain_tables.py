import sqlalchemy

from .. import migration


@migration.migration_class(28)
class DBMigrateWecomPrivateDomainTables(migration.DBMigration):
    """Add WeCom private domain tables"""

    async def upgrade(self):
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(
                """
                CREATE TABLE wecom_private_contact_configs (
                    id VARCHAR(255) PRIMARY KEY,
                    bot_uuid VARCHAR(255) NOT NULL,
                    config_id VARCHAR(255) NOT NULL UNIQUE,
                    qr_code_url TEXT NOT NULL,
                    remark VARCHAR(255) NOT NULL,
                    state VARCHAR(64) NOT NULL,
                    follow_user_ids JSON NOT NULL DEFAULT '[]',
                    enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    is_primary BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(
                """
                CREATE TABLE wecom_private_leads (
                    id VARCHAR(255) PRIMARY KEY,
                    bot_uuid VARCHAR(255) NOT NULL,
                    external_userid VARCHAR(255) NOT NULL UNIQUE,
                    follow_user_id VARCHAR(255) NOT NULL,
                    source_state VARCHAR(64),
                    first_add_time TIMESTAMP,
                    current_tags JSON NOT NULL DEFAULT '[]',
                    profile_status VARCHAR(50) NOT NULL DEFAULT 'anonymous',
                    bound_game_identity JSON NOT NULL DEFAULT '{}',
                    remark_snapshot JSON NOT NULL DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(
                """
                CREATE TABLE wecom_private_routing_decisions (
                    id VARCHAR(255) PRIMARY KEY,
                    session_id VARCHAR(255) NOT NULL,
                    trigger_type VARCHAR(50) NOT NULL,
                    trigger_reason TEXT NOT NULL,
                    decision VARCHAR(50) NOT NULL,
                    matched_rule VARCHAR(255),
                    confidence FLOAT NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(
                """
                CREATE TABLE wecom_private_binding_tasks (
                    id VARCHAR(255) PRIMARY KEY,
                    session_id VARCHAR(255) NOT NULL UNIQUE,
                    requested_fields JSON NOT NULL DEFAULT '[]',
                    provided_uid VARCHAR(255),
                    provided_server VARCHAR(255),
                    verify_status VARCHAR(50) NOT NULL DEFAULT 'pending',
                    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(
                """
                CREATE TABLE wecom_private_closure_records (
                    id VARCHAR(255) PRIMARY KEY,
                    session_id VARCHAR(255) NOT NULL UNIQUE,
                    resolution_type VARCHAR(50) NOT NULL,
                    tag_updates JSON NOT NULL DEFAULT '{}',
                    followup_needed BOOLEAN NOT NULL DEFAULT FALSE,
                    knowledge_feedback TEXT,
                    closed_by VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text("ALTER TABLE service_desk_sessions ADD COLUMN lead_id VARCHAR(255)")
        )
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text("ALTER TABLE service_desk_sessions ADD COLUMN risk_level VARCHAR(32) NOT NULL DEFAULT 'normal'")
        )
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text("ALTER TABLE service_desk_sessions ADD COLUMN closed_at TIMESTAMP")
        )

    async def downgrade(self):
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text('DROP TABLE wecom_private_closure_records'))
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text('DROP TABLE wecom_private_binding_tasks'))
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text('DROP TABLE wecom_private_routing_decisions'))
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text('DROP TABLE wecom_private_leads'))
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text('DROP TABLE wecom_private_contact_configs'))
