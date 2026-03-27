# Knowledge — 前端设计

> 版本: 1.0 | 更新: 2026-03-27 | 技术栈: HTML + TailwindCSS CDN + jQuery 3.7.1

---

## 1. 页面清单

| 页面 | 文件 | 路径 | 用途 | 权限 |
|------|------|------|------|------|
| 仪表盘 | index.html | / | 统计概览、最近知识、快捷操作 | 公开 |
| 知识列表 | knowledge.html | /knowledge | 知识 CRUD、分类筛选 | 公开 |
| 向量搜索 | search.html | /search | 语义搜索 | 公开 |
| Skill 市场 | skills.html | /skills | Skill 浏览、创建、收藏 | 公开 |
| 元数据浏览 | metadata.html | /metadata | 数据库表结构浏览 | 公开 |
| 团队管理 | teams.html | /teams | 团队空间、成员管理 | 公开 |

> 当前无认证，所有页面公开访问。后续引入 JWT 后增加路由守卫。

---

## 2. 路由设计

静态 HTML 多页应用，无 SPA 路由。页面间通过 `<a href>` 跳转。

| 路径 | 文件 | 说明 |
|------|------|------|
| / | index.html | 仪表盘 |
| /knowledge | knowledge.html | 知识列表（内嵌创建/编辑 Modal） |
| /search | search.html | 搜索页 |
| /skills | skills.html | Skill 市场（内嵌创建/编辑 Modal） |
| /metadata | metadata.html | 元数据浏览 |
| /teams | teams.html | 团队管理 |

知识详情和 Skill 详情通过页面内 Modal 展示，不单独页面。

---

## 3. 页面到组件树映射

### 全局组件（components.js）
- `sidebar` — 左侧导航栏，所有页面共享
- `toast(msg, type)` — 全局提示（success/error/warning）
- `modal(title, content)` — 通用弹窗
- `pagination(total, page, onChange)` — 分页组件
- `loading(container)` — 局部 loading 骨架屏
- `emptyState(container, msg)` — 空状态占位

### 页面私有组件

| 页面 | 组件 | 说明 |
|------|------|------|
| index.html | statsCards, recentList, quickActions | 统计卡片、最近列表、快捷入口 |
| knowledge.html | knowledgeList, knowledgeForm(Modal), categoryFilter | 列表、表单弹窗、分类筛选 |
| search.html | searchInput, resultList, filterPanel | 搜索框、结果列表、过滤面板 |
| skills.html | skillGrid, skillForm(Modal), categoryTabs | 卡片网格、表单弹窗、分类 Tab |
| metadata.html | tableList, columnTable | 表列表、字段详情表格 |
| teams.html | teamList, teamForm(Modal), memberList | 团队列表、创建弹窗、成员列表 |

---

## 4. 状态管理划分

jQuery 多页应用，状态管理通过全局变量 + DOM 状态：

| 状态类型 | 存储方式 | 示例 |
|---------|---------|------|
| Server State | API 返回 → 渲染到 DOM | 知识列表、Skill 列表、统计数据 |
| UI State | JS 变量 / DOM class | 当前页码、选中分类、Modal 开关、loading 状态 |
| Derived State | 从 Server State 计算 | 搜索结果数量、分页总页数 |

全局状态（window 级）：
- `window.currentPage` — 当前分页页码
- `window.currentCategory` — 当前选中分类

页面状态（函数作用域）：
- 表单输入值 → DOM input.value
- Modal 开关 → DOM class toggle
- Loading → DOM 骨架屏显隐

---

## 5. API 映射

| 页面/组件 | HTTP 方法 | 路径 | operationId |
|-----------|----------|------|-------------|
| 仪表盘 statsCards | GET | /api/v1/dashboard/stats | getDashboardStats |
| 知识列表 | GET | /api/v1/knowledge | listKnowledge |
| 知识创建弹窗 | POST | /api/v1/knowledge | createKnowledge |
| 知识编辑弹窗 | PUT | /api/v1/knowledge/{id} | updateKnowledge |
| 知识删除 | DELETE | /api/v1/knowledge/{id} | deleteKnowledge |
| 搜索页 | POST | /api/v1/search | semanticSearch |
| Skill 列表 | GET | /api/v1/skills | listSkills |
| Skill 创建弹窗 | POST | /api/v1/skills | createSkill |
| Skill 收藏 | POST | /api/v1/skills/{id}/favorite | toggleSkillFavorite |
| 元数据表列表 | GET | /api/v1/metadata/tables | listMetadataTables |
| 元数据表详情 | GET | /api/v1/metadata/tables/{name} | getMetadataTable |
| 元数据导入 | POST | /api/v1/metadata/import | importMetadata |
| 团队列表 | GET | /api/v1/teams | listTeams |
| 团队创建 | POST | /api/v1/teams | createTeam |
| 团队成员 | GET | /api/v1/teams/{id}/members | listTeamMembers |
| 添加成员 | POST | /api/v1/teams/{id}/members | addTeamMember |

