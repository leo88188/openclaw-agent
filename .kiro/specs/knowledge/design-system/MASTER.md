# Knowledge — 设计系统 (Design System)

> 版本: 2.0 | 更新: 2026-03-27 | 状态: active
> 来源: config.json (优先) + ui-ux-pro-max 工具推荐 (补充)
> 对齐: PRD v3.0 — 11 个用户故事 / 57 个验收场景

---

## 1. 设计原则

| 原则 | 说明 | 落地规则 |
|------|------|---------|
| 内容优先 | Notion-like，大量留白，信息密度适中 | 正文区域最大宽度 960px，卡片内边距 ≥ 16px |
| 即时反馈 | 每个用户操作都有明确视觉反馈 | 所有异步操作必须有 loading → success/error 状态 |
| 容错设计 | 错误状态提供恢复路径 | 错误页面必须有重试按钮或引导操作 |
| 一致性 | 同类元素统一交互模式 | 所有列表页共用同一状态机，所有表单共用校验规则 |
| 可访问性 | WCAG AA 标准 | 文字对比度 ≥ 4.5:1，触控目标 ≥ 44px，支持键盘导航 |

---

## 2. 风格定义

| 属性 | 值 | 来源 | 说明 |
|------|-----|------|------|
| design_style | `notion` | config.json | 干净、内容优先、微交互、大量留白 |
| design_color | `ocean` | config.json | 海洋蓝色系 |
| design_font | `clean` | config.json | 无衬线、干净 |
| design_theme | `light` | config.json | 浅色主题 |

> 工具推荐 Data-Dense Dashboard 风格，但 config.json 指定 notion，以 config.json 为准。
> 从工具推荐中吸收：row highlighting on hover、smooth filter animations、data loading spinners。

---

## 3. 配色系统

### 3.1 主色板

| 角色 | 色值 | CSS 变量 | 用途 |
|------|------|---------|------|
| Primary | `#0066cc` | `--primary` | 主按钮、链接、选中态、侧边栏高亮 |
| Primary Light | `#e6f2ff` | `--primary-light` | 选中行背景、Tag 背景、hover 底色 |
| Primary Dark | `#003d7a` | `--primary-dark` | 按钮 hover/active 态 |
| Accent | `#00b4d8` | `--accent` | 辅助强调、进度条、图标 |
| Background | `#ffffff` | `--bg` | 页面主背景 |
| Surface | `#f7f6f3` | `--surface` | 卡片背景、侧边栏、输入框 |
| Text | `#37352f` | `--text` | 正文文字 |
| Text Muted | `#9b9a97` | `--text-muted` | 辅助文字、placeholder |
| Border | `#e3e2de` | `--border` | 分割线、边框 |

### 3.2 语义色

| 语义 | 色值 | CSS 变量 | 用途 |
|------|------|---------|------|
| Success | `#0f766e` | `--success` | 成功 Toast、在线状态 |
| Success Light | `#ecfdf5` | `--success-light` | 成功 Toast 背景 |
| Warning | `#d97706` | `--warning` | 警告提示 |
| Warning Light | `#fffbeb` | `--warning-light` | 警告 Toast 背景 |
| Error | `#eb5757` | `--error` | 错误提示、删除按钮、必填星号 |
| Error Light | `#fef2f2` | `--error-light` | 错误 Toast 背景 |
| Info | `#0066cc` | `--info` | 信息提示（复用 Primary） |
| Info Light | `#e6f2ff` | `--info-light` | 信息 Toast 背景 |

### 3.3 CSS 变量定义

