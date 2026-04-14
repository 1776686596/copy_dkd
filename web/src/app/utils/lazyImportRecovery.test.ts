import assert from 'node:assert/strict';
import test from 'node:test';

import {
  createRecoverableLazyImport,
  isRecoverableDynamicImportError,
  RETRY_KEY_PREFIX,
} from './lazyImportRecovery';

class MemoryStorage {
  private store = new Map<string, string>();

  getItem(key: string) {
    return this.store.get(key) ?? null;
  }

  setItem(key: string, value: string) {
    this.store.set(key, value);
  }

  removeItem(key: string) {
    this.store.delete(key);
  }
}

test('识别浏览器动态导入 chunk 获取失败错误', () => {
  assert.equal(
    isRecoverableDynamicImportError(
      new TypeError(
        'Failed to fetch dynamically imported module: /assets/page-legacy.js',
      ),
    ),
    true,
  );

  assert.equal(
    isRecoverableDynamicImportError(
      new TypeError('Importing a module script failed.'),
    ),
    true,
  );

  assert.equal(
    isRecoverableDynamicImportError(new Error('普通接口请求失败')),
    false,
  );
});

test('首次遇到旧 chunk 失效时只触发一次刷新并写入重试标记', async () => {
  const storage = new MemoryStorage();
  let reloadCount = 0;
  const loader = createRecoverableLazyImport(
    () =>
      Promise.reject(
        new TypeError(
          'Failed to fetch dynamically imported module: /assets/page-legacy.js',
        ),
      ),
    'service-desk',
    {
      storage,
      reload: () => {
        reloadCount += 1;
      },
    },
  );

  const outcome = await Promise.race([
    loader().then(
      () => 'resolved',
      () => 'rejected',
    ),
    Promise.resolve('pending'),
  ]);

  assert.equal(outcome, 'pending');
  assert.equal(reloadCount, 1);
  assert.equal(storage.getItem(`${RETRY_KEY_PREFIX}service-desk`), '1');
});

test('重试标记已存在时不再循环刷新并抛出原始错误', async () => {
  const storage = new MemoryStorage();
  storage.setItem(`${RETRY_KEY_PREFIX}service-desk`, '1');
  let reloadCount = 0;
  const error = new TypeError(
    'Failed to fetch dynamically imported module: /assets/page-legacy.js',
  );
  const loader = createRecoverableLazyImport(
    () => Promise.reject(error),
    'service-desk',
    {
      storage,
      reload: () => {
        reloadCount += 1;
      },
    },
  );

  await assert.rejects(loader(), error);
  assert.equal(reloadCount, 0);
  assert.equal(storage.getItem(`${RETRY_KEY_PREFIX}service-desk`), null);
});

test('导入成功后会清理重试标记', async () => {
  const storage = new MemoryStorage();
  storage.setItem(`${RETRY_KEY_PREFIX}service-desk`, '1');
  const module = { default: () => null };
  const loader = createRecoverableLazyImport(
    () => Promise.resolve(module),
    'service-desk',
    { storage },
  );

  const result = await loader();

  assert.equal(result, module);
  assert.equal(storage.getItem(`${RETRY_KEY_PREFIX}service-desk`), null);
});
