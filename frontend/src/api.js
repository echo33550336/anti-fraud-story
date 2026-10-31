import { STORY_ID } from './story.js';

export function createApiClient(base = '/api/story') {
  let sessionId = null;
  async function request(path, options = {}) {
    const response = await fetch(`${base}${path}`, {
      method: options.method || 'GET',
      headers: { 'Content-Type': 'application/json' },
      body: options.body ? JSON.stringify(options.body) : undefined
    });
    let result;
    try { result = await response.json(); } catch { throw new Error(`服务返回非 JSON：${response.status}`); }
    if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
    return result;
  }
  return {
    async start() {
      const result = await request('/start', { method: 'POST', body: { story_id: STORY_ID } });
      if (result.story_id !== STORY_ID) throw new Error(`后端剧情版本不匹配：需要 ${STORY_ID}，收到 ${result.story_id || '未提供版本号'}`);
      if (!result.session_id || !result.node) throw new Error('后端缺少 session_id 或 node');
      sessionId = result.session_id;
      return result;
    },
    answer({ node_id, option_id }) { return request('/answer', { method: 'POST', body: { session_id: sessionId, node_id, option_id } }); },
    open({ node_id, text }) { return request('/open', { method: 'POST', body: { session_id: sessionId, node_id, text } }); },
    confirm({ node_id, option_id, open_text }) { return request('/confirm', { method: 'POST', body: { session_id: sessionId, node_id, option_id, open_text } }); },
    review() { return request(`/review?session_id=${encodeURIComponent(sessionId)}`); }
  };
}
