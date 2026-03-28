# Knowledge — 交互设计文档

> 版本: 2.0 | 更新: 2026-03-28 | 状态: active
> 对齐: PRD v3.0 — 11 个用户故事 / 57 个验收场景
> 设计配置: notion 风格 / ocean 配色 / clean 字体 / light 主题
> 设计系统: design-system/MASTER.md v2.0

---

## 1. 设计系统

详见 `design-system/MASTER.md`（完整 CSS 变量、组件规范、交互模式）。

| 属性 | 配置值 | 解析结果 |
|------|--------|---------|
| 风格 | notion | Notion-like：干净、内容优先、微交互、大量留白 |
| 配色 | ocean | Primary #0066cc / Light #e6f2ff / Dark #003d7a / Accent #00b4d8 |
| 字体 | clean | Noto Sans SC / 思源黑体，Google Fonts CDN |
| 主题 | light | 白色背景 #ffffff，Surface #f7f6f3 |

> 工具推荐 Data-Dense Dashboard 风格 + Fira Code 字体，但 config.json 指定 notion + clean，以 config.json 为准。
> 从工具推荐中吸收：row highlighting on hover、smooth filter animations、data loading spinners。

### CSS 变量（前端直接使用）

```css
:root {
  --bg: #ffffff; --surface: #f7f6f3; --primary: #0066cc;
  --primary-light: #e6f2ff; --primary-dark: #003d7a; --accent: #00b4d8;
  --text: #37352f; --text-muted: #9b9a97; --border: #e3e2de;
  --shadow-sm: rgba(15,15,15,0.04); --shadow-md: rgba(15,15,15,0.08);
  --success: #0f766e; --success-light: #ecfdf5;
  --warning: #d97706; --warning-light: #fffbeb;
  --error: #eb5757; --error-light: #fef2f2;
  --info: #0066cc; --info-light: #e6f2ff;
  --radius-sm: 4px; --radius-md: 6px; --radius-lg: 8px; --radius-xl: 12px;
  --transition-fast: 150ms ease-out; --transition-normal: 200ms ease-out;
}
```

### 字体加载

```html
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;700&display=swap" rel="stylesheet">
```

---

## 2. 页面清单与导航

### 2.1 全局导航（左侧边栏） — US-10

| 属性 | 值 |
|------|-----|
| 宽度 | 240px（desktop）/ 60px 图标模式（tablet）/ 隐藏+汉堡菜单（mobile） |
| 背景 | var(--surface) |
| 当前页高亮 | 左侧 3px var(--primary) 边框 + 背景 var(--primary-light) |
| 折叠/展开 | 底部 toggle 按钮，状态存 localStorage |
| 底部状态 | 绿色圆点 8px + "系统运行中"（后端正常时） |

### 2.2 页面路由

| 页面 | 路由 | 优先级 | 导航图标 | 对应 US |
|------|------|--------|---------|---------|
| 仪表盘 | `/` (index.html) | P2 | fa-dashboard | US-9 |
| 知识管理 | `/knowledge.html` | P0 | fa-book | US-1, US-2 |
| 语义搜索 | `/search.html` | P0 | fa-search | US-3 |
| Skill 市场 | `/skills.html` | P1 | fa-magic | US-6, US-7 |
| 元数据浏览 | `/metadata.html` | P1 | fa-database | US-4, US-5 |
| 团队管理 | `/teams.html` | P2 | fa-users | US-8 |

### 2.3 页面间导航关系

- 仪表盘「最近知识」→ 点击跳转 `/knowledge.html`（带 id 参数打开详情 Modal）
- 仪表盘「快捷操作」→ 新建知识 → `/knowledge.html`（自动打开创建 Modal）
- 搜索结果 → 点击结果卡片 → 根据来源类型跳转对应页面（知识/元数据/Skill）
- 所有页面 → 顶部搜索框 → `/search.html`（带 query 参数）

---

## 3. 核心页面交互设计

### 3.1 仪表盘 `/` (P2) — US-9

**布局：** 上下结构

