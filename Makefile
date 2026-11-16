.DEFAULT_GOAL := help

.PHONY: help install migrate dev web build

help:
	@printf '%s\n' 'make install   安装锁定的前后端依赖' \
		'make migrate   升级本地数据库' \
		'make dev       启动 FastAPI 开发服务' \
		'make web       启动 Vite 开发服务' \
		'make build     构建录入端和只读端'

install:
	uv --directory backend sync --locked
	npm --prefix frontend ci --no-audit --no-fund

migrate:
	umask 077 && uv --directory backend run --locked alembic upgrade head

dev: migrate
	uv --directory backend run --locked uvicorn app.main:app --reload --no-access-log

web:
	npm --prefix frontend run dev

build:
	npm --prefix frontend run build
