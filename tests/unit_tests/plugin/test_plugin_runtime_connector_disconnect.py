from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_emit_event_bypasses_runtime_when_disconnected(monkeypatch):
    from src.langbot.pkg.plugin import connector as connector_module

    fake_event_ctx = MagicMock()
    monkeypatch.setattr(
        connector_module.context.EventContext,
        'from_event',
        MagicMock(return_value=fake_event_ctx),
    )

    mock_app = MagicMock()
    mock_app.instance_config.data = {'plugin': {'enable': True}}
    mock_app.logger = MagicMock()

    connector = connector_module.PluginRuntimeConnector(mock_app, AsyncMock())
    connector.runtime_connected = False
    connector.handler = MagicMock()
    connector.handler.emit_event = AsyncMock(side_effect=AssertionError('runtime should not be called'))

    result = await connector.emit_event(MagicMock(), ['langbot-team/AgenticRAG'])

    assert result is fake_event_ctx
    connector.handler.emit_event.assert_not_called()


@pytest.mark.asyncio
async def test_list_tools_returns_empty_when_disconnected():
    from src.langbot.pkg.plugin.connector import PluginRuntimeConnector

    mock_app = MagicMock()
    mock_app.instance_config.data = {'plugin': {'enable': True}}
    mock_app.logger = MagicMock()

    connector = PluginRuntimeConnector(mock_app, AsyncMock())
    connector.runtime_connected = False
    connector.handler = MagicMock()
    connector.handler.list_tools = AsyncMock(side_effect=AssertionError('runtime should not be called'))

    result = await connector.list_tools(['langbot-team/AgenticRAG'])

    assert result == []
    connector.handler.list_tools.assert_not_called()
