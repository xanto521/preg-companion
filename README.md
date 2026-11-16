# 孕期陪伴

自部署的单记录者孕期记录工具。需求、数据模型和 M1–M5 的规划见 [架构设计文档](<docs/孕期陪伴应用 · 架构设计文档.md>)。

## 本地开发

需要 Python 3.12、uv、Node.js 22.12+（22.x）或 24+，以及 npm。

```sh
cp .env.example .env
make install
make dev
```

另开一个终端运行 `make web`。

| 地址 | 用途 |
| --- | --- |
| [http://127.0.0.1:5173](http://127.0.0.1:5173) | 录入端 |
| [http://127.0.0.1:5173/viewer.html](http://127.0.0.1:5173/viewer.html) | 只读端页面预览 |
| [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) | 当前已实现的 API |
| [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health) | 服务健康检查 |

`make dev` 会先迁移数据库。本地数据库默认位于 `data/app.db`，可通过 `PREG_DATA_DIR` 配置。SQLite 连接启用 WAL 和外键检查。运行 `make build` 后，重启 FastAPI 即可由同一个服务访问录入端 `/` 和只读入口 `/view/demo`。

首次启动后，在后端所在机器上生成一次性设置链接。这里以 Vite 的录入端地址为例。

```sh
uv --directory backend run --locked python -m app.security.setup http://127.0.0.1:5173
```

在浏览器打开命令输出的链接并设置至少 12 个字符的口令。链接一次有效，1 小时后过期。后续直接访问录入端，用同一口令登录。忘记口令时，在原命令末尾加 `--reset` 可撤销现有会话并生成新的设置链接。

## Docker Compose

```sh
docker compose up --build -d --wait
```

访问 [http://127.0.0.1:8000](http://127.0.0.1:8000)。数据库保存在 `app-data` 命名卷，容器启动时会运行迁移。录入端绑定宿主机回环地址，端口可通过 `APP_PORT` 调整。

在容器中生成设置链接。把命令最后的地址替换为实际访问录入端的地址。

```sh
docker compose exec -T app python -m app.security.setup http://127.0.0.1:8000
```

局域网 HTTP 开发实例用于测试数据。录入真实数据时需为录入端配置 HTTPS。可选的 Caddy `https` profile 用于公开查看和日历路径，将 `PREG_PUBLIC_DOMAIN` 设置为指向主机的域名并开放 80/443 后，运行 `docker compose --profile https up --build -d --wait`。分享页目前为占位页，分享和日历输出由后续阶段接入。

## M1 录入

登录后先设置预产期，再从「今天」新建或打开产检记录。预产期调整会保留历史。产检支持记录医院、医生、指标、医嘱、小结、下次预约和家人可见设置。编辑或删除记录时，系统会检查记录版本。

报告与影像支持 JPG、PNG、WebP 和 PDF，单文件最多 20 MB。附件写入数据卷的 `attachments/` 目录，经登录后下载。表单草稿可在同一浏览器标签页刷新后恢复。附件需重新选择。

## 代码入口

| 路径 | 用途 |
| --- | --- |
| `backend/app/api` | 登录、预产期、产检和健康检查 HTTP 路由 |
| `backend/app/domain` | 独立业务逻辑，已包含以预产期计算孕天数的函数 |
| `backend/app/db` | SQLAlchemy 模型、SQLite 连接和 Alembic 迁移 |
| `frontend/src/pages` | 录入端页面 |
| `frontend/src/viewer` | 独立构建的家人查看入口 |
| `deploy/proxy` | 可选 HTTPS 代理 |
