// 穷举 one-ticket-v1 剧情图，检查 16 个结局是否都可达。
// 用法：node tools/check-reachability.mjs
import { createDemoClient } from '../src/engine.js';
import { S, E } from '../src/story.js';

const FREE = { N03: ['STOP', 'CONTINUE'], N15: ['VERIFY', 'REPORT', 'DELETE', 'SHARE'] };
const key = n => 'N' + String(n).padStart(2, '0');

// 按一条确定的答案序列重放整局
async function run(steps) {
  const c = createDemoClient();
  let cur = (await c.start()).node;
  for (const s of steps) {
    if (s.node !== cur.id) return { error: `节点错位：期望 ${cur.id}，得到 ${s.node}` };
    const free = !!S[Number(cur.id.slice(1))].free;
    const r = free
      ? await c.confirm({ node_id: cur.id, option_id: s.option, open_text: '（穷举）' })
      : await c.answer({ node_id: cur.id, option_id: s.option });
    if (r.ending_id) return { ending: r.ending_id, review: await c.review() };
    cur = r.next_node;
  }
  return { node: cur.id };
}

const reached = new Map();   // endingId -> 示例路径
const visited = new Set();
let paths = 0, deadEnds = [];

async function dfs(steps) {
  const r = await run(steps);
  if (r.error) { deadEnds.push({ steps, error: r.error }); return; }
  if (r.ending) {
    paths++;
    if (!reached.has(r.ending)) reached.set(r.ending, { steps, review: r.review });
    return;
  }
  const cur = r.node;
  if (visited.has(cur + '|' + steps.length) && steps.length > 14) return;
  visited.add(cur + '|' + steps.length);
  const number = Number(cur.slice(1));
  const node = S[number];
  const opts = node.free ? FREE[cur] : (node.options || []).map((_, i) => String.fromCharCode(65 + i));
  if (!opts) { deadEnds.push({ steps, error: `${cur} 既无选项也无自由回答` }); return; }
  for (const o of opts) await dfs(steps.concat({ node: cur, option: o }));
}

await dfs([]);

const all = Object.keys(E);
const missing = all.filter(id => !reached.has(id));

console.log(`已枚举终局路径：${paths} 条`);
console.log(`可达结局：${reached.size} / ${all.length}`);
if (missing.length) {
  console.log(`\n不可达结局：${missing.join(', ')}`);
} else {
  console.log('全部 16 个结局均可达 ✓');
}
if (deadEnds.length) {
  console.log(`\n异常路径 ${deadEnds.length} 条，示例：`);
  for (const d of deadEnds.slice(0, 3)) console.log('  ', d.error, JSON.stringify(d.steps.slice(-3)));
}

console.log('\n每个结局的最短路径：');
for (const id of all) {
  const hit = reached.get(id);
  if (!hit) { console.log(`  ${id}  —  不可达`); continue; }
  const short = [...hit.steps];
  console.log(`  ${id}  ${String(short.length).padStart(2)} 步  ` +
    short.map(s => `${s.node}:${s.option}`).join(' → '));
}

// 分数区间
const scores = [...reached.entries()].map(([id, h]) => `${id}=${h.review.score}(${h.review.rating})`);
console.log('\n演示引擎给出的分数：');
console.log('  ' + scores.join('  '));
