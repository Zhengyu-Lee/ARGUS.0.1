# ARGUS-Lite — 舆情采集审核系统（Python 精简版）

基于 ARGUS (Advanced Reconnaissance & Global Unified Surveillance) 架构精简，
采用 Python 重写，保留核心的数据采集 → 分析 → 审核 流水线。

## 数据来源

| 来源 | 类型 | 采集方式 |
|------|------|----------|
| RSS 新闻源 | 安全/科技/新闻网站 | RSS/Atom |
| 微博热搜 | 微博热搜榜 | 微博开放 API |
| 抖音热点 | 抖音热点榜 | 抖音开放 API |
| 微信公众号 | 公众号文章 | 搜狗微信搜索 |
| 手动输入 | 用户粘贴/上传 | Web 表单 |

## 架构

```
采集层 ──→ 规则引擎 ──→ SQLite ──→ Web 审核界面
(RSS/微博/抖音/微信)     (AI分析)     (存储)       (Flask :8090)
```

## 快速启动

### 方式一：本地运行

```bash
# 1. 安装依赖
make install

# 2. 启动 Web 界面
make run-web

# 3. 打开浏览器 http://localhost:8090
# 4. 点击"立即采集"获取数据
```

### 方式二：Docker 运行

```bash
# 启动所有服务
make docker-up

# 查看状态
docker compose -f deploy/docker-compose.yml ps

# 停止
make docker-down
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/reviews | 获取审核列表 |
| GET | /api/review/:id | 获取单条详情 |
| POST | /api/review/:id | 审核通过/拒绝 |
| POST | /api/collect | 触发数据采集 |
| POST | /api/manual | 手动提交文本 |
| GET | /api/stats | 统计数据 |
| GET | /api/collectors | 采集器列表 |
| GET | / | Web 仪表盘 |

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| DATABASE_URL | sqlite:///data/argus.db | 数据库连接 |
| COLLECT_INTERVAL | 15 | 采集间隔（分钟） |
| PORT | 8090 | Web 端口 |
| SECRET_KEY | argus-lite-secret | Flask 密钥 |

## 项目结构

```
argus/
├── collectors/           # 数据采集器
│   ├── __init__.py       # 采集管理器
│   ├── rss.py            # RSS 采集
│   ├── weibo.py          # 微博热搜
│   ├── douyin.py         # 抖音热点
│   ├── wechat.py         # 微信公众号
│   └── manual.py         # 手动输入
├── web/                  # Web 审核界面
│   ├── app.py            # Flask 应用
│   └── templates/
│       └── dashboard.html
├── models.py             # 数据模型
├── analyzer.py           # 规则引擎 & AI 分析
├── requirements.txt
├── Makefile
└── deploy/
    ├── docker-compose.yml
    └── Dockerfile.python
```

## 与原始 ARGUS 的对应关系

| ARGUS (Go) | ARGUS-Lite (Python) | 说明 |
|------------|-------------------|------|
| cmd/rss-worker | collectors/rss.py | RSS 采集 |
| cmd/opinion-worker | collectors/weibo.py, douyin.py | 社交热点采集 |
| internal/types | models.py | 数据模型 |
| internal/rules | analyzer.py | 规则引擎 |
| internal/llm | analyzer.py | AI 分析 |
| internal/broker/kafka | SQLite (简化) | 消息总线 |
| cmd/review-api | web/app.py | Web 审核 API |
| deploy/docker-compose.yml | deploy/docker-compose.yml | Docker 部署 |
