from __future__ import annotations

import asyncio
import time
from typing import Any


class WecomPrivatePageClient:
    def __init__(
        self,
        *,
        entry_id: str,
        workbench_url: str,
        storage_state_dir: str,
        logger=None,
        poll_interval_seconds: int = 2,
        headless: bool = True,
        print_login_qr: bool = True,
        browser_executable_path: str | None = None,
    ) -> None:
        self.entry_id = entry_id
        self.workbench_url = workbench_url
        self.storage_state_dir = storage_state_dir
        self.logger = logger
        self.poll_interval_seconds = poll_interval_seconds
        self.headless = headless
        self.print_login_qr = print_login_qr
        self.browser_executable_path = browser_executable_path.strip() if browser_executable_path else None

        self._stop_event = asyncio.Event()
        self._message_callback = None
        self._send_queue: asyncio.Queue[dict[str, str]] = asyncio.Queue()
        self._login_state_checked = False
        self._login_required = False
        self._login_qr_image_base64: str | None = None
        self._login_qr_updated_at: int | None = None

    @staticmethod
    def _as_bool(value: Any, default: bool) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {'1', 'true', 'yes', 'on'}
        return bool(value)

    @classmethod
    def from_config(cls, config: dict[str, Any], logger=None) -> 'WecomPrivatePageClient':
        return cls(
            entry_id=str(config.get('entry_id') or '').strip(),
            workbench_url=str(config.get('workbench_url') or '').strip(),
            storage_state_dir=str(config.get('storage_state_dir') or '').strip(),
            logger=logger,
            poll_interval_seconds=int(config.get('poll_interval_seconds', 2) or 2),
            headless=cls._as_bool(config.get('headless'), True),
            print_login_qr=cls._as_bool(config.get('print_login_qr'), True),
            browser_executable_path=config.get('browser_executable_path'),
        )

    def set_message_callback(self, callback) -> None:
        self._message_callback = callback

    def get_login_runtime_state(self) -> dict[str, Any]:
        return {
            'login_state_checked': self._login_state_checked,
            'login_required': self._login_required,
            'login_qr_image_base64': self._login_qr_image_base64,
            'login_qr_updated_at': self._login_qr_updated_at,
        }

    def set_login_runtime_state(
        self,
        *,
        checked: bool,
        required: bool,
        qr_image_base64: str | None = None,
        updated_at: int | None = None,
    ) -> None:
        self._login_state_checked = checked
        self._login_required = required
        self._login_qr_image_base64 = qr_image_base64
        self._login_qr_updated_at = updated_at if updated_at is not None else int(time.time())

    def clear_login_runtime_state(self) -> None:
        self._login_state_checked = True
        self._login_required = False
        self._login_qr_image_base64 = None
        self._login_qr_updated_at = None

    async def send_text(self, *, conversation_id: str, external_user_id: str, text: str) -> dict[str, str]:
        payload = {
            'conversation_id': conversation_id,
            'external_user_id': external_user_id,
            'text': text,
        }
        await self._send_queue.put(payload)
        return payload

    async def send_text_msg(
        self,
        open_kfid: str,
        external_userid: str,
        msgid: str,
        content: str,
    ) -> dict[str, str]:
        conversation_id = open_kfid or external_userid or msgid
        return await self.send_text(
            conversation_id=conversation_id,
            external_user_id=external_userid,
            text=content,
        )

    async def emit_message(self, payload: dict[str, Any]) -> None:
        if self._message_callback is not None:
            await self._message_callback(payload)

    async def run_forever(self) -> None:
        self._stop_event.clear()
        while not self._stop_event.is_set():
            await asyncio.sleep(self.poll_interval_seconds)

    async def disconnect(self) -> None:
        self._stop_event.set()
