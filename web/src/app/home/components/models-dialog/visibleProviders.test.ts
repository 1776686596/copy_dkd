import assert from 'node:assert/strict';
import test from 'node:test';

import { getVisibleProviders } from './visibleProviders.js';

test('hides the built-in cloud provider from the models dialog list', () => {
  const providers = [
    {
      uuid: 'builtin',
      requester: 'space-chat-completions',
      name: 'LangBot Models',
    },
    {
      uuid: 'custom-openai',
      requester: 'openai-chat-completions',
      name: 'OpenAI',
    },
  ];

  assert.deepEqual(getVisibleProviders(providers), [providers[1]]);
});

test('keeps all custom providers visible', () => {
  const providers = [
    {
      uuid: 'custom-openai',
      requester: 'openai-chat-completions',
      name: 'OpenAI',
    },
    {
      uuid: 'custom-azure',
      requester: 'azure-openai-chat-completions',
      name: 'Azure OpenAI',
    },
  ];

  assert.deepEqual(getVisibleProviders(providers), providers);
});
