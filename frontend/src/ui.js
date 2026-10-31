// 所有页面结构由 JavaScript 创建；index.html 仅加载本应用。
function el(tag, properties = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(properties)) {
    if (key === 'cls') node.className = value;
    else if (key === 'text') node.textContent = value;
    else node.setAttribute(key, value);
  }
  for (const child of children.flat(Infinity)) {
    if (child == null) continue;
    node.append(typeof child === 'string' ? document.createTextNode(child) : child);
  }
  return node;
}

const button = (id, text, cls = '') => el('button', { id, cls, type: 'button', text });
const span = (id, text = '') => el('span', { id, text });

function coverScreen() {
  const description = el('p', {},
    '一张员工赠票，两个声称认识你的人。', el('br'),
    '2026年10月27日傍晚，林夏在大剧院遇见了多年未见的小岚。', el('br'),
    '从那一刻起，每一次核实与付款，都可能改变故事的走向。');
  return el('section', { id: 'cover', cls: 'screen cover' },
    el('div', { cls: 'cover-box' },
      el('div', { cls: 'kicker', text: 'HALLOWEEN · AN INTERACTIVE ANTI-FRAUD STORY' }),
      el('h1', { text: '终场前的一张票' }),
      el('div', { cls: 'pill', text: '15个剧情节点　·　16个结局' }),
      description,
      button('start', '进入故事　→', 'start'),
      el('div', { cls: 'hint', text: '虚构反诈演练 · 游戏内付款均为模拟' }),
      el('a', { cls: 'demo-link', href: '?mode=demo', text: '没有后端？改用演示模式' })));
}

function topBar(title, right) {
  return el('header', { cls: 'top' },
    el('div', { cls: 'brand', text: title }),
    el('div', { cls: 'meta' }, right));
}

function character(id, name, src, side) {
  return el('figure', { id, cls: `prologue-character ${side}` },
    el('img', { src, alt: name }), el('figcaption', { text: name }));
}

function prologueScreen() {
  return el('section', { id: 'prologue', cls: 'screen prologue hidden', 'aria-label': '序章' },
    topBar('序章 · 售票处的重逢', [span('prologueProgress', '01 / 25'), button('skipPrologue', '跳过序章')]),
    el('div', { cls: 'prologue-stage' },
      character('prologueLin', '林夏', 'public/art/lin.webp', 'left'),
      el('div', { id: 'prologueFocus', cls: 'prologue-focus hidden', 'aria-live': 'polite' }),
      character('prologueLan', '小岚', 'public/art/lan.webp', 'right')),
    el('div', { cls: 'prologue-dialogue', 'aria-live': 'polite' },
      el('div', { id: 'prologueSpeaker', cls: 'prologue-speaker' }),
      el('div', { id: 'prologueText', cls: 'prologue-text' }),
      el('div', { cls: 'prologue-controls' },
        span('prologueAudioStatus', '配音待导入'),
        el('div', {},
          button('replayPrologueVoice', '重播语音'),
          button('togglePrologueAuto', '自动推进：开'),
          button('nextPrologue', '下一句 →')))));
}

function gameScreen() {
  const progress = el('div', { cls: 'meter' }, el('b', { id: 'progressBar' }));
  const portrait = el('figure', { id: 'portrait', cls: 'portrait' },
    el('img', { id: 'portraitImg', alt: '角色立绘' }),
    el('figcaption', { id: 'portraitName' }));
  const note = el('div', { cls: 'scene-note' },
    el('strong', { id: 'sceneTitle' }), span('sceneMeta'));
  const phone = el('div', { id: 'phone', cls: 'phone hidden' },
    el('div', { id: 'phoneHead', cls: 'phone-head', text: '虚拟手机' }),
    el('div', { id: 'phoneBody' }));
  const freeform = el('div', { id: 'freeform', cls: 'freeform hidden' },
    el('textarea', { id: 'answer', maxlength: '500', placeholder: '写下林夏会如何处理……' }),
    button('submitAnswer', '提交回答 →'));
  return el('section', { id: 'game', cls: 'screen game hidden' },
    topBar('终场前的一张票', [span('progressLabel', '节点 01 / 15'), progress,
      button('voiceToggle', '语音：开'), button('bgmToggle', '音乐：开'),
      button('motionToggle', '动效：开'), button('restartTop', '重开')]),
    el('div', { cls: 'stage' }, portrait, note, phone, el('img', { id: 'prop', cls: 'prop hidden', alt: '场景道具' })),
    el('div', { cls: 'dialogue-shell' },
      el('div', { id: 'speaker', cls: 'name' }),
      el('div', { id: 'actLabel', cls: 'act-label hidden' }),
      el('div', { id: 'beatCount', cls: 'beat-count hidden', 'aria-live': 'polite' }),
      el('div', { id: 'narrative', cls: 'narrative', 'aria-live': 'polite' }),
      el('div', { id: 'beatCtl', cls: 'beat-ctl hidden' },
        button('skipBeats', '全部展开'),
        button('nextBeat', '继续 ▸')),
      el('div', { cls: 'interact' },
        el('div', { id: 'prompt', cls: 'interact-title' }),
        el('div', { id: 'choices', cls: 'choices' }), freeform),
      el('div', { cls: 'footer' },
        span('status', '正在准备故事'),
        span('', '选择后自动推进 · 可通过重开重新体验'))));
}

function endingScreen() {
  return el('section', { id: 'end', cls: 'screen end hidden' },
    el('div', { cls: 'end-box' },
      el('div', { cls: 'kicker', style: 'text-align:center', text: 'THE STORY ENDS HERE' }),
      el('h2', { id: 'endingTitle' }),
      el('div', { id: 'rating', cls: 'end-rating' }),
      el('div', { cls: 'score' },
        el('strong', { id: 'score', text: '--' }),
        el('small', { id: 'scoreLabel', text: ' / 100 · 后端评分' })),
      el('div', { id: 'endingStory', cls: 'end-story' }),
      el('div', { id: 'summary', cls: 'summary' }),
      el('div', { id: 'badges', cls: 'badges' }),
      el('div', { cls: 'end-actions' }, button('again', '再玩一次 ↻', 'again'))));
}

export function mountApp(root) {
  root.replaceChildren(el('div', { cls: 'app' },
    el('div', { id: 'back', cls: 'back' }),
    el('div', { cls: 'shade' }),
    coverScreen(), prologueScreen(), gameScreen(), endingScreen(),
    el('div', { id: 'actCurtain', cls: 'act-curtain hidden' },
      el('span', { id: 'actCurtainKicker', cls: 'act-curtain-kicker' }),
      el('strong', { id: 'actCurtainText', cls: 'act-curtain-text' })),
    el('div', { id: 'toast', cls: 'toast' })));
}
