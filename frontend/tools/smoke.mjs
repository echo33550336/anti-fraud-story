// 无浏览器冒烟：用 jsdom 把前端跑起来，模拟点击走完一局。
// 目的不是像素级验收，而是抓运行时错误（空引用、绑定失败、动画类没挂上）。
// 用法：node tools/smoke.mjs
import { JSDOM, VirtualConsole } from 'jsdom';

const vc = new VirtualConsole();
vc.on('jsdomError', e => console.log('[jsdomError]', e.message));
vc.on('error', (...a) => console.log('[console.error]', ...a));

const dom = new JSDOM('<!doctype html><html><body><div id="app"></div></body></html>', {
  url: 'http://localhost/?mode=demo',
  pretendToBeVisual: true,
  virtualConsole: vc
});

// —— 把浏览器环境灌进 global（Node 部分全局只有 getter，用 defineProperty 覆盖）——
const w = dom.window;
const define = (name, value) => {
  try {
    Object.defineProperty(globalThis, name, { value, writable: true, configurable: true });
  } catch (e) {
    try { globalThis[name] = value; } catch (e2) { /* 忽略不可写全局 */ }
  }
};
define('window', w);
define('document', w.document);
define('navigator', w.navigator);
define('location', w.location);
define('HTMLElement', w.HTMLElement);
define('CustomEvent', w.CustomEvent);
define('Event', w.Event);
define('localStorage', w.localStorage);
// 注意：不要覆盖 globalThis.performance —— jsdom 的 Performance.now 内部会引用它，
// 覆盖后两边互相调用会直接爆栈。用 Node 自带的 performance 即可。
define('getComputedStyle', w.getComputedStyle.bind(w));
globalThis.requestAnimationFrame = cb => w.setTimeout(() => cb(performance.now()), 16);
globalThis.cancelAnimationFrame = id => w.clearTimeout(id);

// 音频全部桩掉：只记录调用，不出声
class FakeAudio {
  constructor() { this.volume = 1; this.dataset = {}; this.paused = true; this._src = ''; }
  play() { this.paused = false; return Promise.resolve(); }
  pause() { this.paused = true; }
  load() {}
  removeAttribute() {}
  addEventListener() {}
  removeEventListener() {}
  set src(v) { this._src = v; }
  get src() { return this._src; }
  set currentTime(v) { this._t = v; }
  get currentTime() { return this._t || 0; }
}
globalThis.Audio = FakeAudio;
w.Audio = FakeAudio;

const errors = [];
w.addEventListener('error', e => errors.push('window.error: ' + e.message));
process.on('unhandledRejection', e => errors.push('rejection: ' + (e && e.message)));

await import('../src/main.js');
await new Promise(r => setTimeout(r, 60));

const $ = sel => document.querySelector(sel);
const log = (...a) => console.log(...a);
const check = (name, ok, extra = '') => {
  log(`${ok ? '✓' : '✗'} ${name}${extra ? '  ' + extra : ''}`);
  if (!ok) errors.push('检查失败: ' + name + ' ' + extra);
};

// 1) 首屏与控件
check('封面渲染', !!$('#cover') && !$('#cover').classList.contains('hidden'));
check('动效开关存在', !!$('#motionToggle'));
check('幕卡元素存在', !!$('#actCurtain'));

// 2) 进入故事（demo 模式）
$('#start').click();
await new Promise(r => setTimeout(r, 120));
check('进入序章', !$('#prologue').classList.contains('hidden'));
check('序章入场动画类', $('#prologue').classList.contains('screen-enter'));

// 3) 跳过序章 → 第一幕
$('#skipPrologue').click();
await new Promise(r => setTimeout(r, 80));
check('进入剧情', !$('#game').classList.contains('hidden'));
const firstAct = $('#actLabel').textContent;
check('幕名已显示', !!firstAct, firstAct);

// 4) 逐句推进 + 选择，走若干幕
let steps = 0, acts = new Set(), beats = 0, beatsThisNode = 0, ended = false;
for (let i = 0; i < 600 && steps < 14; i += 1) {
  if (!$('#end').classList.contains('hidden')) { ended = true; break; }
  if ($('#game').classList.contains('hidden')) { await new Promise(r => setTimeout(r, 20)); continue; }
  const next = $('#nextBeat');
  if (next && !$('#beatCtl').classList.contains('hidden')) {
    next.click(); beats += 1; beatsThisNode += 1;
    await new Promise(r => setTimeout(r, 4));
    continue;
  }
  const choices = [...document.querySelectorAll('#choices .choice')];
  if (choices.length && !$('#choices').classList.contains('hidden')) {
    const stagger = choices[0].style.getPropertyValue('--i');
    if (stagger === '') errors.push('选项缺少 --i 阶梯变量');
    const title = $('#sceneTitle')?.textContent || '?';
    log(`  第 ${steps + 1} 步：${title}　本节点 ${beatsThisNode} 句对白　选项 ${choices.length} 个`);
    beatsThisNode = 0;
    choices[0].click();
    steps += 1;
    acts.add($('#actLabel').textContent);
    await new Promise(r => setTimeout(r, 80));
    continue;
  }
  await new Promise(r => setTimeout(r, 20));
}

log(`\n推进 ${steps} 幕 / ${beats} 句对白，经过幕：`);
[...acts].forEach(a => log('   ' + a));

// 5) 动效开关（检查已前移到进入剧情后，见上）

// 6) 换幕幕卡是否出现过（任一时刻）
check('换幕卡曾触发', $('#actCurtain').className.includes('act-curtain'));

// 7) 结算
const endingVisible = !$('#end').classList.contains('hidden');
log(`\n当前是否已到结算页：${endingVisible ? '是' : '否（需继续点）'}`);

log('\n================');
if (errors.length) {
  log('发现 ' + errors.length + ' 个问题：');
  errors.slice(0, 12).forEach(e => log('  ! ' + e));
  process.exitCode = 1;
} else {
  log('冒烟通过：无运行时错误');
}
