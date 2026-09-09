# 官方 QQ 机器人：开放平台 + Linux 部署

本文覆盖阶段 0（开放平台手工配置）和阶段 4（systemd 上线）。代码入口是 `rag/qq_bot.py`。

## 阶段 0：开放平台

这些步骤不过代码。凭证没配好时，本机 demo 会在启动时直接退出。

1. 打开 [QQ 开放平台](https://q.qq.com/)，用个人主体注册并创建机器人。
2. 在机器人管理端记下 `AppID`、`AppSecret`，写入 `rag/.env` 的 `QQ_APP_ID` / `QQ_APP_SECRET`。
3. 「事件订阅与回调」选 **WebSocket**，不要选 Webhook。
4. 勾选事件：
   - 群聊：`GROUP_AT_MESSAGE_CREATE`（玩家必须 @ 机器人）
   - 单聊：`C2C_MESSAGE_CREATE`
5. 配置沙箱：
   - 一个你当群主或管理员、且不超过 20 人的测试群
   - 一个沙箱单聊 QQ 号
6. 用机器人资料卡把测试机器人加进沙箱群，并打开单聊窗口。

未过审时只能在沙箱里测。本机跑 demo 不需要公网 IP。Linux 正式环境需要把 VPS 公网 IPv4 填进管理端的 **IP 白名单**。

本机先验证通道（不加载知识库，几秒内启动）：

```bash
cd rag
python qq_bot.py --echo
```

沙箱群 `@机器人 你好` 应回「你好」；单聊发同一句也应回显。通道通了再去掉 `--echo` 做完整问答。

## 阶段 4：GitHub 拉代码 + 单独同步数据

机器建议：2 核、4GB 内存、磁盘至少 3GB，Python 3.10+。出网需能访问智谱 / OpenRouter，以及 `api.sgroup.qq.com`、`api.bot.qq.com`。

不要整包上传。仓库只放代码和 `knowledge_base/`。下面这些**不进 Git**：

| 路径 | 原因 | 上服务器的方式 |
|------|------|----------------|
| `rag/.env` | API Key / QQ Secret | 服务器上现写，或 `scp` 一次 |
| `rag/chroma_db/` | 约 1GB，单文件可能超过 GitHub 100MB | 本机 ingest 后 `rsync` |
| `rag/bm25_cache.pkl` | 本机缓存 | 可 `rsync`，没有则启动时重建 |
| `unpacked_data/` | 游戏解包资源 | 服务器不需要 |

建议仓库设为 **private**。`knowledge_base/` 是整理过的游戏数据，不宜公开。

### 首次上机

```bash
# 服务器
sudo mkdir -p /opt/fu_wiki_robot
sudo chown "$USER":"$USER" /opt/fu_wiki_robot
git clone git@github.com:NekoMashiro/starbound_fu_wiki_robot.git /opt/fu_wiki_robot
cd /opt/fu_wiki_robot
python3 -m venv .venv
.venv/bin/pip install -r rag/requirements.txt
```

本机把密钥和向量库拷过去（只做一次，或 ingest 之后再做）：

```bash
# 本机
scp rag/.env user@vps:/opt/fu_wiki_robot/rag/.env
rsync -av --delete rag/chroma_db/ user@vps:/opt/fu_wiki_robot/rag/chroma_db/
# 可选：已经有缓存则启动更快
rsync -av rag/bm25_cache.pkl user@vps:/opt/fu_wiki_robot/rag/
```

### 以后更新

代码：

```bash
# 服务器
cd /opt/fu_wiki_robot
git pull
sudo systemctl restart fu-wiki-qq
```

知识库（本机重新 ingest 之后）：

```bash
# 本机
rsync -av --delete knowledge_base/ user@vps:/opt/fu_wiki_robot/knowledge_base/
rsync -av --delete rag/chroma_db/ user@vps:/opt/fu_wiki_robot/rag/chroma_db/
rsync -av rag/bm25_cache.pkl user@vps:/opt/fu_wiki_robot/rag/
# 服务器
sudo systemctl restart fu-wiki-qq
```

### 服务器安装

```bash
cd /opt/fu_wiki_robot
python3 -m venv .venv
.venv/bin/pip install -r rag/requirements.txt

# 先确认 Linux 上 RAG 本身可用
cd rag && ../.venv/bin/python cli.py

# 再确认 QQ 通道（可先 --echo）
../.venv/bin/python qq_bot.py --echo
```

编辑 `deploy/fu-wiki-qq.service` 里的路径、用户后安装：

```bash
sudo cp deploy/fu-wiki-qq.service /etc/systemd/system/fu-wiki-qq.service
sudo systemctl daemon-reload
sudo systemctl enable --now fu-wiki-qq
```

开放平台：把 VPS 公网 IPv4 加入 IP 白名单。正式环境会拦截非白名单 IP；沙箱通常不受影响。

### 运维

```bash
journalctl -u fu-wiki-qq -f
```

日志里应看到「RAG 引擎就绪」，以及每次问答的耗时。

- 更新知识库：本机 ingest 后 rsync `rag/chroma_db` 和 `knowledge_base`，然后 `sudo systemctl restart fu-wiki-qq`
- 不要在服务器上跑 `ingest.py --reset`，除非那台机器也要重建索引
- 冷启动要加载 BM25，期间入站消息可能失败，属预期

验收：服务开机自启；沙箱群收到一条 Markdown 答案；单聊为流式 Markdown；`systemctl restart` 后仍能连上。
