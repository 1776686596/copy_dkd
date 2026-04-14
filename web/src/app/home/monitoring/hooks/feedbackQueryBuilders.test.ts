import assert from 'node:assert/strict';
import test from 'node:test';

import {
  buildFeedbackListQuery,
  buildFeedbackStatsQuery,
} from './feedbackQueryBuilders.js';

test('equivalent stats params produce the same query string', () => {
  const first = buildFeedbackStatsQuery({
    botIds: ['bot-1', 'bot-2'],
    pipelineIds: ['pipe-1'],
    startTime: '2026-04-14T14:00:00.000Z',
    endTime: '2026-04-14T14:30:00.000Z',
  });

  const second = buildFeedbackStatsQuery({
    botIds: ['bot-1', 'bot-2'],
    pipelineIds: ['pipe-1'],
    startTime: '2026-04-14T14:00:00.000Z',
    endTime: '2026-04-14T14:30:00.000Z',
  });

  assert.equal(first, second);
});

test('feedback list query serializes filters and pagination in a stable order', () => {
  const query = buildFeedbackListQuery({
    botIds: ['bot-1'],
    pipelineIds: ['pipe-1'],
    startTime: '2026-04-14T14:00:00.000Z',
    endTime: '2026-04-14T14:30:00.000Z',
    feedbackType: 'dislike',
    limit: 50,
    offset: 100,
  });

  assert.equal(
    query,
    [
      'botId=bot-1',
      'pipelineId=pipe-1',
      'startTime=2026-04-14T14%3A00%3A00.000Z',
      'endTime=2026-04-14T14%3A30%3A00.000Z',
      'feedbackType=2',
      'limit=50',
      'offset=100',
    ].join('&'),
  );
});