```
┌─────────────────────────────────────────────┐
│ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐        │
│ │知识总数│ │Skill数│ │数据表数│ │系统状态│        │  ← 4 统计卡片
│ │  128  │ │  45  │ │  32  │ │ 正常  │        │
│ └──────┘ └──────┘ └──────┘ └──────┘        │
├─────────────────────────────────────────────┤
│ [📝 新建知识] [🔍 搜索知识] [📦 导入元数据]    │  ← 快捷操作
├─────────────────────────────────────────────┤
│ 系统信息: 版本 v1.0 | FastAPI | MySQL       │  ← 系统信息
└─────────────────────────────────────────────┘
```

**交互：**
- 统计卡片: 数字从 0 动画递增到实际值（300ms ease-out）
- 快捷操作: hover 时卡片微上浮 translateY(-2px)
- API 失败时: 统计卡片显示 "-" 占位符，不阻塞页面其他功能

**状态：**
- Loading: 4 个卡片骨架屏
- Error: 统计卡片显示 "-"，不阻塞其他功能
- Empty: 「还没有知识条目，立即创建第一条」+ CTA 按钮

---

### 3.2 知识管理 `/knowledge.html` (P0) — US-1, US-2

**布局：** 顶部操作栏 + 卡片网格

```
┌─────────────────────────────────────────────┐
│ [分类下拉▼] [标签筛选▼]    [搜索框🔍]  [+ 新建] │  ← 操作栏
├─────────────────────────────────────────────┤
│ ┌─────────┐ ┌─────────┐ ┌─────────┐        │
│ │ 知识卡片 │ │ 知识卡片 │ │ 知识卡片 │        │  ← 卡片网格
│ │ 标题     │ │ 标题     │ │ 标题     │        │     desktop:3列
│ │ 摘要...  │ │ 摘要...  │ │ 摘要...  │        │     tablet:2列
│ │ 分类 标签│ │ 分类 标签│ │ 分类 标签│        │     mobile:1列
│ │ 时间     │ │ 时间     │ │ 时间     │        │
│ └─────────┘ └─────────┘ └─────────┘        │
│              [1] [2] [3] ... [>]             │  ← 分页(20条/页)
└─────────────────────────────────────────────┘
```

**操作栏交互：**
- 分类下拉: 单选，选中后立即触发列表刷新，显示选中分类名
- 标签筛选: 多选下拉，选中标签显示为 chip，可逐个移除
- 搜索框: 输入后 300ms 防抖触发关键词搜索
- 新建按钮: 打开创建 Modal

**知识卡片交互：**
- 展示: 标题（H3 截断 1 行）+ 摘要（截断 2 行）+ 分类标签 + 更新时间
- Hover: box-shadow 加深 + cursor: pointer
- 点击: 打开详情 Modal
- 右上角: 更多操作按钮（⋯），hover 显示下拉菜单（编辑、删除）

**创建/编辑 Modal（720px）：**
- 标题输入框（必填，placeholder: "输入知识标题"）
- Markdown 编辑器（必填，左右分栏：编辑 | 预览）
- 分类选择（下拉，可输入新分类）
- 标签输入（Enter 添加 chip，可删除）
- 底部: [取消] [保存]
- 校验: 标题为空时显示"标题不能为空"红色提示
- 保存: 按钮 loading → API → 成功 Toast + 关闭 + 刷新 / 失败 Toast
- 未保存退出: dirty 检测 → 确认弹窗「有未保存的修改，确定离开？」

**详情 Modal（720px）：**
- 顶部: 标题 + 分类标签 + 创建时间 + 更新时间
- 内容: Markdown 渲染（只读）
- 底部: [编辑] [删除]
- 删除: 确认弹窗「确定要删除「{标题}」吗？此操作不可撤销。」→ 确认后软删除

**分页：** 每页 20 条，页码按钮 + 上一页/下一页，切换时顶部 loading bar

**状态：**
- Loading: 卡片骨架屏（3×4 网格）
- Empty: 「还没有知识条目」+ [创建第一条知识] CTA
- 筛选无结果: 「没有符合条件的知识条目」+ [清除筛选] 链接

---

### 3.3 语义搜索 `/search.html` (P0) — US-3

**布局：** 居中搜索 → 左侧过滤 + 右侧结果

