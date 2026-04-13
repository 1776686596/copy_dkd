from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_wecomweb_client_caches_login_qr_runtime_state(monkeypatch):
    from langbot.libs.wecom_web_page_api.client import WecomWebPageClient

    qr_png = b"fake-qr-png"
    monkeypatch.setattr("langbot.libs.wecom_web_page_api.client.time.time", lambda: 1710000000)

    client = WecomWebPageClient(
        account_label="escort-account",
        workbench_url="https://work.weixin.qq.com/kf/",
        storage_state_dir="./tmp/wecomweb",
    )

    qr_locator = SimpleNamespace(screenshot=AsyncMock(return_value=qr_png))
    client._find_first_visible_locator = AsyncMock(return_value=qr_locator)
    client._render_image_to_terminal = lambda image_bytes: "QR"

    await client._show_login_qr()

    assert client.get_login_runtime_state() == {
        "login_required": True,
        "login_qr_image_base64": "ZmFrZS1xci1wbmc=",
        "login_qr_updated_at": 1710000000,
    }


def test_wecomweb_client_clear_login_runtime_state_keeps_last_qr_hash():
    from langbot.libs.wecom_web_page_api.client import WecomWebPageClient

    client = WecomWebPageClient(
        account_label="escort-account",
        workbench_url="https://work.weixin.qq.com/kf/",
        storage_state_dir="./tmp/wecomweb",
    )
    client._login_required = True
    client._login_qr_image_base64 = "cached-qr"
    client._login_qr_updated_at = 1710000000
    client._last_qr_hash = "existing-hash"

    client._clear_login_runtime_state()

    assert client.get_login_runtime_state() == {
        "login_required": False,
        "login_qr_image_base64": None,
        "login_qr_updated_at": None,
    }
    assert client._last_qr_hash == "existing-hash"


@pytest.mark.asyncio
async def test_get_runtime_bot_info_includes_wecomweb_login_runtime_state():
    from langbot.pkg.api.http.service.bot import BotService

    service = BotService(
        SimpleNamespace(
            platform_mgr=SimpleNamespace(
                get_bot_by_uuid=AsyncMock(
                    return_value=SimpleNamespace(
                        adapter=SimpleNamespace(
                            bot_account_id="escort-account",
                            bot=SimpleNamespace(
                                get_login_runtime_state=lambda: {
                                    "login_required": True,
                                    "login_qr_image_base64": "cached-qr",
                                    "login_qr_updated_at": 1710000000,
                                }
                            ),
                        )
                    )
                )
            ),
            instance_config=SimpleNamespace(data={"api": {}}),
        )
    )
    service.get_bot = AsyncMock(
        return_value={
            "uuid": "bot-uuid",
            "adapter": "wecomweb",
        }
    )

    runtime_bot = await service.get_runtime_bot_info("bot-uuid")

    assert runtime_bot["adapter_runtime_values"] == {
        "bot_account_id": "escort-account",
        "webhook_url": None,
        "webhook_full_url": None,
        "extra_webhook_full_url": None,
        "login_required": True,
        "login_qr_image_base64": "cached-qr",
        "login_qr_updated_at": 1710000000,
    }


@pytest.mark.asyncio
async def test_get_runtime_bot_info_does_not_expose_wecomweb_login_fields_to_other_adapters():
    from langbot.pkg.api.http.service.bot import BotService

    service = BotService(
        SimpleNamespace(
            platform_mgr=SimpleNamespace(
                get_bot_by_uuid=AsyncMock(
                    return_value=SimpleNamespace(
                        adapter=SimpleNamespace(
                            bot_account_id="adapter-account",
                            bot=SimpleNamespace(
                                get_login_runtime_state=lambda: {
                                    "login_required": True,
                                    "login_qr_image_base64": "cached-qr",
                                    "login_qr_updated_at": 1710000000,
                                }
                            ),
                        )
                    )
                )
            ),
            instance_config=SimpleNamespace(data={"api": {}}),
        )
    )
    service.get_bot = AsyncMock(
        return_value={
            "uuid": "bot-uuid",
            "adapter": "wecom",
        }
    )

    runtime_bot = await service.get_runtime_bot_info("bot-uuid")

    assert runtime_bot["adapter_runtime_values"] == {
        "bot_account_id": "adapter-account",
        "webhook_url": "/bots/bot-uuid",
        "webhook_full_url": "http://127.0.0.1:5300/bots/bot-uuid",
        "extra_webhook_full_url": "",
    }
