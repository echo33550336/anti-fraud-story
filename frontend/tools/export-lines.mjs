// 导出"非主角发言"清单：所有幕、所有角色（主角林夏除外）。
//
// 输出：
//   contract/lines.json  机器可读（含配音文件路径与音色）
//   contract/lines.md    人可读（按幕分组 + 按角色索引）
//
// 用法：node tools/export-lines.mjs
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { BEATS, ACT_OF, ACT_NAMES } from '../src/acts.js';

const root = dirname(dirname(fileURLToPath(import.meta.url)));

// 主角：由玩家扮演，不配音
export const PROTAGONIST = '林夏';

// 角色 → 音色（edge-tts 神经音色）与语速
export const VOICE_MAP = {
  旁白: { voice: 'zh-CN-YunjianNeural', rate: '-6%', pitch: '-1Hz', kind: 'narration' },
  小岚: { voice: 'zh-CN-XiaoxiaoNeural', rate: '-4%', pitch: '+2Hz', kind: 'character' },
  票务部: { voice: 'zh-CN-YunyangNeural', rate: '+2%', pitch: '-2Hz', kind: 'character' },
  剧院总机: { voice: 'zh-CN-XiaoyiNeural', rate: '+0%', pitch: '+0Hz', kind: 'character' }
};

const lines = [];
for (const [nodeId, beats] of Object.entries(BEATS)) {
  beats.forEach((beat, index) => {
    if (beat.who === PROTAGONIST) return;
    const act = ACT_OF[nodeId];
    const key = `${nodeId}_${index}`;
    const meta = VOICE_MAP[beat.who] || VOICE_MAP['旁白'];
    lines.push({
      key,
      act,
      act_name: ACT_NAMES[act],
      node: nodeId,
      index,
      who: beat.who,
      type: beat.who === '旁白' ? 'narration' : 'character',
      text: beat.text,
      phone: beat.phone || null,
      voice: meta.voice,
      rate: meta.rate,
      pitch: meta.pitch,
      audio: `public/voice/story/${key}.mp3`,
      audio_ready: existsSync(join(root, 'public', 'voice', 'story', `${key}.mp3`))
    });
  });
}

// 主角台词数量，仅供核对
const protagonistCount = Object.values(BEATS).flat().filter(b => b.who === PROTAGONIST).length;

const speakers = {};
for (const line of lines) speakers[line.who] = (speakers[line.who] || 0) + 1;
const readyAudioLines = lines.filter(line => line.audio_ready).length;

const payload = {
  generated_by: 'tools/export-lines.mjs',
  protagonist: PROTAGONIST,
  note: '主角台词不配音、不自动播放；其余全部自动播放。旁白单独标记 type=narration。',
  counts: {
    total_beats: Object.values(BEATS).flat().length,
    protagonist_lines: protagonistCount,
    voiced_lines: lines.length,
    ready_audio_lines: readyAudioLines,
    tts_fallback_lines: lines.length - readyAudioLines,
    speakers
  },
  lines
};

mkdirSync(join(root, 'contract'), { recursive: true });
writeFileSync(join(root, 'contract', 'lines.json'), JSON.stringify(payload, null, 2), 'utf8');

// ── Markdown ──────────────────────────────────────────────
const md = [];
md.push('# 非主角发言记录（全 15 幕）', '');
md.push(`> 由 \`node tools/export-lines.mjs\` 生成。主角 **${PROTAGONIST}** 的台词不配音、不自动播放，故不在此表。`, '');
md.push('| 项目 | 数量 |');
md.push('| --- | --- |');
md.push(`| 全部分镜句 | ${payload.counts.total_beats} |`);
md.push(`| 主角（${PROTAGONIST}）台词 | ${protagonistCount} |`);
md.push(`| **配音并自动播放** | **${lines.length}** |`);
md.push(`| MP3 已就绪 | ${readyAudioLines} |`);
md.push(`| 浏览器语音回退 | ${lines.length - readyAudioLines} |`);
for (const [who, n] of Object.entries(speakers)) {
  md.push(`| └ ${who} | ${n} |`);
}
md.push('');
md.push('| 角色 | 音色 | 语速 / 音调 |');
md.push('| --- | --- | --- |');
for (const [who, m] of Object.entries(VOICE_MAP)) {
  md.push(`| ${who} | \`${m.voice}\` | ${m.rate} / ${m.pitch} |`);
}
md.push('');

let currentAct = 0;
for (const line of lines) {
  if (line.act !== currentAct) {
    currentAct = line.act;
    md.push(`## ${line.act_name}（${line.node}）`, '');
  }
  const tag = line.type === 'narration' ? '旁白' : line.who;
  md.push(`- **${tag}**：${line.text}${line.phone ? `　\`手机：${line.phone}\`` : ''}`);
  if (lines.indexOf(line) === lines.length - 1) md.push('');
}

md.push('---', '', '## 按角色索引', '');
for (const who of Object.keys(VOICE_MAP)) {
  const own = lines.filter(l => l.who === who);
  if (!own.length) continue;
  md.push(`### ${who}（${own.length} 句）`, '');
  for (const l of own) md.push(`- \`${l.key}\` ${l.text}`);
  md.push('');
}

writeFileSync(join(root, 'contract', 'lines.md'), md.join('\n'), 'utf8');

console.log(`已导出 contract/lines.json 与 lines.md`);
console.log(`  全部 ${payload.counts.total_beats} 句，主角 ${protagonistCount} 句，待配音 ${lines.length} 句`);
console.log(`  MP3 已就绪 ${readyAudioLines}，浏览器语音回退 ${lines.length - readyAudioLines}`);
for (const [who, n] of Object.entries(speakers)) console.log(`    ${who}：${n}`);
