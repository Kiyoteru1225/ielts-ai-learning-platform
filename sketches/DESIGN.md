# Stripe Navy — IELTS 学习平台设计规范

> 基于 Stripe 设计系统，适配雅思 AI 学习平台

---

## 1. 色彩系统

```css
:root {
  /* 背景 */
  --color-bg:          #fafbfc;         /* 页面底色 */
  --color-surface:     #ffffff;         /* 卡片/面板 */
  --color-brand-dark:  #1c1e54;         /* 深色区域（统计面板） */

  /* 文字 */
  --color-heading:     #061b31;         /* 标题 — 深海军蓝 */
  --color-body:        #64748d;         /* 正文 — 石板灰 */
  --color-label:       #273951;         /* 标签 — 深石板 */
  --color-muted:       #94a3b8;         /* 次级/占位 */

  /* 品牌色 */
  --color-purple:      #533afd;         /* 主 CTA / 链接 */
  --color-purple-hover:#4434d4;         /* hover */
  --color-purple-light:#b9b9f9;         /* ghost 边框 */
  --color-purple-bg:   rgba(83,58,253,0.06);  /* 淡紫背景 */

  /* 边框 */
  --border-color:      #e5edf5;         /* 标准边框 */
  --border-radius:     4px;             /* 按钮/输入框 */
  --border-radius-card:6px;             /* 卡片 */

  /* 阴影 */
  --shadow-card: rgba(50,50,93,0.25) 0px 30px 45px -30px,
                 rgba(0,0,0,0.1) 0px 18px 36px -18px;
  --shadow-sm:  rgba(23,23,23,0.06) 0px 3px 6px;

  /* 状态 */
  --color-success:     #15be53;
  --color-success-text:#108c3d;
  --color-danger:      #ea2261;
  --color-danger-bg:   rgba(234,34,97,0.08);
}
```

## 2. 字体

```css
--font-primary: 'Source Sans 3', system-ui, -apple-system, sans-serif;
--font-mono:    'Source Code Pro', ui-monospace, monospace;
```

Google Fonts: `Source Sans 3:wght@300;400;600` + `Source Code Pro:wght@400`

## 3. 字体层级

| 角色 | 大小 | 字重 | 备注 |
|------|------|------|------|
| Hero 标题 | 40px | 300 | letter-spacing: -0.64px |
| 页面标题 | 28px | 300 | letter-spacing: -0.5px |
| 卡片标题 | 20px | 300 | letter-spacing: -0.22px |
| 正文 | 16px | 300 | line-height: 1.5 |
| 标签/按钮 | 14px | 400 | — |
| 辅助文字 | 13px | 300 | 次级信息 |
| 微文字 | 11px | 400 | 状态标签 |

## 4. 组件规格

### 按钮
- Primary: `#533afd` 背景, 白色文字, 4px 圆角, padding 10px 22px
- Ghost: 透明背景, `1px solid #b9b9f9` 边框, `#533afd` 文字
- Hover: primary → `#4434d4`, ghost → `rgba(83,58,253,0.04)` 背景

### 输入框
- 边框: `1px solid #e5edf5`, 4px 圆角, padding 10px 14px
- Focus: `border-color: #533afd`, `box-shadow: 0 0 0 3px rgba(83,58,253,0.1)`
- 标签: `#273951`, 14px, weight 400

### 卡片
- 白底, `1px solid #e5edf5` 边框, 6px 圆角
- 阴影: `--shadow-card`
- 内边距: 28-32px

### 导航
- 白色 sticky, `backdrop-filter: blur(12px)`, 底部 `1px solid #e5edf5`
- 品牌名: 15px weight 600, `#061b31`
- 链接: 14px weight 400, `#061b31`, hover → `#533afd`, active → `#533afd` weight 600
- Logo: 26×26, `#533afd` 背景, 4px 圆角, 白色文字

### 深色区域（统计面板）
- 背景: `#1c1e54`
- 文字: 白色
- 统计卡: `rgba(255,255,255,0.06)` 背景, `rgba(255,255,255,0.1)` 边框

### 警告/错误
- 错误: `rgba(234,34,97,0.08)` 背景, `#ea2261` 文字, `1px solid rgba(234,34,97,0.2)` 边框

### 成功/徽章
- `rgba(21,190,83,0.15)` 背景, `#108c3d` 文字, `1px solid rgba(21,190,83,0.3)` 边框

## 5. 页面清单

| 文件 | 功能 | Jinja2 扩展 |
|------|------|------------|
| `base.html` | 基础骨架（导航+页脚） | 无 |
| `login.html` | 登录表单 | extends base, block content |
| `register.html` | 注册表单 + 密码验证 JS | extends base, block content |
| `writing.html` | 写作提交页（textarea + task 选择） | extends base, block content |
| `result.html` | 评分结果（markdown 渲染 + 查看原文） | extends base, block content |
| `history.html` | 历史记录表格 | extends base, block content |

## 6. 重要原则

1. 不用 Bootstrap — 全部内联 `<style>` 或 `base.html` 中的 `<style>` 块
2. Google Fonts CDN: `Source Sans 3` + `Source Code Pro`
3. 所有标题用 weight 300, 负 letter-spacing
4. 按钮/链接用 `#533afd` 紫色, 不用蓝色
5. 卡片阴影必须是蓝调 `rgba(50,50,93,...)`
6. 保持所有现有的 Jinja2 变量、循环、条件不变
7. 保持所有现有的 form action、method、input name 不变
