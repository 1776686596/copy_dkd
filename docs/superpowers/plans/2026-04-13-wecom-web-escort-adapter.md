# WeCom Web Escort Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改动现有客服台和知识库能力展示的前提下，新增一个基于企业微信客服网页自动化的非官方托管适配器，实现文本消息的 AI 托管、转人工和客服台可见。

**Architecture:** 新增一个 `wecomweb` 平台适配器，对外暴露与 `wecomcs` 相同的客服上下文语义；适配器内部通过 Playwright 持久化会话托管企业微信客服网页，轮询新消息并把回复写回网页输入框。`service_desk` 仅做最小兼容，放宽为“任何能提供客服上下文的适配器”都可进入客服台流程。

**Tech Stack:** Python 3.12、Quart、SQLAlchemy、LangBot 平台适配器体系、Pytest、Playwright for Python

---

## File Structure

- Create: `src/langbot/pkg/platform/sources/wecomweb.py`
  负责新增非官方企微网页托管适配器，桥接 LangBot 事件与网页自动化客户端。
- Create: `src/langbot/pkg/platform/sources/wecomweb.yaml`
  负责后台 bot 配置项声明，让前端继续以普通平台适配器的方式展示配置。
- Create: `src/langbot/libs/wecom_web_page_api/__init__.py`
  暴露网页托管客户端包。
- Create: `src/langbot/libs/wecom_web_page_api/client.py`
  负责 Playwright 浏览器启动、登录态持久化、消息轮询、发送队列、去重与重连。
- Create: `tests/unit_tests/platform/test_wecomweb_adapter.py`
  覆盖新适配器的上下文提取、事件转换、发送出口与桥接调用。
- Modify: `src/langbot/pkg/api/http/service/service_desk.py`
  放宽客服台准入条件，支持 `wecomweb` 这类具备客服上下文的适配器。
- Modify: `src/langbot/pkg/platform/botmgr.py`
  保证新适配器进入现有好友消息处理、客服台分流和回复链路。
- Modify: `pyproject.toml`
  增加 `playwright` 依赖，保证运行环境可安装。
- Modify: `tests/unit_tests/service_desk/test_runtime_flow.py`
  新增 `wecomweb` 走客服台 AI 托管/转人工流的回归测试。
- Modify: `tests/unit_tests/service_desk/test_service_desk_service.py`
  新增客服台对“非 `wecomcs` 但有客服上下文适配器”的兼容测试。

### Task 1: 放宽客服台入口，先用测试锁定兼容语义

**Files:**
- Modify: `src/langbot/pkg/api/http/service/service_desk.py`
- Modify: `tests/unit_tests/service_desk/test_service_desk_service.py`
- Modify: `tests/unit_tests/service_desk/test_runtime_flow.py`

- [ ] **Step 1: 先写客服台兼容的失败测试**

```python
@pytest.mark.asyncio
async def test_handle_incoming_message_accepts_any_adapter_with_service_desk_context():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    service = ServiceDeskService(Mock())
    service._touch_session = AsyncMock(
        return_value={
            'session_id': 'person_customer-1',
            'mode': 'ai_hosted',
            'queue_status': 'ai',
            'manual_claimed_at': None,
            'silent_since': None,
        }
    )
    service.get_bot_config = AsyncMock(return_value={'enabled': True})
    service.list_materials = AsyncMock(return_value=[])

    bot_entity = SimpleNamespace(
        adapter='wecomweb',
        uuid='bot-1',
        use_pipeline_uuid='pipeline-1',
    )
    event = SimpleNamespace(
        message_chain='你好',
        source_platform_object=SimpleNamespace(),
        sender=SimpleNamespace(id='customer-1', nickname='客户A'),
    )
    adapter = Mock()
    adapter.extract_service_desk_context.return_value = {
        'source_entry_id': 'escort-account',
        'external_user_id': 'external-customer-1',
        'last_message_id': 'msg-1',
    }
    adapter.get_launcher_id.return_value = 'escort-account:external-customer-1'

    decision = await service.handle_incoming_message(
        bot_entity=bot_entity,
        event=event,
        adapter=adapter,
        pipeline_uuid='pipeline-1',
    )

    assert decision.action == 'continue_ai'
```

