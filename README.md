# JellyPop Labs skills

JellyPop的实验室 自己做视频时用的 skill，给 Claude Code、Codex 等 AI 编程助手用。每一条规则都来自真实做过的视频。

## 安装

```bash
npx skills add jellypoplabs/skills
```

运行后在列表里勾选想要的 skill。以后有新的 skill，重新运行一次同一条命令就能装上。

## 目前有

| Skill | 做什么 |
|---|---|
| `ai-video-check` | 用代码做视频时的自检：动手前先定风格，先做一小段，渲染后用 ffmpeg 查黑场、卡顿、静音和时长，抽帧看画面，再派一个没看过剧本的 AI 做盲测 |
| `whitebox-check` | 白模自检：用 Blender 白模控制 AI 视频运镜时，查穿模、贴太近、转太快、小物体侧过来被画没，自动挑关键帧，叠图核对参考图，扫描成片有没有跳帧。附「让 AI 写 Blender 白模」的提示词模板 |

`ai-video-check` 需要电脑上装有 ffmpeg。`whitebox-check` 需要 Blender 4.x、ffmpeg 和 Python 的 Pillow。

## 配合使用

做视频的工具本身用官方的：

```bash
npx skills add heygen-com/hyperframes
npx skills add remotion-dev/skills
```
