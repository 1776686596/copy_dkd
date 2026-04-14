const BUILTIN_CLOUD_PROVIDER_REQUESTER = 'space-chat-completions';

export function getVisibleProviders(providers) {
  return providers.filter(
    (provider) => provider.requester !== BUILTIN_CLOUD_PROVIDER_REQUESTER,
  );
}
