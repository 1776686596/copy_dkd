# Demo Login Key And Login Brand Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the existing `Space` login, add configurable demo-key login into the current primary account, and rebrand the login page to `传奇bot` while removing the policy footer.

**Architecture:** Reuse the existing JWT session model and backend `demo_login_key` contract instead of introducing a new account type. On the frontend, extract the login-mode decision into a small pure helper so the coexistence rule (`Space` + key) is testable, then update the login page copy and layout without touching post-login flows.

**Tech Stack:** Python, Quart, React, TypeScript, React Hook Form, node:test, pytest

---

## File Map

- `tests/unit_tests/http/test_user_demo_login.py`
  - 锁定 demo 密匙后端契约：服务层签发 JWT、`/auth-key` 路由、`account-info` 特性开关。
- `src/langbot/pkg/api/http/service/user.py`
  - 校验 `system.demo_login_key`，并为当前第一个用户签发 JWT。
- `src/langbot/pkg/api/http/controller/groups/user.py`
  - 暴露 `/api/v1/user/auth-key`，并在 `/api/v1/user/account-info` 返回 `demo_login_key_enabled`。
- `web/src/app/login/loginPageMode.ts`
  - 纯函数，根据 `account_type`、`has_password`、`demo_login_key_enabled` 计算登录页应展示的入口。
- `web/src/app/login/loginPageMode.test.ts`
  - 用 `node:test` 覆盖 `Space`、密码、密匙三种入口的组合规则。
- `web/src/app/login/page.tsx`
  - 复用登录模式 helper，保留 `Space` 登录、增加密匙登录、改品牌文案、删底部政策区块。
- `web/src/app/infra/http/BackendClient.ts`
  - 保证 `authUserByKey()` 与 `getAccountInfo()` 类型声明和后端契约一致。
- `web/src/i18n/locales/zh-Hans.ts`
  - 登录页中文品牌文案改为 `传奇bot`，删除只用于政策区块的键。
- `web/src/i18n/locales/en-US.ts`
  - 同步英文品牌文案，避免中英文切换时品牌回退成 `LangBot`。

### Task 1: 固化后端 Demo 密匙契约

**Files:**
- Modify: `tests/unit_tests/http/test_user_demo_login.py`
- Modify: `src/langbot/pkg/api/http/service/user.py`
- Modify: `src/langbot/pkg/api/http/controller/groups/user.py`

- [ ] **Step 1: 写出失败的后端契约测试**

```python
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import quart

from langbot.pkg.api.http.controller.groups.user import UserRouterGroup
from langbot.pkg.api.http.service.user import UserService


@pytest.mark.asyncio
async def test_authenticate_with_demo_key_returns_jwt_for_first_user():
    ap = SimpleNamespace(instance_config=SimpleNamespace(data={'system': {'demo_login_key': 'demo-key'}}))
    service = UserService(ap)
    service.get_first_user = AsyncMock(return_value=SimpleNamespace(user='demo@example.com'))
    service.generate_jwt_token = AsyncMock(return_value='jwt-token')

    token = await service.authenticate_with_demo_key('demo-key')

    assert token == 'jwt-token'
    service.generate_jwt_token.assert_awaited_once_with('demo@example.com')


@pytest.mark.asyncio
async def test_auth_key_returns_jwt_when_demo_key_matches():
    user_service = SimpleNamespace(
        authenticate_with_demo_key=AsyncMock(return_value='jwt-token'),
        is_initialized=AsyncMock(return_value=True),
        get_first_user=AsyncMock(
            return_value=SimpleNamespace(account_type='space', password='')
        ),
    )
    ap = SimpleNamespace(
        user_service=user_service,
        instance_config=SimpleNamespace(data={'system': {'demo_login_key': 'demo-key'}}),
    )
    quart_app = quart.Quart(__name__)
    router_group = UserRouterGroup(ap, quart_app)
    await router_group.initialize()

    response = await quart_app.test_client().post(
        '/api/v1/user/auth-key',
        json={'key': 'demo-key'},
    )
    payload = await response.get_json()

    assert response.status_code == 200
    assert payload['code'] == 0
    assert payload['data']['token'] == 'jwt-token'
    user_service.authenticate_with_demo_key.assert_awaited_once_with('demo-key')


@pytest.mark.asyncio
async def test_account_info_exposes_demo_login_key_enabled():
    user_service = SimpleNamespace(
        is_initialized=AsyncMock(return_value=True),
        get_first_user=AsyncMock(
            return_value=SimpleNamespace(account_type='space', password='')
        ),
    )
    ap = SimpleNamespace(
        user_service=user_service,
        instance_config=SimpleNamespace(data={'system': {'demo_login_key': 'demo-key'}}),
    )
    quart_app = quart.Quart(__name__)
    router_group = UserRouterGroup(ap, quart_app)
    await router_group.initialize()

    response = await quart_app.test_client().get('/api/v1/user/account-info')
    payload = await response.get_json()

    assert response.status_code == 200
    assert payload['data']['initialized'] is True
    assert payload['data']['account_type'] == 'space'
    assert payload['data']['has_password'] is False
    assert payload['data']['demo_login_key_enabled'] is True
```

