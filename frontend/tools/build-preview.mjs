// 从现有剧情与素材生成可直接双击打开的轻量视觉预览。
// 预览只展示页面状态，不提交答案、不调用后端。
import { writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { BEATS, ACT_NAMES } from '../src/acts.js';
import { S, E, assets } from '../src/story.js';

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const ids = ['N02', 'N08', 'N15'];
const scenes = ids.map(id => {
  const number = Number(id.slice(1));
  return { id, number, act: ACT_NAMES[number], ...S[number], beats: BEATS[id] };
});
const data = JSON.stringify({ scenes, ending: E.E14, assets }).replaceAll('<', '\\u003c');

const html = `<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>终场前的一张票 · 设计预览</title><link rel="stylesheet" href="src/styles.css">
<style>
.preview-nav{position:fixed;z-index:20;top:12px;left:50%;transform:translateX(-50%);display:flex;gap:4px;padding:5px;
  max-width:calc(100vw - 20px);overflow:auto;border:1px solid #f0c78c88;border-radius:999px;
  background:#17162be9;box-shadow:0 10px 30px #0008;backdrop-filter:blur(16px)}
.preview-nav button{white-space:nowrap;border:0;border-radius:99px;background:transparent;color:#e8d8c9;padding:7px 12px;font-size:11px}
.preview-nav button.active{background:#f2c889;color:#23182c;font-weight:700}
.preview-mark{position:fixed;z-index:21;bottom:12px;right:16px;color:#f8dcbbad;font-size:10px;letter-spacing:.08em}
.cover-box{margin-top:30px}.game .top{padding-top:34px;height:92px}
.preview-choice.selected{border-color:#ffe0a8;background:#a5648eaa;box-shadow:0 0 24px #efa86955}
.preview-hint{font-size:11px;color:#f5d8b1aa;margin:9px 0 0}
.preview-portrait.muted{filter:brightness(.78) saturate(.7)}
.preview-portrait.speaking{filter:brightness(1.08) saturate(1.05)}
@media(max-width:700px){.preview-nav{top:5px}.preview-nav button{font-size:9px;padding:6px 8px}.game .top{padding-top:45px;min-height:94px;height:auto}.preview-mark{font-size:8px}}
</style></head><body>
<div class="app"><div id="back" class="back"></div><div class="shade"></div>
<nav class="preview-nav" aria-label="页面预览切换">
  <button data-view="cover">封面</button><button data-view="N02">陌生来电</button><button data-view="N08">假熟人</button>
  <button data-view="N15">自由回答</button><button data-view="end">结算</button>
</nav>
<section id="cover" class="screen cover"><div class="cover-box">
  <div class="kicker">HALLOWEEN · INTERACTIVE ANTI-FRAUD STORY</div>
  <h1>终场前的一张票</h1><div class="pill">15 个节点 · 16 个结局</div>
  <p>一张真正的员工赠票，两个掌握细节的可疑联系人。<br>从陌生来电到“老同学”的请求，林夏需要一次次决定相信谁。</p>
  <button id="start" class="start">预览对话页　→</button><div class="hint">视觉与交互状态预览 · 不连接后端</div>
</div></section>
<section id="game" class="screen game hidden"><header class="top"><div class="brand">终场前的一张票</div>
  <div class="meta"><span id="progressLabel"></span><div class="meter"><b id="progressBar"></b></div><span>分镜预览</span></div></header>
  <div class="stage"><figure id="portrait" class="portrait preview-portrait"><img id="portraitImg" alt="角色立绘"><figcaption id="portraitName"></figcaption></figure>
    <div class="scene-note"><strong id="sceneTitle"></strong><span id="sceneMeta"></span></div>
    <div id="phone" class="phone hidden"><div id="phoneHead" class="phone-head"></div><div id="phoneBody"></div></div>
    <img id="prop" class="prop hidden" alt="场景物品"></div>
  <div class="dialogue-shell"><div id="speaker" class="name"></div><div id="actLabel" class="act-label"></div>
    <div id="beatCount" class="beat-count"></div><div id="narrative" class="narrative" aria-live="polite"></div>
    <div id="beatCtl" class="beat-ctl"><button id="skipBeats">跳到选项</button><button id="nextBeat">继续 ▸</button></div>
    <div class="interact"><div id="prompt" class="interact-title"></div><div id="choices" class="choices"></div>
      <div id="freeform" class="freeform hidden"><textarea id="answer" placeholder="在这里输入你的处理方式……"></textarea><button id="submitAnswer">提交回答 →</button></div>
      <div class="preview-hint">本页只预览分镜和交互样式；完整流程请运行 frontend-js。</div></div>
    <div class="footer"><span>点击“继续”或按空格推进</span><span>选择与自由回答不会同时出现</span></div>
  </div></section>
<section id="end" class="screen end hidden"><div class="end-box"><div class="kicker" style="text-align:center">THE STORY ENDS HERE</div>
  <h2 id="endingTitle"></h2><div id="rating" class="end-rating"></div><div class="score"><strong id="score">82</strong><small> / 100 · 演示评分</small></div>
  <div id="endingStory" class="end-story"></div><div id="summary" class="summary"></div><div id="badges" class="badges"></div>
  <div class="end-actions"><button id="again" class="again">返回封面 ↻</button></div></div></section>
<div class="preview-mark">LOCAL DESIGN PREVIEW</div></div>
<script>
const DATA = ${data};
const $ = selector => document.querySelector(selector);
let current = null, index = 0;
function background(key){ $('#back').style.backgroundImage = 'url("' + encodeURI(DATA.assets[key] || DATA.assets.B) + '")'; }
function show(view){
  for(const id of ['cover','game','end']) $('#'+id).classList.toggle('hidden',id!==view);
  document.querySelectorAll('.preview-nav button').forEach(button=>button.classList.toggle('active',button.dataset.view===(view==='game'?current?.id:view)));
}
function portraitFor(beat){
  const remote = beat.who==='票务部'||beat.who==='剧院总机'||(beat.who==='小岚'&&current.number>=8);
  const image = remote ? DATA.assets[beat.who==='票务部'?'caller':'caller2'] : DATA.assets[current.person] || DATA.assets.lin;
  if($('#portraitImg').getAttribute('src')!==image) $('#portraitImg').src=image;
  $('#portrait').classList.toggle('speaking',beat.who!=='旁白');
  $('#portrait').classList.toggle('muted',beat.who==='旁白');
  $('#portraitName').textContent=remote?(beat.who==='小岚'?'未核实的微信账号':beat.who):'林夏';
  $('#speaker').textContent=beat.who==='小岚'&&current.number>=8?'自称“小岚”的账号':beat.who;
  $('#phoneHead').textContent=current.number>=8&&current.number<=14?'微信 · 身份未核实':'陌生来电 · 身份未核实';
}
function drawBeat(){
  const beat=current.beats[index]; portraitFor(beat);
  const text=$('#narrative'); text.replaceChildren();
  current.beats.slice(Math.max(0,index-1),index+1).forEach((item,i)=>{const p=document.createElement('p');p.className='beat'+(i===0&&index>0?' previous':'');p.textContent=item.text;text.append(p)});
  const messages=current.beats.slice(0,index+1).filter(item=>item.phone);
  $('#phone').classList.toggle('hidden',messages.length===0);$('#phoneBody').replaceChildren();
  for(const item of messages){const div=document.createElement('div');div.className='message';div.textContent=item.phone;$('#phoneBody').append(div)}
  $('#beatCount').textContent=(index+1)+' / '+current.beats.length;
  $('#nextBeat').textContent=index===current.beats.length-1?'显示互动 ▸':'继续 ▸';
  $('#beatCtl').classList.remove('hidden');$('#prompt').classList.add('hidden');$('#choices').classList.add('hidden');$('#freeform').classList.add('hidden');
}
function showInteraction(){
  $('#beatCtl').classList.add('hidden');$('#prompt').classList.remove('hidden');
  $('#prompt').textContent=current.prompt;
  $('#choices').replaceChildren();
  if(current.free){$('#freeform').classList.remove('hidden');$('#choices').classList.add('hidden')}
  else {$('#freeform').classList.add('hidden');$('#choices').classList.remove('hidden');
    current.options.forEach(([label],i)=>{const button=document.createElement('button');button.className='choice preview-choice';button.textContent=String.fromCharCode(65+i)+'. '+label;
      button.onclick=()=>{document.querySelectorAll('.preview-choice').forEach(x=>x.classList.remove('selected'));button.classList.add('selected')};$('#choices').append(button)})}
}
function openScene(id){ current=DATA.scenes.find(scene=>scene.id===id); if(!current)return; index=0; background(current.bg); show('game');
  $('#progressLabel').textContent='第'+current.number+'幕 · '+current.number+'/15';$('#progressBar').style.width=(current.number/15*100)+'%';
  $('#sceneTitle').textContent=current.title;$('#sceneMeta').textContent=current.time;$('#actLabel').textContent=current.act;
  $('#prop').classList.toggle('hidden',!current.prop);if(current.prop)$('#prop').src=DATA.assets[current.prop]||current.prop;
  $('#answer').value='';drawBeat();
}
function openEnding(){background('end');show('end');$('#endingTitle').textContent=DATA.ending[0];$('#rating').textContent='E14 · '+DATA.ending[1];
  $('#endingStory').textContent=DATA.ending[2];$('#summary').textContent=DATA.ending[3];$('#badges').replaceChildren();
  ['线索保管员','安全传递者'].forEach(label=>{const badge=document.createElement('span');badge.className='badge';badge.textContent='✦ '+label;$('#badges').append(badge)})}
document.querySelectorAll('.preview-nav button').forEach(button=>button.onclick=()=>{const id=button.dataset.view;if(id==='cover'){background('cover');show('cover')}else if(id==='end')openEnding();else openScene(id)});
$('#start').onclick=()=>openScene('N02');$('#again').onclick=()=>{background('cover');show('cover')};
$('#nextBeat').onclick=()=>{if(index<current.beats.length-1){index++;drawBeat()}else showInteraction()};
$('#skipBeats').onclick=()=>{index=current.beats.length-1;drawBeat();showInteraction()};
$('#submitAnswer').onclick=()=>{$('#answer').value=$('#answer').value.trim()||'先联系剧院官方总机核实身份，保存聊天与转账记录，再向平台和银行咨询止付。';$('#answer').focus()};
document.addEventListener('keydown',event=>{if(event.code==='Space'&&current&&!$('#game').classList.contains('hidden')&&!['TEXTAREA','BUTTON'].includes(event.target.tagName)&&!$('#beatCtl').classList.contains('hidden')){event.preventDefault();$('#nextBeat').click()}});
background('cover');show('cover');
</script></body></html>`;

const output = join(root, 'preview.html');
writeFileSync(output, html, 'utf8');
console.log(`已生成 ${output}（${Math.round(Buffer.byteLength(html) / 1024)} KB）`);
