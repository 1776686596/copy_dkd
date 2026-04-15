from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_stdio_runtime_launch_uses_runtime_stdio_args(monkeypatch):
    from src.langbot.pkg.plugin.connector import PluginRuntimeConnector

    captured: dict[str, object] = {}

    class FakeStdioClientController:
        def __init__(self, command: str, args: list[str], env: dict[str, str], working_dir: str = '.'):
            captured['command'] = command
            captured['args'] = args
            captured['env'] = env
            captured['working_dir'] = working_dir

        async def run(self, new_connection_callback):
            return None

    mock_app = MagicMock()
    mock_app.instance_config.data = {'plugin': {'enable': True}}
    mock_app.logger = MagicMock()

    connector = PluginRuntimeConnector(mock_app, AsyncMock())
    connector.heartbeat_task = MagicMock()

    monkeypatch.setattr('src.langbot.pkg.plugin.connector.platform.get_platform', lambda: 'linux')
    monkeypatch.setattr(
        'src.langbot.pkg.plugin.connector.platform.use_websocket_to_connect_plugin_runtime',
        lambda: False,
    )
    monkeypatch.setattr(
        'src.langbot.pkg.plugin.connector.stdio_client_controller.StdioClientController',
        FakeStdioClientController,
    )

    await connector.initialize()

    assert captured['command']
    assert captured['args'] == ['-m', 'langbot_plugin.cli.__init__', 'rt', '-s']
