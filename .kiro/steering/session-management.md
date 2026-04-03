---
inclusion: always
---

# 会话记忆管理规则

Agent 在与用户对话时，必须主动管理会话记忆，确保对话上下文不丢失。

## 触发时机

### 会话开始时
- 调用 `GET /ai/session-store/get?session_id={id}` 恢复上次会话摘要
- 将摘要作为 system context 注入当前对话

### 对话过程中（每 5-10 轮）
- 调用 `POST /ai/session-store/save` 压缩保存当前会话
- 参数：session_id、最近的 messages 列表
- 不要等用户说"保存"，主动定期保存

### 会话结束时
- 用户明确说"结束"、"再见"、"下次聊"时
- 调用 `POST /ai/session-store/end` 提取长期记忆
- 这会自动从摘要中提取有价值的信息存入持久记忆

## API 接口

所有接口需要 Bearer token 鉴权（MCP Token）。

### 保存会话摘要
```
POST /ai/session-store/save
Authorization: Bearer {mcp_token}
Body: { "session_id": "uuid", "messages": [...] }
```

### 获取会话摘要
```
GET /ai/session-store/get?session_id={id}
Authorization: Bearer {mcp_token}
```

### 结束会话（提取长期记忆）
```
POST /ai/session-store/end
Authorization: Bearer {mcp_token}
Body: { "session_id": "uuid" }
```

## 保存策略

- 每次保存传最近 20 条消息即可，服务端会自动压缩合并
- session_id 用 UUID 格式，同一次对话保持不变
- 摘要会自动缓存到 Redis（24h），下次恢复很快
- 结束会话时会自动提取关键决策、用户偏好、待办事项等存入长期记忆

## 重要原则

- 宁可多保存，不要漏保存
- 用户的关键决策、偏好、结论必须被记住
- 临时性的寒暄、重复内容会被自动过滤
- 不要问用户"要不要保存"，直接保存
