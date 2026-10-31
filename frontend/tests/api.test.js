import test from 'node:test';
import assert from 'node:assert/strict';
import { createApiClient } from '../src/api.js';

test('API 客户端按会话提交稳定选项 ID，并使用同源路径', async () => {
  const original = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return { ok: true, json: async () => calls.length === 1
      ? { story_id: 'one-ticket-v1', session_id: 'session-test', node: { id: 'N01' } }
      : { story_id: 'one-ticket-v1', ending_id: 'E02' } };
  };
  try {
    const client = createApiClient();
    await client.start();
    await client.answer({ node_id: 'N01', option_id: 'B' });
    assert.equal(calls[0].url, '/api/story/start');
    assert.equal(calls[1].url, '/api/story/answer');
    assert.deepEqual(JSON.parse(calls[1].options.body), { session_id: 'session-test', node_id: 'N01', option_id: 'B' });
  } finally { globalThis.fetch = original; }
});

test('旧版后端缺少剧情版本号时拒绝对接', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () => ({ ok: true, json: async () => ({ session_id: 'old', node: { id: 'N01' } }) });
  try { await assert.rejects(createApiClient().start(), /后端剧情版本不匹配/); }
  finally { globalThis.fetch = original; }
});
