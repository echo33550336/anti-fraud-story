# 反诈互动剧情

前后端整合版。前端从后端创建会话并提交固定选项、自由回答；结局评分和复盘由后端依据会话记录生成。

## 运行

在一个终端启动后端：

```powershell
cd backend
python app.py
```

在另一个终端启动前端静态服务器：

```powershell
cd frontend
python -m http.server 8080 --bind 127.0.0.1
```

打开 <http://localhost:8080>。前端默认请求 `http://localhost:5000`；需要更改时，可在加载 `src/game.js` 前设置 `window.ANTIFRAUD_API_BASE`。

## 目录

- `backend/`：Python 标准库 HTTP 服务、剧情图配置和会话引擎。
- `frontend/`：静态页面、剧情展示数据和美术资源。
- `docs/`：前后端差距清单与改造建议。

游戏中的付款均为模拟。旧的 `frontend/examples/backend-adapter.example.js` 使用已废弃接口，因此由 `.gitignore` 排除。
