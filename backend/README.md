# 后端

Python 标准库 HTTP API，负责会话、剧情推进、规则计算和结局复盘。

## 运行

从仓库根目录启动：

```powershell
cd backend
python app.py
```

默认监听 `http://127.0.0.1:5000`。启动后访问 <http://127.0.0.1:5000/> 就是完整游戏页面——同一个进程同时托管 `../frontend/` 与 `/api/story/*`；本地 CORS 允许 `localhost`、`127.0.0.1` 和 `::1` 来源。

## 结构

```text
app.py                                HTTP 路由与 CORS/OPTIONS
game/sessions.py                      会话、选项提交、自由回答和复盘
game/engine.py                        图推进、条件分支、评分和徽章
game/scoring.py                       整数评分函数（不使用浮点/小数）
game/config/story_frontend_graph.json 当前前端剧情图
game/config/story_15nodes.json        旧版线性模型配置
game/schemas.py                       两种配置结构校验
deploy/                               部署样例
```

分数统一由 [`game/scoring.py`](game/scoring.py) 的整数函数计算：当前图剧情用 `compute_frontend_score`（10–100），旧七维模型用 `compute_dimension_score`（50–100）。两个函数都只做整数运算，返回 `int`，不保留小数。

当前会话保存在单进程内存，空闲 2 小时后过期，服务重启后不会保留。`story_15nodes.json` 是旧模型配置；相关旧文档归档在 [`docs/archive/backend`](../docs/archive/backend/)。当前会话流程使用前端图配置。

API：`POST /api/story/start`、`POST /api/story/answer`、`POST /api/story/open`；并提供 `GET /api/story/state`、`GET /api/story/review` 和 `POST /api/story/stop`。
