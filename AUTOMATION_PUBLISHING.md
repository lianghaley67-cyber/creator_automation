# 内容自动化与多平台分发

当前流水线：

```text
真实经历/微信语音
  -> AI 文案
  -> 音频（Edge TTS，失败自动重试；OpenAI/ElevenLabs/本地语音兜底）
  -> 视频任务
  -> 多平台分发包
  -> 微信公众号草稿箱
  -> 小红书创作后台人工确认发布
```

## 微信公众号

在 `.env` 配置：

```env
WECHAT_APP_ID=公众号AppID
WECHAT_APP_SECRET=公众号AppSecret
EDGE_TTS_RETRIES=3
```

还需要在微信公众号后台把服务器公网 IP 加入 API 白名单。

第一次使用时，在任务卡的“长期分发工作台”上传公众号封面。系统会把微信返回的
永久素材 `media_id` 保存到 SQLite，以后自动复用。

点击“发送到公众号草稿箱”只会创建草稿，不会直接公开发布。请在公众号后台预览、
检查后再发布。

## 小红书

系统会生成：

- 20 字以内标题
- 正文和话题
- 音频、视频等源素材路径
- 可下载的发布包

点击“打开小红书后台”后粘贴正文、上传素材并确认发布。当前不调用非官方个人账号
发布接口，避免登录失效、验证码和账号风控。

## 服务器更新

```bash
cd /home/ubuntu/creator_automation
git pull --ff-only origin main
docker compose build creator-studio
docker compose up -d creator-studio
docker compose logs -f --tail=100 creator-studio
```

验证：

```bash
curl http://127.0.0.1/api/health
docker exec creator-studio python -c "import edge_tts, pyttsx3; print('TTS dependencies OK')"
```