```
初始状态（无搜索词）:
┌─────────────────────────────────────────────┐
│                                             │
│           🔍 搜索知识库                       │
│     ┌──────────────────────────────┐        │
│     │ 输入自然语言描述...           │        │  ← 大搜索框居中
│     └──────────────────────────────┘        │     56px高,圆角28px
│                                             │
│     热门搜索: [订单状态] [用户表] [SQL优化]   │  ← 热门标签
│                                             │
└─────────────────────────────────────────────┘

有结果状态:
┌──────────┬──────────────────────────────────┐
│ 过滤面板  │  搜索框 [输入内容...]              │
│          │                                  │
│ 来源类型  │  找到 23 条结果（0.8s）            │
│ ☐ 知识   │                                  │
│ ☐ 元数据  │  ┌──────────────────────────────┐│
│ ☐ Skill  │  │ 结果标题                      ││
│          │  │ ...匹配内容<mark>高亮</mark>... ││
│ 分类      │  │ 来源:知识 · 相关度 92%        ││
│ ☐ 业务知识│  └──────────────────────────────┘│
│ ☐ 技术文档│                                  │
│          │  ┌──────────────────────────────┐│
│ 时间范围  │  │ 结果标题                      ││
│ [最近7天▼]│  │ ...匹配内容高亮摘要...          ││
│          │  └──────────────────────────────┘│
│          │                                  │
│[清除筛选] │         [滚动加载更多...]          │
└──────────┴──────────────────────────────────┘
```

**搜索框交互：**
- 初始: 页面居中大搜索框
- 输入后: 搜索框上移到顶部，过滤面板从左侧滑入
- 防抖: 停止输入 300ms 后自动搜索；Enter 立即搜索
- 空查询: 提示"请输入搜索内容"，不发起请求
- 清空: 右侧 × 按钮，回到初始状态
- 搜索中: 搜索按钮禁用防止重复提交

**过滤面板交互：**
- 来源类型: checkbox 多选（知识/元数据/Skill），选中后立即重新搜索
- 分类: checkbox 多选
- 时间范围: 下拉（全部 / 最近 7 天 / 最近 30 天 / 最近 90 天）
- 重置: 底部「清除所有筛选」链接

**搜索结果交互：**
- 结果卡片: 标题 + 高亮匹配摘要（`<mark>` 标签）+ 来源类型 + 相关度百分比
- 点击结果: 根据来源类型跳转（知识→详情 Modal / 元数据→metadata 页 / Skill→详情 Modal）
- 加载更多: 滚动到底部自动加载（infinite scroll）
- 响应时间: < 2 秒

**状态：**
- Searching: 搜索框下方 loading bar + 结果区域骨架屏
- No Results: 居中「没有找到相关结果，试试换个描述方式？」
- Error: Toast 错误提示 + 重试按钮

---

### 3.4 元数据浏览 `/metadata.html` (P1) — US-4, US-5

**布局：** 左侧表列表 + 右侧字段详情（master-detail）

```
┌──────────────┬──────────────────────────────┐
│ 数据库表列表  │  表名: users                  │
│              │  注释: 用户信息表              │
│ 🔍 搜索表名   │  字段数: 12                   │
│              │                              │
│ ▸ users      │  字段列表:                     │
│   orders     │  ┌────┬──────┬────┬────────┐ │
│   products   │  │字段 │ 类型  │索引 │ 注释   │ │
│   payments   │  ├────┼──────┼────┼────────┤ │
│   ...        │  │ id │bigint│ PK │ 主键ID │ │
│              │  │name│varchar│   │ 用户名 │ │
│              │  │phone│varchar│IDX│ 手机号 │ │
│              │  └────┴──────┴────┴────────┘ │
│              │                              │
│ [导入元数据]  │  最后导入: 2026-03-27 10:00   │
└──────────────┴──────────────────────────────┘
```

**左侧表列表交互：**
- 搜索框: 实时前端过滤表名
- 表项: 点击选中，左侧 3px var(--primary) 指示线
- 每行显示: 表名 + 字段数量 + 表注释（截断）

**右侧字段详情交互：**
- 表格: 字段名（代码字体）、类型、是否可空、默认值、注释、索引信息
- 索引标识: PK 红色 Badge、IDX 蓝色 Badge、UNI 绿色 Badge
- 字段行 hover: 背景 var(--primary-light)

**导入元数据交互：**
- 点击「导入元数据」→ 确认弹窗（显示将连接的数据库名称）
- 导入中: 按钮 loading + 进度提示（「正在导入... 已处理 12/45 张表」）
- 成功: Toast（「导入完成，新增 X 表，更新 Y 表」）+ 刷新列表
- 失败: Toast（「数据库连接失败，请检查配置」）
- 重复导入: 增量更新，不产生重复记录

