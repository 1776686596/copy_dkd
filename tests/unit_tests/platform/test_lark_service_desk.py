from types import SimpleNamespace


def test_lark_adapter_extracts_service_desk_context_for_p2p_message():
    from langbot.pkg.platform.sources.lark import LarkAdapter

    adapter = object.__new__(LarkAdapter)
    event = SimpleNamespace(
        header=SimpleNamespace(tenant_key='tenant-key-1'),
        event=SimpleNamespace(
            message=SimpleNamespace(chat_type='p2p', message_id='om_dc1321'),
            sender=SimpleNamespace(
                sender_id=SimpleNamespace(open_id='ou_customer_1'),
            ),
        ),
    )

    assert adapter.extract_service_desk_context(event) == {
        'source_entry_id': 'tenant-key-1',
        'external_user_id': 'ou_customer_1',
        'last_message_id': 'om_dc1321',
    }


def test_lark_adapter_ignores_group_message_for_service_desk_context():
    from langbot.pkg.platform.sources.lark import LarkAdapter

    adapter = object.__new__(LarkAdapter)
    event = SimpleNamespace(
        header=SimpleNamespace(tenant_key='tenant-key-1'),
        event=SimpleNamespace(
            message=SimpleNamespace(chat_type='group', message_id='om_dc1321'),
            sender=SimpleNamespace(
                sender_id=SimpleNamespace(open_id='ou_customer_1'),
            ),
        ),
    )

    assert adapter.extract_service_desk_context(event) == {}
