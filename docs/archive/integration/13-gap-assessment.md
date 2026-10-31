# 《终场前的一张票》前后端对接差距清单

> 归档审查：本文记录 2026-10-30 的改造前状态。当前实现与 API 以仓库根目录 README 和源码为准。

> 审查对象：
> - 前端：`前端源码_后端对齐包.zip`（解压到 `_incoming/frontend_fixed/`）
> - 后端：`反诈-demo-backend.zip`（解压到 `_incoming/backend/反诈陪练-demo-backend/`）
> 审查时间：2026-10-30
> 方法：读源码 + 起服务实测 + 配置自校验 + 资源存在性检查

## 0. 一句话结论

**现在还不能对接。** 这不是“差一个 fetch 地址”的问题，而是**两端跑的是两套不同的游戏模型**：

- 前端是完整的离线剧情游戏：15 个节点、13 个二选一 + 2 个自由回答（N03、N15）、16 个 E 结局、本地评分/徽章，选项可以中途直接跳结局。
- 后端是另一套确定性引擎：15 个线性节点、10 个二选一 + 5 个三选一、3 个开放题（N12–N14）、16 个 R/P 结局、七维评分，必须走完 15 步才结算。
- 前端没有真正调用后端；`examples/backend-adapter.example.js` 里的 `/api/free-answer`、`/api/result` 后端都不存在；后端也没有 CORS。
- 后端配置虽然已经把标题改成《终场前的一张票》，但 README、08 文档、开放题位置、结局体系仍是“两张票/七维/R 结局”的旧模型，属于**半迁移状态**。

结论：**先定“哪一套剧情和结局是权威”，再写对接层。** 否则会把两套规则硬拼在一起，出现“前端跳 E05、后端算 R12”“前端没走完 15 步、后端无法结算”这类问题。

---

## 1. 两个包各自是什么

### 1.1 前端（可直接离线跑）

关键文件：

- `index.html`：只加载 `src/story.js` 和 `src/game.js`，**没有加载 adapter**。
- `src/story.js`：15 个节点（`S`）+ 16 个结局（`E`，E01–E16）+ 美工资源映射。
- `src/game.js`：本地状态、选择跳转、自由回答关键词路由、本地评分/徽章、结局展示。
- `examples/backend-adapter.example.js`：对接示例，默认不加载。
- `接口对齐.md`：前端作者自己列出的接入点和待统一事项（已明确指出旧后端不兼容）。
- `美工/`：15 张 JPEG；用 PowerShell 直接解压会因文件名编码失败，需按 GBK 恢复（见 §5.4）。

前端实测：

- `node --check` 通过；
- 用 `python -m http.server` 起静态服务，`index.html` 200，15 个美工资源全部 200；
- **但页面完全不发网络请求**，所有选择、评分、结局都在本地完成。

### 1.2 后端（确定性引擎，能自洽，但不是前端的剧情）

关键文件：

- `app.py`：标准库 HTTP 服务，只提供 `/api/story/*`。
- `game/config/story_15nodes.json`：15 节点、16 结局、23 条变体；标题已是“终场前的一张票”，但结构和文本是另一套。
- `game/engine.py`、`game/sessions.py`、`game/schemas.py`、`scripts/validate_config.py`。
- `README.md`、`08-完整15步剧情与16结局.md`：仍是旧版《终场前的两张票》的口径。

后端实测：

- `python scripts/validate_config.py` 通过：248,832 条封闭组合、16/16 结局可达、16 条见证路径参考分匹配。
- `POST /api/story/start` 能返回 N01；固定选项 `POST /api/story/answer` 能推进。
- `POST /api/story/open` 在 N03 返回 `400 当前节点不接受开放回答`。
- `OPTIONS /api/story/start` 返回 `501 Unsupported method`，响应没有 `Access-Control-Allow-Origin`。
- 未结束时 `GET /api/story/review` 返回 `409 演练尚未结束`。

> 重要：后端自校验通过，只证明“后端自己那套 15 步/七维/16 R 结局是自洽的”，**不证明它能接前端**。

---

## 2. 最硬的差距：两套剧情/结局模型

