from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_wecomprivate_runtime_returns_basic_runtime_values_without_login_state():
    from langbot.pkg.api.http.service.bot import BotService

    service = BotService(
        SimpleNamespace(
            platform_mgr=SimpleNamespace(get_bot_by_uuid=AsyncMock(return_value=None)),
            instance_config=SimpleNamespace(data={'api': {}}),
        )
    )
    service.get_bot = AsyncMock(
        return_value={
            'uuid': 'bot-uuid',
            'adapter': 'wecomprivate',
        }
    )

    runtime_bot = await service.get_runtime_bot_info('bot-uuid')

    assert runtime_bot['adapter_runtime_values'] == {
        'webhook_url': None,
        'webhook_full_url': None,
        'extra_webhook_full_url': None,
    }


@pytest.mark.asyncio
async def test_wecomprivate_runtime_keeps_bot_account_id_without_login_state():
    from langbot.pkg.api.http.service.bot import BotService

    service = BotService(
        SimpleNamespace(
            platform_mgr=SimpleNamespace(
                get_bot_by_uuid=AsyncMock(
                    return_value=SimpleNamespace(
                        adapter=SimpleNamespace(
                            bot_account_id='private-entry',
                            bot=SimpleNamespace(),
                        )
                    )
                )
            ),
            instance_config=SimpleNamespace(data={'api': {}}),
        )
    )
    service.get_bot = AsyncMock(
        return_value={
            'uuid': 'bot-uuid',
            'adapter': 'wecomprivate',
        }
    )

    runtime_bot = await service.get_runtime_bot_info('bot-uuid')

    assert runtime_bot['adapter_runtime_values'] == {
        'bot_account_id': 'private-entry',
        'webhook_url': None,
        'webhook_full_url': None,
        'extra_webhook_full_url': None,
    }
