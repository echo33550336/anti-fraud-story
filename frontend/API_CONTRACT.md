# 前后端契约：one-ticket-v1

本契约以《终场前的一张票》当前前端剧情为准：15 个节点、13 个固定二选一、N03/N15 两处自由回答、E01–E16 共 16 个结局，允许中途结局。序章 P01–P25 只负责展示，不写入后端选择历史。

## 全局约定

- 请求与响应为 UTF-8 JSON；所有端点在同源 `/api/story` 下。
- 服务端保存权威状态，客户端只发送 `session_id`、`node_id`、`option_id` 或自由回答文本；不得信任客户端金额、结局或分数。
- 每个响应中的 `story_id` 应为 `one-ticket-v1`。至少 `/start` 必须返回它，前端据此阻止旧版后端误接。
- 409 表示节点或会话状态冲突；422 表示内容不合要求；其他错误返回 `{ "error": "可读说明" }`。

## 接口

### `POST /api/story/start`

请求：`{"story_id":"one-ticket-v1"}`

响应：

```json
{
  "story_id":"one-ticket-v1",
  "session_id":"opaque-session-id",
  "node":{
    "id":"N01","title":"走出剧院","time":"10月27日 · 18:30",
    "scene":"……","lines":[{"speaker":"林夏","text":"……"}],
    "prompt":"离开前，你会记住什么？","free":false,
    "options":[{"id":"A","text":"查看票面……"},{"id":"B","text":"收好票……"}],
    "presentation":{"bg":"A","person":"lin","speaker":"林夏","phone":[],"prop":"ticket"},
    "progress":{"current":1,"total":15}
  }
}
```

`presentation` 可由服务端返回；缺省时前端按本地节点 ID 的视觉元数据补齐。**剧情文本、选项及回应以服务端为准。**

### `POST /api/story/answer`

请求：`{"session_id":"…","node_id":"N01","option_id":"A"}`

响应二选一：

```json
{"story_id":"one-ticket-v1","response":"林夏再次看了票面。","next_node":{"id":"N02","...":"同上节点结构"}}
```

```json
{"story_id":"one-ticket-v1","response":"……","ending_id":"E02"}
```

### `POST /api/story/open`

请求：`{"session_id":"…","node_id":"N03","text":"我会联系剧院总机核实"}`

响应：`{"story_id":"one-ticket-v1","intent":"verify","suggested_option_id":"STOP","need_confirm":true,"message":"请确认系统理解的行动"}`。

N03 的确认 ID 为 `STOP` 或 `CONTINUE`；N15 为 `VERIFY`、`REPORT`、`DELETE`、`SHARE`。无法判断时 `suggested_option_id:null`，前端要求重写。后端若一次就完成判断，也可直接返回 `next_node` 或 `ending_id`。

### `POST /api/story/confirm`

请求：`{"session_id":"…","node_id":"N03","option_id":"STOP","open_text":"我会联系剧院总机核实"}`

响应结构同 `/answer`。N03 的 `STOP` 可直接进入 E01，`CONTINUE` 进入 N04；N15 的四个 ID 分别进入 E11–E14。

### `GET /api/story/review?session_id=…`

仅结局后可用。响应：

```json
{
  "story_id":"one-ticket-v1","ending_id":"E12",
  "title":"证据保全，积极反诈","rating":"优秀",
  "narration":"……","next_step":"……",
  "score":91,"badges":["独立核验","线索保管员"]
}
```

前端不在后端模式计算分数或推断结局；以 `review` 结果展示。结局文案与徽章若由后端维护，也应在此返回。

## 与现有旧后端的差异

现有后端的 N12–N14 开放题、R/P 结局、线性 15 步及七维评分属于另一套模型。它不能只改接口名字就满足此契约；需要将剧情引擎改为图结构，支持中途结局与 E01–E16，并返回当前剧情版本号。前端已有同源代理，无需在旧后端上临时开放 CORS。

## 剧情数据导出（给后端直接对接）

`contract/story-one-ticket-v1.json` 由 `node tools/export-contract.mjs` 生成，与前端同源，可作为后端实现的唯一数据依据：

- `nodes[]`：`id / act / act_name / title / time / scene / speaker / prompt / free / options[{id,text,next}] / beats[] / presentation`
- `endings[]`：E01–E16 的 `title / rating / narration / next_step`
- `free_answers`：N03、N15 的确认 ID → 下一节点或结局（与 `src/engine.js` 一致）
- `acts[]`：五幕与节点的对应

### node.beats（逐句推进）

可选数组。后端返回则前端直接使用；未返回时回退到本地 `src/acts.js`；两者都没有时回退到 `scene` 文本（当前 N01 走这条，由序章接管）。

```json
"beats": [
  { "who": "旁白", "text": "林夏走出剧院大门，回头看了一眼售票窗口。灯还亮着，队伍还在排。" },
  { "who": "票务部", "text": "喂，您好，请问是林先生吗？", "phone": "来电 · 本市号码 · 未知联系人" }
]
```

`who` 取值：`旁白 / 林夏 / 小岚 / 票务部 / 剧院总机`，决定头像与配色；`phone` 可选，表示这一句出现时右侧虚拟手机弹出的一行。
