import sqlalchemy

from .. import migration


@migration.migration_class(30)
class DBMigrateWecomPrivateUserLayering(migration.DBMigration):
    """Add WeCom private lead layering fields"""

    async def upgrade(self):
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(
                """
                ALTER TABLE wecom_private_leads
                ADD COLUMN user_layer VARCHAR(50) NOT NULL DEFAULT 'normal'
                """
            )
        )
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(
                """
                ALTER TABLE wecom_private_leads
                ADD COLUMN layer_source VARCHAR(50) NOT NULL DEFAULT 'system'
                """
            )
        )
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(
                """
                ALTER TABLE wecom_private_leads
                ADD COLUMN profile_signals JSON NOT NULL DEFAULT '[]'
                """
            )
        )
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(
                """
                ALTER TABLE wecom_private_leads
                ADD COLUMN layer_updated_at TIMESTAMP NULL
                """
            )
        )

    async def downgrade(self):
        # SQLite 在仓库兼容范围内不稳定支持 DROP COLUMN，沿用现有 migration 风格：
        # 仅对 PostgreSQL 回滚新增列，SQLite 保留未映射列以避免降级失败。
        if self.ap.persistence_mgr.db.name == 'postgresql':
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text('ALTER TABLE wecom_private_leads DROP COLUMN layer_updated_at')
            )
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text('ALTER TABLE wecom_private_leads DROP COLUMN profile_signals')
            )
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text('ALTER TABLE wecom_private_leads DROP COLUMN layer_source')
            )
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text('ALTER TABLE wecom_private_leads DROP COLUMN user_layer')
            )
