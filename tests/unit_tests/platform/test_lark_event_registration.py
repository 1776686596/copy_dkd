from types import SimpleNamespace


def test_lark_adapter_registers_bot_p2p_chat_entered_event(monkeypatch):
    from langbot.pkg.platform.sources import lark

    class FakeEventBuilder:
        def __init__(self):
            self.registered_message = False
            self.registered_card_action = False
            self.registered_p2p_chat_entered = False

        def register_p2_im_message_receive_v1(self, _handler):
            self.registered_message = True
            return self

        def register_p2_card_action_trigger(self, _handler):
            self.registered_card_action = True
            return self

        def register_p2_im_chat_access_event_bot_p2p_chat_entered_v1(self, _handler):
            self.registered_p2p_chat_entered = True
            return self

        def build(self):
            return object()

    builder = FakeEventBuilder()

    monkeypatch.setattr(
        lark.lark_oapi.EventDispatcherHandler,
        'builder',
        staticmethod(lambda *_args, **_kwargs: builder),
    )
    monkeypatch.setattr(lark.lark_oapi.ws, 'Client', lambda *_args, **_kwargs: object())
    monkeypatch.setattr(lark.LarkAdapter, 'build_api_client', lambda self, _config: object())
    monkeypatch.setattr(lark.LarkAdapter, 'request_app_ticket', lambda self, _api_client, _config: None)
    monkeypatch.setattr(
        lark.abstract_platform_adapter.AbstractMessagePlatformAdapter,
        '__init__',
        lambda self, **_kwargs: None,
    )

    lark.LarkAdapter(
        config={'app_id': 'app-id', 'app_secret': 'app-secret', 'bot_name': 'bot-name'},
        logger=SimpleNamespace(),
    )

    assert builder.registered_message is True
    assert builder.registered_card_action is True
    assert builder.registered_p2p_chat_entered is True
