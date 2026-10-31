import { mountApp } from './ui.js';
import { assets, S, STORY_ID } from './story.js';
import { BEATS, ACT_OF, ACT_NAMES, ENDING_BEATS } from './acts.js';
import { initBgm, setBgmAct, toggleBgm, duckBgm } from './bgm.js';
import { setupPrologue } from './prologue.js';
import { createApiClient } from './api.js';
import { createDemoClient } from './engine.js';

mountApp(document.querySelector('#app'));

const $ = selector => document.querySelector(selector);
const requestedMode = new URLSearchParams(location.search).get('mode');
let mode = requestedMode === 'demo' ? 'demo' : 'api';
let client = mode === 'demo' ? createDemoClient() : createApiClient();
let node = null;
let busy = false;
let lastAct = 0;

function screen(name) {
  for (const id of ['cover', 'prologue', 'game', 'end']) {
    const el = $(`#${id}`);
    const active = id === name;
    el.classList.toggle('hidden', !active);
    if (active) {
      el.classList.remove('screen-enter');
      void el.offsetWidth;          // 强制回流，让入场动画每次都能重播
      el.classList.add('screen-enter');
    }
  }
}
function bg(key) { $('#back').style.backgroundImage = `url("${encodeURI(assets[key] || assets.A)}")`; }
function message(value) {
  $('#toast').textContent = value;
  $('#toast').classList.add('show');
  clearTimeout(message.timer);
  message.timer = setTimeout(() => $('#toast').classList.remove('show'), 5000);
}
function setBusy(value) {
  busy = value;
  $('#status').textContent = value ? '正在等待后端…' : (mode === 'demo' ? '演示模式 · 本地规则' : '后端会话 · 服务端判定');
  for (const button of $('#game').querySelectorAll('button')) button.disabled = value;
}
function addText(parent, text, tag = 'p') {
  const item = document.createElement(tag);
  item.textContent = text;
  parent.append(item);
  return item;
}
function presentationFor(publicNode) {
  const number = Number(publicNode.id?.slice(1));
  const local = S[number] || {};
  return { bg: local.bg, person: local.person, speaker: local.speaker, phone: local.phone || [], prop: local.prop,
    ...(publicNode.presentation || {}) };
}
/* ---------- 配音：非主角自动播放 ----------
   主角（林夏）不配音。其余角色与旁白按 public/voice/story/{节点}_{行号}.mp3 自动播放；
   文件缺失时回落到浏览器 TTS，音色与 contract/lines.json 的 VOICE_MAP 保持一致。 */
const PROTAGONIST = '林夏';
let storyVoiceOn = true;
let storyToken = 0;
const storyAudio = new Audio();
const TTS_FALLBACK = {
  旁白: { pitch: 0.92, rate: 0.94 },
  小岚: { pitch: 1.22, rate: 0.96 },
  票务部: { pitch: 0.9, rate: 1.04 },
  剧院总机: { pitch: 1.08, rate: 1.0 }
};

function stopStoryAudio() {
  storyToken++;
  try { storyAudio.pause(); } catch (e) {}
  if ('speechSynthesis' in window) speechSynthesis.cancel();
  duckBgm(false);
}
storyAudio.addEventListener('ended', () => duckBgm(false));

function speakFallback(text, who, my) {
  if (!('speechSynthesis' in window)) { duckBgm(false); return; }
  const preset = TTS_FALLBACK[who] || TTS_FALLBACK['旁白'];
  const utter = new SpeechSynthesisUtterance(text);
  utter.lang = 'zh-CN';
  utter.pitch = preset.pitch;
  utter.rate = preset.rate;
  const zh = speechSynthesis.getVoices().filter(v => v.lang && v.lang.toLowerCase().startsWith('zh'));
  const natural = zh.find(v => /natural|online|neural/i.test(v.name));
  if (natural || zh[0]) utter.voice = natural || zh[0];
  utter.onend = () => { if (my === storyToken) duckBgm(false); };
  utter.onerror = () => { if (my === storyToken) duckBgm(false); };
  speechSynthesis.speak(utter);
}

