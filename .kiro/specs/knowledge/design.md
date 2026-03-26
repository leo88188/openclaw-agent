# Knowledge — 技术设计文档

## 1. 系统架构

```
┌─────────────────────────────────────────────────┐
│                   Browser                        │
│  HTML + TailwindCSS CDN + jQuery AJAX           │
└──────────────────┬──────────────────────────────┘
                   │ HTTP/REST
┌──────────────────▼──────────────────────────────┐
│              FastAPI Server                       │
│  ┌─────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │  CORS   │ │ Static   │ │   API Routers    │  │
│  │Middleware│ │  Files   │ │ /api/v1/*        │  │
│  └─────────┘ └──────────┘ └───────┬──────────┘  │
│                                    │             │
│  ┌────────────────────────────────▼──────────┐  │
│  │            Service Layer                   │  │
│  │  knowledge_svc / skill_svc / meta_svc     │  │
│  └──────┬──────────┬──────────┬──────────────┘  │
│         │          │          │                   │
│  ┌──────▼───┐ ┌────▼────┐ ┌──▼──────────────┐  │
│  │  MySQL   │ │  Redis  │ │  Vector Store   │  │
│  │knowledge │ │  Cache  │ │  (内置/可扩展)   │  │
│  └──────────┘ └─────────┘ └─────────────────┘  │
└─────────────────────────────────────────────────┘
```

## 2. 目录结构

```
knowledge/
├── server/                    # 后端
│   ├── main.py               # FastAPI 入口，挂载静态文件
│   ├── config.py             # 配置（DB/Redis/向量）
│   ├── database.py           # MySQL 连接
│   ├── redis_client.py       # Redis 连接
│   ├── models/               # SQLAlchemy 模型
│   │   ├── knowledge.py
│   │   ├── skill.py
│   │   ├── metadata.py
│   │   └── team.py
│   ├── routers/              # API 路由
│   │   ├── knowledge.py
│   │   ├── skill.py
│   │   ├── metadata.py
│   │   ├── search.py
│   │   ├── team.py
│   │   └── dashboard.py
│   ├── services/             # 业务逻辑
│   │   ├── knowledge_svc.py
│   │   ├── skill_svc.py
│   │   ├── metadata_svc.py
│   │   ├── vector_svc.py
│   │   └── search_svc.py
│   └── requirements.txt
├── static/                    # 前端
│   ├── index.html            # 仪表盘
│   ├── knowledge.html        # 知识列表
│   ├── search.html           # 向量搜索
│   ├── skills.html           # Skill 市场
│   ├── metadata.html         # 元数据浏览
│   ├── teams.html            # 团队管理
│   ├── js/
│   │   ├── api.js            # API 接口封装
│   │   ├── app.js            # 全局初始化
│   │   ├── components.js     # 通用组件
│   │   └── utils.js          # 工具函数
│   └── css/
│       └── custom.css        # 自定义样式（连接线、动画）
└── README.md
```

## 3. 数据库设计 (MySQL: knowledge)

### knowledge_items 知识条目
```sql
CREATE TABLE knowledge_items (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    category VARCHAR(100),
    tags JSON,
    team_id BIGINT,
    created_by VARCHAR(100),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_deleted TINYINT DEFAULT 0,
    vector_id VARCHAR(100),
    INDEX idx_category (category),
    INDEX idx_team (team_id),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### skills 提示词/Skill
```sql
CREATE TABLE skills (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    prompt_template TEXT NOT NULL,
    params JSON,
    category VARCHAR(100),
    is_public TINYINT DEFAULT 1,
    created_by VARCHAR(100),
    favorite_count INT DEFAULT 0,
    use_count INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_deleted TINYINT DEFAULT 0,
    INDEX idx_category (category),
    INDEX idx_public (is_public)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### db_metadata 数据库元数据
```sql
CREATE TABLE db_metadata (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    db_name VARCHAR(100) NOT NULL,
    table_name VARCHAR(100) NOT NULL,
    column_name VARCHAR(100),
    column_type VARCHAR(100),
    column_comment TEXT,
    table_comment TEXT,
    vector_id VARCHAR(100),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_table (db_name, table_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### teams 团队
```sql
CREATE TABLE teams (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_by VARCHAR(100),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### team_members 团队成员
```sql
CREATE TABLE team_members (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    team_id BIGINT NOT NULL,
    user_name VARCHAR(100) NOT NULL,
    role ENUM('admin', 'editor', 'viewer') DEFAULT 'viewer',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_team_user (team_id, user_name),
    FOREIGN KEY (team_id) REFERENCES teams(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### skill_favorites 收藏
```sql
CREATE TABLE skill_favorites (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    skill_id BIGINT NOT NULL,
    user_name VARCHAR(100) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_skill_user (skill_id, user_name),
    FOREIGN KEY (skill_id) REFERENCES skills(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## 4. Redis 缓存策略

| Key 模式 | 用途 | TTL |
|----------|------|-----|
| `knowledge:list:{page}:{category}` | 知识列表缓存 | 5min |
| `knowledge:detail:{id}` | 知识详情缓存 | 10min |
| `skills:list:{page}:{category}` | Skill列表缓存 | 5min |
| `dashboard:stats` | 仪表盘统计 | 2min |
| `metadata:tables` | 表列表缓存 | 30min |

## 5. 向量化方案

采用内置简易向量存储（基于 numpy 余弦相似度），后续可扩展为 Milvus/Qdrant：
- 文本通过 API 调用嵌入模型获取向量
- 向量存储在内存 + 文件持久化
- 搜索时计算余弦相似度，返回 Top-K

## 6. 前端设计规范

- 布局：Grid 8列，TailwindCSS 响应式
- 配色：白底 + 蓝色主色调 (#3B82F6) + 灰色辅助
- 节点连接线：CSS `::before`/`::after` 伪元素实现
  - 完成：绿色 (#10B981) 实线
  - 进行中：蓝色 (#3B82F6) 实线
  - 未开始：灰色 (#9CA3AF) 虚线
- 动画：CSS keyframes（pulse/breathe/swing）
- 字体：系统默认 sans-serif

## 7. 任务拆分

| # | 任务 | 负责 | 依赖 | 预估 |
|---|------|------|------|------|
| T1 | 后端项目骨架 + DB连接 | Backend | 无 | 1h |
| T2 | 数据库建表 | Backend | T1 | 0.5h |
| T3 | 知识CRUD API | Backend | T2 | 2h |
| T4 | Skill CRUD API | Backend | T2 | 1.5h |
| T5 | 元数据导入API | Backend | T2 | 1h |
| T6 | 向量搜索服务 | Backend | T3 | 2h |
| T7 | 仪表盘/统计API | Backend | T3,T4 | 1h |
| T8 | 前端骨架 + 布局 | Frontend | 无 | 1h |
| T9 | api.js 接口封装 | Frontend | T3 | 1h |
| T10 | 仪表盘页面 | Frontend | T7,T9 | 1.5h |
| T11 | 知识管理页面 | Frontend | T3,T9 | 2h |
| T12 | 搜索页面 | Frontend | T6,T9 | 1.5h |
| T13 | Skill页面 | Frontend | T4,T9 | 1.5h |
| T14 | 元数据页面 | Frontend | T5,T9 | 1h |
