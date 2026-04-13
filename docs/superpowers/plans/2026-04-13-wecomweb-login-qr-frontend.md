# Wecomweb Login QR Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `wecomweb` Bot 在前端配置页显示扫码登录二维码，并在扫码成功后自动消失，页面恢复成原本配置页样子。

**Architecture:** 复用现有 `/api/v1/platform/bots/<uuid>` Bot 详情接口，在 `adapter_runtime_values` 中为 `wecomweb` 暴露登录态与二维码数据。`WecomWebPageClient` 负责缓存二维码与登录态，前端 `BotForm` 只在编辑态的 `wecomweb` Bot 上轮询并临时渲染二维码卡片。

**Tech Stack:** Python 3.11+/Quart、Playwright for Python、React 19、TypeScript、Vite、Pytest

---

## File Structure

- Modify: `src/langbot/libs/wecom_web_page_api/client.py`
  增加二维码缓存、登录态读取与清理逻辑，保留终端输出兜底。
- Modify: `src/langbot/pkg/api/http/service/bot.py`
  在 `get_runtime_bot_info()` 中为 `wecomweb` 输出登录态运行信息。
- Create: `tests/unit_tests/platform/test_wecomweb_login_runtime.py`
  覆盖二维码缓存、登录成功清理和 Bot 运行信息输出。
- Modify: `web/src/app/home/bots/components/bot-form/BotForm.tsx`
  为 `wecomweb` 编辑态 Bot 增加登录态轮询与临时二维码卡片。
- Modify: `web/src/app/infra/entities/api/index.ts`
  补充 `adapter_runtime_values` 的前端类型。

---

### Task 1: 先用测试锁定 wecomweb 二维码缓存与运行态输出

**Files:**
- Create: `tests/unit_tests/platform/test_wecomweb_login_runtime.py`
- Modify: `src/langbot/libs/wecom_web_page_api/client.py`
- Modify: `src/langbot/pkg/api/http/service/bot.py`

- [ ] **Step 1: 写二维码缓存的失败测试**

```python
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest


@pytest.mark.asyncio
async def test_client_caches_login_qr_snapshot():
    from langbot.libs.wecom_web_page_api.client import WecomWebPageClient

    client = WecomWebPageClient(
        account_label='escort-account',
        workbench_url='https://work.weixin.qq.com/kf/',
        storage_state_dir='./tmp/wecomweb',
        print_login_qr=False,
    )
    qr_locator = Mock()
    qr_locator.screenshot = AsyncMock(return_value=b'fake-qrcode')
    client._find_first_visible_locator = AsyncMock(return_value=qr_locator)

    await client._show_login_qr()

    state = client.get_login_runtime_state()
    assert state['login_required'] is True
    assert state['login_qr_image_base64']
    assert state['login_qr_updated_at'] is not None
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && uv run python -m pytest tests/unit_tests/platform/test_wecomweb_login_runtime.py::test_client_caches_login_qr_snapshot -v`

Expected: FAIL，原因是 `WecomWebPageClient` 还没有 `get_login_runtime_state()` 和二维码缓存字段。

- [ ] **Step 3: 写运行态输出的失败测试**

```python
@pytest.mark.asyncio
async def test_get_runtime_bot_info_exposes_wecomweb_login_state():
    from langbot.pkg.api.http.service.bot import BotService

    service = BotService(SimpleNamespace())
    service.get_bot = AsyncMock(
        return_value={
            'uuid': 'bot-1',
            'adapter': 'wecomweb',
            'adapter_config': {},
        }
    )
    runtime_bot = SimpleNamespace(
        adapter=SimpleNamespace(
            bot_account_id='escort-account',
            bot=SimpleNamespace(
                get_login_runtime_state=Mock(
                    return_value={
                        'login_required': True,
                        'login_qr_image_base64': 'ZmFrZQ==',
                        'login_qr_updated_at': 1710000000,
                    }
                )
            ),
        )
    )
    service.ap.platform_mgr = SimpleNamespace(get_bot_by_uuid=AsyncMock(return_value=runtime_bot))
    service.ap.instance_config = SimpleNamespace(data={'api': {}})

    result = await service.get_runtime_bot_info('bot-1')

    assert result['adapter_runtime_values']['login_required'] is True
    assert result['adapter_runtime_values']['login_qr_image_base64'] == 'ZmFrZQ=='
```

- [ ] **Step 4: 运行测试并确认失败**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && uv run python -m pytest tests/unit_tests/platform/test_wecomweb_login_runtime.py::test_get_runtime_bot_info_exposes_wecomweb_login_state -v`

Expected: FAIL，原因是 `get_runtime_bot_info()` 还没有输出 `wecomweb` 登录字段。

- [ ] **Step 5: 写最小实现，让客户端缓存二维码并暴露读取方法**

```python
import base64