| 维度 | 前端 | 后端 | 结果 |
|---|---|---|---|
| 节点形态 | 15 个节点，13 个二选一 + 2 个自由回答（N03、N15） | 15 个线性节点，10 个二选一 + 5 个三选一，开放题在 N12–N14 | 节点数量一样，**节点语义和选项数完全不同** |
| 跳转方式 | 每个选项直接给 `next` 节点或 `E` 结局；N02→N03/N04，N03→E01/4，N04→5/E02…… | 每个节点固定 `next` 到下一节点，选项只写状态；结局只能在 N15 后由 `build_review` 路由 | 后端无法表达前端的“中途结局/分支图” |
| 结局 | E01–E16，带标题、评级、故事、点评；E15/E16 还是补充规则 | R01–R14 + P01/P02，带 priority、loss 条件、七维参考分 | **两套 16 结局，ID 和语义都不对应** |
| 自由回答 | N03、N15 | N12、N13、N14 | 位置完全错位 |
| 评分 | 本地 `scoreFor`：扣付款额、按结局加减，10–100 | 七维加权：50–100 整数 | 数值区间和算法都不同 |
| 徽章 | 本地 5 类中文徽章 | 7 个 ID 徽章，由 flags 判定 | 名称/数量/触发不同 |
| 状态 | `ticketPaid/secondPaid/smallPaid/investPaid/verifiedOfficial/stopped` | `ticket_loss/shop_loss/recovery_loss` + `data_submitted/auth_granted/payment_made` + `n04/n08/n12/n13` 等 | 字段不是同一套 |
| 故事粒度 | 假票务、假小岚、128 山货、188 腊味、3000 投资、追加费用、最后付款分节点展开 | 把假小岚 + 山货 + 投资压缩进 N08/N11，N12–N14 仍是旧版“解释/证据/告白” | 后端 15 节点无法一一对应前端 15 节点 |

**结论：** 不能做“ID 映射”就完事。要么前端改成后端的线性/七维/R 结局，要么后端改成前端的图结构/E 结局。两种都需要先做产品决策。

---

## 3. P0：不解决就一定跑不通

### P0-1 前端没有真正接后端

- `index.html` 只有：
  ```html
  <script src="src/story.js"></script>
  <script src="src/game.js"></script>
  ```
  没有引入 `examples/backend-adapter.example.js`。
- `game.js` 的 `choose()` 直接改本地 `current`/`state`，不等待任何 HTTP 响应。
- `ending()` 用本地 `E` 表显示结局；`backendResult` 只有在 `ending_id` 与本地一致时才覆盖分数/徽章。
- 因此当前页面是**纯离线演示**，不是“接了一半”。

### P0-2 adapter 的端点后端不存在

`examples/backend-adapter.example.js` 期望：

- `POST {API_BASE}/api/free-answer`，返回 `{target: "E01"}` 或 `{target: 4}`
- `POST {API_BASE}/api/result`，返回 `{ending_id, score, badges}`

后端实际只有：

- `POST /api/story/start`
- `POST /api/story/answer`
- `POST /api/story/open`
- `POST /api/story/confirm`
- `GET /api/story/state`
- `POST /api/story/stop`
- `GET /api/story/review`

`/api/free-answer` 和 `/api/result` 都是 404。adapter 还默认 `API_BASE = 'http://localhost:8000'`，后端默认端口是 `5000`。

### P0-3 接口协议不匹配

| 前端期望 | 后端实际 | 差距 |
|---|---|---|
| 自由回答一次返回 `target`/`ending_id` | `/api/story/open` 只返回 intent/suggested_option_id/need_confirm，还要 `/api/story/confirm` | 前端没有“意图确认”UI |
| 固定选项只带 label 和本地 target | `/api/story/answer` 要 `{session_id,node_id,option_id}` | 前端没有 `session_id`，选项没有 `option_id` |
| 结束由本地 `E` 表决定 | `/api/story/review?session_id=` 才有结局/分数/徽章 | 前端没有 session，也不请求 review |
| 前端 `history` 只有 `{node,answer}` | 后端日志要 node/option/source/intent | 历史不可作为权威路径 |
| 前端 `state` 是本地金额字段 | 后端是 loss counters + flags | 不能直接透传 |

### P0-4 自由回答节点错位

- 前端：N03（是否官方核实）、N15（核实/举报/删除/分享），其余 13 个节点固定选项。
- 后端：N12、N13、N14 开放；N03、N15 都是固定选项。
- 实测：在后端走到 N03 后 `POST /api/story/open` 返回 **400 当前节点不接受开放回答**。
- 即使把 N15 文本发过去，后端 N15 只接受 A/B，不会返回 E11–E14。

### P0-5 CORS / 预检缺失

前端如果跑在 `http://localhost:8080`，后端在 `http://127.0.0.1:5000`，浏览器会：

