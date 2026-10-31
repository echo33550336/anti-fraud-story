const $ = selector => document.querySelector(selector);
// 同源部署（后端同时托管 frontend/）时用相对路径；本地分开调试（静态服务 8080）时回落到 5000。
const API_BASE = window.ANTIFRAUD_API_BASE !== undefined
  ? window.ANTIFRAUD_API_BASE
  : (location.port === '8080' ? 'http://localhost:5000' : '');
let sessionId = null;
let activeNode = null;
let busy = false;
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
  ['cover', 'game', 'end'].forEach(item => $('#'+item).classList.toggle('hidden', item !== name));
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

async function post(path, payload) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(result.error || `请求失败（${response.status}）`);
  return result;
}

function setBusy(value) {
  busy = value;
  $('#start').disabled = value;
  $('#again').disabled = value;
  $('#submitAnswer').disabled = value;
  $('#choices').querySelectorAll('button').forEach(button => { button.disabled = value; });
}

function render(node, progress) {
  if (!node) return;
  activeNode = node;
  screen('game');
  bg(node.bg);
  const number = Number(node.id.slice(1));
  setText($('#progressLabel'), `节点 ${String(number).padStart(2, '0')} / ${progress.total || 15}`);
  $('#progressBar').style.width = `${Math.min(100, number / (progress.total || 15) * 100)}%`;
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
    try {
      if (window.GameAudio) GameAudio.sfx(node.id === 'N02' ? 'ring' : 'message');
    } catch (error) {
      console.warn('phone sfx failed', error);
    }
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
  setText($('#status'), node.free ? '自由回答 · 由后端识别并推进' : '固定选项 · 由后端记录并推进');
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
  if (!review || !review.ending_id) throw new Error('后端没有返回完整结局复盘');
  activeNode = null;
  screen('end');
  bg('end');
  if (window.GameAudio) {
    try {
      GameAudio.sfx(['危险', '高风险', '警示'].indexOf(review.rating) !== -1 ? 'bad' : 'good');
    } catch (error) {
      console.warn('review sfx failed', error);
    }
  }
  setText($('#endingTitle'), review.title);
  setText($('#rating'), `${review.ending_id} · ${review.rating}`);
  animateScore(review.score);
  setText($('#scoreLabel'), ' / 100 · 后端评分');
  setText($('#endingStory'), review.narration);
  setText($('#summary'), review.note);
  $('#badges').replaceChildren();
  (review.badges || []).forEach(name => {
    const badge = document.createElement('span');
    badge.className = 'badge';
    badge.textContent = `✦ ${typeof name === 'string' ? name : name.name}`;
    $('#badges').append(badge);
  });
  setBusy(false);
}

async function startSession() {
  if (busy) return;
  setBusy(true);
  if (window.GameAudio) {
    try {
      GameAudio.unlock();
      GameAudio.sfx('click');
    } catch (error) {
      console.warn('audio start failed', error);
    }
  }
  try {
    const result = await post('/api/story/start', {});
    sessionId = result.session_id;
    render(result.node, result.progress || {});
  } catch (error) {
    setBusy(false);
    toast(`无法连接后端：${error.message}`);
  }
}

async function choose(option) {
  if (busy || !sessionId || !activeNode) return;
  setBusy(true);
  if (window.GameAudio) {
    try {
      GameAudio.sfx('click');
      if (/支付|转账|付款|购买/.test(option.text || '')) GameAudio.sfx('pay');
    } catch (error) {
      console.warn('choice sfx failed', error);
    }
  }
  try {
    const result = await post('/api/story/answer', {
      session_id: sessionId,
      node_id: activeNode.id,
      option_id: option.id
    });
    if (result.status === 'finished') showReview(result.review);
    else render(result.next_node, result.progress || {});
  } catch (error) {
    setBusy(false);
    toast(`选项未提交：${error.message}`);
  }
}

async function submitFreeAnswer() {
  if (busy || !sessionId || !activeNode) return;
  const text = $('#answer').value.trim();
  if (text.length < 4) {
    toast('请写下至少4个字的处理方式。');
    return;
  }
  setBusy(true);
  try {
    if (window.GameAudio) GameAudio.sfx('click');
  } catch (error) {
    console.warn('answer sfx failed', error);
  }
  try {
    const result = await post('/api/story/open', {
      session_id: sessionId,
      node_id: activeNode.id,
      text
    });
    if (result.need_confirm && !result.target) {
      setBusy(false);
      toast('后端无法从这段回答确定行动，请补充明确的处理方式。');
    } else if (result.status === 'finished') {
      showReview(result.review);
    } else if (result.next_node) {
      render(result.next_node, result.progress || {});
    } else {
      setBusy(false);
      toast('后端没有返回下一步节点。');
    }
  } catch (error) {
    setBusy(false);
    toast(`自由回答未提交：${error.message}`);
  }
}

function toast(message) {
  const element = $('#toast');
  element.textContent = message;
  element.classList.add('show');
  setTimeout(() => element.classList.remove('show'), 2600);
}

function returnToCover() {
  sessionId = null;
  activeNode = null;
  bg('cover');
  screen('cover');
}

$('#start').onclick = startSession;
$('#again').onclick = startSession;
$('#submitAnswer').onclick = submitFreeAnswer;
$('#restartTop').onclick = returnToCover;
bg('cover');
