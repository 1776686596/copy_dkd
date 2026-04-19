import sqlalchemy

from .. import migration


@migration.migration_class(29)
class DBMigrateWecomPrivateAiReceptionConfig(migration.DBMigration):
    """Add WeCom private AI reception config table"""

    async def upgrade(self):
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(
                """
                CREATE TABLE wecom_private_reception_configs (
                    bot_uuid VARCHAR(255) PRIMARY KEY,
                    reception_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    welcome_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    fallback_reply_text TEXT,
                    binding_required_fields JSON NOT NULL DEFAULT '[]',
                    binding_trigger_keywords JSON NOT NULL DEFAULT '[]',
                    binding_prompt_text TEXT,
                    human_handoff_direct_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text("ALTER TABLE wecom_private_binding_tasks ADD COLUMN provided_role_name VARCHAR(255)")
        )

    async def downgrade(self):
        # SQLite 在仓库兼容范围内不稳定支持 DROP COLUMN，沿用现有 migration 风格：
        # 仅对 PostgreSQL 回滚新增列，SQLite 保留未映射列以避免降级失败。
        if self.ap.persistence_mgr.db.name == 'postgresql':
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text('ALTER TABLE wecom_private_binding_tasks DROP COLUMN provided_role_name')
            )
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text('DROP TABLE wecom_private_reception_configs'))
