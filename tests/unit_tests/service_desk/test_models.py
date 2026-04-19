import sqlalchemy


def test_required_database_version_is_29():
    from langbot.pkg.utils import constants

    assert constants.required_database_version == 29


def test_wecom_private_models_exist():
    from langbot.pkg.entity.persistence.service_desk import (
        ServiceDeskSession,
        WecomPrivateBindingTask,
        WecomPrivateClosureRecord,
        WecomPrivateContactConfig,
        WecomPrivateLead,
        WecomPrivateReceptionConfig,
        WecomPrivateRoutingDecision,
    )

    session_columns = ServiceDeskSession.__table__.c
    reception_columns = WecomPrivateReceptionConfig.__table__.c
    binding_columns = WecomPrivateBindingTask.__table__.c

    assert 'lead_id' in session_columns
    assert 'risk_level' in session_columns
    assert 'closed_at' in session_columns

    assert WecomPrivateContactConfig.__tablename__ == 'wecom_private_contact_configs'
    assert isinstance(WecomPrivateLead.__table__.c['current_tags'].type, sqlalchemy.JSON)
    assert WecomPrivateReceptionConfig.__tablename__ == 'wecom_private_reception_configs'
    assert reception_columns['bot_uuid'].primary_key is True
    assert reception_columns['fallback_reply_text'].nullable is True
    assert reception_columns['binding_prompt_text'].nullable is True
    assert isinstance(reception_columns['binding_required_fields'].type, sqlalchemy.JSON)
    assert isinstance(reception_columns['binding_trigger_keywords'].type, sqlalchemy.JSON)
    assert isinstance(binding_columns['requested_fields'].type, sqlalchemy.JSON)
    assert 'provided_role_name' in binding_columns
    assert isinstance(binding_columns['provided_role_name'].type, sqlalchemy.String)
    assert binding_columns['provided_role_name'].nullable is True
    assert isinstance(WecomPrivateClosureRecord.__table__.c['tag_updates'].type, sqlalchemy.JSON)
    assert WecomPrivateRoutingDecision.__table__.c['decision'].nullable is False
