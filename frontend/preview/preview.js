// 独立视觉预览：使用现有美工资源，直接双击 preview.html 即可运行。
const root = document.querySelector('#preview');
const art = name => `./public/art/${name}.jpg`;
const scenes = [
  { chapter:'序章 · 售票处的重逢', place:'10月27日 · 大剧院', bg:'A', left:'lin', right:'lan', speaker:'小岚', text:'别买了。我这儿有员工内部票——每个员工每月两张福利票，我这月的还没用。送你。', note:'员工内部赠票 · 不对外销售', choices:null },
  { chapter:'第二幕 · 陌生来电', place:'10月27日 · 回家途中', bg:'B', left:'alert', right:'caller', speaker:'自称票务部的人', text:'这张员工票需要补差。您加我微信，转900元，我马上帮您把票状态改好。', note:'来电 · 本市号码 · 未知联系人', choices:['先不添加，自己核实剧院规定','添加微信，听他进一步解释'] },
  { chapter:'第三幕 · 主动核实', place:'独立拨打剧院总机', bg:'C', left:'alert', right:'caller2', speaker:'剧院总机', text:'员工内部赠票凭票入场，没有补差这一说。', note:'剧院官方总机 · 独立拨打', choices:['停止联系，保存来电记录','继续听对方解释'] }
];
let index = -1;
function showCover(){
  index=-1;
  root.innerHTML=`<main class="view cover" style="--bg:url('${art('cover')}')"><div class="veil"></div><div class="cover-card"><div class="eyebrow">HALLOWEEN · 反诈互动剧情</div><h1>真票假局</h1><p class="subtitle">一张真票，两场骗局，十五次选择。</p><p>多年未见的小岚送来一张演出票。离开剧院后，一通掌握票面信息的陌生来电，改变了林夏的夜晚。</p><button id="start">进入预览 <span>→</span></button><small>独立视觉预览 · 使用 frontend-js2 的现有素材</small></div></main>`;
  document.querySelector('#start').onclick=()=>showScene(0);
}
function showScene(n){
  index=n;
  const s=scenes[n];
  const options=s.choices?`<div class="choices">${s.choices.map((x,i)=>`<button data-choice="${i}"><b>0${i+1}</b>${x}<span>↗</span></button>`).join('')}</div>`:`<button class="continue" id="continue">继续剧情 →</button>`;
  root.innerHTML=`<main class="view game" style="--bg:url('${art(s.bg)}')"><div class="veil"></div><header><div class="brand">真票假局 <i>· 剧情预览</i></div><div class="progress">${String(n+1).padStart(2,'0')} / 03 <span><b style="width:${(n+1)/3*100}%"></b></span></div><button class="restart" id="restart">返回封面</button></header><div class="stage"><div class="chapter"><span>${s.chapter}</span><strong>${s.place}</strong></div><figure class="character ${s.speaker==='小岚'?'dim':''}"><img src="${art(s.left)}" alt="林夏"><figcaption>林夏</figcaption></figure><figure class="character right ${s.speaker==='小岚'||n>0?'active':''}"><img src="${art(s.right)}" alt="${n===0?'小岚':'未核实联系人'}"><figcaption>${n===0?'小岚':'未核实联系人'}</figcaption></figure><div class="phone"><div class="phone-top"><span class="dot"></span> 线索特写</div><div class="phone-note">${s.note}</div></div></div><section class="dialogue"><div class="name">${s.speaker}</div><p>${s.text}</p><div class="controls">${options}</div><div class="foot">演示交互 · 选择后自动推进</div></section></main>`;
  document.querySelector('#restart').onclick=showCover;
  const next=document.querySelector('#continue'); if(next) next.onclick=()=>showScene(n+1);
  document.querySelectorAll('[data-choice]').forEach(b=>b.onclick=()=>n<scenes.length-1?showScene(n+1):showEnd(b.dataset.choice));
}
function showEnd(choice){
  const safe=choice==='0';
  root.innerHTML=`<main class="view ending" style="--bg:url('${art('end')}')"><div class="veil"></div><div class="end-card"><div class="eyebrow">预览结束</div><h1>${safe?'独立核实，守住边界':'真票信息，也能被冒用'}</h1><p>${safe?'你没有把熟悉的细节直接当作身份凭证。':'对方能说出票号，仍需要通过自己找到的官方渠道核实。'}</p><div class="badge">✦ ${safe?'独立核验':'风险识别'}</div><small>这里仅演示页面效果；完整版本含15幕、16个结局和后端评分。</small><button id="again">重新预览 ↻</button></div></main>`;
  document.querySelector('#again').onclick=showCover;
}
showCover();
