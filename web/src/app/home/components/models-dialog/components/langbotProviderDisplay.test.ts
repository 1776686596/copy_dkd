import assert from 'node:assert/strict';
import test from 'node:test';

import { getProviderDisplayInfo } from './langbotProviderDisplay.js';

test('special cloud provider uses generic display text instead of raw brand name', () => {
  const displayInfo = getProviderDisplayInfo({
    isLangBotModels: true,
    providerName: 'LangBot Models',
    baseUrl: 'https://api.example.com/v1',
    apiKeys: ['sk-1234567890'],
    genericTitle: 'Cloud Models',
    genericDescription: 'Managed cloud models available after login',
  });

  assert.deepEqual(displayInfo, {
    title: 'Cloud Models',
    subtitle: 'Managed cloud models available after login',
  });
});

test('regular provider keeps its own name and masked api key summary', () => {
  const displayInfo = getProviderDisplayInfo({
    isLangBotModels: false,
    providerName: 'OpenAI',
    baseUrl: 'https://api.openai.com/v1',
    apiKeys: ['sk-1234567890'],
    genericTitle: 'Cloud Models',
    genericDescription: 'Managed cloud models available after login',
  });

  assert.deepEqual(displayInfo, {
    title: 'OpenAI',
    subtitle: 'https://api.openai.com/v1 · sk-1...7890',
  });
});
