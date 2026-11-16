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

## Docker Compose

```sh
docker compose up --build -d --wait
```

访问 [http://127.0.0.1:8000](http://127.0.0.1:8000)。数据库保存在 `app-data` 命名卷，容器启动时会运行迁移。录入端绑定宿主机回环地址，端口可通过 `APP_PORT` 调整。

可选的 `https` profile 使用 Caddy。将 `PREG_PUBLIC_DOMAIN` 设置为指向主机的域名并开放 80/443 后，运行 `docker compose --profile https up --build -d --wait`。公网代理只转发查看、日历和静态资源路径。当前的分享页是空壳，分享令牌校验、日历输出和录入鉴权待实现。请使用测试数据。

## 代码入口

| 路径 | 用途 |
| --- | --- |
| `backend/app/api` | HTTP 路由，从健康检查起步 |
| `backend/app/domain` | 独立业务逻辑，已包含以预产期计算孕天数的函数 |
| `backend/app/db` | SQLAlchemy 模型、SQLite 连接、Alembic 首版迁移 |
| `frontend/src/pages` | 录入端页面 |
| `frontend/src/viewer` | 独立构建的家人查看入口 |
| `deploy/proxy` | 可选 HTTPS 代理 |

下一步按 M1 接入记录者认证、预产期与校正历史、产检增删改查和附件上传。