1. 发送 `OPTIONS` 预检；
2. 后端 `BaseHTTPRequestHandler` 没有 `do_OPTIONS`，返回 **501**；
3. 响应没有 `Access-Control-Allow-Origin`，跨域 POST 被浏览器拦截。

实测：

```text
OPTIONS /api/story/start -> 501 Unsupported method ('OPTIONS')
POST    /api/story/start -> 200，但响应头没有 Access-Control-Allow-Origin
```

不解决这一条，前端永远调不通本地后端（除非改成同源反向代理）。

### P0-6 后端 review 不能直接给前端用

后端 `build_review()` 返回：

```json
{
  "ending_id": "R01",
  "score": 88,
  "dimensions": {"funds": 2, "...": "..."},
  "badges": ["authorization_guardian", "..."],
  "romance_choice": "A",
  "witness_path": ["A", "B", "..."]
}
```

前端需要的是：

```js
E12 = ["证据保全，积极反诈", "优秀", "林夏整理……", "及时求助……"]
```

差距：

- ID 体系不同：`R01` vs `E01`；
- 没有 `title`、`rating`、`narration`、`next_step`；
- 徽章返回 ID，前端显示中文名称，需要映射；
- 前端本地 `E` 结局已经渲染，后端如果返回不同结局，前端 `setGameResult` 不支持改写结局（只允许同一 ID 覆盖分数/徽章）。

### P0-7 后端节点缺少前端展示字段

后端 `_public_node()` 返回：

```json
{"id","act","time","scene","lines","prompt","ui_option_order","options","variant_id"}
```

前端 `S` 需要：

```js
{title, time, bg, person, speaker, text, phone, prop, options}
```

后端没有 `title/bg/person/phone/prop`，`scene+lines` 也不是前端 `text` 的写法。若让后端做剧情源，前端必须：

- 要么按节点 ID 维护一份“展示元数据映射”（bg/person/phone/prop）；
- 要么扩展后端节点协议，返回这些展示字段。

### P0-8 选项 ID / 历史 / 状态不可信

- 前端 `story.js` 的选项是 `[label, target]`，没有 `option_id`。
- 前端 `history` 记的是 `{node, answer: "选项文字"}`，文案一改就无法回放。
- 前端 `state` 由本地 `choose()` 直接加金额；后端不应接受客户端传来的金额/已付事实。
- 若接后端，必须改成：
  - `options: [{id, text, next|ending}]`；
  - 提交 `{session_id, node_id, option_id}`；
  - 金额、付款、授权、资料暴露全部由后端根据选项重算。

### P0-9 后端只支持“走完 15 步”的结算，前端允许提前结局

- 前端 N03 选“官方核实”直接到 E01；N04 拒绝付款到 E02；N07 不通过好友到 E04……
- 后端 `compute_dimensions()` 要求 N08、N12、N13 都已有选择；`build_review()` 要求 `n11_seen`。
- 提前结束的路径在后端根本算不出七维/结局，必须新增“提前结局”路由或改成前端图引擎。

---

## 4. P1：能跑通后必须补的

1. **后端配置是半迁移状态**
   - 配置标题是“终场前的一张票”，但 `README.md`、`08-完整15步剧情与16结局.md`、`meta.source_of_truth` 仍是《终场前的两张票》。
   - `acts` 的 A3/A4/A5 时间还是 15:52/15:58/16:06，节点 N12 还是 16:03，和“10月27日/次日”的剧情时间不一致。
   - N12–N14 仍是旧版“解释/证据/告白”，不是前端的“3000 投资/追加费用/最终核实”。
   - N08 把“假小岚 + 128 山货 + 188 腊味 + 3000 投资”压成一个节点，前端是 N08–N14 六个节点。
2. **23 条变体没有前端渲染方案**
   - 后端变体覆盖 `contact_closed`、`ticket_loss`、`shop_loss`、`recovery_loss`、`identity_confirmed`、`n12` 等条件；前端本地 `S` 没有变体概念。
   - 若后端做剧情源，前端必须渲染 `variant_id` 对应的 `scene/lines/options`，不能继续读本地 `S`。
3. **评分/徽章/评级语义不同**
   - 前端 E 结局有“优秀/良好/危险/警示/高风险/完美”评级，后端只有 50–100 分和七维。
   - 前端 `scoreFor` 和 `badgesFor` 是本地演示值；后端七维是另一套完成度。两者不能同时显示，必须先定权威。
