# 孕期陪伴

## 项目入口

- [架构设计文档](<docs/孕期陪伴应用 · 架构设计文档.md>)记录业务范围、数据模型、API 和 M1–M5 的计划。
- [UI 设计规范](<docs/孕期陪伴应用 · UI 设计规范.md>)约定录入端和家人查看端的布局、交互和配色。
- [README](README.md)记录运行方式、首次设置口令和 M1 的使用流程。

项目是单记录者应用，采用 FastAPI、SQLAlchemy、Alembic 和 SQLite，前端采用 Vue 3 和 Vite。M1 已实现记录者登录、预产期设置及校正历史、孕周计算、产检增删改查和附件上传。M2 的里程碑规则和 ICS 订阅按架构文档推进。家人查看页目前是占位页。

## 改动约定

- 在 `backend/app/api/` 处理 HTTP、鉴权和请求校验，在 `backend/app/domain/` 放业务计算，沿用 `backend/app/db/` 的数据库会话和迁移。修改表结构时新增 Alembic 迁移，兼容已有数据。
- 校正预产期时保留历史和已记录的产检孕周。产检修改和删除沿用版本检查，附件通过有鉴权的接口访问。
- 录入端入口在 `frontend/src/pages/`，家人查看端在 `frontend/src/viewer/` 独立构建。两端共用 [配色令牌](frontend/src/styles/tokens.css)。新增界面按移动端优先设计，状态同时用文字表示。
- 口令、设置链接、会话令牌、`.env`、数据库、附件和备份留在运行环境。测试使用合成数据。

## 开发服务器

- 本机用于编辑代码、Git 提交和推送。服务器上的代码拉取、依赖安装、环境配置、构建、迁移、运行测试和部署都在 3.214 上执行。
- 用 `ssh chatbi-server-local` 连接 `192.168.3.214`。项目目录是 `/home/chatbi/apps/preg-companion`，工作分支为 `main`，远端为 [GitHub 仓库](https://github.com/xanto521/preg-companion)。
- 部署时在服务器目录执行 `git pull --ff-only origin main`，使用服务器上的 Docker Compose。部署参数保存在服务器的 `.env` 和 `docker-compose.override.yml`，SQLite 与附件保存在 Compose 的 `app-data` 命名卷。
- 开发入口是 [192.168.3.214:18080](http://192.168.3.214:18080/)，供同一局域网内试用。该入口使用 HTTP，录入真实数据前需按架构文档配置 HTTPS。
- 部署后检查 `docker compose ps app` 和 `/api/health`。涉及数据库或录入流程的改动，在服务器验证迁移和实际页面操作，再更新开发实例。
