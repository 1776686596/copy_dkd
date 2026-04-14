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
        "login_state_checked": True,
        "login_required": True,
        "login_qr_image_base64": "ZmFrZS1xci1wbmc=",
        "login_qr_updated_at": 1710000000,
    }


@pytest.mark.asyncio
async def test_wecomweb_client_marks_login_checked_when_qr_not_ready_yet():
    from langbot.libs.wecom_web_page_api.client import WecomWebPageClient

    client = WecomWebPageClient(
        account_label="escort-account",
        workbench_url="https://work.weixin.qq.com/kf/",
        storage_state_dir="./tmp/wecomweb",
    )

    client._find_first_visible_locator = AsyncMock(return_value=None)

    await client._show_login_qr()

    assert client.get_login_runtime_state() == {
        "login_state_checked": True,
        "login_required": True,
        "login_qr_image_base64": None,
        "login_qr_updated_at": None,
    }


@pytest.mark.asyncio
async def test_wecomweb_client_run_forever_prints_same_qr_again_after_login_restored(monkeypatch, capsys):
    from langbot.libs.wecom_web_page_api.client import WecomWebPageClient

    qr_png = b"fake-qr-png"
    monkeypatch.setattr("langbot.libs.wecom_web_page_api.client.time.time", lambda: 1710000000)

    client = WecomWebPageClient(
        account_label="escort-account",
        workbench_url="https://work.weixin.qq.com/kf/",
        storage_state_dir="./tmp/wecomweb",
    )

    sleep_calls = 0

    async def fake_sleep(_seconds):
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls >= 3:
            client._stop_event.set()

    qr_locator = SimpleNamespace(screenshot=AsyncMock(return_value=qr_png))
    client._ensure_browser = AsyncMock()
    client._is_login_required = AsyncMock(side_effect=[True, False, True])
    client._find_first_visible_locator = AsyncMock(return_value=qr_locator)
    client._render_image_to_terminal = lambda image_bytes: "QR"
    client._drain_send_queue = AsyncMock()
    client._poll_once = AsyncMock()
    monkeypatch.setattr("langbot.libs.wecom_web_page_api.client.asyncio.sleep", fake_sleep)

    await client.run_forever()

    output = capsys.readouterr().out
    assert output.count("请使用企业微信扫码登录企微客服网页") == 2


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
                                    "login_state_checked": True,
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
        "login_state_checked": True,
        "login_required": True,
        "login_qr_image_base64": "cached-qr",
        "login_qr_updated_at": 1710000000,
    }


@pytest.mark.asyncio
async def test_get_runtime_bot_info_returns_wecomweb_login_defaults_without_runtime_bot():
    from langbot.pkg.api.http.service.bot import BotService

    service = BotService(
        SimpleNamespace(
            platform_mgr=SimpleNamespace(get_bot_by_uuid=AsyncMock(return_value=None)),
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
        "webhook_url": None,
        "webhook_full_url": None,
        "extra_webhook_full_url": None,
        "login_state_checked": False,
        "login_required": False,
        "login_qr_image_base64": None,
        "login_qr_updated_at": None,
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
                                    "login_state_checked": True,
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


@pytest.mark.asyncio
async def test_wecomweb_client_run_forever_clears_cached_login_state_after_login_restored(monkeypatch):
    from langbot.libs.wecom_web_page_api.client import WecomWebPageClient

    client = WecomWebPageClient(
        account_label="escort-account",
        workbench_url="https://work.weixin.qq.com/kf/",
        storage_state_dir="./tmp/wecomweb",
    )

    async def fake_show_login_qr():
        client._login_required = True
        client._login_qr_image_base64 = "cached-qr"
        client._login_qr_updated_at = 1710000000

    sleep_calls = 0

    async def fake_sleep(_seconds):
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls >= 2:
            client._stop_event.set()

    client._ensure_browser = AsyncMock()
    client._is_login_required = AsyncMock(side_effect=[True, False])
    client._show_login_qr = fake_show_login_qr
    client._drain_send_queue = AsyncMock()
    client._poll_once = AsyncMock()
    monkeypatch.setattr("langbot.libs.wecom_web_page_api.client.asyncio.sleep", fake_sleep)

    await client.run_forever()

    assert client.get_login_runtime_state() == {
        "login_state_checked": True,
        "login_required": False,
        "login_qr_image_base64": None,
        "login_qr_updated_at": None,
    }


@pytest.mark.asyncio
async def test_bot_service_create_bot_runs_enabled_runtime_bot(monkeypatch):
    from langbot.pkg.api.http.service.bot import BotService

    runtime_bot = SimpleNamespace(enable=True, run=AsyncMock())
    load_bot = AsyncMock(return_value=runtime_bot)
    execute_async = AsyncMock(
        side_effect=[
            SimpleNamespace(first=lambda: None),
            None,
        ]
    )
    monkeypatch.setattr("langbot.pkg.api.http.service.bot.uuid.uuid4", lambda: "bot-uuid")

    service = BotService(
        SimpleNamespace(
            persistence_mgr=SimpleNamespace(
                execute_async=execute_async,
                serialize_model=lambda *_args, **_kwargs: {"uuid": "bot-uuid"},
            ),
            platform_mgr=SimpleNamespace(load_bot=load_bot),
            instance_config=SimpleNamespace(data={"system": {}}),
        )
    )
    service.get_bots = AsyncMock(return_value=[])
    service.get_bot = AsyncMock(return_value={"uuid": "bot-uuid", "enable": True})

    bot_uuid = await service.create_bot(
        {
            "name": "bot",
            "description": "",
            "adapter": "wecomweb",
            "adapter_config": {"account_label": "a", "workbench_url": "u", "storage_state_dir": "d"},
            "enable": True,
        }
    )

    assert bot_uuid == "bot-uuid"
    load_bot.assert_awaited_once()
    runtime_bot.run.assert_awaited_once()


@pytest.mark.asyncio
async def test_wecomweb_client_falls_back_to_system_browser_when_builtin_browser_missing(
    monkeypatch, tmp_path
):
    import playwright.async_api as playwright_async_api

    from langbot.libs.wecom_web_page_api import client as wecom_client_module
    from langbot.libs.wecom_web_page_api.client import WecomWebPageClient

    fake_page = SimpleNamespace(goto=AsyncMock())
    fake_context = SimpleNamespace(pages=[fake_page])
    launch_context = AsyncMock(
        side_effect=[
            RuntimeError("Executable doesn't exist at /root/.cache/ms-playwright/..."),
            fake_context,
        ]
    )
    fake_playwright = SimpleNamespace(
        chromium=SimpleNamespace(launch_persistent_context=launch_context)
    )

    class FakeStarter:
        async def start(self):
            return fake_playwright

    monkeypatch.setattr(playwright_async_api, "async_playwright", lambda: FakeStarter())
    monkeypatch.setattr(
        wecom_client_module.shutil,
        "which",
        lambda name: "/usr/bin/google-chrome" if name == "google-chrome" else None,
    )

    client = WecomWebPageClient(
        account_label="escort-account",
        workbench_url="https://work.weixin.qq.com/kf/",
        storage_state_dir=str(tmp_path / "wecomweb"),
    )

    await client._ensure_browser()

    assert launch_context.await_count == 2
    first_call = launch_context.await_args_list[0].kwargs
    second_call = launch_context.await_args_list[1].kwargs
    assert "executable_path" not in first_call
    assert second_call["executable_path"] == "/usr/bin/google-chrome"
    fake_page.goto.assert_awaited_once_with(
        "https://work.weixin.qq.com/kf/",
        wait_until="domcontentloaded",
    )