class WecomWebPageClient:
    def __init__(...):
        ...
        self._login_required = False
        self._login_qr_image_base64: str | None = None
        self._login_qr_updated_at: int | None = None

    def get_login_runtime_state(self) -> dict[str, Any]:
        return {
            'login_required': self._login_required,
            'login_qr_image_base64': self._login_qr_image_base64,
            'login_qr_updated_at': self._login_qr_updated_at,
        }

    def _clear_login_runtime_state(self) -> None:
        self._login_required = False
        self._login_qr_image_base64 = None
        self._login_qr_updated_at = None

    async def _show_login_qr(self) -> None:
        ...
        self._login_required = True
        self._login_qr_image_base64 = base64.b64encode(qr_png).decode('ascii')
        self._login_qr_updated_at = int(time.time())
```

- [ ] **Step 6: 在登录成功路径上清空二维码缓存**

```python
    async def run_forever(self) -> None:
        self._stop_event.clear()
        while not self._stop_event.is_set():
            try:
                await self._ensure_browser()
                if await self._is_login_required():
                    await self._show_login_qr()
                    await asyncio.sleep(self.poll_interval_seconds)
                    continue

                self._clear_login_runtime_state()
                await self._drain_send_queue()
                await self._poll_once()
```

- [ ] **Step 7: 在 Bot 运行信息里输出 wecomweb 登录态**

```python
    async def get_runtime_bot_info(self, bot_uuid: str, include_secret: bool = True) -> dict:
        ...
        runtime_bot = await self.ap.platform_mgr.get_bot_by_uuid(bot_uuid)
        if runtime_bot is not None:
            adapter_runtime_values['bot_account_id'] = runtime_bot.adapter.bot_account_id
            if persistence_bot['adapter'] == 'wecomweb':
                get_state = getattr(getattr(runtime_bot.adapter, 'bot', None), 'get_login_runtime_state', None)
                if callable(get_state):
                    adapter_runtime_values.update(get_state())
        ...
        adapter_runtime_values.setdefault('login_required', False)
        adapter_runtime_values.setdefault('login_qr_image_base64', None)
        adapter_runtime_values.setdefault('login_qr_updated_at', None)
```

- [ ] **Step 8: 运行新增测试并确认通过**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && uv run python -m pytest tests/unit_tests/platform/test_wecomweb_login_runtime.py -v`

Expected: PASS

- [ ] **Step 9: 回归现有 wecomweb 与客服台测试**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && uv run python -m pytest tests/unit_tests/platform/test_wecomweb_adapter.py tests/unit_tests/service_desk -v`

Expected: PASS，无客服台回归

- [ ] **Step 10: 提交**

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add tests/unit_tests/platform/test_wecomweb_login_runtime.py \
        src/langbot/libs/wecom_web_page_api/client.py \
        src/langbot/pkg/api/http/service/bot.py
git commit -m "feat: expose wecomweb login runtime state"
```

---

### Task 2: 用前端最小改动把二维码挂到 Bot 配置页里

**Files:**
- Modify: `web/src/app/home/bots/components/bot-form/BotForm.tsx`
- Modify: `web/src/app/infra/entities/api/index.ts`

- [ ] **Step 1: 先写清楚前端要读取的运行态类型**

```ts
export interface BotAdapterRuntimeValues {
  bot_account_id?: string | null;
  webhook_url?: string | null;
  webhook_full_url?: string | null;
  extra_webhook_full_url?: string | null;
  login_required?: boolean;
  login_qr_image_base64?: string | null;
  login_qr_updated_at?: number | null;
}

export interface Bot {
  ...
  adapter_runtime_values?: BotAdapterRuntimeValues;
}
```

- [ ] **Step 2: 在 BotForm 中增加二维码状态与轮询控制变量**

```tsx
  const [loginRequired, setLoginRequired] = useState(false);
  const [loginQrImageBase64, setLoginQrImageBase64] = useState<string | null>(null);
  const loginPollingRef = useRef<number | null>(null);
```

- [ ] **Step 3: 新增单次拉取运行态的函数**

```tsx
  async function refreshWecomWebLoginState(botId: string) {
    const res = await httpClient.getBot(botId);
    const runtimeValues = (res.bot.adapter_runtime_values ?? {}) as BotAdapterRuntimeValues;
    setLoginRequired(runtimeValues.login_required === true);
    setLoginQrImageBase64(runtimeValues.login_qr_image_base64 ?? null);
  }
```

- [ ] **Step 4: 只在 wecomweb 编辑态启动轮询**

