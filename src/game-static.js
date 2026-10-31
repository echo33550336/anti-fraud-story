/* Static (GitHub Pages) UI for 终场前的一张票.
 * Uses StaticEngine + data/story_frontend_graph.json; no backend required. */
const $ = selector => document.querySelector(selector);
const GRAPH_URL = 'data/story_frontend_graph.json';
const TOTAL_NODES = 15;

let config = null;
let flags = {};
let history = [];
let activeNode = null;
let busy = false;
let ready = false;
let backIndex = 0;

function bg(key) {
  const url = `url("${encodeURI(assets[key] || assets.cover)}")`;
  const first = $('#back');
  const second = $('#backNext');
  if (!second) {
    first.style.backgroundImage = url;
    return;
  }
  const incoming = backIndex === 0 ? second : first;
  const outgoing = backIndex === 0 ? first : second;
  incoming.style.backgroundImage = url;
  incoming.style.opacity = '1';
  outgoing.style.opacity = '0';
  backIndex = 1 - backIndex;
}

function screen(name) {
  ['cover', 'game', 'end'].forEach(item => $('#' + item).classList.toggle('hidden', item !== name));
}

function setText(element, value) {
  element.textContent = value || '';
}

function addMessage(text) {
  const element = document.createElement('div');
  element.className = 'message';
  element.textContent = text;
  $('#phoneBody').append(element);
}

function setBusy(value) {
  busy = value;
  $('#start').disabled = value || !ready;
  $('#again').disabled = value || !ready;
  $('#submitAnswer').disabled = value;
  $('#choices').querySelectorAll('button').forEach(button => { button.disabled = value; });
}

function nodeById(nodeId) {
  return StaticEngine.getNode(config, nodeId);
}

function render(node) {
  if (!node) return;
  activeNode = node;
  screen('game');
  bg(node.bg);
  const number = Number(String(node.id).slice(1));
  setText($('#progressLabel'), `节点 ${String(number).padStart(2, '0')} / ${TOTAL_NODES}`);
  $('#progressBar').style.width = `${Math.min(100, number / TOTAL_NODES * 100)}%`;
  setText($('#sceneTitle'), node.title);
  setText($('#sceneMeta'), node.time);
  setText($('#speaker'), node.speaker);

  $('#narrative').replaceChildren();
  (node.text || '').split('\n').forEach((line, index) => {
    const paragraph = document.createElement('p');
    paragraph.textContent = line;
    paragraph.style.animationDelay = `${index * 0.06}s`;
    $('#narrative').append(paragraph);
  });
  setText($('#prompt'), node.prompt);
  const face = assets[node.person] || assets.lin;
  $('#portraitImg').src = encodeURI(face);
  setText($('#portraitName'), node.person === 'lan' || node.person === 'lan2' ? '小岚' : node.person === 'zhou' ? '阿舟' : '林夏');
  $('#prop').classList.toggle('hidden', !node.prop);
  if (node.prop) $('#prop').src = encodeURI(assets[node.prop]);
  $('#phone').classList.toggle('hidden', !node.phone || node.phone.length === 0);
  $('#phoneBody').replaceChildren();
  (node.phone || []).forEach(addMessage);
  const phoneBox = $('#phone');
  phoneBox.classList.remove('shake');
  if (node.phone && node.phone.length) {
    void phoneBox.offsetWidth;
    phoneBox.classList.add('shake');
    if (window.GameAudio) GameAudio.sfx(node.id === 'N02' ? 'ring' : 'message');
  }

  $('#choices').replaceChildren();
  $('#choices').classList.toggle('hidden', !!node.free);
  $('#freeform').classList.toggle('hidden', !node.free);
  $('#answer').value = '';
  if (!node.free) {
    node.options.forEach((option, index) => {
      const button = document.createElement('button');
      button.className = 'choice';
      const label = document.createElement('span');
      label.textContent = `${String.fromCharCode(65 + index)}.`;
      button.append(label, document.createTextNode(option.text));
      button.onclick = () => choose(option);
      $('#choices').append(button);
    });
  }
  setText($('#status'), node.free
    ? '自由回答 · 由规则引擎识别并推进'
    : '固定选项 · 由规则引擎记录并推进');
  setBusy(false);
}