- [ ] **Step 2: 运行测试，确认当前分支后端契约是否已经齐备**

Run: `uv run pytest tests/unit_tests/http/test_user_demo_login.py -v`
Expected: PASS；如果 FAIL，说明当前分支里的 demo-key scaffold 与已确认设计不一致，继续执行 Step 3 对齐实现。

- [ ] **Step 3: 仅在测试失败时，把后端实现对齐到最小契约**

```python
# src/langbot/pkg/api/http/service/user.py
import secrets

async def authenticate_with_demo_key(self, login_key: str) -> str:
    configured_key = self.ap.instance_config.data.get('system', {}).get('demo_login_key', '')

    if not configured_key:
        raise ValueError('Demo login key is not configured')

    if not login_key or not secrets.compare_digest(login_key, configured_key):
        raise ValueError('Invalid demo login key')

    user_obj = await self.get_first_user()
    if user_obj is None:
        raise ValueError('System not initialized')

    return await self.generate_jwt_token(user_obj.user)
```

```python
# src/langbot/pkg/api/http/controller/groups/user.py
@self.route('/auth-key', methods=['POST'], auth_type=group.AuthType.NONE)
async def _() -> str:
    json_data = await quart.request.json
    login_key = json_data.get('key', '')

    if not login_key:
        return self.fail(1, 'Login key is required')

    try:
        token = await self.ap.user_service.authenticate_with_demo_key(login_key)
    except ValueError as e:
        return self.fail(1, str(e))

    return self.success(data={'token': token})


@self.route('/account-info', methods=['GET'], auth_type=group.AuthType.NONE)
async def _() -> str:
    if not await self.ap.user_service.is_initialized():
        return self.success(data={'initialized': False})

    user_obj = await self.ap.user_service.get_first_user()
    if user_obj is None:
        return self.success(data={'initialized': False})

    return self.success(
        data={
            'initialized': True,
            'account_type': user_obj.account_type,
            'has_password': bool(user_obj.password and user_obj.password.strip()),
            'demo_login_key_enabled': bool(
                self.ap.instance_config.data.get('system', {}).get('demo_login_key', '').strip()
            ),
        }
    )
```

- [ ] **Step 4: 再跑一次后端测试，确认通过**

Run: `uv run pytest tests/unit_tests/http/test_user_demo_login.py -v`
Expected: PASS，3 个测试全部通过。

- [ ] **Step 5: 提交后端契约改动**

```bash
git add tests/unit_tests/http/test_user_demo_login.py src/langbot/pkg/api/http/service/user.py src/langbot/pkg/api/http/controller/groups/user.py
git commit -m "feat(auth): add demo login key contract"
```

### Task 2: 抽出登录方式判定并补前端测试

**Files:**
- Create: `web/src/app/login/loginPageMode.ts`
- Create: `web/src/app/login/loginPageMode.test.ts`

- [ ] **Step 1: 写失败的前端判定测试**

```ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { resolveLoginPageMode } from './loginPageMode.ts';

test('space 账号配置 demo key 时同时展示 Space 和密匙登录', () => {
  assert.deepEqual(
    resolveLoginPageMode({
      accountType: 'space',
      hasPassword: false,
      demoLoginKeyEnabled: true,
    }),
    {
      showSpaceLogin: true,
      showPasswordLogin: false,
      showDemoKeyLogin: true,
    },
  );
});

test('本地账号未配置 demo key 时只展示密码登录', () => {
  assert.deepEqual(
    resolveLoginPageMode({
      accountType: 'local',
      hasPassword: true,
      demoLoginKeyEnabled: false,
    }),
    {
      showSpaceLogin: false,
      showPasswordLogin: true,
      showDemoKeyLogin: false,
    },
  );
});

test('space 账号已设置密码且未配置 demo key 时展示 Space 和密码登录', () => {
  assert.deepEqual(
    resolveLoginPageMode({
      accountType: 'space',
      hasPassword: true,
      demoLoginKeyEnabled: false,
    }),
    {
      showSpaceLogin: true,
      showPasswordLogin: true,
      showDemoKeyLogin: false,
    },
  );
});
```

- [ ] **Step 2: 运行测试，确认 helper 缺失时报错**

