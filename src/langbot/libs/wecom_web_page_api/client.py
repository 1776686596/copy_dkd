from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import shutil
import time
from pathlib import Path
from typing import Any

from PIL import Image


DEFAULT_SELECTORS = {
    'login_qr': [
        'img[src*="qrcode"]',
        'img[alt*="二维码"]',
        '[class*="qrcode"] img',
        '[class*="qr"] img',
        'canvas',
    ],
    'conversation_item': [
        '[data-conversation-id]',
        '[data-id]',
        '[role="listitem"]',
        '[class*="conversation-item"]',
        '[class*="session-item"]',
    ],
    'conversation_title': [
        '[data-conversation-title]',
        '[class*="conversation-title"]',
        '[class*="session-title"]',
        '[class*="nickname"]',
        '[class*="name"]',
    ],
    'message_row': [
        '[data-message-id]',
        '[class*="message-item"]',
        '[class*="message-row"]',
        '[class*="msg-item"]',
        '[class*="chat-item"]',
    ],
    'message_text': [
        '[class*="message-text"]',
        '[class*="text-content"]',
        '[class*="msg-text"]',
        '[class*="bubble-text"]',
        '[class*="content"]',
    ],
    'input': [
        'div[contenteditable="true"]',
        'textarea',
    ],
    'send_button': [
        'button:has-text("发送")',
        'button[aria-label*="发送"]',
        '[class*="send-btn"]',
        '[class*="send-button"]',
    ],
}