- [ ] **Step 2: 运行单测并确认它因为现有 `wecomcs` 限制而失败**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && pytest tests/unit_tests/service_desk/test_service_desk_service.py -k service_desk_context -v`

Expected: FAIL，原因是 `handle_incoming_message` 里写死 `bot_entity.adapter != 'wecomcs'`。

- [ ] **Step 3: 再写运行流回归测试，锁定 `RuntimeBot` 仍会把 `wecomweb` 消息送进客服台**

```python
@pytest.mark.asyncio
async def test_wecomweb_message_enters_service_desk_flow():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    from langbot.pkg.api.http.service.service_desk import ServiceDeskDecision
    from langbot.pkg.platform.botmgr import RuntimeBot

    bot = object.__new__(RuntimeBot)
    bot.bot_entity = SimpleNamespace(
        adapter='wecomweb',
        uuid='bot-1',
        use_pipeline_uuid='pipeline-1',
    )
    bot.ap = Mock()
    bot.logger = Mock()
    bot.logger.info = AsyncMock()
    bot.ap.service_desk_service = Mock()
    bot.ap.service_desk_service.handle_incoming_message = AsyncMock(
        return_value=ServiceDeskDecision(action='continue_ai')
    )

    event = SimpleNamespace(
        message_chain='我要下载链接',
        sender=SimpleNamespace(id='customer-1', nickname='客户A'),
    )
    adapter = Mock()
    adapter.get_launcher_id.return_value = 'escort-account:external-customer-1'
    adapter.extract_service_desk_context.return_value = {
        'source_entry_id': 'escort-account',
        'external_user_id': 'external-customer-1',
        'last_message_id': 'msg-1',
    }

    handled = await bot._handle_service_desk_before_pipeline(
        event,
        adapter,
        pipeline_uuid='pipeline-1',
    )

    assert handled is False
    bot.ap.service_desk_service.handle_incoming_message.assert_awaited_once()
```

- [ ] **Step 4: 运行运行流测试并确认当前实现尚未覆盖新适配器**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && pytest tests/unit_tests/service_desk/test_runtime_flow.py -k wecomweb -v`

Expected: FAIL，原因是客服台服务拒绝非 `wecomcs` 适配器。

- [ ] **Step 5: 写最小实现，放宽客服台准入条件**

```python
async def handle_incoming_message(
    self,
    *,
    bot_entity,
    event,
    adapter,
    pipeline_uuid: str | None = None,
) -> ServiceDeskDecision:
    if not hasattr(adapter, 'extract_service_desk_context'):
        return ServiceDeskDecision(action='continue_ai')

    source_event = getattr(event, 'source_platform_object', event)
    context = adapter.extract_service_desk_context(source_event)
    if not context.get('source_entry_id') or not context.get('external_user_id'):
        return ServiceDeskDecision(action='continue_ai')
```

- [ ] **Step 6: 重新运行这两个测试并确认转绿**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && pytest tests/unit_tests/service_desk/test_service_desk_service.py tests/unit_tests/service_desk/test_runtime_flow.py -k 'service_desk_context or wecomweb' -v`

Expected: PASS，且现有 `wecomcs` 相关测试不回归。

- [ ] **Step 7: 提交这一小步**

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add src/langbot/pkg/api/http/service/service_desk.py \
        tests/unit_tests/service_desk/test_service_desk_service.py \
        tests/unit_tests/service_desk/test_runtime_flow.py
git commit -m "feat: allow service desk adapters with extracted context"
```

### Task 2: 用测试定义 `wecomweb` 适配器的最小行为

**Files:**
- Create: `tests/unit_tests/platform/test_wecomweb_adapter.py`
- Create: `src/langbot/pkg/platform/sources/wecomweb.py`
- Create: `src/langbot/pkg/platform/sources/wecomweb.yaml`

- [ ] **Step 1: 写适配器失败测试，锁定客服上下文、回复出口和监听注册**

```python
from unittest.mock import AsyncMock, Mock

import pytest


@pytest.mark.asyncio
async def test_wecomweb_adapter_extracts_service_desk_context():
    from langbot.pkg.platform.sources.wecomweb import WecomWebAdapter, WecomWebMessageEvent

    adapter = object.__new__(WecomWebAdapter)
    event = WecomWebMessageEvent(
        account_id='escort-account',
        external_user_id='external-customer-1',
        message_id='msg-1',
        conversation_id='conv-1',
        sender_name='客户A',
        content='你好',
        timestamp=1710000000,
    )

    assert adapter.extract_service_desk_context(event) == {
        'source_entry_id': 'escort-account',
        'external_user_id': 'external-customer-1',
        'last_message_id': 'msg-1',
    }


@pytest.mark.asyncio
async def test_wecomweb_adapter_reply_message_uses_browser_client():
    from types import SimpleNamespace

    from langbot.pkg.platform.sources.wecomweb import WecomWebAdapter
    import langbot_plugin.api.entities.builtin.platform.message as platform_message

    adapter = object.__new__(WecomWebAdapter)
    adapter.bot = Mock()
    adapter.bot.send_text = AsyncMock()

    event = SimpleNamespace(
        source_platform_object=SimpleNamespace(
            account_id='escort-account',
            external_user_id='external-customer-1',
            conversation_id='conv-1',
            message_id='msg-1',
        )
    )
    message = platform_message.MessageChain([platform_message.Plain(text='这里是 AI 回复')])

    await WecomWebAdapter.reply_message(adapter, event, message)

    adapter.bot.send_text.assert_awaited_once_with(
        conversation_id='conv-1',
        external_user_id='external-customer-1',
        text='这里是 AI 回复',
    )
```