```tsx
  useEffect(() => {
    if (!initBotId || currentAdapter !== 'wecomweb') {
      setLoginRequired(false);
      setLoginQrImageBase64(null);
      if (loginPollingRef.current) {
        window.clearInterval(loginPollingRef.current);
        loginPollingRef.current = null;
      }
      return;
    }

    refreshWecomWebLoginState(initBotId).catch(() => {});
    loginPollingRef.current = window.setInterval(() => {
      refreshWecomWebLoginState(initBotId).catch(() => {});
    }, 3000);

    return () => {
      if (loginPollingRef.current) {
        window.clearInterval(loginPollingRef.current);
        loginPollingRef.current = null;
      }
    };
  }, [initBotId, currentAdapter]);
```

- [ ] **Step 5: 在适配器配置卡片中插入临时二维码区**

```tsx
            {currentAdapter === 'wecomweb' && loginRequired && (
              <Card className="border-dashed">
                <CardHeader>
                  <CardTitle>扫码登录企业微信客服</CardTitle>
                  <CardDescription>
                    仅首次登录或登录失效时显示，扫码成功后会自动消失。
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {loginQrImageBase64 ? (
                    <img
                      src={`data:image/png;base64,${loginQrImageBase64}`}
                      alt="企业微信登录二维码"
                      className="mx-auto h-56 w-56 rounded-lg border bg-white p-3"
                    />
                  ) : (
                    <div className="text-sm text-muted-foreground">
                      正在生成登录二维码
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
```

- [ ] **Step 6: 确认“扫码成功后恢复原样”的实现是靠不渲染，而不是渲染成功态**

```tsx
  if (runtimeValues.login_required !== true) {
    setLoginRequired(false);
    setLoginQrImageBase64(null);
  }
```

- [ ] **Step 7: 运行前端构建验证**

Run: `cd /home/daisheng/code/copy_dkd/LangBot/web && npm run build`

Expected: PASS

- [ ] **Step 8: 提交**

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add web/src/app/home/bots/components/bot-form/BotForm.tsx \
        web/src/app/infra/entities/api/index.ts
git commit -m "feat: show wecomweb login qr in bot form"
```

---

### Task 3: 做端到端冒烟与发布前回归

**Files:**
- Modify: `src/langbot/libs/wecom_web_page_api/client.py`
- Modify: `src/langbot/pkg/api/http/service/bot.py`
- Modify: `web/src/app/home/bots/components/bot-form/BotForm.tsx`
- Modify: `web/src/app/infra/entities/api/index.ts`
- Create: `tests/unit_tests/platform/test_wecomweb_login_runtime.py`

- [ ] **Step 1: 跑后端聚焦测试**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && uv run python -m pytest tests/unit_tests/platform/test_wecomweb_login_runtime.py tests/unit_tests/platform/test_wecomweb_adapter.py tests/unit_tests/service_desk -v`

Expected: PASS

- [ ] **Step 2: 跑语法检查**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && python3 -m compileall src/langbot/libs/wecom_web_page_api/client.py src/langbot/pkg/api/http/service/bot.py`

Expected: PASS

- [ ] **Step 3: 跑前端构建**

Run: `cd /home/daisheng/code/copy_dkd/LangBot/web && npm run build`

Expected: PASS

- [ ] **Step 4: 做手工冒烟**

```text
1. 启动服务并打开一个 wecomweb Bot 配置页
2. 确认未登录时二维码显示在适配器配置区
3. 扫码登录一次
4. 确认二维码区域自动消失
5. 刷新页面，确认已登录状态下不再显示二维码
6. 让登录态失效或切换到新 Bot，确认二维码会重新出现
```

- [ ] **Step 5: 最终提交**

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add tests/unit_tests/platform/test_wecomweb_login_runtime.py \
        src/langbot/libs/wecom_web_page_api/client.py \
        src/langbot/pkg/api/http/service/bot.py \
        web/src/app/home/bots/components/bot-form/BotForm.tsx \
        web/src/app/infra/entities/api/index.ts
git commit -m "feat: add wecomweb frontend login qr flow"
git push copy_dkd push-copy-dkd-master
```

---

## Self-Review

### Spec coverage

- 前端二维码显示位置：Task 2 覆盖
- 扫码成功后自动消失：Task 1 + Task 2 覆盖
- 仅 `wecomweb` 生效：Task 1 + Task 2 覆盖
- 保留终端二维码兜底：Task 1 明确保留
- 登录失效后重新出现：Task 1 + Task 3 手工冒烟覆盖

### Placeholder scan

- 无 `TODO`、`TBD`、`后续补` 之类占位项

### Type consistency

- 后端运行态字段统一为：
  - `login_required`
  - `login_qr_image_base64`
  - `login_qr_updated_at`
- 前端类型与接口输出字段保持一致
