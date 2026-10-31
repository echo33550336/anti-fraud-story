// 导出序章配音清单：contract/prologue-lines.json
// 林夏（主角）不配音，与 15 幕保持一致的“主角无声”设定，因此只导出旁白/小岚/售票处同事。
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { PROLOGUE } from '../src/prologue.js';

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const OUT = join(ROOT, 'contract', 'prologue-lines.json');
const AUDIO_DIR = join(ROOT, 'public', 'voice', 'prologue');
const PROTAGONIST = '林夏';

const VOICE = {
  '旁白': { voice: 'zh-CN-YunjianNeural', rate: '-6%', pitch: '-1Hz' },
  '小岚': { voice: 'zh-CN-XiaoxiaoNeural', rate: '-4%', pitch: '+2Hz' },
  '售票处同事（画外）': { voice: 'zh-CN-XiaoyiNeural', rate: '+6%', pitch: '+4Hz' }
};

async function exists(path) {
  try { await readFile(path); return true; } catch { return false; }
}

const lines = [];
const skipped = [];
for (const beat of PROLOGUE) {
  if (beat.speaker === PROTAGONIST) { skipped.push(beat.id); continue; }
  const preset = VOICE[beat.speaker];
  if (!preset) throw new Error(`未知说话人：${beat.speaker}（${beat.id}）`);
  const audio = `public/voice/prologue/${beat.id}.mp3`;
  lines.push({
    key: beat.id,
    speaker: beat.speaker,
    focus: beat.focus,
    text: beat.text,
    voice: preset.voice,
    rate: preset.rate,
    pitch: preset.pitch,
    audio,
    audio_ready: await exists(join(AUDIO_DIR, `${beat.id}.mp3`))
  });
}

await mkdir(dirname(OUT), { recursive: true });
const payload = {
  story_id: 'one-ticket-v1',
  part: 'prologue',
  protagonist_unvoiced: PROTAGONIST,
  voice_map: VOICE,
  skipped,
  total: lines.length,
  lines
};
await writeFile(OUT, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
const ready = lines.filter(item => item.audio_ready).length;
console.log(`序章台词 ${PROLOGUE.length} 句：配音 ${lines.length} 句（跳过主角 ${skipped.length} 句），已有音频 ${ready}/${lines.length}`);
console.log(`清单：contract/prologue-lines.json`);