**状态：**
- Loading: 左侧列表骨架屏 + 右侧表格骨架屏
- Empty: 「还没有导入数据库元数据」+ [导入元数据] CTA
- Error: 错误提示 + 重试按钮

---

### 3.5 Skill 市场 `/skills.html` (P1) — US-6, US-7

**布局：** 顶部分类 Tab + 卡片网格

```
┌─────────────────────────────────────────────┐
│ [全部] [数据分析] [代码生成] [文案写作] [+ 创建] │  ← 分类Tab
├─────────────────────────────────────────────┤
│ ┌──────────┐ ┌──────────┐ ┌──────────┐     │
│ │ ⚡ Skill名│ │ ⚡ Skill名│ │ ⚡ Skill名│     │  ← 卡片网格
│ │ 描述摘要  │ │ 描述摘要  │ │ 描述摘要  │     │
│ │ 分类      │ │ 分类      │ │ 分类      │     │
│ │ ❤ 12 👁 56│ │ ❤ 8  👁 34│ │ ❤ 23 👁 89│     │
│ └──────────┘ └──────────┘ └──────────┘     │
│              [1] [2] [3] ... [>]             │  ← 分页
└─────────────────────────────────────────────┘
```

**分类 Tab 交互：**
- 横向排列，选中 Tab 下方 2px var(--primary) 指示线
- 切换 Tab: 列表区域 loading bar + 重新加载

**Skill 卡片交互：**
- 展示: 图标 + 名称 + 描述（截断 2 行）+ 分类标签 + 收藏数 + 使用次数
- Hover: 微上浮 + 阴影加深
- 点击: 打开 Skill 详情 Modal

**Skill 详情 Modal（640px）：**
- 内容: 名称、描述、提示词模板（代码块展示）、参数说明、使用统计
- 操作:
  - [❤ 收藏/取消收藏] — 点击切换，乐观更新图标和计数
  - [使用] — 展开参数填写区域 → 填写 → 生成最终提示词 → 一键复制
  - [编辑]（仅作者可见）— 打开编辑 Modal
  - [删除]（仅作者可见）— 确认弹窗后删除

**创建 Skill Modal（640px）：**
- 字段: 名称（必填）、描述、分类（下拉）、提示词模板（必填，支持 `{{参数名}}` 占位符）、是否公开（toggle，默认私有）
- 保存流程同知识创建

**状态：**
- Loading: 卡片骨架屏
- Empty: 「还没有 Skill，成为第一个贡献者」+ [创建 Skill] CTA
- 筛选无结果: 「该分类下暂无 Skill」

---

### 3.6 团队管理 `/teams.html` (P2) — US-8

**布局：** 团队卡片列表 + 团队详情 Modal

**团队列表：**
- 卡片展示: 团队名 + 描述 + 成员数 + 创建时间
- 操作: [创建团队] 按钮

**创建团队 Modal（560px）：**
- 字段: 团队名称（必填）、描述
- 创建成功后创建者自动成为管理员

**团队详情 Modal（720px）：**
- 团队信息: 名称、描述
- 成员列表表格: 用户名 | 角色（下拉: admin/editor/viewer）| 操作
- 添加成员: 输入用户名 + 选择角色 → 添加
- 角色变更: 下拉切换 → 即时保存
- 移除成员: 点击删除 → 确认弹窗

**知识隔离：** 搜索结果仅返回用户有权限访问的团队空间内容

---

## 4. 组件规范 — US-11

### 4.1 通用组件清单

| 组件 | 文件 | 状态 | 对应 US |
|------|------|------|---------|
| Sidebar | components.js | default / collapsed / mobile-hidden | US-10 |
| Toast | components.js | success / error / warning / info | US-11 |
| Modal | components.js | open / closing (动画) | US-11 |
| Confirm Dialog | components.js | open / confirming (loading) | US-11 |
| Pagination | components.js | default / disabled (首页/末页) | US-2 |
| Skeleton Loading | components.js | card / list / table | US-11 |
| Empty State | components.js | no-data / no-results / error | US-11 |

### 4.2 按钮状态矩阵