- [ ] **Step 2: 运行新增测试，确认因为适配器文件不存在而失败**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && pytest tests/unit_tests/platform/test_wecomweb_adapter.py -v`

Expected: FAIL，报 `ModuleNotFoundError` 或属性不存在。

- [ ] **Step 3: 写最小适配器实现和 yaml 元数据**

```python
@dataclass
class WecomWebMessageEvent:
    account_id: str
    external_user_id: str
    message_id: str
    conversation_id: str
    sender_name: str
    content: str
    timestamp: int


class WecomWebAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    def extract_service_desk_context(self, event: WecomWebMessageEvent) -> dict[str, str]:
        return {
            'source_entry_id': event.account_id,
            'external_user_id': event.external_user_id,
            'last_message_id': event.message_id,
        }

    async def reply_message(self, message_source, message, quote_origin: bool = False):
        event = message_source.source_platform_object
        text = ''.join(component.text for component in message if isinstance(component, platform_message.Plain))
        await self.bot.send_text(
            conversation_id=event.conversation_id,
            external_user_id=event.external_user_id,
            text=text,
        )
```

```yaml
apiVersion: v1
kind: MessagePlatformAdapter
metadata:
  name: wecomweb
  label:
    zh_Hans: 企业微信客服
  description:
    zh_Hans: 企业微信客服网页托管模式（演示用）
spec:
  categories:
    - china
  config:
    - name: account_label
      type: string
      required: true
      default: "企微客服托管号"
    - name: workbench_url
      type: string
      required: true
      default: "https://work.weixin.qq.com/kf/"
    - name: storage_state_dir
      type: string
      required: true
      default: "./data/wecomweb"
```

- [ ] **Step 4: 运行测试，确认最小适配器行为通过**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && pytest tests/unit_tests/platform/test_wecomweb_adapter.py -v`

Expected: PASS。

- [ ] **Step 5: 提交这一小步**

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add src/langbot/pkg/platform/sources/wecomweb.py \
        src/langbot/pkg/platform/sources/wecomweb.yaml \
        tests/unit_tests/platform/test_wecomweb_adapter.py
git commit -m "feat: add wecom web escort adapter skeleton"
```

### Task 3: 引入网页托管客户端并用测试锁定收发桥接

**Files:**
- Create: `src/langbot/libs/wecom_web_page_api/__init__.py`
- Create: `src/langbot/libs/wecom_web_page_api/client.py`
- Modify: `src/langbot/pkg/platform/sources/wecomweb.py`
- Modify: `pyproject.toml`
- Modify: `tests/unit_tests/platform/test_wecomweb_adapter.py`

- [ ] **Step 1: 先写客户端桥接失败测试，锁定去重和发送队列**

```python
@pytest.mark.asyncio
async def test_client_deduplicates_seen_messages():
    from langbot.libs.wecom_web_page_api.client import WecomWebPageClient

    client = WecomWebPageClient(
        account_label='escort-account',
        workbench_url='https://work.weixin.qq.com/kf/',
        storage_state_dir='./tmp/wecomweb',
    )

    payload = {
        'conversation_id': 'conv-1',
        'external_user_id': 'external-customer-1',
        'message_id': 'msg-1',
        'sender_name': '客户A',
        'content': '你好',
        'timestamp': 1710000000,
    }

    assert client._remember_message(payload) is True
    assert client._remember_message(payload) is False