Run: `node --test web/src/app/login/loginPageMode.test.ts`
Expected: FAIL，报错为 `Cannot find module ... loginPageMode.ts` 或 `resolveLoginPageMode is not exported`。

- [ ] **Step 3: 写最小 helper 实现**

```ts
export type LoginPageAccountType = 'local' | 'space' | null;

export interface LoginPageModeInput {
  accountType: LoginPageAccountType;
  hasPassword: boolean;
  demoLoginKeyEnabled: boolean;
}

export interface LoginPageMode {
  showSpaceLogin: boolean;
  showPasswordLogin: boolean;
  showDemoKeyLogin: boolean;
}

export function resolveLoginPageMode({
  accountType,
  hasPassword,
  demoLoginKeyEnabled,
}: LoginPageModeInput): LoginPageMode {
  const showDemoKeyLogin = demoLoginKeyEnabled;
  const showSpaceLogin = accountType === 'space';
  const showPasswordLogin =
    !showDemoKeyLogin &&
    (accountType === 'local' || (accountType === 'space' && hasPassword));

  return {
    showSpaceLogin,
    showPasswordLogin,
    showDemoKeyLogin,
  };
}
```

- [ ] **Step 4: 再跑一次前端测试，确认通过**

Run: `node --test web/src/app/login/loginPageMode.test.ts`
Expected: PASS，3 个测试全部通过。

- [ ] **Step 5: 提交登录模式 helper**

```bash
git add web/src/app/login/loginPageMode.ts web/src/app/login/loginPageMode.test.ts
git commit -m "test(web): cover login page mode resolution"
```

### Task 3: 接入登录页并清理品牌与政策区块

**Files:**
- Modify: `web/src/app/login/page.tsx`
- Modify: `web/src/app/infra/http/BackendClient.ts`
- Modify: `web/src/i18n/locales/zh-Hans.ts`
- Modify: `web/src/i18n/locales/en-US.ts`

- [ ] **Step 1: 把登录页接到 helper，并删除底部政策区块**

```tsx
import { resolveLoginPageMode } from './loginPageMode';

// ...

  const { showPasswordLogin, showDemoKeyLogin, showSpaceLogin } =
    resolveLoginPageMode({
      accountType,
      hasPassword,
      demoLoginKeyEnabled,
    });

// ...

          <img
            src={langbotIcon}
            alt="传奇bot"
            className="w-16 h-16 mb-4 mx-auto"
          />

// 删除整个底部协议 <p>...</p> 区块，不再渲染隐私政策和数据收集政策链接
```

- [ ] **Step 2: 补齐前端 HTTP 类型，保证密匙接口与 `account-info` 返回值一致**

```ts
public authUserByKey(key: string): Promise<ApiRespUserToken> {
  return this.post('/api/v1/user/auth-key', { key });
}

public getAccountInfo(): Promise<{
  initialized: boolean;
  account_type?: 'local' | 'space';
  has_password?: boolean;
  demo_login_key_enabled?: boolean;
}> {
  return this.get('/api/v1/user/account-info');
}
```

- [ ] **Step 3: 改中英文品牌文案为 `传奇bot`，并删除已无引用的政策键**

```ts
// web/src/i18n/locales/zh-Hans.ts
welcome: '欢迎回到 传奇bot 👋',
loginLoadErrorDesc: '无法连接到传奇bot后端服务，请确认服务已启动后重试。',
spaceLoginSuccessDescription: '正在跳转到传奇bot...',
```

```ts
// web/src/i18n/locales/en-US.ts
welcome: 'Welcome back to 传奇bot 👋',
loginLoadErrorDesc:
  'Unable to connect to the 传奇bot backend. Please make sure the service is running and try again.',
spaceLoginSuccessDescription: 'Redirecting to 传奇bot...',
```

- [ ] **Step 4: 跑前端构建，确认类型与打包都通过**

Run: `npm run build`
Expected: PASS，`tsc && vite build` 成功完成，没有 `loginPageMode`、`authUserByKey` 或已删除文案键的报错。

- [ ] **Step 5: 做一次手工验收并提交**

Run: `sed -n '15,30p' src/langbot/templates/config.yaml`
Expected: 看到 `system.demo_login_key: ''` 配置项仍保留，便于演示环境填值。

Run: `git add web/src/app/login/page.tsx web/src/app/infra/http/BackendClient.ts web/src/i18n/locales/zh-Hans.ts web/src/i18n/locales/en-US.ts`

Run: `git commit -m "feat(web): show demo key login beside space login"`

Manual check:
- 在配置中填入 `system.demo_login_key: "demo-key"` 后打开登录页
- 页面同时出现 `通过 Space 登录` 和 `通过密匙登录`
- 页面品牌显示为 `传奇bot`
- 页面底部不再出现“隐私政策 / 数据收集政策”