```css
:root {
  /* 主色 */
  --bg: #ffffff;
  --surface: #f7f6f3;
  --primary: #0066cc;
  --primary-light: #e6f2ff;
  --primary-dark: #003d7a;
  --accent: #00b4d8;
  /* 文字 */
  --text: #37352f;
  --text-muted: #9b9a97;
  /* 边框与阴影 */
  --border: #e3e2de;
  --shadow-sm: rgba(15, 15, 15, 0.04);
  --shadow-md: rgba(15, 15, 15, 0.08);
  --shadow-lg: rgba(15, 15, 15, 0.12);
  /* 语义色 */
  --success: #0f766e;
  --success-light: #ecfdf5;
  --warning: #d97706;
  --warning-light: #fffbeb;
  --error: #eb5757;
  --error-light: #fef2f2;
  --info: #0066cc;
  --info-light: #e6f2ff;
  /* 圆角 */
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;
  --radius-xl: 12px;
  /* 过渡 */
  --transition-fast: 150ms ease-out;
  --transition-normal: 200ms ease-out;
  --transition-slow: 300ms ease-out;
}
```

---

## 4. 字体系统

### 4.1 字体栈

| 用途 | 字体栈 | 来源 |
|------|--------|------|
| 正文 | `'Noto Sans SC', 'Source Han Sans SC', sans-serif` | config.json clean |
| 代码 | `'JetBrains Mono', 'Fira Code', monospace` | 工具推荐 |

> 工具推荐 Fira Code + Fira Sans，但 config.json 指定 clean（Noto Sans SC），以 config.json 为准。
> 代码/元数据场景采用工具推荐的 JetBrains Mono。

**Google Fonts 加载：**
```html
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;700&display=swap" rel="stylesheet">
```

### 4.2 字体层级

| Token | 大小 | 字重 | 行高 | 用途 |
|-------|------|------|------|------|
| h1 | 28px | 700 | 1.3 | 页面标题 |
| h2 | 22px | 600 | 1.4 | 区块标题 |
| h3 | 18px | 600 | 1.4 | 卡片标题、Modal 标题 |
| body | 15px | 400 | 1.6 | 正文内容 |
| small | 13px | 400 | 1.5 | 辅助文字、标签、筛选项 |
| caption | 12px | 500 | 1.4 | 时间戳、计数、Badge |
| code | 14px | 400 | 1.5 | 代码块、元数据字段 |

---

## 5. 间距系统

基准: 4px

| Token | 值 | 用途 |
|-------|-----|------|
| xs | 4px | 图标与文字间距 |
| sm | 8px | 紧凑元素间距、Tag 内边距 |
| md | 16px | 卡片内边距、表单字段间距 |
| lg | 24px | 区块间距、Modal 内边距 |
| xl | 32px | 页面区域间距 |
| 2xl | 48px | 大区块分隔 |

---

## 6. 组件规范

### 6.1 按钮

| 类型 | 样式 | 用途 |
|------|------|------|
| Primary | bg: var(--primary), text: white, radius: 6px, h: 40px | 主操作（保存、创建、搜索） |
| Secondary | bg: transparent, border: var(--border), text: var(--text), h: 40px | 次要操作（取消、筛选） |
| Danger | bg: transparent, text: var(--error), hover-bg: var(--error-light), h: 40px | 危险操作（删除） |
| Ghost | bg: transparent, text: var(--text-muted), hover-bg: var(--surface), h: 36px | 图标按钮、更多操作 |

**按钮状态矩阵：**

| 状态 | Primary | Secondary | Danger | Ghost |
|------|---------|-----------|--------|-------|
| Default | bg-primary text-white | border-border text-text | text-error | text-muted |
| Hover | bg-primary-dark | bg-surface | bg-error-light | bg-surface |
| Active | scale(0.98) bg-primary-dark | scale(0.98) | scale(0.98) | — |
| Disabled | opacity-50 cursor-not-allowed | opacity-50 | opacity-50 | opacity-50 |
| Loading | spinner + text 替换 + 禁用 | spinner + 禁用 | spinner + 禁用 | — |

### 6.2 输入框

| 属性 | 值 |
|------|-----|
| 高度 | 40px |
| 边框 | 1px solid var(--border) |
| 圆角 | var(--radius-md) |
| 背景 | var(--surface) |
| 内边距 | 0 12px |

**输入框状态：**

| 状态 | 边框 | 背景 | 附加 |
|------|------|------|------|
| Default | var(--border) | var(--surface) | — |
| Focus | var(--primary) | var(--bg) | box-shadow: 0 0 0 2px var(--primary-light) |
| Error | var(--error) | var(--bg) | 下方红色错误文字 |
| Disabled | var(--border) | #f0f0f0 | opacity: 0.6, cursor: not-allowed |

