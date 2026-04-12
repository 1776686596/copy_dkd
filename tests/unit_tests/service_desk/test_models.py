import sqlalchemy


def test_required_database_version_is_26():
    from langbot.pkg.utils import constants

    assert constants.required_database_version == 26


def test_service_desk_session_has_manual_takeover_fields():
    from langbot.pkg.entity.persistence.service_desk import ServiceDeskSession

    columns = ServiceDeskSession.__table__.c

    assert 'session_id' in columns
    assert 'bot_uuid' in columns
    assert 'mode' in columns
    assert 'queue_status' in columns
    assert 'source_entry_id' in columns
    assert 'last_message_id' in columns
    assert 'claimed_by_user_uuid' in columns
    assert 'silent_since' in columns


def test_service_desk_material_has_keyword_and_payload_fields():
    from langbot.pkg.entity.persistence.service_desk import ServiceDeskMaterial

    columns = ServiceDeskMaterial.__table__.c

    assert isinstance(columns['trigger_keywords'].type, sqlalchemy.JSON)
    assert isinstance(columns['payload'].type, sqlalchemy.JSON)