function playStoryAudio(nodeId, index, beat) {
  if (!storyVoiceOn || !beat || beat.who === PROTAGONIST) return;
  duckBgm(true);
  const my = ++storyToken;
  const src = `public/voice/story/${nodeId}_${index}.mp3`;
  let settled = false;
  const fallback = () => {
    if (settled || my !== storyToken) return;
    settled = true;
    storyAudio.onerror = null;
    speakFallback(beat.text, beat.who, my);
  };
  storyAudio.onerror = fallback;
  storyAudio.src = src;
  const playing = storyAudio.play();
  if (playing && playing.catch) playing.catch(fallback);
}

/* ---------- 分镜逐句推进（15 幕） ---------- */
let beatState = null;

function setInteractVisible(show) {
  $('#prompt').classList.toggle('hidden', !show);
  if (!show) { $('#choices').classList.add('hidden'); $('#freeform').classList.add('hidden'); return; }
  const free = !!node?.free;
  $('#choices').classList.toggle('hidden', free);
  $('#freeform').classList.toggle('hidden', !free);
}

function pushBeatLine(beat, index) {
  stopStoryAudio();
  const line = document.createElement('p');
  line.className = 'beat';
  if (beat.who) line.dataset.who = beat.who;
  line.textContent = beat.text;
  const narrative = $('#narrative');
  narrative.querySelectorAll('.beat').forEach(previous => previous.classList.add('previous'));
  narrative.append(line);
  while (narrative.children.length > 2) narrative.firstElementChild.remove();
  const unverified = beat.who === '小岚' && Number(node?.id?.slice(1)) >= 8;
  $('#speaker').textContent = unverified ? '自称“小岚”的账号' : (beat.who || '旁白');
  const portrait = $('#portrait');
  portrait.classList.toggle('speaking', beat.who !== '旁白');
  portrait.classList.toggle('remote', unverified || beat.who === '票务部' || beat.who === '剧院总机');
  if (unverified || beat.who === '票务部' || beat.who === '剧院总机') {
    const src = encodeURI(assets[beat.who === '票务部' ? 'caller' : 'caller2']);
    if ($('#portraitImg').getAttribute('src') !== src) $('#portraitImg').src = src;
    $('#portraitName').textContent = unverified ? '未核实的微信账号' : beat.who;
    $('#phoneHead').textContent = unverified ? '微信 · 身份未核实' : '陌生来电 · 身份未核实';
  } else {
    const view = presentationFor(node);
    const src = encodeURI(assets[view.person] || assets.lin);
    if ($('#portraitImg').getAttribute('src') !== src) $('#portraitImg').src = src;
    $('#portraitName').textContent = '林夏';
    $('#phoneHead').textContent = Number(node?.id?.slice(1)) >= 8 && Number(node?.id?.slice(1)) <= 14
      ? '微信 · 身份未核实' : '虚拟手机';
  }
  if (beat.phone) {
    $('#phone').classList.remove('hidden');
    addText($('#phoneBody'), beat.phone, 'div').className = 'message';
    $('#phoneBody').scrollTop = $('#phoneBody').scrollHeight;
  }
  if (typeof index === 'number' && index >= 0 && node?.id) playStoryAudio(node.id, index, beat);
}

function advanceBeat() {
  if (!beatState) return;
  const { beats } = beatState;
  if (beatState.i >= beats.length) { finishBeats(); return; }
  const index = beatState.i;
  pushBeatLine(beats[index], index);
  beatState.i += 1;
  $('#beatCount').textContent = `${beatState.i} / ${beats.length}`;
  const narrative = $('#narrative');
  narrative.scrollTop = narrative.scrollHeight;
  $('#nextBeat').textContent = beatState.i >= beats.length ? '做出选择 ▸' : '继续 ▸';
}

