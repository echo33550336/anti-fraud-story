# v3 已应用的补丁（2026-10-31）

来源：`frontend-js2.patch` 里的修复，按 v3 代码结构重新适配后落盘。
**v3 新增的动效系统与原有剧情均未改动**：`src/main.js`、`src/acts.js`、`src/story.js` 一行未动；
`motionToggle`、`actCurtain`（换幕黑场卡）、背景缓推、台词分级、结算滚动等全部保留。

## 已改文件（文本）

| 文件 | 改动 |
|---|---|
| `src/styles.css` | +43 行：移动端封面排版（kicker 不拆词、正文去硬换行、卡片构图）+ `.demo-link` 样式。追加在 v3 动效样式之后，仅覆盖封面排版 |
| `src/ui.js` | 封面底部加「没有后端？改用演示模式」（`?mode=demo`）；动效相关的 `motionToggle`、`actCurtain` 未动 |
| `src/prologue.js` | 林夏 7 句不再请求不存在的 `P04.mp3` 等，状态显示「主角独白 · 按阅读节奏推进」 |
| `tools/clean-art-watermarks.py` | 新增：裁掉素材左上「AI生成」/右下「小云雀AI」 |
| `tools/export-prologue-lines.mjs` | 新增：导出 `contract/prologue-lines.json`（18 句待配、7 句主角跳过） |
| `tools/gen-prologue-voice.py` | 新增：序章配音生成（云健/晓晓/晓伊，与 15 幕同音色） |
| `contract/prologue-lines.json` | 新增，生成物 |
| `README.md` | +23 行：序章配音、素材水印、演示模式入口 |

## 素材（二进制，已就地处理）

`public/art/*.jpg` 15 张已执行裁剪（`--top 0.125 --bottom 0.105`），水印消失。
裁图有损，**原始素材在 `frontend-js-v3.zip` 里**；需要还原时重新解压即可。

## 验证

无头 Edge 实拍（1440×900 / 390×844）在 `../frontend-js3-verify/`：

- `v3p-01-desktop-cover.png`：桌面封面，水印已无、演示入口可见
- `v3p-03-prologue-p04.png`：序章 P04 主角独白状态
- `v3p-05-act-curtain.png`：v3 换幕黑场卡（第 02 幕 · 陌生来电）正常工作
- `v3p-06-act2.png`：第 2 幕游戏界面，动效开关在顶栏
- `v3p-07-mobile-cover.png`：移动端封面排版正常
- `v3p-09-mobile-game.png`：移动端游戏界面，顶栏含「动效：开」

## 仍未做（需要构建机 / 后续）

1. **配音 MP3**：本机无 `edge-tts`、PyPI 不通。执行：
   ```bash
   node tools/export-lines.mjs && python tools/gen-story-voice.py   # 补 29 句旁白
   node tools/export-prologue-lines.mjs && python tools/gen-prologue-voice.py   # 序章 18 句
   ```
2. **立绘棋盘格纹理**：源图 JPEG 里烘焙的透明底，属源素材问题；建议重新导出透明 PNG/WebP，届时改 `src/story.js` 的 `assets` 与 `src/ui.js` 序章两处路径即可。
3. **冒烟脚本**：`node_modules` 不随包提交，`tools/smoke.mjs` 需先安装 `jsdom`（本机 npm 网络不可用，未跑）。
4. `preview.html` 是 v3 的静态设计预览（由 `tools/build-preview.mjs` 生成，封面文案内联），不包含本次新增的演示入口；需要时重跑生成脚本再手工补该链接。

## 文本补丁

`../frontend-js3.patch`（8 文件，+522/−4，不含二进制）可在干净的 v3 解压目录上复现本次文本改动：

```bash
git -c core.autocrlf=false apply --check frontend-js3.patch
git -c core.autocrlf=false apply frontend-js3.patch
python tools/clean-art-watermarks.py          # 仅在刚解压的原始 v3 目录上执行一次；重复执行会二次裁剪
```