function animateScore(value) {
  const element = $('#score');
  const target = Number(value) || 0;
  const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduce) {
    setText(element, target);
    return;
  }
  element.classList.remove('counting');
  void element.offsetWidth;
  element.classList.add('counting');
  const start = performance.now();
  function frame(now) {
    const progress = Math.min(1, (now - start) / 800);
    const eased = 1 - Math.pow(1 - progress, 3);
    setText(element, Math.round(target * eased));
    if (progress < 1) requestAnimationFrame(frame);
    else setText(element, target);
  }
  requestAnimationFrame(frame);
}

function showReview(review) {
  if (!review || !review.ending_id) {
    toast('结算失败：缺少结局数据。');
    return;
  }
  activeNode = null;
  screen('end');
  bg('end');
  if (window.GameAudio) {
    GameAudio.sfx(['危险', '高风险', '警示'].indexOf(review.rating) !== -1 ? 'bad' : 'good');
  }
  setText($('#endingTitle'), review.title);
  setText($('#rating'), `${review.ending_id} · ${review.rating}`);
  animateScore(review.score);
  setText($('#scoreLabel'), ' / 100 · 规则评分');
  setText($('#endingStory'), review.narration);
  setText($('#summary'), review.note);
  $('#badges').replaceChildren();
  (review.badges || []).forEach(name => {
    const badge = document.createElement('span');
    badge.className = 'badge';
    badge.textContent = `✦ ${name}`;
    $('#badges').append(badge);
  });
  setBusy(false);
}

function startSession() {
  if (busy || !ready) return;
  setBusy(true);
  if (window.GameAudio) {
    GameAudio.unlock();
    GameAudio.sfx('click');
  }
  flags = {};
  history = [];
  render(nodeById('N01'));
}

function finish(endingId) {
  const review = StaticEngine.buildReview(config, flags, endingId, history);
  showReview(review);
}

function choose(option) {
  if (busy || !activeNode) return;
  setBusy(true);
  if (window.GameAudio) {
    GameAudio.sfx('click');
    if (/支付|转账|付款|购买/.test(option.text || '')) GameAudio.sfx('pay');
  }
  try {
    const applied = StaticEngine.applyChoice(config, flags, activeNode.id, option.id);
    flags = applied.flags;
    history.push({ node: activeNode.id, option: option.id, answer: option.text });
    if (String(applied.target).startsWith('E')) finish(applied.target);
    else render(nodeById(applied.target));
  } catch (error) {
    setBusy(false);
    toast(`选项处理失败：${error.message}`);
  }
}

function submitFreeAnswer() {
  if (busy || !activeNode) return;
  const text = $('#answer').value.trim();
  if (text.length < 4) {
    toast('请写下至少4个字的处理方式。');
    return;
  }
  setBusy(true);
  if (window.GameAudio) GameAudio.sfx('click');
  try {
    const applied = StaticEngine.applyFreeAnswer(config, flags, activeNode.id, text);
    if (!applied) {
      setBusy(false);
      toast('这段回答暂时无法判断行动，请补上：核实、继续联系、保存举报、删除或分享。');
      return;
    }
    flags = applied.flags;
    history.push({ node: activeNode.id, answer: text, target: applied.target });
    if (String(applied.target).startsWith('E')) finish(applied.target);
    else render(nodeById(applied.target));
  } catch (error) {
    setBusy(false);
    toast(`自由回答处理失败：${error.message}`);
  }
}

function toast(message) {
  const element = $('#toast');
  element.textContent = message;
  element.classList.add('show');
  setTimeout(() => element.classList.remove('show'), 2800);
}

function returnToCover() {
  activeNode = null;
  bg('cover');
  screen('cover');
}

async function boot() {
  setBusy(true);
  try {
    const response = await fetch(GRAPH_URL, { cache: 'no-cache' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    config = await response.json();
    ready = true;
    bg('cover');
    screen('cover');
    setBusy(false);
    setText($('#status'), '规则引擎已就绪，点击进入故事');
  } catch (error) {
    setBusy(false);
    toast(`加载剧情配置失败：${error.message}`);
  }
}

$('#start').onclick = startSession;
$('#again').onclick = startSession;
$('#submitAnswer').onclick = submitFreeAnswer;
$('#restartTop').onclick = returnToCover;
bg('cover');
screen('cover');
setBusy(true);
boot();
