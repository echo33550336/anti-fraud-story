// 导出后端可直接消费的剧情契约：contract/story-one-ticket-v1.json
//
// 数据来源（唯一事实源）：
//   src/story.js  — 15 节点、16 结局、选项与跳转
//   src/acts.js   — 第二至第五幕分镜
//   src/engine.js — 自由回答的确认 ID 与结局映射（下方 free_answers 与之一致）
//
// 用法：node tools/export-contract.mjs
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { S, E, STORY_ID, assets } from '../src/story.js';
import { BEATS, ACT_OF, ACT_NAMES, ENDING_BEATS } from '../src/acts.js';

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const key = n => 'N' + String(n).padStart(2, '0');

const nodes = Object.entries(S).map(([number, scene]) => {
  const id = key(Number(number));
  return {
    id,
    act: ACT_OF[id] ?? null,
    act_name: ACT_NAMES[ACT_OF[id]] ?? null,
    title: scene.title,
    time: scene.time,
    scene: scene.text,
    speaker: scene.speaker,
    prompt: scene.prompt,
    free: !!scene.free,
    options: (scene.options || []).map(([text, target], index) => ({
      id: String.fromCharCode(65 + index),
      text,
      next: typeof target === 'number' ? key(target) : target
    })),
    beats: BEATS[id] || null,
    presentation: {
      bg: scene.bg,
      person: scene.person,
      speaker: scene.speaker,
      phone: scene.phone || [],
      prop: scene.prop || null
    }
  };
});

const endings = Object.entries(E).map(([id, [title, rating, narration, next_step]]) => ({
  id, title, rating, narration, next_step,
  beats: ENDING_BEATS[id] || null
}));

const contract = {
  story_id: STORY_ID,
  generated_by: 'tools/export-contract.mjs',
  note: '节点文本、选项跳转、结局文案以此文件为准；后端实现 API_CONTRACT.md 时应原样返回这里的字段。',
  acts: Object.entries(ACT_NAMES).map(([no, name]) => ({
    no: Number(no), name, nodes: nodes.filter(n => n.act === Number(no)).map(n => n.id)
  })),
  assets,
  // 自由回答的确认 ID → 下一节点或结局（与 src/engine.js 的 freeTargets 一致）
  free_answers: {
    N03: { STOP: 'E01', CONTINUE: 'N04' },
    N15: { VERIFY: 'E11', REPORT: 'E12', DELETE: 'E13', SHARE: 'E14' }
  },
  nodes,
  endings,
  counts: { nodes: nodes.length, endings: endings.length, beats: nodes.reduce((n, x) => n + (x.beats ? x.beats.length : 0), 0) }
};

const outDir = join(root, 'contract');
mkdirSync(outDir, { recursive: true });
const out = join(outDir, 'story-one-ticket-v1.json');
writeFileSync(out, JSON.stringify(contract, null, 2), 'utf8');

console.log(`已导出 ${out}`);
console.log(`  节点 ${contract.counts.nodes}　结局 ${contract.counts.endings}　分镜句 ${contract.counts.beats}`);
for (const a of contract.acts) console.log(`  ${a.name}：${a.nodes.join(', ')}`);
