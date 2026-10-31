import { assets } from './story.js';
// 序章只交代事实，不计分；每一行都有稳定 ID，便于后续导入同名 MP3。
export const PROLOGUE = [
  { id:'P01', speaker:'旁白', focus:'none', text:'10月27日，傍晚六点半。距离万圣节还有几天，市中心的大剧院门口已经热闹起来。', visual:'ambience' },
  { id:'P02', speaker:'旁白', focus:'none', text:'南瓜灯挂满门廊，紫色射灯映着玻璃墙。戴巫师帽的观众走向入口，一个小女孩举着发光南瓜灯，从人群里跑过。', visual:'crowd' },
  { id:'P03', speaker:'旁白', focus:'lin', text:'林夏刚下班，特意绕路来到售票处。他想买一张万圣节演出的票。' },
  { id:'P04', speaker:'林夏', focus:'lin', text:'你好，买一张万圣节晚上的票。' },
  { id:'P05', speaker:'旁白', focus:'lan', text:'窗口里，穿着剧院工装的姑娘正整理票夹。她一抬头，动作忽然停住。' },
  { id:'P06', speaker:'林夏', focus:'lin', text:'……小岚？' },
  { id:'P07', speaker:'小岚', focus:'lan', text:'林夏？！' },
  { id:'P08', speaker:'旁白', focus:'both', text:'票夹险些从她手里滑下。两人隔着窗口愣了片刻，随后一起笑了。' },
  { id:'P09', speaker:'林夏', focus:'lin', text:'你怎么在这儿？' },
  { id:'P10', speaker:'小岚', focus:'lan', text:'我在这儿上班啊，票务！你呢，来看演出？', visual:'badge' },
  { id:'P11', speaker:'林夏', focus:'lin', text:'嗯，听朋友说万圣节那场气氛特别好。咱俩得多少年没见了？' },
  { id:'P12', speaker:'小岚', focus:'lan', text:'毕业以后就没见过了吧。你怎么还是这副样子。' },
  { id:'P13', speaker:'旁白', focus:'both', text:'林夏拿出钱，小岚却把他的手轻轻挡了回去。', visual:'cash' },
  { id:'P14', speaker:'小岚', focus:'lan', text:'别买了。我这儿有员工内部票，每个员工每月两张福利票，我这月的还没用。送你。' },
  { id:'P15', speaker:'旁白', focus:'ticket', text:'她从票夹里抽出一张硬卡纸门票，隔着窗口递来。金边在灯下微微发亮。', visual:'ticket' },
  { id:'P16', speaker:'旁白', focus:'ticket', text:'票面写着《南瓜夜·尖叫音乐会》、10月31日19:30、VIP A区3排。右下角还有一行小字：员工内部赠票，不对外销售。', visual:'ticket' },
  { id:'P17', speaker:'林夏', focus:'lin', text:'这怎么好意思。' },
  { id:'P18', speaker:'小岚', focus:'lan', text:'老同学，客气什么。' },
  { id:'P19', speaker:'林夏', focus:'lin', text:'那……改天我请你吃个饭？这么多年没见了。你号码多少？' },
  { id:'P20', speaker:'小岚', focus:'lan', text:'你写这块，我空了加你！', visual:'note' },
  { id:'P21', speaker:'旁白', focus:'note', text:'林夏低头在便签上写下联系方式。纸的开头是“159……”，余下的号码被他手掌挡住。', visual:'note' },
  { id:'P22', speaker:'售票处同事（画外）', focus:'none', text:'小岚！你过来一下！', visual:'coworker' },
  { id:'P23', speaker:'小岚', focus:'lan', text:'马上！你写完放这就好！', visual:'note' },
  { id:'P24', speaker:'林夏', focus:'lin', text:'你先忙，我回头找你！' },
  { id:'P25', speaker:'旁白', focus:'none', text:'林夏走出剧院。写着联系方式的便签，还留在售票处的窗口里。', visual:'note' }
];


