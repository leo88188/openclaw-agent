# Knowledge — 前端设计

> 版本: 2.0 | 更新: 2026-03-28 | 技术栈: HTML + TailwindCSS CDN + jQuery 3.7.1
> 变更: 整合 ui-design.md v2.0 交互规范，补充设计系统、组件规范、动效、响应式设计
> 交互设计权威来源: `ui-design.md`（前端 agent 实现时以此为准）
> 实现状态: ✅ 已同步 ui-design.md v2.0 全部交互规范（2026-03-28 11:12 迭代完成）

---

## 1. 设计系统

详见 `ui-design.md` 第 1 章。以下为前端 agent 直接使用的关键配置。

| 属性 | config.json 值 | 解析结果 |
|------|---------------|---------|
| 风格 | notion | Notion-like：干净、内容优先、微交互、大量留白 |
| 配色 | ocean | Primary #0066cc / Light #e6f2ff / Dark #003d7a / Accent #00b4d8 |
| 字体 | clean | Noto Sans SC / 思源黑体，Google Fonts CDN |
| 主题 | light | 白色背景 #ffffff，Surface #f7f6f3 |

CSS 变量和字体加载方式见 `ui-design.md` 第 1 章。

---

## 2. 页面清单与路由

### 2.1 页面清单

| 页面 | 文件 | 路径 | 用途 | 优先级 | 对应 US |
|------|------|------|------|--------|---------|
| 仪表盘 | index.html | / | 统计概览、快捷操作、系统信息 | P2 | US-9 |
| 知识管理 | knowledge.html | /knowledge | 知识 CRUD、分类筛选 | P0 | US-1, US-2 |
| 语义搜索 | search.html | /search | 语义搜索、过滤面板、结果列表 | P0 | US-3 |
| Skill 市场 | skills.html | /skills | Skill 浏览、创建、收藏 | P1 | US-6, US-7 |
| 元数据浏览 | metadata.html | /metadata | 数据库表结构浏览、导入 | P1 | US-4, US-5 |
| 团队管理 | teams.html | /teams | 团队空间、成员管理 | P2 | US-8 |

> 当前无认证，所有页面公开访问。后续引入 JWT 后增加路由守卫。

### 2.2 路由设计

静态 HTML 多页应用，无 SPA 路由。页面间通过 `<a href>` 跳转。
知识详情和 Skill 详情通过页面内 Modal 展示，不单独页面。

### 2.3 页面间导航关系

- 仪表盘「快捷操作」→ 新建知识 → `/knowledge.html`（自动打开创建 Modal）
- 搜索结果 → 点击结果卡片 → 根据 source_type 跳转对应页面
- 所有页面 → 顶部搜索框 → `/search.html`（带 query 参数）

---

## 3. 页面到组件树映射

### 3.1 全局组件（components.js）

| 组件 | 函数名 | 状态 | 对应 US |
|------|--------|------|---------|
| Sidebar | sidebar | default / collapsed / mobile-hidden | US-10 |
| Toast | toast(msg, type) | success / error / warning / info | US-11 |
| Modal | modal(title, content) | open / closing (动画) | US-11 |
| Confirm Dialog | confirm(msg, onOk) | open / confirming (loading) | US-11 |
| Pagination | pagination(total, page, onChange) | default / disabled | US-2 |
| Skeleton Loading | loading(container) | card / list / table | US-11 |
| Empty State | emptyState(container, msg, cta) | no-data / no-results / error | US-11 |

### 3.2 页面私有组件

| 页面 | 组件 | 说明 |
|------|------|------|
| index.html | statsCards, quickActions | 统计卡片（数字递增动画）、快捷入口 |
| knowledge.html | knowledgeList, knowledgeForm(Modal), categoryFilter, tagFilter | 卡片网格、表单弹窗、分类/标签筛选 |
| search.html | searchInput, resultList, filterPanel | 大搜索框、结果列表、左侧过滤面板 |
| skills.html | skillGrid, skillForm(Modal), categoryTabs, skillDetail(Modal) | 卡片网格、表单弹窗、分类 Tab、详情弹窗 |
| metadata.html | tableList, columnTable, importButton | 左侧表列表、右侧字段表格、导入按钮 |
| teams.html | teamList, teamForm(Modal), memberList | 团队卡片、创建弹窗、成员列表 |