4. **自由回答确认流程缺失**
   - 后端 `open` 返回 `need_confirm: true`，必须 `confirm` 后才写入状态；前端现在提交后直接跳转，没有确认卡。
   - 后端对 N12/N13/N14 的关键词表仍指旧选项语义；若改用 N03/N15，需要重写 `_INTENT_RULES`。
5. **会话/重开/中途停止**
   - 前端 `reset()` 只重置本地变量；后端要 `POST /api/story/start` 建新 session。
   - 前端“重开”应清掉旧 `session_id`；后端 session 2 小时 TTL、内存态，多进程会丢。
   - 前端没有“中途停止/已发生选择复盘”的入口；后端有 `/api/story/stop`。
6. **错误与加载状态**
   - 前端没有 loading/网络错误/超时 UI；后端错误返回 `{error}`，前端需要统一处理。
   - 后端 409（节点不匹配/重复作答）、422（敏感信息）需要前端提示。
7. **展示闭环**
   - 前端的 `phone` 气泡、`prop`、立绘、背景、场景标题，后端都没有；需要展示映射或协议扩展。
   - 后端 `answer` 返回的 `response`（选项即时回应）前端目前完全不显示——前端是选择后直接跳节点，缺少“回应”这一拍。
8. **结局文案归属**
   - 前端 `E` 表已经写死 16 段结局文案；后端 `endings` 也有 16 段不同文案。
   - 必须二选一：前端保留文案、后端只给分数/徽章；或后端给完整结局、前端删本地 `E` 表。

---

## 5. P2：交付/部署/资源问题

### 5.1 静态资源包编码

前端 zip 里 `美工/`、`接口对齐.md`、剧情 md 的文件名是 **GBK 字节、未打 UTF-8 标志**：

- 用 PowerShell `Expand-Archive` 会报“无法处理无效的存档条目”，美工目录整个丢失；
- 用 Python `zipfile` 按 `cp437 -> gbk` 恢复后才能得到 15 张图。

建议：

- 重新打包时把文件名改成 ASCII（如 `art/bg-a.jpg`），或把 zip 标记为 UTF-8；
- README 里写清“若解压后没有 `美工/`，说明解压工具不识别文件名编码”，避免演示现场丢图。

### 5.2 服务形态

- 前端是纯静态文件，后端是 Python 标准库 HTTP；两者默认不同端口、不同源。
- 需要选一种：
  - 同源反向代理（推荐演示）：`/api/*` 反代到后端，前端和 API 同源，免 CORS；
  - 或给后端加 CORS 头 + `do_OPTIONS`。
- 前端 `API_BASE` 不能写死 `localhost:8000`，要用环境配置或同源相对路径 `/api`。
- 公网部署时后端要设 `HOST=0.0.0.0`/`ALLOW_PUBLIC=1`；前端要 HTTPS，否则混合内容拦截。

### 5.3 运行/测试

- 后端只用标准库，无 `requirements.txt`，Python 3.7 实测可跑；但如果部署环境是 3.10+ 也建议写明版本。
- 后端 session 在内存，单进程；Render/Docker 多 worker 会丢会话。
- 没有前后端联调的 e2e 用例；`validate_config.py` 只验证后端自己的封闭选项，不验证前端路径。
- 前端没有构建步骤，`index.html` 直接打开/file:// 也能跑，但接 API 后必须用 http(s) 起服务（file:// 的 fetch 会被限制）。

### 5.4 其他

- 前端 `setGameResult` 不支持改写结局，只支持同 ID 覆盖分数/徽章；如果要后端决定结局，需要改 `ending()`。
- 前端 `scoreLabel` 写死“本地演示评分”；接入后要区分“后端评分/本地回退”。
- 后端 `review` 不含结局标题/旁白；`/api/story/state` 不含开放题标记；前端无法知道当前节点是否自由回答（只能靠本地 `free` 字段）。
- 后端 `app.py` 无请求日志脱敏；开放题里的手机号/身份证由 `sessions.py` 拦截，但日志仍建议不要打印正文。

---

## 6. 三条可选路线（先做决策）

### 方案 A：兼容层，最快让现有前端“看起来接了后端”（1–2 天）

保留前端剧情、E 结局、本地图；后端只做两件事：

1. `POST /api/free-answer`：接收 `{node_id, text, history, state}`，对 N03/N15 返回 `{target}`（E01 或 4；E11/E12/E13/E14）；
2. `POST /api/result`：接收前端 `game:ended` 的 `{ending_id, history, state}`，返回同 `ending_id` 的权威 `score`/`badges`。

