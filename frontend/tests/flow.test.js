import test from 'node:test';
import assert from 'node:assert/strict';
import { createDemoClient } from '../src/engine.js';
import { E, S, STORY_ID } from '../src/story.js';
import { PROLOGUE } from '../src/prologue.js';

test('交付数据覆盖 15 节点、16 结局及 25 句序章', () => {
  assert.equal(Object.keys(S).length, 15);
  assert.equal(Object.keys(E).length, 16);
  assert.equal(PROLOGUE.length, 25);
  assert.deepEqual(Object.values(S).filter(node => node.free).map(node => node.title), ['独立核实', '终场前的核实']);
});

test('N03 开放回答需确认，然后可提前进入 E01', async () => {
  const game = createDemoClient();
  const started = await game.start();
  assert.equal(started.story_id, STORY_ID);
  assert.equal((await game.answer({ node_id: 'N01', option_id: 'A' })).next_node.id, 'N02');
  assert.equal((await game.answer({ node_id: 'N02', option_id: 'B' })).next_node.id, 'N03');
  const intent = await game.open({ node_id: 'N03', text: '先找剧院官方总机核实，再保留记录' });
  assert.equal(intent.suggested_option_id, 'STOP');
  assert.equal(intent.need_confirm, true);
  assert.equal((await game.confirm({ node_id: 'N03', option_id: 'STOP', open_text: '先找剧院官方总机核实，再保留记录' })).ending_id, 'E01');
  const review = await game.review();
  assert.equal(review.ending_id, 'E01');
  assert.equal(review.history.length, 3);
});

test('固定选项使用稳定 ID 且阻止重复提交', async () => {
  const game = createDemoClient();
  await game.start();
  await game.answer({ node_id: 'N01', option_id: 'B' });
  await assert.rejects(game.answer({ node_id: 'N01', option_id: 'B' }), /节点已变化/);
  assert.equal((await game.answer({ node_id: 'N02', option_id: 'A' })).next_node.id, 'N04');
  assert.equal((await game.answer({ node_id: 'N04', option_id: 'B' })).ending_id, 'E02');
  assert.equal((await game.review()).ending_id, 'E02');
});
