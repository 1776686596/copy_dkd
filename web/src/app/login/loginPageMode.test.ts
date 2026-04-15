import test from 'node:test';
import assert from 'node:assert/strict';

// @ts-expect-error TS5097: Node 原生执行 TypeScript 测试时需要显式扩展名
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

test('本地账号已设置密码且配置 demo key 时同时展示密码和密匙登录', () => {
  assert.deepEqual(
    resolveLoginPageMode({
      accountType: 'local',
      hasPassword: true,
      demoLoginKeyEnabled: true,
    }),
    {
      showSpaceLogin: false,
      showPasswordLogin: true,
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

test('space 账号已设置密码且配置 demo key 时展示 Space、密码和密匙登录', () => {
  assert.deepEqual(
    resolveLoginPageMode({
      accountType: 'space',
      hasPassword: true,
      demoLoginKeyEnabled: true,
    }),
    {
      showSpaceLogin: true,
      showPasswordLogin: true,
      showDemoKeyLogin: true,
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