需要：

- 把前端 `freeRoute`、`scoreFor`、`badgesFor` 的规则重写到后端（或后端调用一个小规则表）；
- 打开 CORS；
- 在 `index.html` 里加载 adapter；
- 前端 `ending_id` 保持不变，后端只覆盖分数/徽章。

优点：改动小、前端美术/剧情不动、演示能跑。
缺点：前端仍是本地跳转，后端不掌握完整路径，金额/结局可被前端改；**适合演示，不适合作为“权威复盘”**。

### 方案 B：前端为产品口径，后端改成图引擎（推荐正式版，3–5 天）

以现有前端剧情/美术/E 结局为准：

- 新建“图结构”剧情配置：节点、选项 ID、每个选项的 `next` 或 `ending`、N03/N15 自由回答、E01–E16 结局；
- 后端保留 HTTP/session 骨架、错误码、敏感信息拦截、校验脚本；
- 增加：提前结局、E 结局、自由回答 N03/N15 的意图映射、review 返回标题/评级/旁白/点评；
- 前端：选项加 `option_id`，引入 adapter，`choose` 改为等待 `/api/story/answer`，结局从 `/api/story/review` 取；
- 展示：后端返回节点展示字段，或前端保留按节点 ID 的 `bg/person/phone/prop` 映射；
- CORS/同源代理。

优点：保留现有前端体验和美术，后端真正权威。
缺点：后端剧情层基本重写；需要产品确认 E 结局和评分口径。

### 方案 C：后端为权威，前端改成后端剧情（2–3 天）

保留后端的 15 步/七维/R 结局：

- 把前端 `story.js` 的 15 节点、E 结局替换成后端 config 的 N01–N15、R01–R14/P01/P02；
- 把前端自由回答 N03/N15 改成 N12–N14；
- 前端流程改为“每步等后端”；
- 前端现有“假小岚/山货/投资”的分节点剧情要压缩/重写，E15/E16 规则删除。

优点：后端评分/校验/16 结局直接可用。
缺点：前端剧情和美术大量返工，体验会变；不建议在现有展示版本上做。

### 建议

- 如果**比赛演示优先**：先做 **方案 A**，把“能跑”解决；同时明确它是演示级，不宣称后端权威。
- 如果**评审要求后端权威/可复盘**：做 **方案 B**，以前端剧情为准重建后端剧情层。
- 如果**后端七维/16 R 结局是硬指标**：只能做 **方案 C**，但要接受前端剧情重写。
- **不要**直接把两套 16 结局做 ID 映射糊在一起——语义不对应，复盘会自相矛盾。

---

## 7. 推荐方案 B 的落地清单

### 7.1 先定契约

建议统一成一组接口（名字可沿用 `/api/story/*`）：

```http
POST /api/story/start
  -> { session_id, node, progress }

POST /api/story/answer
  { session_id, node_id, option_id }
  -> { response, next_node, ending_id?, progress }
  // next_node 和 ending_id 二选一

POST /api/story/open
  { session_id, node_id, text }
  -> { intent, suggested_option_id, need_confirm }

POST /api/story/confirm
  { session_id, node_id, option_id, open_text }
  -> { response, next_node, ending_id?, progress }

GET  /api/story/review?session_id=
  -> { ending_id, title, rating, narration, next_step, score, badges, dimensions?, review }

POST /api/story/stop
  -> { review: { status, completed, total, choices } }
```

`node` 至少包含：

```json
{
  "id": "N03",
  "act": "A1",
  "time": "10月27日 · 稍后",
  "title": "独立核实",
  "scene": "……",
  "lines": [{"speaker": "剧院总机", "text": "……"}],
  "prompt": "自由回答：……",
  "free": true,
  "ui_option_order": [],
  "options": [],
  "presentation": {"bg": "C", "person": "alert", "speaker": "剧院总机", "phone": [], "prop": null},
  "variant_id": "default"
}
```

### 7.2 前端改动

1. `index.html` 在 `game.js` 后加载 adapter（或把 adapter 合并进 `game.js`）。
2. `story.js` 的选项改成带 ID：
   ```js
   options: [
     {id: "A", text: "查看票面……", next: 2},
     {id: "B", text: "收好票……", next: 2}
   ]
   ```
