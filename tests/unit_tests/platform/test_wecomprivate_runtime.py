from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_wecomprivate_runtime_returns_login_defaults_without_runtime_bot():
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
        'login_state_checked': False,
        'login_required': False,
        'login_qr_image_base64': None,
        'login_qr_updated_at': None,
    }


@pytest.mark.asyncio
async def test_wecomprivate_runtime_uses_adapter_login_state_when_available():
    from langbot.pkg.api.http.service.bot import BotService

    service = BotService(
        SimpleNamespace(
            platform_mgr=SimpleNamespace(
                get_bot_by_uuid=AsyncMock(
                    return_value=SimpleNamespace(
                        adapter=SimpleNamespace(
                            bot_account_id='private-entry',
                            bot=SimpleNamespace(
                                get_login_runtime_state=lambda: {
                                    'login_state_checked': True,
                                    'login_required': True,
                                    'login_qr_image_base64': 'cached-qr',
                                    'login_qr_updated_at': 1710000000,
                                }
                            ),
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
        'login_state_checked': True,
        'login_required': True,
        'login_qr_image_base64': 'cached-qr',
        'login_qr_updated_at': 1710000000,
    }
