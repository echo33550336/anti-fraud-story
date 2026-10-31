# 反诈陪练｜终场前的一张票

一款由剧情选择驱动的反诈互动演练。玩家经历票务冒充、熟人账号仿冒和投资诱导，在关键节点练习核实来源、拒绝转账、保存证据与寻求帮助。后端按会话中的实际选择推进剧情并生成复盘。

> **模拟演练：**所有付款均为虚构，不连接真实支付渠道。自由回答使用配置关键词匹配，不使用生成式 AI。

## 项目特色

- **双重骗局连续演练：**从假票务个人收款码和重复转账，走到假熟人小额交易、投资与追加费用。
- **路径决定结局：**15 个剧情节点、16 个结局；E15/E16 会根据此前核实和付款记录分流。
- **服务端负责复盘：**后端保存选项与模拟付款事实，计算评分和徽章，并返回对应结局说明。
- **练习可执行的处置：**独立核实、及时停止、整理必要证据、联系正规渠道及脱敏提醒。

## 技术栈

| 层 | 实现 |
|---|---|
| 前端 | HTML、CSS、原生 JavaScript，无构建步骤 |
| API | Python 标准库 `http.server` |
| 剧情引擎 | JSON 图配置、确定性条件路由、关键词规则 |
| 会话 | 服务端进程内存储，空闲 2 小时过期 |

项目没有第三方 Python 依赖。会话不写入数据库；服务重启后会丢失，当前设计适用于本地演示和单进程运行。

## 快速运行

在仓库根目录打开两个 PowerShell 窗口。

**后端：**

```powershell
cd backend
python app.py
```

**前端：**

```powershell
cd frontend
python -m http.server 8080 --bind 127.0.0.1
```

浏览器打开 <http://localhost:8080>。前端默认调用 `http://localhost:5000`。后端 CORS 当前仅允许 loopback 开发来源。

## 仓库导航

```text
backend/   API、会话、剧情引擎、配置与部署文件
frontend/  页面、交互代码、样式和美术资源
docs/      阅读导航、剧情设计及归档分析资料
```

- [后端说明](backend/README.md) · [前端说明](frontend/README.md)
- [文档索引](docs/README.md) · [剧情节点设计](docs/story/15-node-16-ending-design.md)
- [历史差距审查](docs/archive/integration/13-gap-assessment.md) · [历史改造建议](docs/archive/integration/14-backend-alignment-plan.md)

`docs/archive/` 中的文件记录早期模型和改造过程；当前接口与行为以源码及本 README 为准。