function finishBeats() {
  beatState = null;
  $('#beatCtl').classList.add('hidden');
  $('#beatCount').classList.add('hidden');
  setInteractVisible(true);
}

function expandAllBeats() {
  if (!beatState) return;
  const { beats } = beatState;
  const start = beatState.i;
  const lastIndex = beats.length - 1;
  stopStoryAudio();
  for (let k = start; k < beats.length; k += 1) pushBeatLine(beats[k]);
  beatState.i = beats.length;
  $('#narrative').scrollTop = $('#narrative').scrollHeight;
  finishBeats();
  // 展开时不逐句朗读，只读最后一句，避免音频排队
  if (lastIndex >= 0 && node?.id) playStoryAudio(node.id, lastIndex, beats[lastIndex]);
}
$('#nextBeat').onclick = advanceBeat;
$('#skipBeats').onclick = expandAllBeats;
$('#voiceToggle').onclick = () => {
  storyVoiceOn = !storyVoiceOn;
  $('#voiceToggle').textContent = storyVoiceOn ? '语音：开' : '语音：关';
  $('#voiceToggle').classList.toggle('off', !storyVoiceOn);
  if (!storyVoiceOn) stopStoryAudio();
};
$('#bgmToggle').onclick = () => {
  const on = toggleBgm();
  $('#bgmToggle').textContent = on ? '音乐：开' : '音乐：关';
  $('#bgmToggle').classList.toggle('off', !on);
};
$('#motionToggle').onclick = () => {
  const off = document.documentElement.classList.toggle('no-motion');
  $('#motionToggle').textContent = off ? '动效：关' : '动效：开';
  $('#motionToggle').classList.toggle('off', off);
};

/* ---------- 换幕黑场卡：只做视觉过渡，不改变任何推进逻辑 ---------- */
let curtainTimer = null;
function showActCurtain(act) {
  if (document.documentElement.classList.contains('no-motion')) return;
  const curtain = $('#actCurtain');
  if (!curtain) return;
  $('#actCurtainKicker').textContent = `第 ${String(act).padStart(2, '0')} 幕`;
  $('#actCurtainText').textContent = (ACT_NAMES[act] || '').replace(/^第.+?幕\s*·\s*/, '');
  curtain.classList.remove('hidden', 'in');
  void curtain.offsetWidth;
  curtain.classList.add('in');
  clearTimeout(curtainTimer);
  curtainTimer = setTimeout(() => {
    curtain.classList.remove('in');
    setTimeout(() => curtain.classList.add('hidden'), 420);
  }, 760);
}

$('#narrative').onclick = () => { if (beatState) advanceBeat(); };
document.addEventListener('keydown', event => {
  if (!beatState) return;
  if (event.target?.tagName === 'TEXTAREA') return;
  if (event.code === 'Space' || event.code === 'Enter') { event.preventDefault(); advanceBeat(); }
});

