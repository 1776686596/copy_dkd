type ReloadStorage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

export const RETRY_KEY_PREFIX = 'langbot:lazy-import-retry:';

function getErrorMessage(error: unknown) {
  if (typeof error === 'string') {
    return error;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return '';
}

export function isRecoverableDynamicImportError(error: unknown) {
  const message = getErrorMessage(error).toLowerCase();

  return (
    message.includes('failed to fetch dynamically imported module') ||
    message.includes('importing a module script failed') ||
    message.includes('error loading dynamically imported module')
  );
}

function getDefaultStorage(): ReloadStorage | undefined {
  if (typeof window === 'undefined') {
    return undefined;
  }

  return window.sessionStorage;
}

function reloadWindow() {
  if (typeof window === 'undefined') {
    return;
  }

  window.location.reload();
}

export function createRecoverableLazyImport<TModule>(
  importer: () => Promise<TModule>,
  routeKey: string,
  options: {
    storage?: ReloadStorage;
    reload?: () => void;
  } = {},
) {
  const retryKey = `${RETRY_KEY_PREFIX}${routeKey}`;
  const storage = options.storage ?? getDefaultStorage();
  const reload = options.reload ?? reloadWindow;

  return async () => {
    try {
      const module = await importer();
      storage?.removeItem(retryKey);
      return module;
    } catch (error) {
      if (!isRecoverableDynamicImportError(error) || !storage) {
        throw error;
      }

      if (storage.getItem(retryKey) === '1') {
        storage.removeItem(retryKey);
        throw error;
      }

      storage.setItem(retryKey, '1');
      reload();

      return new Promise<never>(() => {});
    }
  };
}