| 类型 | Default | Hover | Active | Disabled | Loading |
|------|---------|-------|--------|----------|---------|
| Primary | bg-primary text-white | bg-primary-dark | scale(0.98) | opacity-50 | spinner + 禁用 |
| Secondary | border-border text-text | bg-surface | scale(0.98) | opacity-50 | spinner + 禁用 |
| Danger | text-error | bg-error-light | scale(0.98) | opacity-50 | spinner + 禁用 |
| Ghost | text-muted | bg-surface | — | opacity-50 | — |

### 4.3 表单组件状态

| 状态 | 边框 | 背景 | 附加 |
|------|------|------|------|
| Default | var(--border) | var(--surface) | — |
| Focus | var(--primary) | var(--bg) | 2px primary-light 外发光 |
| Error | var(--error) | var(--bg) | 下方红色错误文字 |
| Disabled | var(--border) | #f0f0f0 | opacity: 0.6 |

**校验规则：**
- 必填字段: onBlur 校验 + 提交时再次校验
- 错误提示: 字段下方 inline 红色文字，12px，var(--error)

### 4.4 Toast 规范

| 类型 | 图标 | 背景 | 左边框 | 持续时间 |
|------|------|------|--------|---------|
| Success | fa-check-circle | var(--success-light) | 3px var(--success) | 3s |
| Error | fa-times-circle | var(--error-light) | 3px var(--error) | 5s |
| Warning | fa-exclamation-triangle | var(--warning-light) | 3px var(--warning) | 4s |
| Info | fa-info-circle | var(--info-light) | 3px var(--info) | 3s |

位置: 右上角，距顶 24px 距右 24px，宽 360px，垂直堆叠间距 8px。3 秒后自动消失。

### 4.5 确认弹窗规范

仅以下操作需要确认弹窗：
- 删除知识条目 / 删除 Skill / 移除团队成员 / 导入元数据（覆盖操作）

确认按钮点击后变为"处理中..."状态并禁用，防止重复点击。点击遮罩层或 ESC 可关闭。

### 4.6 空状态文案

| 页面 | 无数据文案 | CTA |
|------|----------|-----|
| 知识列表 | 还没有知识条目 | 创建第一条知识 |
| 搜索无结果 | 没有找到相关结果，试试换个描述方式？ | — |
| Skill 市场 | 还没有 Skill，成为第一个贡献者 | 创建 Skill |
| 元数据 | 还没有导入数据库元数据 | 导入元数据 |
| 团队列表 | 还没有团队 | 创建团队 |

---

## 5. 动效规范

### 5.1 页面切换

多页应用，无 SPA 过渡。页面加载时内容区域 fadeIn 200ms ease-out。

### 5.2 元素动效

| 场景 | 动效 | 时长 | 缓动 |
|------|------|------|------|
| Modal 打开 | fadeIn + translateY(20px→0) | 200ms | ease-out |
| Modal 关闭 | fadeOut + translateY(0→10px) | 150ms | ease-in |
| Toast 进入 | translateX(100%→0) | 200ms | ease-out |
| Toast 退出 | opacity(1→0) | 150ms | ease-in |
| 卡片 hover | translateY(0→-2px) + shadow 加深 | 150ms | ease-out |
| 按钮 active | scale(1→0.98) | 100ms | ease-out |
| 骨架屏 | 背景色 shimmer | 1.5s | linear infinite |
| 列表刷新 | 顶部 loading bar 从左到右 | 持续到完成 | linear |
| 数字递增 | 0 → 目标值（仪表盘） | 300ms | ease-out |

### 5.3 减弱动效

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## 6. 响应式设计

### 6.1 断点定义

| 断点 | 宽度 | TailwindCSS |
|------|------|-------------|
| mobile | < 640px | 默认 |
| tablet | 640-1024px | sm: / md: |
| desktop | > 1024px | lg: |

### 6.2 各断点布局变化

| 组件 | Mobile | Tablet | Desktop |
|------|--------|--------|---------|
| Sidebar | 隐藏，汉堡菜单 | 60px 图标模式 | 240px 完整展开 |
| 知识卡片 | 1 列 | 2 列 | 3 列 |
| Skill 卡片 | 1 列 | 2 列 | 3 列 |
| 搜索过滤面板 | 折叠为顶部筛选按钮 | 左侧 200px | 左侧 240px |
| 元数据 master-detail | 上下堆叠 | 左 200px + 右 | 左 280px + 右 |
| Modal | 全屏 | 640px 居中 | 720px 居中 |
| 统计卡片 | 2×2 网格 | 4 列 | 4 列 |