function renderNode(next) {
  if (!next?.id) throw new Error('后端未返回节点');
  node = next;
  stopStoryAudio();
  const view = presentationFor(next);
  const act = ACT_OF[next.id];
  if (act) setBgmAct(act);
  screen('game'); bg(view.bg);
  const number = Number(next.id.slice(1));
  const current = next.progress?.current ?? number;
  const total = next.progress?.total ?? 15;
  $('#progressLabel').textContent = act
    ? `第${act}幕 · ${current}/${total}`
    : `节点 ${String(current).padStart(2, '0')} / ${total}`;
  $('#progressBar').style.width = `${Math.min(100, current / total * 100)}%`;
  $('#sceneTitle').textContent = next.title || S[number]?.title || next.id;
  $('#sceneMeta').textContent = next.time || '';
  const actLabel = $('#actLabel');
  if (act) {
    actLabel.textContent = ACT_NAMES[act];
    actLabel.classList.remove('hidden');
    if (act !== lastAct) {           // 换幕：幕名标签闪一次 + 黑场幕卡
      lastAct = act;
      actLabel.classList.remove('flash');
      void actLabel.offsetWidth;
      actLabel.classList.add('flash');
      showActCurtain(act);
    }
  } else actLabel.classList.add('hidden');
  $('#portraitImg').src = encodeURI(assets[view.person] || assets.lin);
  $('#portraitName').textContent = view.person?.startsWith('lan') ? '小岚' : view.person === 'zhou' ? '阿舟' : '林夏';
  $('#prop').classList.toggle('hidden', !view.prop);
  if (view.prop) $('#prop').src = encodeURI(assets[view.prop] || view.prop);
  $('#phone').classList.add('hidden');
  $('#phoneBody').replaceChildren();

  $('#answer').value = '';
  $('#prompt').textContent = next.prompt || '';
  $('#choices').replaceChildren();
  if (!next.free) {
    for (const [index, option] of (next.options || []).entries()) {
      const button = document.createElement('button');
      button.className = 'choice';
      button.style.setProperty('--i', index);
      button.textContent = `${option.id}. ${option.text}`;
      button.onclick = () => submitChoice(option.id);
      $('#choices').append(button);
    }
  }

  $('#narrative').replaceChildren();
  const beats = BEATS[next.id];
  if (beats && beats.length) {
    beatState = { beats, i: 0 };
    $('#beatCount').classList.remove('hidden');
    $('#speaker').textContent = beats[0].who || '旁白';
    $('#beatCtl').classList.remove('hidden');
    $('#nextBeat').textContent = '继续 ▸';
    setInteractVisible(false);
    advanceBeat();
  } else {
    beatState = null;
    $('#beatCtl').classList.add('hidden');
    $('#beatCount').classList.add('hidden');
    $('#speaker').textContent = view.speaker || next.lines?.[0]?.speaker || '旁白';
    for (const line of view.phone || []) addText($('#phoneBody'), line, 'div').className = 'message';
    $('#phone').classList.toggle('hidden', !view.phone?.length);
    const dialogue = typeof next.scene === 'string' ? next.scene : next.lines?.map(line => line.text).join('\n') || '';
    dialogue.split('\n').forEach(line => addText($('#narrative'), line));
    setInteractVisible(true);
  }
  setBusy(false);
}

async function advance(result) {
  if (result.story_id && result.story_id !== STORY_ID) throw new Error('后端返回了另一套剧情版本');
  if (result.response) message(result.response);
  if (result.ending_id) {
    const review = await client.review();
    if (review.story_id && review.story_id !== STORY_ID) throw new Error('结算剧情版本与当前页面不一致');
    renderEnding(review);
  } else {
    renderNode(result.next_node);
  }
}
async function submitChoice(optionId) {
  if (busy || !node) return;
  setBusy(true);
  try { await advance(await client.answer({ node_id: node.id, option_id: optionId })); }
  catch (error) { message(error.message); setBusy(false); }
}

const intentLabels = { STOP: '停止联系并保留记录', CONTINUE: '继续与联系人沟通', VERIFY: '通过官方渠道核实身份', REPORT: '保存证据并举报求助', DELETE: '删除记录，不再处理', SHARE: '向身边人分享脱敏提醒' };
async function submitOpen() {
  if (busy || !node) return;
  const text = $('#answer').value.trim();
  if (text.length < 4) return message('请至少写四个字，说明你的行动。');
  setBusy(true);
  try {
    const result = await client.open({ node_id: node.id, text });
    if (result.next_node || result.ending_id) return await advance(result);
    const suggested = result.suggested_option_id;
    if (!suggested) { message(result.message || '意图不清楚，请补充具体行动。'); return; }
    $('#freeform').classList.add('hidden');
    $('#choices').classList.remove('hidden');
    $('#choices').replaceChildren();
    const confirm = document.createElement('button');
    confirm.className = 'choice';
    confirm.textContent = `确认：${intentLabels[suggested] || result.suggested_label || suggested}`;
    confirm.onclick = async () => {
      if (busy) return;
      setBusy(true);
      try { await advance(await client.confirm({ node_id: node.id, option_id: suggested, open_text: text })); }
      catch (error) { message(error.message); setBusy(false); }
    };
    const rewrite = document.createElement('button');
    rewrite.className = 'choice';
    rewrite.textContent = '重新表述回答';
    rewrite.onclick = () => { $('#choices').classList.add('hidden'); $('#freeform').classList.remove('hidden'); $('#answer').focus(); };
    $('#choices').append(confirm, rewrite);
    $('#prompt').textContent = result.message || '请确认系统理解的行动';
  } catch (error) { message(error.message); }
  finally { setBusy(false); }
}