### 请求模式
- 页面初始化：单个请求（仪表盘 getStats）
- 分页：offset 分页，page + page_size 参数
- 无 optimistic update（jQuery 场景下保持简单）

---

## 6. 页面状态机

每个列表页遵循统一状态流转：

```
初始化 → loading → loaded(有数据) / empty(无数据) / error
                         ↓                              ↓
                    refreshing                     retry → loading
```

| 状态 | UI 表现 | 触发条件 |
|------|---------|---------|
| loading | 骨架屏 / spinner | 页面初始化、切换分类、翻页 |
| loaded | 正常数据列表 | API 返回成功且有数据 |
| empty | 空状态插画 + 提示文案 | API 返回成功但 items 为空 |
| error | 错误提示 + 重试按钮 | API 请求失败 |
| refreshing | 列表上方 loading bar | 创建/编辑/删除后刷新列表 |

---

## 7. 表单校验规则

### 知识条目表单
| 字段 | 校验 | 前端/后端 | 提示 |
|------|------|----------|------|
| title | 必填，1-255 字符 | 前端 + 后端 | "请输入标题" |
| content | 必填，≤ 100KB | 前端 + 后端 | "请输入内容" |
| category | 可选，≤ 100 字符 | 前端 | — |

### Skill 表单
| 字段 | 校验 | 前端/后端 | 提示 |
|------|------|----------|------|
| name | 必填，1-255 字符 | 前端 + 后端 | "请输入 Skill 名称" |
| prompt_template | 必填 | 前端 + 后端 | "请输入提示词模板" |
| category | 可选 | 前端 | — |

### 校验失败提示方式
- 字段下方红色 inline 提示
- 提交按钮禁用直到校验通过

---

## 8. 错误提示与 Loading 策略

| 场景 | 方式 | 说明 |
|------|------|------|
| 页面初始加载 | 全局骨架屏 | 替换整个内容区域 |
| 列表刷新 | 顶部 loading bar | 不遮挡已有内容 |
| 表单提交 | 按钮 loading + 禁用 | 防止重复提交 |
| 操作成功 | Toast (success) | 右上角，3s 自动消失 |
| 业务错误 | Toast (error) | 右上角，5s 自动消失 |
| 网络错误 | Toast (error) + 重试按钮 | "网络请求失败，请重试" |
| 空状态 | 居中插画 + 文案 | 区分"无数据"和"搜索无结果" |

---

## 9. 权限控制

当前阶段无认证，所有功能对所有用户开放。

后续迭代计划：
- 页面级：团队管理页需要登录
- 组件级：删除按钮仅 admin/editor 可见
- 无权限时：按钮 disabled + tooltip 提示

---

## 10. 配置驱动（config.json）

### 10.1 读取点
- 所有页面的全局样式（sidebar、header、字体、主色调）
- 前端 agent 根据以下配置值查找精确 CSS 值

### 10.2 字段说明

| 字段 | 值 | 用途 |
|------|-----|------|
| design_style | "notion" | Notion 风格：干净简洁、大量留白、内容优先 |
| design_color | "ocean" | 海洋蓝色系（ocean 海洋蓝） |
| design_font | "clean" | 干净无衬线字体 |
| design_theme | "light" | 浅色主题 |
| design_notes | "管理后台风格，干净简洁，浅色系，内容优先" | 补充说明 |

### 10.3 容错策略
- config 字段缺失 → 使用默认值（notion / ocean / clean / light）
- TailwindCSS CDN 加载失败 → 页面仍可用，仅样式降级

### 10.4 功能开关
- 所有功能开关为 run-time（页面加载时从 config 读取）
- 当前无 build-time 开关（无构建工具）

---

## 附录：响应式断点

| 断点 | 宽度 | 布局变化 |
|------|------|---------|
| mobile | < 640px | 隐藏 sidebar，汉堡菜单；单列布局 |
| tablet | 640-1024px | 收缩 sidebar（仅图标）；双列卡片 |
| desktop | > 1024px | 完整 sidebar + 内容区；三列卡片 |
