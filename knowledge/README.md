# Knowledge - AI知识库管理平台

## 快速启动

### 1. 安装依赖
```bash
cd knowledge
pip install -r server/requirements.txt
```

### 2. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env 填入数据库和 Redis 配置
```

### 3. 创建数据库
```sql
CREATE DATABASE knowledge DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 4. 启动服务
```bash
cd knowledge
python -m uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. 访问
- 前端: http://localhost:8000
- API 文档: http://localhost:8000/docs

## 技术栈
- 后端: FastAPI + SQLAlchemy + MySQL + Redis
- 前端: HTML + TailwindCSS CDN + jQuery
- 架构: 前后端分离，后端挂载静态文件
