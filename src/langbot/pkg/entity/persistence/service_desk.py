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


class WecomPrivateContactConfig(Base):
    """WeCom private domain primary contact configuration"""

    __tablename__ = 'wecom_private_contact_configs'

    id = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    bot_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    config_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, unique=True, index=True)
    qr_code_url = sqlalchemy.Column(sqlalchemy.Text, nullable=False)
    remark = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    state = sqlalchemy.Column(sqlalchemy.String(64), nullable=False, index=True)
    follow_user_ids = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, server_default='[]')
    enabled = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=True, server_default=sqlalchemy.true())
    is_primary = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=True, server_default=sqlalchemy.true())
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )


class WecomPrivateLead(Base):
    """WeCom private domain lead profile"""

    __tablename__ = 'wecom_private_leads'

    id = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    bot_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    external_userid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, unique=True, index=True)
    follow_user_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    source_state = sqlalchemy.Column(sqlalchemy.String(64), nullable=True, index=True)
    first_add_time = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    current_tags = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, server_default='[]')
    profile_status = sqlalchemy.Column(
        sqlalchemy.String(50),
        nullable=False,
        default='anonymous',
        server_default='anonymous',
    )
    user_layer = sqlalchemy.Column(
        sqlalchemy.String(50),
        nullable=False,
        default='normal',
        server_default='normal',
    )
    layer_source = sqlalchemy.Column(
        sqlalchemy.String(50),
        nullable=False,
        default='system',
        server_default='system',
    )
    profile_signals = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, server_default='[]')
    layer_updated_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    bound_game_identity = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, server_default='{}')
    remark_snapshot = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, server_default='{}')
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )


class WecomPrivateRoutingDecision(Base):
    """WeCom private domain routing decision"""

    __tablename__ = 'wecom_private_routing_decisions'

    id = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    session_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    trigger_type = sqlalchemy.Column(sqlalchemy.String(50), nullable=False)
    trigger_reason = sqlalchemy.Column(sqlalchemy.Text, nullable=False)
    decision = sqlalchemy.Column(sqlalchemy.String(50), nullable=False)
    matched_rule = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    confidence = sqlalchemy.Column(sqlalchemy.Float, nullable=False, default=1.0, server_default='1')
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())


class WecomPrivateReceptionConfig(Base):
    """WeCom private domain AI reception configuration"""

    __tablename__ = 'wecom_private_reception_configs'

    bot_uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    reception_enabled = sqlalchemy.Column(
        sqlalchemy.Boolean,
        nullable=False,
        default=True,
        server_default=sqlalchemy.true(),
    )
    welcome_enabled = sqlalchemy.Column(
        sqlalchemy.Boolean,
        nullable=False,
        default=True,
        server_default=sqlalchemy.true(),
    )
    fallback_reply_text = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    binding_required_fields = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, server_default='[]')
    binding_trigger_keywords = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, server_default='[]')
    binding_prompt_text = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    human_handoff_direct_enabled = sqlalchemy.Column(
        sqlalchemy.Boolean,
        nullable=False,
        default=True,
        server_default=sqlalchemy.true(),
    )
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )


class WecomPrivateBindingTask(Base):
    """WeCom private domain binding task"""

    __tablename__ = 'wecom_private_binding_tasks'

    id = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    session_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, unique=True, index=True)
    requested_fields = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, server_default='[]')
    provided_uid = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    provided_server = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    provided_role_name = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    verify_status = sqlalchemy.Column(
        sqlalchemy.String(50),
        nullable=False,
        default='pending',
        server_default='pending',
    )
    requested_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    completed_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )


class WecomPrivateClosureRecord(Base):
    """WeCom private domain closure record"""

    __tablename__ = 'wecom_private_closure_records'

    id = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    session_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, unique=True, index=True)
    resolution_type = sqlalchemy.Column(sqlalchemy.String(50), nullable=False)
    tag_updates = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, server_default='{}')
    followup_needed = sqlalchemy.Column(
        sqlalchemy.Boolean,
        nullable=False,
        default=False,
        server_default=sqlalchemy.false(),
    )
    knowledge_feedback = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    closed_by = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())


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
    lead_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True, index=True)
    risk_level = sqlalchemy.Column(
        sqlalchemy.String(32),
        nullable=False,
        default='normal',
        server_default='normal',
    )
    closed_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )
