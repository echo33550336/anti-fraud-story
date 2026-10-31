// 背景音乐：一幕一曲，切幕时交叉淡入淡出；说话时自动压低（duck）。
//
// 音轨：public/voice/bgm/act01.mp3 … act15.mp3（tools/gen-bgm.py 生成）
// 限制：浏览器要求先有用户手势才能出声，所以 initBgm() 必须在点击之后调用。

const BASE = 'public/voice/bgm/';
const FADE_MS = 900;
const STEP_MS = 30;
const NORMAL_VOLUME = 0.55;
const DUCK_VOLUME = 0.16;

const cache = new Map();
let current = null;
let currentAct = 0;
let enabled = true;
let ducked = false;
let fadeTimer = null;

function track(act) {
  if (!cache.has(act)) {
    const el = new Audio(`${BASE}act${String(act).padStart(2, '0')}.mp3`);
    el.loop = true;
    el.preload = 'auto';
    el.volume = 0;
    cache.set(act, el);
  }
  return cache.get(act);
}

function targetVolume() {
  if (!enabled) return 0;
  return ducked ? DUCK_VOLUME : NORMAL_VOLUME;
}

function fadeTo(el, to, ms) {
  const from = el.volume;
  const start = performance.now();
  const tick = now => {
    const k = Math.min(1, (now - start) / ms);
    el.volume = Math.max(0, Math.min(1, from + (to - from) * k));
    if (k < 1 && el.dataset.fading === '1') requestAnimationFrame(tick);
    else el.dataset.fading = '0';
  };
  el.dataset.fading = '1';
  requestAnimationFrame(tick);
}

/** 进入某一幕：切到对应音轨，旧的淡出、新的淡入 */
export function setBgmAct(act) {
  if (!act || act === currentAct) return;
  const next = track(act);
  const prev = current;
  currentAct = act;
  current = next;

  if (prev && prev !== next) {
    const from = prev.volume;
    prev.dataset.fading = '0';
    const start = performance.now();
    const out = now => {
      const k = Math.min(1, (now - start) / FADE_MS);
      prev.volume = Math.max(0, from * (1 - k));
      if (k < 1) requestAnimationFrame(out);
      else { prev.pause(); prev.currentTime = 0; }
    };
    requestAnimationFrame(out);
  }

  next.volume = 0;
  const play = next.play();
  if (play && play.catch) play.catch(() => { /* 未解锁或被拦截，等下一次交互 */ });
  fadeTo(next, targetVolume(), FADE_MS);
}

/** 首次点击后调用，解锁播放并启动当前幕 */
export function initBgm(act) {
  enabled = true;
  if (act) setBgmAct(act);
}

/** 播放语音时压低音乐 */
export function duckBgm(on) {
  ducked = !!on;
  if (!current) return;
  current.volume = targetVolume();
}

export function toggleBgm() {
  enabled = !enabled;
  if (current) {
    if (enabled) {
      const play = current.play();
      if (play && play.catch) play.catch(() => {});
      current.volume = targetVolume();
    } else {
      current.pause();
    }
  }
  return enabled;
}

export function isBgmEnabled() {
  return enabled;
}

export function stopBgm() {
  for (const el of cache.values()) { el.pause(); el.currentTime = 0; }
  current = null;
  currentAct = 0;
}
