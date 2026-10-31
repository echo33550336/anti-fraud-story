const $ = selector => document.querySelector(selector);
const API_BASE = window.ANTIFRAUD_API_BASE || 'http://localhost:5000';
let sessionId = null;
let activeNode = null;
let busy = false;

function bg(key) {
  $('#back').style.backgroundImage = `url("${encodeURI(assets[key] || assets.cover)}")`;
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
  (node.text || '').split('\n').forEach(line => {
    const paragraph = document.createElement('p');
    paragraph.textContent = line;
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

function showReview(review) {
  if (!review || !review.ending_id) throw new Error('后端没有返回完整结局复盘');
  activeNode = null;
  screen('end');
  bg('end');
  setText($('#endingTitle'), review.title);
  setText($('#rating'), `${review.ending_id} · ${review.rating}`);
  setText($('#score'), review.score);
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
