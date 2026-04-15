import assert from 'node:assert/strict';
import test from 'node:test';

import { mergeServiceDeskTimelineMessages } from './timelineMessages.js';

test('客服详情没有消息时回退显示消息记录里的对话', () => {
  const merged = mergeServiceDeskTimelineMessages(
    [],
    [
      {
        id: 'msg-1',
        timestamp: '2026-04-15T08:00:00.000Z',
        message_content: '用户提问',
        session_id: 'session-1',
        role: 'user',
        user_name: '客户A',
      },
      {
        id: 'msg-2',
        timestamp: '2026-04-15T08:01:00.000Z',
        message_content: '客服回复',
        session_id: 'session-1',
        role: 'assistant',
        user_name: '客服A',
      },
    ],
  );

  assert.equal(merged.length, 2);
  assert.deepEqual(
    merged.map((item) => ({
      id: item.id,
      role: item.role,
      message_content: item.message_content,
    })),
    [
      {
        id: 'msg-1',
        role: 'user',
        message_content: '用户提问',
      },
      {
        id: 'msg-2',
        role: 'assistant',
        message_content: '客服回复',
      },
    ],
  );
});

test('客服详情和消息记录同时存在时按消息 id 去重合并', () => {
  const merged = mergeServiceDeskTimelineMessages(
    [
      {
        id: 'msg-1',
        timestamp: '2026-04-15T08:00:00.000Z',
        message_content: '用户提问',
        session_id: 'session-1',
        role: 'user',
        user_name: '客户A',
      },
    ],
    [
      {
        id: 'msg-1',
        timestamp: '2026-04-15T08:00:00.000Z',
        message_content: '用户提问',
        session_id: 'session-1',
        role: 'user',
        user_name: '客户A',
      },
      {
        id: 'msg-2',
        timestamp: '2026-04-15T08:01:00.000Z',
        message_content: '客服回复',
        session_id: 'session-1',
        role: 'assistant',
        user_name: '客服A',
      },
    ],
  );

  assert.equal(merged.length, 2);
  assert.deepEqual(
    merged.map((item) => item.id),
    ['msg-1', 'msg-2'],
  );
});
