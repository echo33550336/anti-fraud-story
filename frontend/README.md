# 前端

无构建步骤的静态页面，由后端会话 API 驱动。

```text
index.html     页面入口
src/game.js    会话请求、节点渲染和后端复盘展示
src/story.js   场景资源映射与离线展示内容
src/styles.css 页面样式
美工/          背景、立绘和场景图片
```

在仓库根目录启动后端后，直接访问 <http://127.0.0.1:5000/> 即可（后端会托管本目录）。也可以单独起静态服务器调试：

```powershell
python -m http.server 8080 --bind 127.0.0.1
```

打开 <http://localhost:8080>。同源部署时页面用相对路径调 API；单独 8080 调试时自动回落到 `http://localhost:5000`。可在加载 `src/game.js` 前设置 `window.ANTIFRAUD_API_BASE` 覆盖。剧情原稿见 [`docs/story`](../docs/story/15-node-16-ending-design.md)。
