# 前端

无构建步骤的静态页面，由后端会话 API 驱动。

```text
index.html     页面入口
src/game.js    会话请求、节点渲染和后端复盘展示
src/story.js   场景资源映射与离线展示内容
src/styles.css 页面样式
美工/          背景、立绘和场景图片
```

在仓库根目录启动后端后，于本目录运行静态服务器：

```powershell
python -m http.server 8080 --bind 127.0.0.1
```

打开 <http://localhost:8080>。默认 API 地址为 `http://localhost:5000`，可在加载 `src/game.js` 前设置 `window.ANTIFRAUD_API_BASE`。剧情原稿见 [`docs/story`](../docs/story/15-node-16-ending-design.md)。