```

```python
@pytest.mark.asyncio
async def test_adapter_forwards_browser_events_to_registered_listener():
    from langbot.pkg.platform.sources.wecomweb import WecomWebAdapter
    import langbot_plugin.api.entities.builtin.platform.events as platform_events

    adapter = object.__new__(WecomWebAdapter)
    adapter.listeners = {}
    adapter.bot = Mock()
    adapter.bot.set_message_callback = Mock()

    received = []

    async def on_friend_message(event, runtime_adapter):
        received.append((event.sender.id, str(event.message_chain), runtime_adapter))

    WecomWebAdapter.register_listener(adapter, platform_events.FriendMessage, on_friend_message)

    callback = adapter.bot.set_message_callback.call_args.args[0]
    await callback(
        {
            'account_id': 'escort-account',
            'external_user_id': 'external-customer-1',
            'conversation_id': 'conv-1',
            'message_id': 'msg-1',
            'sender_name': '客户A',
            'content': '你好',
            'timestamp': 1710000000,
        }
    )

    assert received[0][0] == 'external-customer-1'
```

- [ ] **Step 2: 运行测试，确认桥接客户端和回调注册尚未实现**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && pytest tests/unit_tests/platform/test_wecomweb_adapter.py -k 'deduplicates or forwards_browser' -v`

Expected: FAIL。

- [ ] **Step 3: 写最小客户端实现，并把 Playwright 作为运行时依赖声明进去**

```python
class WecomWebPageClient:
    def __init__(self, *, account_label: str, workbench_url: str, storage_state_dir: str):
        self.account_label = account_label
        self.workbench_url = workbench_url
        self.storage_state_dir = storage_state_dir
        self._seen_message_keys: set[str] = set()
        self._message_callback = None

    def set_message_callback(self, callback):
        self._message_callback = callback

    def _remember_message(self, payload: dict) -> bool:
        message_key = f"{payload['conversation_id']}:{payload['message_id']}"
        if message_key in self._seen_message_keys:
            return False
        self._seen_message_keys.add(message_key)
        return True
```

```toml
dependencies = [
    # ...
    "playwright>=1.52.0",
]
```

- [ ] **Step 4: 在 `wecomweb.py` 里接上客户端回调注册**

```python
def register_listener(self, event_type, callback):
    self.listeners[event_type] = callback
    if event_type == platform_events.FriendMessage:
        self.bot.set_message_callback(self._handle_browser_message)


async def _handle_browser_message(self, payload: dict):
    event = WecomWebMessageEvent(**payload)
    yiri_event = await self.event_converter.target2yiri(event)
    await self.listeners[platform_events.FriendMessage](yiri_event, self)
```

- [ ] **Step 5: 运行测试，确认桥接层最小行为通过**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && pytest tests/unit_tests/platform/test_wecomweb_adapter.py -v`

Expected: PASS。

- [ ] **Step 6: 提交这一小步**

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add pyproject.toml \
        src/langbot/libs/wecom_web_page_api/__init__.py \
        src/langbot/libs/wecom_web_page_api/client.py \
        src/langbot/pkg/platform/sources/wecomweb.py \
        tests/unit_tests/platform/test_wecomweb_adapter.py
git commit -m "feat: add wecom web bridge client"
```

### Task 4: 实现网页登录托管循环，打通文本收发与登录态持久化

**Files:**
- Modify: `src/langbot/libs/wecom_web_page_api/client.py`
- Modify: `src/langbot/pkg/platform/sources/wecomweb.py`
- Modify: `tests/unit_tests/platform/test_wecomweb_adapter.py`

- [ ] **Step 1: 写失败测试，锁定客户端启动参数和消息轮询入口**

```python
def test_client_config_preserves_polling_and_headed_flags():
    from langbot.libs.wecom_web_page_api.client import WecomWebPageClient

    client = WecomWebPageClient(
        account_label='escort-account',
        workbench_url='https://work.weixin.qq.com/kf/',
        storage_state_dir='./tmp/wecomweb',
        poll_interval_seconds=2,
        headless=False,
    )

    assert client.poll_interval_seconds == 2
    assert client.headless is False
```

```python
@pytest.mark.asyncio
async def test_wecomweb_adapter_run_async_calls_client_loop():
    from langbot.pkg.platform.sources.wecomweb import WecomWebAdapter

    adapter = object.__new__(WecomWebAdapter)
    adapter.bot = Mock()
    adapter.bot.run_forever = AsyncMock()

    await WecomWebAdapter.run_async(adapter)

    adapter.bot.run_forever.assert_awaited_once()
```