3. `game.js`：
   - `reset()` 调 `POST /start`，保存 `session_id`；
   - `choose(optionId)` 改为 `await POST /answer`，按 `next_node`/`ending_id` 渲染；
   - 自由回答 `POST /open`，展示 `need_confirm` 确认卡，再 `POST /confirm`；
   - 结束调 `GET /review`，用后端 `title/rating/narration/score/badges` 渲染；
   - 删除/降级本地 `scoreFor`/`badgesFor`，只作离线回退；
   - 加 loading/error/重试/防重复提交。
4. 展示映射：若后端不返回 `bg/person/phone/prop`，前端按 `node.id` 维护一张展示表；剧情文本、选项、回应全部用后端返回，不再读本地 `S`。
5. `history` 改成 `{node_id, option_id, source}`；不要把本地金额当权威。

### 7.3 后端改动

1. 剧情配置从“线性 next”改为“每个选项带 next/ending 的图”；
2. 增加 E01–E16（标题/评级/旁白/点评/参考分/触发条件）；
3. N03/N15 开放回答规则（intent → target/ending）；
4. 提前结局路由；
5. `review` 返回结局文案、徽章中文名、维度/见证路径；
6. CORS 或同源反代；
7. 端到端用例：16 个 E 结局各一条路径、N03 两条、N15 四条、提前结局、重复提交、关闭会话。

### 7.4 验收用例（最小）

- `N01→N02→N03` 自由回答“找剧院官方核实” → 返回 `E01`，前端显示 E01；
- `N02→N04→N05` 模拟付 900 → `N05→N06` 拒绝二次转账 → `E04`/`E15`（按统一后的规则）；
- `N15` 自由回答四种意图 → `E11/E12/E13/E14`；
- 任意早结局路径不应要求 N08/N12/N13；
- `OPTIONS` 预检 200 + `Access-Control-Allow-Origin`；
- 刷新/重开生成新 `session_id`；
- 前端资源 15/15 加载；
- 后端 `validate_config.py` 与前端路径测试同时通过。

---

## 8. 待产品确认

1. **权威剧情/结局是哪套？** 前端 E01–E16，还是后端 R01–R14/P01–P02？
2. **权威评分是哪套？** 前端本地 `scoreFor`，还是后端七维 50–100？
3. **自由回答节点确认**：N03/N15（前端）还是 N12–N14（后端）？
4. **现有前端美术/剧情是否必须保留？** 决定选 B 还是 C。
5. **部署形态**：同源反代还是跨域 CORS？
6. **后端是否允许重写 config/engine？** 方案 B 需要。
7. **“中途结局”是否保留？** 前端现在大量提前结局，后端线性模型不支持。

---

## 9. 附：实测记录

### 9.1 后端

```text
python scripts/validate_config.py
配置结构: 15 节点、16 结局、7 徽章
封闭选项组合: 248832
可达结局: 16/16
见证路径: 16/16，参考分精确匹配
早断联: N05-N07 未产生资料、授权或付款暴露
恋爱分支: A/B/C 不改变安全维度、结局或分数
```

```text
POST /api/story/start -> 200，node 字段无 title/bg/person/phone/prop
POST /api/story/answer (N01,A) -> 200，next=N02
POST /api/story/open  (N03,text) -> 400 当前节点不接受开放回答
OPTIONS /api/story/start -> 501 Unsupported method
GET  /api/story/review (未结束) -> 409 演练尚未结束
```

### 9.2 前端

```text
node --check src/game.js / src/story.js / examples/backend-adapter.example.js -> 无语法错误
python -m http.server 8081 -> index 200
美工资源 15/15 -> 200 image/jpeg
index.html 未加载 backend-adapter
```

### 9.3 资源编码

```text
PowerShell Expand-Archive:
  无法处理无效的存档条目“����/ͷ��A.jpeg” ...
  美工/ 未解出
Python zipfile:
  raw name -> cp437 -> gbk 后恢复：
  美工/背景A：校园外与节日入口.jpeg 等 15 张
```

---

## 10. 注意：不要和另一版剧情混用

工作区里还有一套 `11-万圣节的一张票-完整剧情文本.md` / `12-万圣节的一张票-15步映射与前端落地.md`，那是**另一个故事**（万圣节赠票、短信链接、假小岚、19:10 来电、线下赠票）。本报告分析的两个 zip 是《终场前的一张票》（大剧院售票处、900 元补差、山货、3000 投资、E01–E16）。两者剧情、结局 ID、节点逻辑都不同，**不要把这些文档和这两个包混着接**。
