# Knowledge — 部署文档

## 环境配置

| 组件 | 地址 | 备注 |
|------|------|------|
| MySQL | 127.0.0.1:3306 | database: knowledge |
| Redis | 127.0.0.1:6381 | 无密码 |
| 后端 | http://localhost:9999 | FastAPI + Uvicorn |
| 前端 | http://localhost:9998 | Python http.server |

## 数据库表

knowledge_items, skills, db_metadata, teams, team_members, skill_favorites — 共 6 张表，建表 SQL 见 design.md。

## 部署步骤

```bash
cd knowledge
bash restart.sh
```

restart.sh 会自动：
1. 杀掉 9998/9999 端口已有进程
2. 创建 logs 目录
3. nohup 后台启动后端（日志: logs/backend.log）
4. nohup 后台启动前端（日志: logs/frontend.log）

## 验证

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:9999/docs  # 期望 200
curl -s -o /dev/null -w "%{http_code}" http://localhost:9998/      # 期望 200
```

## 回滚方案

1. 杀掉进程：`lsof -ti :9998 :9999 | xargs kill -9`
2. 回退代码：`git checkout HEAD~1 -- knowledge/`
3. 重新启动：`bash knowledge/restart.sh`

## 监控检查清单

- [ ] 后端日志无报错：`tail -f knowledge/logs/backend.log`
- [ ] 前端日志无报错：`tail -f knowledge/logs/frontend.log`
- [ ] MySQL 连接正常：`mysql -h 127.0.0.1 -u root -proot -e "SELECT 1"`
- [ ] Redis 连接正常：`redis-cli -h 127.0.0.1 -p 6381 ping`

## 更新记录

| 日期 | 内容 |
|------|------|
| 2026-03-26 | 迭代：建表、restart.sh 脚本、服务启动验证 |