class WecomWebPageClient:
    def __init__(
        self,
        *,
        account_label: str,
        workbench_url: str,
        storage_state_dir: str,
        logger=None,
        poll_interval_seconds: int = 2,
        headless: bool = True,
        print_login_qr: bool = True,
        browser_executable_path: str | None = None,
        selectors: dict[str, list[str]] | None = None,
    ):
        self.account_label = account_label
        self.workbench_url = workbench_url
        self.storage_state_dir = storage_state_dir
        self.logger = logger
        self.poll_interval_seconds = poll_interval_seconds
        self.headless = headless
        self.print_login_qr = print_login_qr
        self.browser_executable_path = browser_executable_path.strip() if browser_executable_path else None
        self.selectors = self._merge_selectors(selectors)

        self._playwright = None
        self._browser_context = None
        self._page = None
        self._stop_event = asyncio.Event()
        self._message_callback = None
        self._send_queue: asyncio.Queue[dict[str, str]] = asyncio.Queue()
        self._seen_message_keys: set[str] = set()
        self._conversation_keys: dict[str, str] = {}
        self._recent_outbound_texts: dict[str, str] = {}
        self._last_qr_hash: str | None = None
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

    @staticmethod
    def _merge_selectors(custom_selectors: dict[str, Any] | None) -> dict[str, list[str]]:
        merged = {key: list(value) for key, value in DEFAULT_SELECTORS.items()}
        if not custom_selectors:
            return merged

        for key, value in custom_selectors.items():
            if isinstance(value, list) and value:
                merged[key] = [str(item) for item in value if item]

        return merged

    def set_message_callback(self, callback):
        self._message_callback = callback

    def get_login_runtime_state(self) -> dict[str, Any]:
        return {
            'login_state_checked': self._login_state_checked,
            'login_required': self._login_required,
            'login_qr_image_base64': self._login_qr_image_base64,
            'login_qr_updated_at': self._login_qr_updated_at,
        }

    def _clear_login_runtime_state(self, *, checked: bool | None = None) -> None:
        if checked is not None:
            self._login_state_checked = checked
        self._login_required = False
        self._login_qr_image_base64 = None
        self._login_qr_updated_at = None

    def _remember_message(self, payload: dict[str, Any]) -> bool:
        message_key = f"{payload['conversation_id']}:{payload['message_id']}"
        if message_key in self._seen_message_keys:
            return False
        self._seen_message_keys.add(message_key)
        return True

    async def send_text(self, *, conversation_id: str, external_user_id: str, text: str) -> dict[str, str]:
        await self._send_queue.put(
            {
                'conversation_id': conversation_id,
                'external_user_id': external_user_id,
                'text': text,
            }
        )
        self._recent_outbound_texts[external_user_id] = text.strip()
        return {'conversation_id': conversation_id, 'external_user_id': external_user_id, 'text': text}

    async def send_text_msg(
        self,
        open_kfid: str,
        external_userid: str,
        msgid: str,
        content: str,
    ) -> dict[str, str]:
        conversation_id = self._conversation_keys.get(external_userid) or external_userid
        return await self.send_text(
            conversation_id=conversation_id,
            external_user_id=external_userid,
            text=content,
        )

    async def run_forever(self) -> None:
        self._stop_event.clear()
        while not self._stop_event.is_set():
            try:
                await self._ensure_browser()
                if await self._is_login_required():
                    await self._show_login_qr()
                    await asyncio.sleep(self.poll_interval_seconds)
                    continue
                self._last_qr_hash = None
                self._clear_login_runtime_state(checked=True)

                await self._drain_send_queue()
                await self._poll_once()
            except Exception as exc:
                await self._log('error', f'wecomweb polling error: {exc}')
                await self._reset_browser()

            await asyncio.sleep(self.poll_interval_seconds)

    async def disconnect(self) -> None:
        self._stop_event.set()
        await self._reset_browser()

    async def _reset_browser(self) -> None:
        if self._browser_context is not None:
            await self._browser_context.close()
        if self._playwright is not None:
            await self._playwright.stop()

        self._playwright = None
        self._browser_context = None
        self._page = None

    async def _ensure_browser(self) -> None:
        if self._page is not None:
            return

        Path(self.storage_state_dir).mkdir(parents=True, exist_ok=True)

        try:
            from playwright.async_api import async_playwright
        except ModuleNotFoundError as exc:
            raise RuntimeError('Playwright 未安装，请先执行 `playwright install chromium`') from exc

        self._playwright = await async_playwright().start()
        launch_kwargs = self._build_launch_kwargs(self.browser_executable_path)

        try:
            self._browser_context = await self._playwright.chromium.launch_persistent_context(**launch_kwargs)
        except Exception as exc:
            fallback_browser = self._resolve_fallback_browser_executable(exc, launch_kwargs)
            if fallback_browser is None:
                raise

            await self._log('warning', f'Playwright 内置浏览器不可用，回退到系统浏览器：{fallback_browser}')
            launch_kwargs = self._build_launch_kwargs(fallback_browser)
            self._browser_context = await self._playwright.chromium.launch_persistent_context(**launch_kwargs)

        self._page = self._browser_context.pages[0] if self._browser_context.pages else await self._browser_context.new_page()
        await self._page.goto(self.workbench_url, wait_until='domcontentloaded')

    def _build_launch_kwargs(self, executable_path: str | None = None) -> dict[str, Any]:
        launch_kwargs: dict[str, Any] = {
            'user_data_dir': self.storage_state_dir,
            'headless': self.headless,
        }
        if executable_path:
            launch_kwargs['executable_path'] = executable_path
        return launch_kwargs

    def _resolve_fallback_browser_executable(
        self,
        error: Exception,
        launch_kwargs: dict[str, Any],
    ) -> str | None:
        if launch_kwargs.get('executable_path'):
            return None

        if "Executable doesn't exist" not in str(error):
            return None

        return self._find_system_browser_executable()

    @staticmethod
    def _find_system_browser_executable() -> str | None:
        for candidate in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser'):
            executable_path = shutil.which(candidate)
            if executable_path:
                return executable_path
        return None

    async def _is_login_required(self) -> bool:
        qr_locator = await self._find_first_visible_locator(self.selectors['login_qr'])
        if qr_locator is not None:
            return True

        input_locator = await self._find_first_visible_locator(self.selectors['input'])
        return input_locator is None

    async def _show_login_qr(self) -> None:
        qr_locator = await self._find_first_visible_locator(self.selectors['login_qr'])
        if qr_locator is None:
            return

        qr_png = await qr_locator.screenshot()
        self._login_state_checked = True
        self._login_required = True
        self._login_qr_image_base64 = base64.b64encode(qr_png).decode('ascii')
        self._login_qr_updated_at = int(time.time())

        qr_hash = hashlib.sha1(qr_png).hexdigest()
        if qr_hash == self._last_qr_hash:
            return

        self._last_qr_hash = qr_hash
        if not self.print_login_qr:
            return

        print('\n请使用企业微信扫码登录企微客服网页：\n')
        print(self._render_image_to_terminal(qr_png))
        print('\n扫码成功后会自动继续监听消息。\n')

    @staticmethod
    def _render_image_to_terminal(image_bytes: bytes, width: int = 48) -> str:
        image = Image.open(io.BytesIO(image_bytes)).convert('L')
        image = image.resize((width, width), Image.Resampling.NEAREST)
        rows = []
        for y in range(0, image.height, 2):
            row = []
            for x in range(image.width):
                top = image.getpixel((x, y)) < 128
                bottom = image.getpixel((x, min(y + 1, image.height - 1))) < 128
                if top and bottom:
                    row.append('██')
                elif top:
                    row.append('▀▀')
                elif bottom:
                    row.append('▄▄')
                else:
                    row.append('  ')
            rows.append(''.join(row))
        return '\n'.join(rows)

    async def _poll_once(self) -> None:
        conversation_payload = await self._select_latest_conversation()
        if conversation_payload is None:
            return

        self._conversation_keys[conversation_payload['external_user_id']] = conversation_payload['conversation_id']

        for payload in await self._extract_active_messages(conversation_payload):
            if not payload.get('content'):
                continue

            outgoing = self._recent_outbound_texts.get(payload['external_user_id'], '')
            if outgoing and outgoing == payload['content'].strip():
                continue

            if not self._remember_message(payload):
                continue

            if self._message_callback is not None:
                await self._message_callback(payload)

    async def _select_latest_conversation(self) -> dict[str, str] | None:
        for selector in self.selectors['conversation_item']:
            locator = self._page.locator(selector)
            count = await locator.count()
            for index in range(count):
                item = locator.nth(index)
                if not await item.is_visible():
                    continue

                await item.click()
                title = (await item.inner_text()).strip()
                if not title:
                    continue

                conversation_id = (
                    await item.get_attribute('data-conversation-id')
                    or await item.get_attribute('data-id')
                    or title
                )
                return {
                    'conversation_id': conversation_id,
                    'external_user_id': title,
                    'sender_name': title,
                }

        return None

    async def _extract_active_messages(self, conversation_payload: dict[str, str]) -> list[dict[str, Any]]:
        extraction_script = """
        (messageSelectors, textSelectors) => {
          const findText = (root) => {
            for (const selector of textSelectors) {
              const node = root.querySelector(selector);
              const text = (node?.innerText || node?.textContent || '').trim();
              if (text) return text;
            }
            return (root.innerText || root.textContent || '').trim();
          };

          const rows = [];
          for (const selector of messageSelectors) {
            const matched = Array.from(document.querySelectorAll(selector));
            if (matched.length) {
              rows.push(...matched);
              break;
            }
          }

          return rows.map((row, index) => {
            const text = findText(row);
            const className = typeof row.className === 'string' ? row.className : '';
            const messageId = row.getAttribute('data-message-id') || row.getAttribute('data-id') || `${index}:${text}`;
            const lowered = className.toLowerCase();
            const direction = lowered.includes('right') || lowered.includes('self') || lowered.includes('send') || lowered.includes('outgoing')
              ? 'assistant'
              : 'customer';
            return {
              message_id: messageId,
              content: text,
              direction,
            };
          }).filter(item => item.content);
        }
        """
        rows = await self._page.evaluate(
            extraction_script,
            self.selectors['message_row'],
            self.selectors['message_text'],
        )

        payloads = []
        for index, row in enumerate(rows):
            if row.get('direction') == 'assistant':
                continue

            content = row.get('content', '').strip()
            if not content:
                continue

            raw_message_id = str(row.get('message_id') or '')
            if not raw_message_id:
                raw_message_id = f'{conversation_payload["conversation_id"]}:{index}:{hash(content)}'

            payloads.append(
                {
                    'account_id': self.account_label,
                    'external_user_id': conversation_payload['external_user_id'],
                    'conversation_id': conversation_payload['conversation_id'],
                    'message_id': raw_message_id,
                    'sender_name': conversation_payload['sender_name'],
                    'content': content,
                    'timestamp': int(time.time()),
                }
            )

        return payloads

    async def _drain_send_queue(self) -> None:
        while not self._send_queue.empty():
            payload = await self._send_queue.get()
            await self._send_text_now(payload)

    async def _send_text_now(self, payload: dict[str, str]) -> None:
        await self._open_conversation(payload['external_user_id'])
        input_locator = await self._find_first_visible_locator(self.selectors['input'])
        if input_locator is None:
            raise RuntimeError('未找到企微客服输入框')

        await input_locator.click()
        try:
            await input_locator.fill(payload['text'])
        except Exception:
            await self._page.evaluate(
                """
                ([selector, text]) => {
                  const el = document.querySelector(selector);
                  if (!el) return false;
                  if (el.tagName === 'TEXTAREA') {
                    el.value = text;
                  } else {
                    el.innerText = text;
                  }
                  el.dispatchEvent(new InputEvent('input', { bubbles: true }));
                  return true;
                }
                """,
                [self.selectors['input'][0], payload['text']],
            )

        button = await self._find_first_visible_locator(self.selectors['send_button'])
        if button is not None:
            await button.click()
        else:
            await input_locator.press('Enter')

    async def _open_conversation(self, external_user_id: str) -> None:
        for selector in self.selectors['conversation_item']:
            locator = self._page.locator(selector)
            count = await locator.count()
            for index in range(count):
                item = locator.nth(index)
                if not await item.is_visible():
                    continue

                title = (await item.inner_text()).strip()
                if external_user_id in title:
                    await item.click()
                    conversation_id = (
                        await item.get_attribute('data-conversation-id')
                        or await item.get_attribute('data-id')
                        or title
                    )
                    self._conversation_keys[external_user_id] = conversation_id
                    return

    async def _find_first_visible_locator(self, selectors: list[str]):
        for selector in selectors:
            locator = self._page.locator(selector)
            count = await locator.count()
            for index in range(count):
                candidate = locator.nth(index)
                try:
                    if await candidate.is_visible():
                        return candidate
                except Exception:
                    continue
        return None

    async def _log(self, level: str, message: str) -> None:
        if self.logger is None:
            print(message)
            return

        log_func = getattr(self.logger, level, None)
        if log_func is None:
            print(message)
            return

        result = log_func(message)
        if asyncio.iscoroutine(result):
            await result

    @staticmethod
    def from_config(config: dict[str, Any], logger=None) -> 'WecomWebPageClient':
        selectors_raw = config.get('selectors')
        selectors = None
        if isinstance(selectors_raw, str) and selectors_raw.strip():
            try:
                selectors = json.loads(selectors_raw)
            except json.JSONDecodeError:
                selectors = None
        elif isinstance(selectors_raw, dict):
            selectors = selectors_raw

        return WecomWebPageClient(
            account_label=config.get('account_label', '企微客服托管号'),
            workbench_url=config.get('workbench_url', 'https://work.weixin.qq.com/kf/'),
            storage_state_dir=config.get('storage_state_dir', './data/wecomweb'),
            logger=logger,
            poll_interval_seconds=int(config.get('poll_interval_seconds', 2)),
            headless=WecomWebPageClient._as_bool(config.get('headless', True), True),
            print_login_qr=WecomWebPageClient._as_bool(config.get('print_login_qr', True), True),
            browser_executable_path=config.get('browser_executable_path'),
            selectors=selectors,
        )
