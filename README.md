# 《终场前的一张票》 | Anti-Fraud Scenario Trainer

反诈互动剧情演练：15 个节点、16 个结局。

An interactive, choice-driven anti-fraud exercise. Players encounter ticketing impersonation, a fake familiar contact, and an escalating investment pitch. The backend advances the story from recorded choices and returns a path-based review.

> **Simulation only:** All payments are fictional. No real payment service is connected. Free-text answers are matched with configured keywords; the project does not use generative AI to interpret them.

**Online demo:** <https://echo33550336.github.io/anti-fraud-story/> — a static front-end port of the same graph and integer scoring rules. The Python backend version lives in [`backend/`](backend/).

## What makes it distinctive

- **Two connected scam patterns:** A fake ticketing fee and repeated-transfer pressure lead into small purchases from an impersonated friend and a larger investment request.
- **Choices shape the ending:** The story has 15 nodes and 16 endings. E15 and E16 depend on earlier verification and payment events.
- **Server-side review:** The backend records choices and simulated payment amounts, then calculates the score and badges and returns the matching ending.
- **Practical response skills:** Players practice independent verification, stopping further payments, preserving relevant evidence, contacting official channels, and sharing privacy-aware warnings.

## 技术栈与 Agent 架构 / Tech stack & agent architecture

> **定位：一个可审计、可复现、可离线运行的“确定性剧情 Agent”，不是 LLM 聊天套壳。**
> 它把 Agent 的 `观察 → 决策 → 行动 → 记忆 → 复盘` 闭环，落在反诈训练这个**不能胡说**的场景里。
>
> 在线 GitHub Pages 版是**前端同构实现**：同一份图配置/整数规则，无服务端会话；`/api/story/*`、服务端 session/记忆由 Python 后端版本提供。

### Agent 闭环

| Agent 环节 | 本项目实现 |
|---|---|
| 观察 Observation | 玩家选择、自由回答、当前节点、已发生事件 |
| 决策 Policy | 剧情图条件路由 + 自由回答关键词意图路由 + 节点校验 |
| 行动 Action | 节点跳转、付款模拟、提前结局、结局触发 |
| 记忆 Memory | 会话 flags、历史选择、累计付款、2 小时 TTL |
| 复盘 Reflection | 路径复盘、整数分数、徽章、结局解释 |
| 工具边界 Tools | `/api/story/start`、`answer`、`open`、`review` 四个显式 API |
| 护栏 Guardrails | 服务端权威、确定性、无 LLM、无外网、参数校验 |

### 技术栈

| 层 | 实现 | 关键能力 |
|---|---|---|
| 运行时 | Python 3.7+ 标准库 `http.server` | 单进程托管 API + 静态页面；零第三方依赖；一条命令启动 |
| 剧情策略 | JSON 图配置 + 确定性条件路由 | 15 节点、16 结局、条件边、提前结局、flags 状态；无死路 |
| 自由回答 | 关键词意图路由 | N03 核实/继续；N15 删除/分享/举报/官方核实；不依赖 LLM |
| 会话记忆 | 内存 session store | flags / history / paid / TTL 2h；重复提交保护；不落盘 |
| 评分 | 整数评分函数 | 付款每满 100 扣 1、最多扣 50；结局罚分；优秀结局保底 82；10–100 |
| 前端 | 原生 HTML / CSS / JavaScript | 零构建；15 张 AI 场景/立绘；虚拟手机；选项/自由回答；复盘页 |
| 前端引擎 | `static-engine.js` 同构实现 | 与 Python 版同一份图配置/整数规则；GitHub Pages 可独立运行 |
| 音效/动效 | 原生 Web Audio + CSS | 原创 32 秒 BGM、点击/来电/付款/结局音效、转场/打字机/手机抖动 |
| 校验/测试 | `unittest` + 配置校验脚本 | 13 项评分单测；16/16 结局；130 条终止路径全量对拍 |
| 交付 | 本地单进程 / GitHub Pages / Docker | 现场断网可跑；Pages 稳定 Demo；Render/Docker 备用 |

### 为什么是 Agent 赛道

- **不是“模型生成下一步”**：剧情由可验证的图策略推进，自由回答由关键词意图路由；不调用大模型，不产生幻觉。
- **可复现、可验收**：同一条路径必得同一结局和分数；130 条终止路径、16 个结局、13 项单测全部可复算。
- **有完整 Agent 工程属性**：状态、策略、工具边界、记忆、护栏、可观测复盘；服务端是唯一权威。
- **确定性是场景优势**：反诈训练不能胡说；零 API 成本、断网可跑、现场不怕模型限流。
- **可平滑升级**：自由回答可在路由层替换为 LLM 意图分类/评分；当前版本保持零依赖兜底。

**硬指标：** 15 节点 / 16 结局 / 130 条终止路径 / 13 项单测 / 16 项配置校验 / 前后端评分多重集一致 / 零第三方依赖。

详细版（含架构图、PPT 两页文案、30 秒口播）：[`docs/技术栈与Agent架构.md`](docs/技术栈与Agent架构.md)

> Sessions are in-memory and not persisted; the single-process setup is intended for local demos and single-instance deployment.

## Run locally

One process serves both the API and the page:

```powershell
cd backend
python app.py
```

Open <http://127.0.0.1:5000/>. The frontend is served from `../frontend/`; the API lives under `/api/story/*`.

For frontend-only iteration, start a static server instead and the page falls back to `http://localhost:5000` for the API:

```powershell
cd frontend
python -m http.server 8080 --bind 127.0.0.1
```

CORS currently allows loopback development origins only.

## Repository map

```text
backend/   API, sessions, story engine, configuration, and deployment files
frontend/  page, interaction code, styles, and artwork
docs/      documentation index, story design, and archived analysis
```

- [Backend guide](backend/README.md) · [Frontend guide](frontend/README.md)
- [Documentation index](docs/README.md) · [Story design](docs/story/15-node-16-ending-design.md)
- [Archived gap assessment](docs/archive/integration/13-gap-assessment.md) · [Archived alignment plan](docs/archive/integration/14-backend-alignment-plan.md)

Files under `docs/archive/` preserve earlier models and planning notes. The source code and this README describe the current implementation.