function renderEnding(review) {
  stopStoryAudio();
  screen('end'); bg('end');
  $('#endingTitle').textContent = review.title || review.ending_id || '本局结束';
  $('#rating').textContent = [review.ending_id, review.rating].filter(Boolean).join(' · ');
  const scoreEl = $('#score');
  const finalScore = Number.isFinite(Number(review.score)) ? Math.round(Number(review.score)) : null;
  scoreEl.classList.remove('tick');
  if (finalScore === null || document.documentElement.classList.contains('no-motion')) {
    scoreEl.textContent = finalScore === null ? '--' : finalScore;
  } else {
    const startedAt = performance.now();
    const duration = 700;
    const tick = now => {
      const k = Math.min(1, (now - startedAt) / duration);
      scoreEl.textContent = Math.round(finalScore * (1 - Math.pow(1 - k, 3)));
      scoreEl.classList.add('tick');
      if (k < 1) requestAnimationFrame(tick);
      else setTimeout(() => scoreEl.classList.remove('tick'), 380);
    };
    requestAnimationFrame(tick);
  }
  $('#scoreLabel').textContent = mode === 'demo' ? ' / 100 · 演示评分' : ' / 100 · 后端评分';
  const story = $('#endingStory');
  story.replaceChildren();
  for (const beat of (ENDING_BEATS[review.ending_id] || [])) {
    const line = document.createElement('p');
    line.className = 'beat';
    line.textContent = beat.text;
    story.append(line);
  }
  if (review.narration) addText(story, review.narration).className = 'end-narration';
  $('#summary').textContent = review.next_step || review.review || '';
  $('#badges').replaceChildren();
  for (const badge of review.badges || []) addText($('#badges'), `✦ ${typeof badge === 'string' ? badge : badge.name || badge.id}`, 'span').className = 'badge';
}

const startPrologue = setupPrologue({ screen, bg, onFinish: () => renderNode(node) });
async function start() {
  if (busy) return;
  busy = true;
  $('#start').disabled = true;
  try {
    const started = await client.start();
    node = started.node;
    initBgm(ACT_OF[node.id] || 1);   // 用户点击后解锁播放，从第一幕的音乐起
    startPrologue();
  } catch (error) {
    message(error.message);
    if (mode === 'api') $('#demoMode').classList.remove('hidden');
  } finally { busy = false; $('#start').disabled = false; }
}

const demoButton = document.createElement('button');
demoButton.id = 'demoMode'; demoButton.className = 'start hidden'; demoButton.textContent = '改用演示模式';
demoButton.onclick = () => { mode = 'demo'; client = createDemoClient(); demoButton.classList.add('hidden'); start(); };
$('#start').after(demoButton);
$('#start').onclick = start;
$('#again').onclick = start;
$('#restartTop').onclick = () => { stopStoryAudio(); beatState = null; bg('cover'); screen('cover'); };
$('#submitAnswer').onclick = submitOpen;
$('#cover .hint').textContent = mode === 'demo' ? '演示模式 · 本地规则，不调用后端' : '后端模式 · 使用同源 /api/story 接口';
bg('cover');
