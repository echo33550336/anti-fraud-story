import { E, S, STORY_ID } from './story.js';

const key = number => `N${String(number).padStart(2, '0')}`;
const freeTargets = { N03: { STOP: 'E01', CONTINUE: 4 }, N15: { VERIFY: 'E11', REPORT: 'E12', DELETE: 'E13', SHARE: 'E14' } };

export function publicNode(number) {
  const scene = S[number];
  if (!scene) throw new Error(`未知节点：${number}`);
  return {
    id: key(number), title: scene.title, time: scene.time,
    scene: scene.text, lines: [{ speaker: scene.speaker, text: scene.text }],
    prompt: scene.prompt, free: !!scene.free,
    options: (scene.options || []).map(([text], index) => ({ id: String.fromCharCode(65 + index), text })),
    presentation: { bg: scene.bg, person: scene.person, speaker: scene.speaker, phone: scene.phone || [], prop: scene.prop || null },
    progress: { current: number, total: 15 }
  };
}

function classify(nodeId, input) {
  const text = input.toLowerCase();
  if (nodeId === 'N03') {
    if (/继续|解释|添加|加微信|听听|联系对方/.test(text)) return 'CONTINUE';
    if (/官方|总机|剧院|核实|不转|拒绝|拉黑|举报|不加|停止|不信/.test(text)) return 'STOP';
  }
  if (nodeId === 'N15') {
    if (/删除|删掉|清空|不处理|不想面对/.test(text)) return 'DELETE';
    if (/分享|提醒朋友|告诉朋友|传播/.test(text)) return 'SHARE';
    if (/举报|报案|银行|支付平台|止付|保存证据|保留证据/.test(text)) return 'REPORT';
    if (/官方|剧院|总机|核实|联系小岚|确认身份/.test(text)) return 'VERIFY';
  }
  return null;
}

function demoScore(endingId, state) {
  let score = 100 - Math.min(50, Math.round((state.ticketPaid + state.secondPaid + state.smallPaid + state.investPaid) / 100))
    - (['E03', 'E10', 'E16'].includes(endingId) ? 18 : 0) - (endingId === 'E13' ? 15 : 0);
  if (['E01', 'E02', 'E05', 'E11', 'E12', 'E14'].includes(endingId)) score = Math.max(score, 82);
  return Math.max(10, Math.min(100, score));
}

function demoBadges(endingId, state) {
  const badges = [];
  if (state.verifiedOfficial || ['E01', 'E02', 'E05', 'E11'].includes(endingId)) badges.push('独立核验');
  if (state.stopped || ['E04', 'E07', 'E08', 'E09', 'E12', 'E14', 'E15'].includes(endingId)) badges.push('及时刹车');
  if (state.ticketPaid || state.smallPaid || state.investPaid) badges.push('识别代价');
  if (['E12', 'E14'].includes(endingId)) badges.push('线索保管员');
  if (endingId === 'E14') badges.push('安全传递者');
  return badges;
}

export function createDemoClient() {
  let current = 1;
  let endingId = null;
  let history = [];
  let state = {};
  const resetState = () => ({ ticketPaid: 0, secondPaid: 0, smallPaid: 0, investPaid: 0, verifiedOfficial: false, stopped: false });
  const advance = (target, answer) => {
    const node = current;
    history.push({ node_id: key(node), ...answer, source: answer.source || 'choice' });
    if (node === 3 && target === 4) state.verifiedOfficial = true;
    if (node === 4 && target === 5) state.ticketPaid += 900;
    if (node === 5 && target === 6) state.secondPaid += 900;
    if (node === 6 && target === 'E03') state.secondPaid = 3000 - state.ticketPaid;
    if (node === 9 && target === 10) state.smallPaid += 128;
    if (node === 10 && target === 11) state.smallPaid += 188;
    if (node === 12 && target === 13) state.investPaid += 3000;
    if (node === 13 && target === 14) state.investPaid += 500;
    if (node === 14 && target === 'E10') state.investPaid += Math.max(0, 5000 - state.ticketPaid - state.secondPaid - state.smallPaid - state.investPaid);
    if ((node === 13 || node === 14) && target === 15) state.stopped = true;
    if (node === 5 && target === 7 && state.verifiedOfficial) target = 'E15';
    if (node === 7 && target === 'E04' && state.verifiedOfficial && state.ticketPaid) target = 'E15';
    if (node === 14 && target === 'E10' && state.secondPaid >= 900) target = 'E16';
    if (typeof target === 'string' && target.startsWith('E')) {
      endingId = target;
      return { ending_id: endingId, response: '' };
    }
    current = target;
    return { next_node: publicNode(current), response: '' };
  };
  return {
    async start() { current = 1; endingId = null; history = []; state = resetState(); return { story_id: STORY_ID, session_id: `demo-${Date.now()}`, node: publicNode(1) }; },
    async answer({ node_id, option_id }) {
      if (node_id !== key(current) || endingId) throw new Error('节点已变化，请重开');
      const index = option_id.charCodeAt(0) - 65;
      const option = S[current].options?.[index];
      if (!option) throw new Error('无效选项');
      return advance(option[1], { option_id, source: 'choice' });
    },
    async open({ node_id, text }) {
      if (node_id !== key(current) || !S[current].free) throw new Error('当前节点不接受自由回答');
      const optionId = classify(node_id, text);
      return { need_confirm: true, suggested_option_id: optionId, intent: optionId || 'unclear', message: optionId ? '请确认系统理解的行动' : '请补充明确的行动' };
    },
    async confirm({ node_id, option_id, open_text }) {
      if (node_id !== key(current) || !S[current].free) throw new Error('当前节点不接受确认');
      const target = freeTargets[node_id]?.[option_id];
      if (!target) throw new Error('无法确认此行动');
      return advance(target, { option_id, source: 'open', text: open_text });
    },
    async review() {
      if (!endingId) throw new Error('剧情尚未结束');
      const [title, rating, narration, nextStep] = E[endingId];
      return { story_id: STORY_ID, ending_id: endingId, title, rating, narration, next_step: nextStep,
        score: demoScore(endingId, state), badges: demoBadges(endingId, state), history };
    }
  };
}
