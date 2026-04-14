export function getProviderDisplayInfo({
  isLangBotModels,
  providerName,
  baseUrl,
  apiKeys,
  genericTitle,
  genericDescription,
}) {
  if (isLangBotModels) {
    return {
      title: genericTitle,
      subtitle: genericDescription,
    };
  }

  const summaryParts = [baseUrl ?? ''];

  if (apiKeys?.length) {
    summaryParts.push(maskApiKey(apiKeys[0]));
  }

  return {
    title: providerName,
    subtitle: summaryParts.filter(Boolean).join(' · '),
  };
}

function maskApiKey(key) {
  if (!key) return '';
  if (key.length <= 8) return '****';
  return `${key.slice(0, 4)}...${key.slice(-4)}`;
}
