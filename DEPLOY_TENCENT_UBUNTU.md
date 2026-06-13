# 腾讯云 Ubuntu 部署说明

这份文档用于把当前 Creator Studio 项目部署到腾讯云 Ubuntu 服务器。部署后只需要打开服务器公网 IP 或域名，就能看到前端页面；FastAPI 后端、Vue 前端静态文件、微信回调接口都由同一个服务承载。

## 1. 服务器准备

腾讯云安全组至少放行：

- `22`：SSH 登录
- `80`：网页访问和微信测试号回调
- `443`：后续配置 HTTPS 时使用

当前项目建议部署目录：

```bash
/home/ubuntu/creator_automation
```

## 2. 拉取代码

如果服务器没有代码：

```bash
cd /home/ubuntu
git clone https://gitee.com/lianghuanhuan/creator_automation.git
cd creator_automation
```

如果服务器已经有代码：

```bash
cd /home/ubuntu/creator_automation
git pull
```

## 3. 一键安装与启动

```bash
cd /home/ubuntu/creator_automation
bash deploy/ubuntu_install.sh
```

脚本会自动完成：

- 安装 Python 3.10、Node.js 24、Nginx、FFmpeg
- 创建 `.venv`
- 安装后端依赖
- 构建 `studio_frontend/dist`
- 创建 `creator-studio` systemd 服务
- 配置 Nginx 反代到 `127.0.0.1:8000`
- 检查 `/api/health`

## 4. 配置密钥

部署后编辑：

```bash
nano /home/ubuntu/creator_automation/.env
```

至少填写：

```env
SCRIPT_AI_PROVIDER=gemini_minimax
GEMINI_API_KEY=你的GeminiKey
MINIMAX_API_KEY=你的MiniMaxKey
DEEPSEEK_API_KEY=你的DeepSeekKey
ZHIPUAI_API_KEY=你的智谱Key
ZHIPU_VIDEO_MODEL=cogvideox-3
WECHAT_CALLBACK_TOKEN=你在微信测试号后台填写的Token
CREATOR_STUDIO_PUBLIC_BASE_URL=http://你的服务器公网IP
```

修改 `.env` 后重启：

```bash
sudo systemctl restart creator-studio
```

也可以使用安全更新脚本，避免手动编辑 `.env` 时误删内容：

```bash
cd /home/ubuntu/creator_automation
python3 deploy/update_env.py --from-stdin --restart
```

然后粘贴需要更新的配置，例如：

```env
TAVILY_API_KEY=你的TavilyKey
GITEE_ACCESS_TOKEN=你的Gitee私人令牌
AI_TRENDS_ENABLED=true
AI_TRENDS_TIME=07:30
OBSIDIAN_REPO_OWNER=lianghuanhuan
OBSIDIAN_REPO_NAME=obsidian
OBSIDIAN_ARCHIVE_DIR=01_Inbox/CreatorStudio
```

粘贴完成后按 `Ctrl+D`。脚本会自动备份旧 `.env`，更新键值，并重启 `creator-studio`。

## 5. 检查服务

```bash
sudo systemctl status creator-studio --no-pager
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1/
```

浏览器访问：

```text
http://你的服务器公网IP/
```

## 6. 微信测试号回调

微信测试号后台填写：

```text
URL:   http://你的服务器公网IP/api/integrations/wechat/callback
Token: 与 .env 的 WECHAT_CALLBACK_TOKEN 完全一致
```

如果你后续绑定域名并配置 HTTPS，把 `CREATOR_STUDIO_PUBLIC_BASE_URL` 改成：

```env
CREATOR_STUDIO_PUBLIC_BASE_URL=https://你的域名
```

然后重启服务。

## 7. 常用运维命令

查看日志：

```bash
sudo journalctl -u creator-studio -f
```

重启后端：

```bash
sudo systemctl restart creator-studio
```

重新构建前端：

```bash
cd /home/ubuntu/creator_automation/studio_frontend
npm run build
sudo systemctl restart creator-studio
```

更新代码并重新部署：

```bash
cd /home/ubuntu/creator_automation
git pull
bash deploy/ubuntu_install.sh
```

## 8. 从 JSON 升级到 SQLite（Docker 部署）

SQLite 免费，并且 Python 已内置运行支持。服务器上的 `sqlite3` 命令行工具仅用于人工检查。

```bash
cd /home/ubuntu/creator_automation
git pull
sudo apt update
sudo apt install -y sqlite3
chmod +x deploy/upgrade_sqlite_docker.sh
bash deploy/upgrade_sqlite_docker.sh
```

首次启动会把 `studio_runtime/studio_state.json` 自动导入
`studio_runtime/studio.db`。旧 JSON 和带时间戳的备份都会保留。

检查数据库：

```bash
sqlite3 studio_runtime/studio.db "PRAGMA integrity_check;"
sqlite3 studio_runtime/studio.db \
  "SELECT section, updated_at FROM state_sections ORDER BY section;"
```
