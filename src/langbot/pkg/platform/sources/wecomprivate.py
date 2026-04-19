from __future__ import annotations

import datetime
import traceback
import typing
from dataclasses import dataclass

import pydantic

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger
import langbot_plugin.api.entities.builtin.command.errors as command_errors
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message
from langbot.libs.wecom_private_page_api import WecomPrivatePageClient


@dataclass
class WecomPrivateMessageEvent:
    entry_id: str
    follow_user_id: str
    external_user_id: str
    message_id: str
    conversation_id: str
    sender_name: str
    content: str
    timestamp: int
    welcome_code: str | None = None


class WecomPrivateMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    @staticmethod
    async def yiri2target(message_chain: platform_message.MessageChain) -> str:
        text_parts = []
        for message in message_chain:
            if type(message) is platform_message.Plain:
                text_parts.append(message.text)
        return ''.join(text_parts).strip() or str(message_chain)

    @staticmethod
    async def target2yiri(message: str, message_id: str):
        yiri_msg_list = [
            platform_message.Source(id=message_id, time=datetime.datetime.now()),
            platform_message.Plain(text=message),
        ]
        return platform_message.MessageChain(yiri_msg_list)


class WecomPrivateEventConverter(abstract_platform_adapter.AbstractEventConverter):
    @staticmethod
    async def yiri2target(event: platform_events.MessageEvent) -> WecomPrivateMessageEvent:
        return event.source_platform_object

    @staticmethod
    async def target2yiri(event: WecomPrivateMessageEvent):
        message_chain = await WecomPrivateMessageConverter.target2yiri(event.content, event.message_id)
        friend = platform_entities.Friend(
            id=f'u{event.external_user_id}',
            nickname=event.sender_name,
            remark='',
        )
        return platform_events.FriendMessage(
            sender=friend,
            message_chain=message_chain,
            time=event.timestamp,
            source_platform_object=event,
        )


class WecomPrivateAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    bot: WecomPrivatePageClient = pydantic.Field(exclude=True)
    message_converter: WecomPrivateMessageConverter = WecomPrivateMessageConverter()
    event_converter: WecomPrivateEventConverter = WecomPrivateEventConverter()
    bot_uuid: str | None = None
    listeners: dict = pydantic.Field(default_factory=dict, exclude=True)

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger):
        required_keys = ['entry_id', 'workbench_url', 'storage_state_dir']
        missing_keys = [key for key in required_keys if not config.get(key)]
        if missing_keys:
            raise command_errors.ParamNotEnoughError('企微私域托管缺少相关配置项，请查看文档或联系管理员')

        bot = WecomPrivatePageClient.from_config(config, logger=logger)
        super().__init__(
            config=config,
            logger=logger,
            bot_account_id=config.get('entry_id', ''),
            listeners={},
            bot=bot,
        )
        self.listeners = {}

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        event_converter = getattr(type(self), 'event_converter', WecomPrivateEventConverter())
        message_converter = getattr(type(self), 'message_converter', WecomPrivateMessageConverter())
        event = await event_converter.yiri2target(message_source)
        content = await message_converter.yiri2target(message)
        await self.bot.send_text(
            conversation_id=event.conversation_id,
            external_user_id=event.external_user_id,
            text=content,
        )

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain):
        message_converter = getattr(type(self), 'message_converter', WecomPrivateMessageConverter())
        content = await message_converter.yiri2target(message)
        await self.bot.send_text(
            conversation_id=target_id,
            external_user_id=target_id,
            text=content,
        )

    def get_launcher_id(self, event: platform_events.MessageEvent) -> str | None:
        source_event = getattr(event, 'source_platform_object', event)
        context = self.extract_service_desk_context(source_event)
        source_entry_id = context.get('source_entry_id')
        external_user_id = context.get('external_user_id')
        if source_entry_id and external_user_id:
            return f'{source_entry_id}:{external_user_id}'
        return None

    def extract_service_desk_context(self, event: WecomPrivateMessageEvent) -> dict[str, str]:
        return {
            'source_entry_id': event.entry_id or '',
            'external_user_id': event.external_user_id or '',
            'last_message_id': str(event.message_id or ''),
        }

    def set_bot_uuid(self, bot_uuid: str):
        self.bot_uuid = bot_uuid

    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter],
            None,
        ],
    ):
        self.listeners[event_type] = callback
        if event_type == platform_events.FriendMessage:
            self.bot.set_message_callback(self._handle_browser_message)

    async def _handle_browser_message(self, payload: dict[str, typing.Any]):
        event = WecomPrivateMessageEvent(
            entry_id=str(payload.get('entry_id') or self.bot.entry_id),
            follow_user_id=str(payload.get('follow_user_id') or ''),
            external_user_id=str(payload['external_user_id']),
            message_id=str(payload['message_id']),
            conversation_id=str(payload.get('conversation_id') or payload['external_user_id']),
            sender_name=str(payload.get('sender_name') or payload['external_user_id']),
            content=str(payload.get('content') or ''),
            timestamp=int(payload.get('timestamp') or datetime.datetime.now().timestamp()),
            welcome_code=payload.get('welcome_code'),
        )
        object.__setattr__(self, 'bot_account_id', event.entry_id)
        try:
            event_converter = getattr(type(self), 'event_converter', WecomPrivateEventConverter())
            converted_event = await event_converter.target2yiri(event)
            listener = getattr(self, 'listeners', {}).get(platform_events.FriendMessage)
            if listener is not None:
                await listener(converted_event, self)
        except Exception:
            await self.logger.error(f'Error in wecomprivate callback: {traceback.format_exc()}')

    async def run_async(self):
        await self.bot.run_forever()

    async def kill(self) -> bool:
        await self.bot.disconnect()
        return True

    async def is_muted(self, group_id: int) -> bool:
        return False

    async def unregister_listener(
        self,
        event_type: type,
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter],
            None,
        ],
    ):
        return super().unregister_listener(event_type, callback)