- [ ] **Step 2: 运行测试，确认启动配置和事件循环还没接上**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && pytest tests/unit_tests/platform/test_wecomweb_adapter.py -k 'polling_and_headed or run_async_calls_client_loop' -v`

Expected: FAIL。

- [ ] **Step 3: 最小实现 Playwright 生命周期封装**

```python
class WecomWebPageClient:
    def __init__(
        self,
        *,
        account_label: str,
        workbench_url: str,
        storage_state_dir: str,
        poll_interval_seconds: int = 2,
        headless: bool = False,
    ):
        self.account_label = account_label
        self.workbench_url = workbench_url
        self.storage_state_dir = storage_state_dir
        self.poll_interval_seconds = poll_interval_seconds
        self.headless = headless

    async def run_forever(self) -> None:
        while True:
            await self._ensure_browser()
            await self._poll_once()
            await asyncio.sleep(self.poll_interval_seconds)
```

```python
async def run_async(self):
    await self.bot.run_forever()
```

- [ ] **Step 4: 补上真实网页登录所需的内部骨架，但先不写复杂 DOM 细节**

```python
async def _ensure_browser(self):
    if self._page is not None:
        return
    playwright = await async_playwright().start()
    self._playwright = playwright
    self._browser_context = await playwright.chromium.launch_persistent_context(
        user_data_dir=self.storage_state_dir,
        headless=self.headless,
    )
    self._page = self._browser_context.pages[0] if self._browser_context.pages else await self._browser_context.new_page()
    await self._page.goto(self.workbench_url)
```

- [ ] **Step 5: 运行测试，确认本轮仍然全绿**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && pytest tests/unit_tests/platform/test_wecomweb_adapter.py -v`

Expected: PASS。

- [ ] **Step 6: 提交这一小步**

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add src/langbot/libs/wecom_web_page_api/client.py \
        src/langbot/pkg/platform/sources/wecomweb.py \
        tests/unit_tests/platform/test_wecomweb_adapter.py
git commit -m "feat: add wecom web browser runtime loop"
```

### Task 5: 补配置说明与最终回归验证

**Files:**
- Modify: `src/langbot/pkg/platform/sources/wecomweb.yaml`
- Modify: `tests/unit_tests/platform/test_wecomweb_adapter.py`
- Modify: `tests/unit_tests/service_desk/test_runtime_flow.py`

- [ ] **Step 1: 写失败测试，锁定新适配器至少能提供演示期需要的配置**

```python
def test_wecomweb_yaml_declares_demo_runtime_fields():
    import yaml
    from pathlib import Path

    spec = yaml.safe_load(
        Path('src/langbot/pkg/platform/sources/wecomweb.yaml').read_text(encoding='utf-8')
    )

    fields = {item['name'] for item in spec['spec']['config']}

    assert {
        'account_label',
        'workbench_url',
        'storage_state_dir',
        'poll_interval_seconds',
        'headless',
    }.issubset(fields)
```

- [ ] **Step 2: 运行该测试，确认配置元数据未补全时失败**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && pytest tests/unit_tests/platform/test_wecomweb_adapter.py -k yaml_declares_demo_runtime_fields -v`

Expected: FAIL。

- [ ] **Step 3: 补全 yaml 配置与说明**

```yaml
    - name: poll_interval_seconds
      label:
        zh_Hans: 监听间隔（秒）
      type: integer
      required: false
      default: 2
    - name: headless
      label:
        zh_Hans: 无头模式
      type: boolean
      required: false
      default: false
```

- [ ] **Step 4: 运行聚焦单测和客服台回归**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && pytest tests/unit_tests/platform/test_wecomweb_adapter.py tests/unit_tests/service_desk/test_service_desk_service.py tests/unit_tests/service_desk/test_runtime_flow.py -v`

Expected: PASS。

- [ ] **Step 5: 运行最小静态检查**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && python -m compileall src/langbot/pkg/platform/sources/wecomweb.py src/langbot/libs/wecom_web_page_api/client.py`

Expected: exit 0，无语法错误。

- [ ] **Step 6: 提交这一小步**

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add src/langbot/pkg/platform/sources/wecomweb.yaml \
        tests/unit_tests/platform/test_wecomweb_adapter.py \
        tests/unit_tests/service_desk/test_service_desk_service.py \
        tests/unit_tests/service_desk/test_runtime_flow.py
git commit -m "feat: wire wecom web escort adapter for demo flow"
```

## Self-Review

- Spec coverage:
  已覆盖非官方网页托管适配器、客服台兼容、AI 托管/转人工可见、文本收发、前端维持原有接入展示、最小验证命令。
- Placeholder scan:
  已用真实文件路径、命令和最小代码骨架表达，没有遗留占位项。
- Type consistency:
  计划统一使用 `WecomWebAdapter`、`WecomWebPageClient`、`WecomWebMessageEvent` 三个核心命名；客服上下文字段统一为 `source_entry_id`、`external_user_id`、`last_message_id`。