export function setupPrologue({ screen, bg, onFinish }) {
  const $ = selector => document.querySelector(selector);
let prologueIndex = 0;
let prologueAuto = true;
let prologueTimer = null;
let prologueAudio = null;
let prologueRun = 0;

function stopPrologueMedia() {
  clearTimeout(prologueTimer);
  prologueTimer = null;
  if (prologueAudio) {
    prologueAudio.pause();
    prologueAudio.removeAttribute('src');
    prologueAudio.load();
    prologueAudio = null;
  }
}

function schedulePrologueFallback(beat, run, label = '配音待导入 · 按阅读节奏推进') {
  if (!prologueAuto || run !== prologueRun) return;
  $('#prologueAudioStatus').textContent = label;
  const delay = Math.max(2800, Math.min(7500, 1500 + beat.text.length * 115));
  prologueTimer = setTimeout(() => {
    if (run === prologueRun) nextPrologue();
  }, delay);
}

function playPrologueVoice(beat, run) {
  // 导入 public/voice/prologue/P01.mp3 ... P25.mp3 后即可逐句自动播放。
  const voice = new Audio(`public/voice/prologue/${beat.id}.mp3`);
  prologueAudio = voice;
  let handled = false;
  const unavailable = () => {
    if (handled || run !== prologueRun) return;
    handled = true;
    schedulePrologueFallback(beat, run);
  };
  voice.addEventListener('error', unavailable, { once: true });
  voice.addEventListener('ended', () => {
    if (run !== prologueRun) return;
    $('#prologueAudioStatus').textContent = '语音播放完毕';
    if (prologueAuto) prologueTimer = setTimeout(nextPrologue, 450);
  }, { once: true });
  voice.play().then(() => {
    if (run === prologueRun) $('#prologueAudioStatus').textContent = `正在播放 ${beat.id}.mp3`;
  }).catch(unavailable);
}

function showPrologueFocus(kind) {
  const panel = $('#prologueFocus');
  panel.replaceChildren();
  panel.classList.toggle('hidden', !kind);
  if (!kind) return;
  panel.dataset.kind = kind;
  const heading = document.createElement('strong');
  const detail = document.createElement('span');
  if (kind === 'ticket') {
    const image = document.createElement('img');
    image.src = encodeURI(assets.ticket);
    image.alt = '员工内部赠票特写';
    panel.append(image);
    heading.textContent = '员工内部赠票';
    detail.textContent = '10月31日 19:30 · VIP A区3排 · 不对外销售';
  } else if (kind === 'note') {
    heading.textContent = '售票处便签';
    detail.textContent = '林夏的联系方式：159……\n写完后留在窗口';
  } else if (kind === 'badge') {
    heading.textContent = '剧院工牌';
    detail.textContent = '小岚 · 票务工作人员';
  } else if (kind === 'cash') {
    heading.textContent = '林夏准备付钱';
    detail.textContent = '小岚挡回现金，提出赠送员工福利票';
  } else if (kind === 'coworker') {
    heading.textContent = '售票处内 · 画外音';
    detail.textContent = '同事叫走小岚，便签留在窗口';
  } else {
    heading.textContent = kind === 'crowd' ? '万圣节前的剧院' : '10月27日 · 18:30';
    detail.textContent = kind === 'crowd' ? '南瓜灯、紫色射灯与入场观众' : '市中心大剧院售票处';
  }
  panel.append(heading, detail);
}

function renderPrologueBeat() {
  stopPrologueMedia();
  const beat = PROLOGUE[prologueIndex];
  if (!beat) return finishPrologue();
  const run = ++prologueRun;
  $('#prologueProgress').textContent = `${String(prologueIndex + 1).padStart(2, '0')} / ${PROLOGUE.length}`;
  $('#prologueSpeaker').textContent = beat.speaker;
  $('#prologueText').textContent = beat.text;
  $('#prologueText').classList.remove('appear');
  void $('#prologueText').offsetWidth;
  $('#prologueText').classList.add('appear');
  $('#prologueLin').classList.toggle('speaking', beat.focus === 'lin' || beat.focus === 'both');
  $('#prologueLan').classList.toggle('speaking', beat.focus === 'lan' || beat.focus === 'both');
  showPrologueFocus(beat.visual);
  $('#prologueAudioStatus').textContent = '正在查找配音…';
  // 主角独白不配音：与 15 幕「主角无声」一致，也不去请求不存在的 P04.mp3 等文件。
  if (beat.speaker === '林夏') {
    schedulePrologueFallback(beat, run, '主角独白 · 按阅读节奏推进');
    return;
  }
  playPrologueVoice(beat, run);
}

function nextPrologue() {
  prologueIndex += 1;
  renderPrologueBeat();
}

function finishPrologue() {
  ++prologueRun;
  stopPrologueMedia();
  onFinish();
}

const startPrologue = () => {
  prologueIndex = 0;
  prologueAuto = true;
  $('#togglePrologueAuto').textContent = '自动推进：开';
  bg('A');
  screen('prologue');
  renderPrologueBeat();
};

$('#nextPrologue').onclick = nextPrologue;
$('#skipPrologue').onclick = finishPrologue;
$('#replayPrologueVoice').onclick = () => renderPrologueBeat();
$('#togglePrologueAuto').onclick = () => {
  prologueAuto = !prologueAuto;
  $('#togglePrologueAuto').textContent = `自动推进：${prologueAuto ? '开' : '关'}`;
  if (!prologueAuto) clearTimeout(prologueTimer);
};

return startPrologue;
}