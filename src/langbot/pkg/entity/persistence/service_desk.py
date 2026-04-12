import sqlalchemy

from .base import Base


class ServiceDeskBotConfig(Base):
    """Service desk bot config"""

    __tablename__ = 'service_desk_bot_configs'

    bot_uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    version_label = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    handoff_keywords = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, server_default='[]')
    fallback_unresolved_count = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, default=2, server_default='2')
    manual_timeout_seconds = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, default=900, server_default='900')
    enabled = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=True, server_default=sqlalchemy.true())
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )


class ServiceDeskMaterial(Base):
    """Service desk material"""

    __tablename__ = 'service_desk_materials'

    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    bot_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    material_type = sqlalchemy.Column(sqlalchemy.String(50), nullable=False)
    title = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    trigger_keywords = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, server_default='[]')
    reply_text = sqlalchemy.Column(sqlalchemy.Text, nullable=False)
    payload = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, server_default='{}')
    priority = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, default=100, server_default='100')
    enabled = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=True, server_default=sqlalchemy.true())
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )


class ServiceDeskSession(Base):
    """Service desk session state"""

    __tablename__ = 'service_desk_sessions'

    session_id = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    bot_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    pipeline_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    mode = sqlalchemy.Column(sqlalchemy.String(50), nullable=False, default='ai_hosted', server_default='ai_hosted')
    queue_status = sqlalchemy.Column(sqlalchemy.String(50), nullable=False, default='ai', server_default='ai')
    handoff_reason = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    source_entry_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    external_user_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    last_message_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    claimed_by_user_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    claimed_by_user_name = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    manual_claimed_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    silent_since = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    last_customer_message_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    last_manual_reply_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    unresolved_count = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, default=0, server_default='0')
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )
