# Knowledge — 设计系统 (Design System)

> 版本: 1.0 | 更新: 2026-03-27 | 状态: active
> 来源: config.json (优先) + ui-ux-pro-max 工具推荐 (补充)

---

## 1. 风格定义

| 属性 | 值 | 来源 |
|------|-----|------|
| design_style | `notion` | config.json |
| design_color | `ocean` | config.json |
| design_font | `clean` | config.json |
| design_theme | `light` | config.json |

**风格特征：** Notion-like — 干净、内容优先、微交互、大量留白、管理后台风格

---

## 2. 配色系统

### 2.1 主色板（ocean + notion 合并）

| 角色 | 色值 | 用途 |
|------|------|------|
| Primary | `#0066cc` | 主操作按钮、链接、选中态、侧边栏高亮 |
| Primary Light | `#e6f2ff` | 选中行背景、Tag 背景、hover 底色 |
| Primary Dark | `#003d7a` | 按钮 hover/active 态 |
| Accent | `#00b4d8` | 辅助强调、图标、进度条 |
| Background | `#ffffff` | 页面主背景 |
| Surface | `#f7f6f3` | 卡片背景、侧边栏背景、输入框背景 |
| Text | `#37352f` | 正文文字 |
| Text Muted | `#9b9a97` | 辅助文字、placeholder、时间戳 |
| Border | `#e3e2de` | 分割线、卡片边框、输入框边框 |

### 2.2 语义色

| 语义 | 色值 | 用途 |
|------|------|------|
| Success | `#0f766e` | 操作成功 Toast、状态标签 |
| Warning | `#d97706` | 警告提示 |
| Error / Danger | `#eb5757` | 错误提示、删除按钮、必填星号 |
| Info | `#0066cc` | 信息提示（复用 Primary） |

### 2.3 CSS 变量

```css
:root {
  --bg: #ffffff;
  --surface: #f7f6f3;
  --primary: #0066cc;
  --primary-light: #e6f2ff;
  --primary-dark: #003d7a;
  --accent: #00b4d8;
  --text: #37352f;
  --text-muted: #9b9a97;
  --border: #e3e2de;
  --shadow: rgba(15, 15, 15, 0.04);
  --success: #0f766e;
  --warning: #d97706;
  --error: #eb5757;
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;
}
```

---

## 3. 字体系统

### 3.1 字体栈

| 用途 | 字体栈 |
|------|--------|
| 正文 | `'Noto Sans SC', 'Source Han Sans SC', '思源黑体', sans-serif` |
| 代码/元数据 | `'JetBrains Mono', 'Fira Code', monospace` |

**Google Fonts 加载：**
```html
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;700&display=swap" rel="stylesheet">
```

### 3.2 字体层级

| 元素 | 大小 | 字重 | 行高 | 用途 |
|------|------|------|------|------|
| H1 | 28px | 700 | 1.3 | 页面标题 |
| H2 | 22px | 600 | 1.4 | 区块标题 |
| H3 | 18px | 600 | 1.4 | 卡片标题 |
| Body | 15px | 400 | 1.6 | 正文内容 |
| Small | 13px | 400 | 1.5 | 辅助文字、标签 |
| Caption | 12px | 500 | 1.4 | 时间戳、计数 |

---

## 4. 间距系统

基准: 4px

| Token | 值 | 用途 |
|-------|-----|------|
| xs | 4px | 图标与文字间距 |
| sm | 8px | 紧凑元素间距 |
| md | 16px | 卡片内边距、表单字段间距 |
| lg | 24px | 区块间距 |
| xl | 32px | 页面区域间距 |
| 2xl | 48px | 大区块分隔 |

---

## 5. 组件规范

### 5.1 按钮

| 类型 | 样式 | 用途 |
|------|------|------|
| Primary | bg: var(--primary), text: white, radius: 6px | 主操作（保存、创建、搜索） |
| Secondary | bg: transparent, border: var(--border), text: var(--text) | 次要操作（取消、筛选） |
| Danger | bg: transparent, text: var(--error), hover-bg: #fef2f2 | 危险操作（删除） |
| Ghost | bg: transparent, text: var(--text-muted), hover-bg: var(--surface) | 图标按钮、更多操作 |

**按钮状态：**

| 状态 | 变化 |
|------|------|
| Default | 正常样式 |
| Hover | 背景加深 5%，cursor: pointer |
| Active | 背景加深 10%，scale(0.98) |
| Disabled | opacity: 0.5, cursor: not-allowed |
| Loading | 文字替换为 spinner，禁用点击 |

### 5.2 输入框

- 高度: 40px
- 边框: 1px solid var(--border)
- 圆角: var(--radius-md)
- 背景: var(--surface)
- Focus: border-color: var(--primary), box-shadow: 0 0 0 2px var(--primary-light)
- Error: border-color: var(--error)

### 5.3 卡片

- 背景: var(--bg)
- 边框: 1px solid var(--border)
- 圆角: var(--radius-lg)
- 阴影: 0 1px 2px var(--shadow)
- Hover: box-shadow: 0 2px 8px rgba(15,15,15,0.08)
- 内边距: 16px

### 5.4 Modal

- 宽度: 560px (表单) / 720px (详情)
- 背景遮罩: rgba(0,0,0,0.4)
- 圆角: var(--radius-lg)
- 进入动画: fadeIn + slideUp 200ms ease-out
- 退出动画: fadeOut + slideDown 150ms ease-in
- 关闭方式: 点击遮罩 / ESC 键 / 关闭按钮

### 5.5 Toast

- 位置: 右上角，距顶 24px 距右 24px
- 宽度: 360px
- 圆角: var(--radius-md)
- 进入: slideInRight 200ms
- 退出: fadeOut 150ms
- 自动消失: success 3s, error 5s
- 堆叠: 多条 Toast 垂直堆叠，间距 8px

---

## 6. 图标

- 图标库: Font Awesome 4.7 (CDN)
- 大小: 16px (内联) / 20px (按钮) / 24px (导航)
- 颜色: 继承父元素 color
- 不使用 emoji 作为功能图标

---

## 7. 交付检查清单

- [ ] 所有颜色使用 CSS 变量，不硬编码
- [ ] 间距遵循 4px 网格
- [ ] 字体层级不超过 6 级
- [ ] 所有按钮有 hover/active/disabled 状态
- [ ] 文字对比度 ≥ 4.5:1
- [ ] 可键盘导航（Tab/Enter/ESC）
- [ ] 触控目标 ≥ 44px
- [ ] 动画尊重 prefers-reduced-motion