**校验规则：**
- 必填字段：onBlur 时校验，提交时再次校验
- 格式校验：onBlur 时校验
- 错误提示：字段下方 inline 红色文字，12px，var(--error)

### 6.3 卡片

| 属性 | 值 |
|------|-----|
| 背景 | var(--bg) |
| 边框 | 1px solid var(--border) |
| 圆角 | var(--radius-lg) |
| 阴影 | 0 1px 2px var(--shadow-sm) |
| 内边距 | 16px |

**卡片状态：**

| 状态 | 变化 |
|------|------|
| Default | 正常样式 |
| Hover | box-shadow: 0 2px 8px var(--shadow-md), translateY(-2px), cursor: pointer |
| Active | — |

### 6.4 Modal

| 属性 | 值 |
|------|-----|
| 宽度 | 560px（表单）/ 720px（详情） |
| 圆角 | var(--radius-xl) |
| 内边距 | 24px |
| 遮罩 | rgba(0, 0, 0, 0.4) |
| 进入动画 | fadeIn + translateY(20px→0) 200ms ease-out |
| 退出动画 | fadeOut + translateY(0→10px) 150ms ease-in |
| 关闭方式 | 点击遮罩 / ESC 键 / 右上角 × 按钮 |

**Modal 内部结构：**
```
┌─────────────────────────────┐
│ 标题                    [×] │  ← header, h3, 底部 1px border
├─────────────────────────────┤
│                             │
│ 内容区域                     │  ← body, max-height: 60vh, overflow-y: auto
│                             │
├─────────────────────────────┤
│              [取消] [主操作]  │  ← footer, 右对齐, 顶部 1px border
└─────────────────────────────┘
```

### 6.5 Toast

| 属性 | 值 |
|------|-----|
| 位置 | 右上角，距顶 24px 距右 24px |
| 宽度 | 360px |
| 圆角 | var(--radius-md) |
| 进入动画 | translateX(100%→0) 200ms ease-out |
| 退出动画 | opacity(1→0) 150ms ease-in |
| 堆叠 | 垂直堆叠，间距 8px |

**Toast 类型：**

| 类型 | 图标 | 背景 | 左边框 | 持续时间 |
|------|------|------|--------|---------|
| Success | fa-check-circle | var(--success-light) | 3px var(--success) | 3s |
| Error | fa-times-circle | var(--error-light) | 3px var(--error) | 5s |
| Warning | fa-exclamation-triangle | var(--warning-light) | 3px var(--warning) | 4s |
| Info | fa-info-circle | var(--info-light) | 3px var(--info) | 3s |

### 6.6 确认弹窗 (Confirm Dialog)

| 属性 | 值 |
|------|-----|
| 宽度 | 420px |
| 结构 | 图标 + 标题 + 描述 + 按钮组 |
| 危险操作 | 图标用 var(--error)，确认按钮用 Danger 样式 |
| 防重复提交 | 确认按钮点击后变为 loading 态 + 禁用 |

**触发场景（仅以下操作需要确认）：**
- 删除知识条目
- 删除 Skill
- 移除团队成员
- 导入元数据（覆盖操作）

### 6.7 骨架屏 (Skeleton)

| 类型 | 结构 |
|------|------|
| 卡片骨架 | 圆角矩形 + 2 行文字条 + 1 行短文字条 |
| 列表骨架 | 5 行，每行 = 圆形头像 + 2 行文字条 |
| 表格骨架 | 表头 + 5 行数据行 |
| 统计卡片骨架 | 4 个等宽矩形 |

**动画：** background shimmer，1.5s linear infinite
**颜色：** 基色 var(--border)，高光 var(--surface)

### 6.8 空状态 (Empty State)

| 属性 | 值 |
|------|-----|
| 布局 | 居中，图标 + 标题 + 描述 + CTA 按钮 |
| 图标 | Font Awesome 图标，48px，var(--text-muted) |
| 标题 | h3，var(--text) |
| 描述 | small，var(--text-muted) |
| CTA | Primary 按钮 |