---

## 4. 状态管理划分

jQuery 多页应用，状态管理通过全局变量 + DOM 状态：

| 状态类型 | 存储方式 | 示例 |
|---------|---------|------|
| Server State | API 返回 → 渲染到 DOM | 知识列表、Skill 列表、统计数据 |
| UI State | JS 变量 / DOM class | 当前页码、选中分类、Modal 开关、loading 状态 |
| Derived State | 从 Server State 计算 | 搜索结果数量、分页总页数 |
| Persistent State | localStorage | 侧边栏折叠状态 |

全局状态（window 级）：
- `window.currentPage` — 当前分页页码
- `window.currentCategory` — 当前选中分类

---

## 5. API 映射

| 页面/组件 | HTTP 方法 | 路径 | operationId |
|-----------|----------|------|-------------|
| 仪表盘 statsCards | GET | /api/v1/dashboard/stats | getDashboardStats |
| 仪表盘 系统状态 | GET | /api/v1/health | healthCheck |
| 知识列表 | GET | /api/v1/knowledge | listKnowledge |
| 知识创建弹窗 | POST | /api/v1/knowledge | createKnowledge |
| 知识编辑弹窗 | PUT | /api/v1/knowledge/{id} | updateKnowledge |
| 知识删除 | DELETE | /api/v1/knowledge/{id} | deleteKnowledge |
| 搜索页 | POST | /api/v1/search | semanticSearch |
| Skill 列表 | GET | /api/v1/skills | listSkills |
| Skill 创建弹窗 | POST | /api/v1/skills | createSkill |
| Skill 编辑弹窗 | PUT | /api/v1/skills/{id} | updateSkill |
| Skill 删除 | DELETE | /api/v1/skills/{id} | deleteSkill |
| Skill 收藏 | POST | /api/v1/skills/{id}/favorite | toggleSkillFavorite |
| Skill 使用 | POST | /api/v1/skills/{id}/use | recordSkillUse |
| 元数据表列表 | GET | /api/v1/metadata/tables | listMetadataTables |
| 元数据表详情 | GET | /api/v1/metadata/tables/{name} | getMetadataTable |
| 元数据导入 | POST | /api/v1/metadata/import | importMetadata |
| 团队列表 | GET | /api/v1/teams | listTeams |
| 团队创建 | POST | /api/v1/teams | createTeam |
| 团队成员 | GET | /api/v1/teams/{id}/members | listTeamMembers |
| 添加成员 | POST | /api/v1/teams/{id}/members | addTeamMember |
| 更新成员角色 | PUT | /api/v1/teams/{id}/members/{uid} | updateTeamMemberRole |
| 移除成员 | DELETE | /api/v1/teams/{id}/members/{uid} | removeTeamMember |

### 请求模式
- 页面初始化：单个请求（仪表盘并发 getStats + healthCheck）
- 分页：offset 分页，page + page_size 参数
- 搜索结果：infinite scroll（滚动加载更多）
- 无 optimistic update（jQuery 场景下保持简单）

---

## 6. 核心页面交互规范

> 详细交互设计见 `ui-design.md` 第 3 章。以下为前端 agent 实现的关键约束。

### 6.1 仪表盘 (P2)
- 布局：4 统计卡片 + 快捷操作 + 系统信息
- 统计卡片数字从 0 动画递增到实际值（300ms ease-out）
- API 失败时卡片显示 "-" 占位符

