.PHONY: help install run-web docker-up docker-down clean

help:
	@echo "ARGUS-Lite 命令"
	@echo "  make install    - 安装 Python 依赖"
	@echo "  make run-web    - 启动 Web 审核界面 (localhost:8090)"
	@echo "  make docker-up  - 启动 Docker 服务 (RSSHub + Redis + Web)"
	@echo "  make docker-down - 停止 Docker 服务"

install:
	pip install -r requirements.txt

run-web:
	cd web && python app.py

docker-up:
	docker compose -f deploy/docker-compose.yml up -d

docker-down:
	docker compose -f deploy/docker-compose.yml down

clean:
	rm -f data/argus.db
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name *.pyc -delete 2>/dev/null || true