### 6.9 分页 (Pagination)

| 属性 | 值 |
|------|-----|
| 布局 | 居中，页码按钮组 + 上一页/下一页 |
| 按钮大小 | 36px × 36px |
| 当前页 | bg: var(--primary), text: white |
| 其他页 | bg: transparent, text: var(--text), hover: var(--surface) |
| 禁用 | opacity: 0.5, cursor: not-allowed |

### 6.10 Tag / Badge

| 类型 | 样式 |
|------|------|
| 分类 Tag | bg: var(--primary-light), text: var(--primary), radius: 4px, padding: 2px 8px |
| 标签 Tag | bg: var(--surface), text: var(--text-muted), border: var(--border), radius: 4px |
| 状态 Badge | 圆形 8px，Success=绿色，Warning=黄色，Error=红色 |
| 索引 Badge | PK=红色, IDX=蓝色, UNI=绿色, radius: 2px, padding: 1px 6px, caption 字号 |

---

## 7. 图标

| 属性 | 值 |
|------|-----|
| 图标库 | Font Awesome 4.7 (CDN) |
| 内联大小 | 16px |
| 按钮大小 | 20px |
| 导航大小 | 24px |
| 颜色 | 继承父元素 color |

**禁止使用 emoji 作为功能图标。**

---

## 8. 交互模式

### 8.1 列表页统一状态机

```
init → loading → loaded(有数据) / empty(无数据) / error
                       ↓                            ↓
                  refreshing                   retry → loading
                       ↓
                  loaded / error
```

### 8.2 表单提交统一流程

```
填写 → 前端校验(onBlur) → 提交 → 按钮loading+禁用 → API请求
  → 成功: Toast(success) + 关闭Modal + 刷新列表
  → 失败: Toast(error) + 按钮恢复 + 保留表单数据
```

### 8.3 删除操作统一流程

```
点击删除 → 确认弹窗 → 确认按钮loading → API请求
  → 成功: Toast(success) + 关闭弹窗 + 刷新列表
  → 失败: Toast(error) + 按钮恢复
取消/ESC → 关闭弹窗，无操作
```

### 8.4 未保存退出保护

```
用户修改表单 → 标记 dirty=true
点击关闭/ESC/遮罩 → 检查 dirty
  → dirty=false: 直接关闭
  → dirty=true: 弹出确认弹窗「有未保存的修改，确定离开？」
    → 确认: 关闭Modal，丢弃修改
    → 取消: 返回编辑
```

---

## 9. 无障碍规范

| 规则 | 实现 |
|------|------|
| 键盘导航 | Tab 遍历可交互元素，Enter 触发，ESC 关闭浮层 |
| 焦点可见 | 所有可交互元素 focus 态有 2px outline |
| ARIA 标签 | Modal 用 role="dialog" aria-modal="true"，Toast 用 role="alert" |
| 颜色不是唯一指示 | 错误状态同时有红色边框 + 文字提示 |
| 触控目标 | 最小 44px × 44px |
| 减弱动效 | 尊重 prefers-reduced-motion |

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## 10. 交付检查清单

- [ ] 所有颜色使用 CSS 变量，不硬编码
- [ ] 间距遵循 4px 网格
- [ ] 字体层级不超过 7 级
- [ ] 所有按钮有 hover/active/disabled/loading 状态
- [ ] 所有输入框有 default/focus/error/disabled 状态
- [ ] 文字对比度 ≥ 4.5:1
- [ ] 可键盘导航（Tab/Enter/ESC）
- [ ] 触控目标 ≥ 44px
- [ ] 动画尊重 prefers-reduced-motion
- [ ] 不使用 emoji 作为功能图标
- [ ] 所有可点击元素有 cursor: pointer
- [ ] hover 过渡 150-300ms
- [ ] 骨架屏覆盖所有异步加载场景
- [ ] 空状态有引导操作
- [ ] 错误状态有重试路径