---

## 7. 全局交互规范

### 7.1 键盘导航

| 快捷键 | 作用域 | 行为 |
|--------|--------|------|
| Tab | 全局 | 焦点在可交互元素间移动 |
| Enter | 按钮/链接 | 触发点击 |
| ESC | Modal/下拉 | 关闭当前浮层 |
| / | 全局（非输入框） | 聚焦搜索框 |

### 7.2 统一状态机

**列表页：**
```
init → loading → loaded(有数据) / empty(无数据) / error
                       ↓                            ↓
                  refreshing                   retry → loading
```

**表单提交：**
```
填写 → 前端校验(onBlur) → 提交 → 按钮loading+禁用 → API请求
  → 成功: Toast(success) + 关闭Modal + 刷新列表
  → 失败: Toast(error) + 按钮恢复 + 保留表单数据
```

**删除操作：**
```
点击删除 → 确认弹窗 → 确认按钮loading → API请求
  → 成功: Toast(success) + 关闭弹窗 + 刷新列表
  → 失败: Toast(error) + 按钮恢复
```

### 7.3 API 错误处理

- 网络错误/服务端错误: 显示错误 Toast，包含具体错误信息
- 不阻塞页面其他功能
- 所有异步操作必须有 loading → success/error 状态

---

## 8. 原型文件索引

| 页面/流程 | 文件 | 说明 |
|----------|------|------|
| 全局页面结构 | wireframes/page-structure.png | 页面导航关系与组件树 |
| 知识 CRUD 流程 | wireframes/knowledge-crud-flow.png | 创建/编辑/删除状态机 |
| 搜索交互流程 | wireframes/search-flow.png | 搜索/过滤/结果状态机 |
| Skill 市场流程 | wireframes/skill-market-flow.png | 浏览/创建/使用状态机 |
| 元数据浏览流程 | wireframes/metadata-flow.png | 表列表/字段详情/导入状态机 |
| 团队管理流程 | wireframes/team-management-flow.png | 团队CRUD/成员管理状态机 |
| 仪表盘流程 | wireframes/dashboard-flow.png | 统计加载/快捷操作状态机 |

> ⚠️ 原型工具（Pencil/Stitch MCP）不可用，使用 Mermaid 状态图 + ASCII 布局描述替代。

---

## 9. Open Questions

| # | 问题 | 当前假设 | 状态 |
|---|------|---------|------|
| 1 | Markdown 编辑器选型 | textarea + 预览分栏（无富文本编辑器依赖） | ⚠️ 需确认是否引入 SimpleMDE |
| 2 | 搜索结果分页方式 | Infinite scroll（滚动加载更多） | 按最佳实践补全 |
| 3 | Skill 参数占位符语法 | `{{参数名}}` 双花括号 | 按最佳实践补全 |
| 4 | 侧边栏折叠状态持久化 | localStorage 存储 | 按最佳实践补全 |
| 5 | 向量搜索结果相关度阈值 | 显示相关度 > 50% 的结果 | ⚠️ 需后端确认 |

---

## 10. 用户故事覆盖矩阵

| US | 名称 | 优先级 | 覆盖章节 |
|----|------|--------|---------|
| US-1 | 知识条目 CRUD | P0 | 3.2 知识管理 |
| US-2 | 知识列表与筛选 | P0 | 3.2 知识管理 |
| US-3 | 向量语义搜索 | P0 | 3.3 语义搜索 |
| US-4 | 数据库元数据导入 | P1 | 3.4 元数据浏览 |
| US-5 | 元数据浏览与搜索 | P1 | 3.4 元数据浏览 |
| US-6 | Skill 创建与管理 | P1 | 3.5 Skill 市场 |
| US-7 | Skill 市场浏览与使用 | P1 | 3.5 Skill 市场 |
| US-8 | 团队空间管理 | P2 | 3.6 团队管理 |
| US-9 | 仪表盘概览 | P2 | 3.1 仪表盘 |
| US-10 | 全局导航与页面切换 | P0 | 2.1 全局导航 |
| US-11 | 通用交互组件 | P0 | 4. 组件规范 |