### 6.2 知识管理 (P0)
- 布局：顶部操作栏（分类下拉 + 标签多选 + 搜索框 + 新建按钮）+ 卡片网格（desktop 3列 / tablet 2列 / mobile 1列）
- 创建/编辑 Modal 720px：标题 + Markdown 编辑器（左右分栏）+ 分类 + 标签
- 详情 Modal 720px：Markdown 渲染（只读）+ 编辑/删除按钮
- 分页：每页 20 条，offset 分页
- 搜索框 300ms 防抖

### 6.3 语义搜索 (P0)
- 初始状态：居中大搜索框（56px 高，圆角 28px）
- 有结果状态：搜索框上移到顶部 + 左侧过滤面板滑入 + 右侧结果列表
- 过滤面板：来源类型（checkbox）+ 分类（checkbox）+ 时间范围（下拉）
- 结果卡片：标题 + 高亮匹配摘要 + source_type + score 百分比
- 加载更多：infinite scroll

### 6.4 元数据浏览 (P1)
- 布局：master-detail（左侧表列表 + 右侧字段详情表格）
- 左侧搜索框实时前端过滤表名
- 索引标识：PK 红色 Badge、IDX 蓝色 Badge、UNI 绿色 Badge
- 导入按钮：确认弹窗 → loading 进度 → 成功/失败 Toast

### 6.5 Skill 市场 (P1)
- 布局：顶部分类 Tab + 卡片网格
- 卡片：图标 + 名称 + 描述 + 分类标签 + 收藏数 + 使用次数
- 详情 Modal 640px：提示词模板（代码块）+ 参数填写 + 一键复制
- 收藏：乐观更新图标和计数

### 6.6 团队管理 (P2)
- 团队卡片列表 + 创建 Modal 560px
- 团队详情 Modal 720px：成员列表表格 + 角色下拉即时保存

---

## 7. 页面状态机

每个列表页遵循统一状态流转：

```
init → loading → loaded(有数据) / empty(无数据) / error
                       ↓                            ↓
                  refreshing                   retry → loading
```

| 状态 | UI 表现 | 触发条件 |
|------|---------|---------|
| loading | 骨架屏 / spinner | 页面初始化、切换分类、翻页 |
| loaded | 正常数据列表 | API 返回成功且有数据 |
| empty | 空状态插画 + 提示文案 + CTA | API 返回成功但 items 为空 |
| error | 错误提示 + 重试按钮 | API 请求失败 |
| refreshing | 列表上方 loading bar | 创建/编辑/删除后刷新列表 |

---

## 8. 表单校验规则

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

### 校验方式
- 必填字段：onBlur 校验 + 提交时再次校验
- 错误提示：字段下方 inline 红色文字
- 提交按钮禁用直到校验通过

---

## 9. 错误提示与 Loading 策略

| 场景 | 方式 | 说明 |
|------|------|------|
| 页面初始加载 | 骨架屏 | 替换整个内容区域 |
| 列表刷新 | 顶部 loading bar | 不遮挡已有内容 |
| 表单提交 | 按钮 loading + 禁用 | 防止重复提交 |
| 操作成功 | Toast (success) | 右上角，3s 自动消失 |
| 业务错误 | Toast (error) | 右上角，5s 自动消失 |
| 网络错误 | Toast (error) | "网络请求失败，请重试" |
| 空状态 | 居中插画 + 文案 + CTA | 区分"无数据"和"搜索无结果" |

### 空状态文案（对齐 ui-design.md）

| 页面 | 无数据文案 | CTA |
|------|----------|-----|
| 知识列表 | 还没有知识条目 | 创建第一条知识 |
| 搜索无结果 | 没有找到相关结果，试试换个描述方式？ | — |
| Skill 市场 | 还没有 Skill，成为第一个贡献者 | 创建 Skill |
| 元数据 | 还没有导入数据库元数据 | 导入元数据 |
| 团队列表 | 还没有团队 | 创建团队 |

---

## 10. 组件规范

> 详细规范见 `ui-design.md` 第 4 章。

### 按钮状态
| 类型 | Default | Hover | Disabled | Loading |
|------|---------|-------|----------|---------|
| Primary | bg-primary text-white | bg-primary-dark | opacity-50 | spinner + 禁用 |
| Secondary | border-border text-text | bg-surface | opacity-50 | spinner + 禁用 |
| Danger | text-error | bg-error-light | opacity-50 | spinner + 禁用 |

### Toast 规范
| 类型 | 持续时间 | 位置 |
|------|---------|------|
| Success | 3s | 右上角 |
| Error | 5s | 右上角 |
| Warning | 4s | 右上角 |
| Info | 3s | 右上角 |

### 确认弹窗
仅以下操作需要确认弹窗：删除知识/删除 Skill/移除团队成员/导入元数据。
确认按钮点击后变为"处理中..."状态并禁用。ESC 或点击遮罩可关闭。

---

## 11. 动效规范

> 详细规范见 `ui-design.md` 第 5 章。

| 场景 | 动效 | 时长 |
|------|------|------|
| Modal 打开 | fadeIn + translateY(20px→0) | 200ms |
| Modal 关闭 | fadeOut + translateY(0→10px) | 150ms |
| Toast 进入 | translateX(100%→0) | 200ms |
| 卡片 hover | translateY(0→-2px) + shadow 加深 | 150ms |
| 骨架屏 | 背景色 shimmer | 1.5s infinite |
| 数字递增 | 0 → 目标值（仪表盘） | 300ms |

支持 `prefers-reduced-motion: reduce` 媒体查询。

---

## 12. 响应式设计

| 断点 | 宽度 | TailwindCSS |
|------|------|-------------|
| mobile | < 640px | 默认 |
| tablet | 640-1024px | sm: / md: |
| desktop | > 1024px | lg: |

| 组件 | Mobile | Tablet | Desktop |
|------|--------|--------|---------|
| Sidebar | 隐藏，汉堡菜单 | 60px 图标模式 | 240px 完整展开 |
| 知识/Skill 卡片 | 1 列 | 2 列 | 3 列 |
| 搜索过滤面板 | 折叠为顶部筛选按钮 | 左侧 200px | 左侧 240px |
| 元数据 master-detail | 上下堆叠 | 左 200px + 右 | 左 280px + 右 |
| Modal | 全屏 | 640px 居中 | 720px 居中 |
| 统计卡片 | 2×2 网格 | 4 列 | 4 列 |

---

## 13. 权限控制

当前阶段无认证，所有功能对所有用户开放。

后续迭代计划：
- 页面级：团队管理页需要登录
- 组件级：删除按钮仅 admin/editor 可见
- 无权限时：按钮 disabled + tooltip 提示

---

## 14. 配置驱动（config.json）

### 14.1 读取点
- 所有页面的全局样式（sidebar、header、字体、主色调）
- 前端 agent 根据以下配置值查找精确 CSS 值

### 14.2 字段说明

| 字段 | 值 | 用途 |
|------|-----|------|
| design_style | "notion" | Notion 风格：干净简洁、大量留白、内容优先 |
| design_color | "ocean" | 海洋蓝色系（ocean 海洋蓝） |
| design_font | "clean" | 干净无衬线字体 |
| design_theme | "light" | 浅色主题 |
| design_notes | "管理后台风格，干净简洁，浅色系，内容优先" | 补充说明 |

### 14.3 容错策略
- config 字段缺失 → 使用默认值（notion / ocean / clean / light）
- TailwindCSS CDN 加载失败 → 页面仍可用，仅样式降级

---

## 15. 键盘导航

| 快捷键 | 作用域 | 行为 |
|--------|--------|------|
| Tab | 全局 | 焦点在可交互元素间移动 |
| Enter | 按钮/链接 | 触发点击 |
| ESC | Modal/下拉 | 关闭当前浮层 |
| / | 全局（非输入框） | 聚焦搜索框 |
