# 🍎 Apple 风格设计优化说明

## 设计理念

遵循苹果设计系统的核心原则：**简约、优雅、注重细节**

### 核心设计原则

1. **留白与呼吸感** - 合理利用空间，避免视觉拥挤
2. **柔和的色彩** - 使用浅灰色系，避免过于鲜艳的颜色
3. **精致的圆角** - 使用更大的圆角半径(12px-20px)
4. **毛玻璃效果** - backdrop-blur 营造层次感
5. **细腻的阴影** - 轻柔的阴影，避免生硬
6. **流畅的动画** - 200ms 的过渡动画
7. **SF 字体** - 使用 -apple-system 字体栈

## 🎨 颜色系统

### Apple Gray Scale
```css
apple-50:  #fafafa  /* 背景色 */
apple-100: #f5f5f7  /* 次要背景 */
apple-200: #e8e8ed  /* 边框 */
apple-300: #d2d2d7  /* 分隔线 */
apple-400: #b0b0b5  /* 占位符 */
apple-500: #86868b  /* 次要文字 */
apple-600: #6e6e73  /* 导航文字 */
apple-700: #515154  /* 常规文字 */
apple-800: #3a3a3c  /* 强调文字 */
apple-900: #1d1d1f  /* 标题文字 */
```

### Apple Blue (Accent Color)
```css
apple-blue-500: #007aff  /* 主要交互色 - iOS Blue */
apple-blue-600: #0071e3  /* Hover 状态 */
```

### 苹果系统色
- **绿色**: #34c759 (Success)
- **橙色**: #ff9500 (Warning)
- **红色**: #ff3b30 (Error/Danger)
- **紫色**: #af52de (Purple)

## 📐 设计规范

### 圆角半径
```css
rounded-xl:   12px  /* 输入框、小卡片 */
rounded-2xl:  20px  /* 大卡片 */
rounded-3xl:  28px  /* 特大容器 */
rounded-full: 9999px /* 按钮、标签 */
```

### 间距系统
```css
gap-1:  4px   /* 最小间距 */
gap-2:  8px   /* 小间距 */
gap-3:  12px  /* 常规间距 */
gap-4:  16px  /* 中等间距 */
gap-6:  24px  /* 大间距 */
gap-8:  32px  /* 超大间距 */
```

### 阴影系统
```css
shadow-apple:    0 2px 16px rgba(0,0,0,0.08)   /* 轻柔阴影 */
shadow-apple-lg: 0 8px 32px rgba(0,0,0,0.12)   /* 中等阴影 */
shadow-apple-xl: 0 16px 48px rgba(0,0,0,0.16)  /* 强阴影 */
```

## 🎯 关键组件设计

### 1. 侧边栏 (Sidebar)
```
- 宽度: 288px (72 * 4)
- 背景: 白色毛玻璃 (bg-white/80 + backdrop-blur-2xl)
- Logo 区域高度: 80px
- 导航项圆角: 12px
- 激活状态: 蓝色背景 + 阴影
- Hover 状态: 淡灰色背景 + 图标放大
```

### 2. 统计卡片 (Stat Card)
```
- 圆角: 20px
- 内边距: 24px
- 背景: 白色到淡灰渐变
- 边框: 半透明灰色
- Hover: 向上移动 + 加深阴影
- 装饰图标: 半透明 + Hover 变色
```

### 3. 按钮 (Buttons)
```
主按钮 (Primary):
- 圆角: 全圆 (rounded-full)
- 背景: #007aff
- 内边距: 10px 20px
- Active: scale(0.95)

次要按钮 (Secondary):
- 圆角: 全圆
- 背景: apple-100
- 文字: apple-900
```

### 4. 输入框 (Input)
```
- 圆角: 12px
- 背景: apple-50
- 边框: apple-300/50 (半透明)
- Focus: 蓝色 ring + 边框变色
- 内边距: 12px 16px
```

### 5. 卡片 (Card)
```
- 圆角: 20px
- 背景: 白色毛玻璃 (white/80)
- 边框: apple-200/50
- 阴影: shadow-apple
- 内边距: 24px
```

### 6. 标签 (Badge)
```
- 圆角: 全圆
- 内边距: 4px 10px
- 字号: 12px
- 背景: 浅色 + 深色文字
```

## 📱 响应式设计

### 断点
```
sm:  640px
md:  768px
lg:  1024px
xl:  1280px
2xl: 1536px
```

### 侧边栏行为
- **桌面端 (≥1024px)**: 固定显示
- **移动端 (<1024px)**: Overlay 叠加层

## 🎭 动画与过渡

### 过渡时间
```
duration-200: 200ms  /* 标准过渡 */
duration-300: 300ms  /* 卡片 hover */
duration-500: 500ms  /* 页面切换 */
```

### 缓动函数
```
ease-out: cubic-bezier(0, 0, 0.2, 1)  /* 主要使用 */
ease-in-out: cubic-bezier(0.4, 0, 0.2, 1)
```

### 常用动画
```css
/* Hover 提升 */
hover:-translate-y-1

/* Active 缩放 */
active:scale-95

/* 图标放大 */
group-hover:scale-110
```

## 🔤 字体系统

### 字体栈
```css
font-family: -apple-system, BlinkMacSystemFont,
             'SF Pro Display', 'SF Pro Text',
             'Helvetica Neue', sans-serif;
```

### 字号等级
```
text-2xs:  11px   /* 辅助信息 */
text-xs:   12px   /* 标签、说明 */
text-sm:   14px   /* 正文 */
text-base: 16px   /* 标题 */
text-lg:   18px   /* 大标题 */
text-xl:   20px   /* 页面标题 */
text-4xl:  36px   /* 统计数字 */
```

### 字重
```
font-medium:   500  /* 常规强调 */
font-semibold: 600  /* 标题 */
font-bold:     700  /* 重要数字 */
```

### 字间距
```
tracking-tight: -0.025em  /* 大标题 */
tracking-wide:  0.025em   /* 小标签 */
```

## 📊 图表样式 (ECharts)

### 配色方案
```javascript
Apple Blue:   #007aff
Apple Green:  #34c759
Apple Purple: #af52de
Apple Orange: #ff9500
Apple Red:    #ff3b30
```

### 图表配置
```javascript
{
  tooltip: {
    backgroundColor: 'rgba(255, 255, 255, 0.95)',
    borderColor: '#e8e8ed',
    borderRadius: 12,
    padding: 12,
    textStyle: { color: '#1d1d1f', fontSize: 12 }
  },

  grid: {
    left: '3%',
    right: '4%',
    containLabel: true
  },

  xAxis/yAxis: {
    axisLabel: { color: '#86868b', fontSize: 11 },
    splitLine: { lineStyle: { color: '#f5f5f7', type: 'dashed' } }
  }
}
```

## ✨ 细节优化

### 1. 滚动条
```css
宽度: 10px
背景: transparent
滑块: rgba(0, 0, 0, 0.15) + 圆角
Hover: rgba(0, 0, 0, 0.25)
```

### 2. 选中文本
```css
background: rgba(0, 122, 255, 0.2)
```

### 3. Focus 状态
```css
outline: 2px solid rgba(0, 122, 255, 0.5)
outline-offset: 2px
```

### 4. 毛玻璃效果
```css
backdrop-filter: blur(20px)
-webkit-backdrop-filter: blur(20px)
```

## 🎪 交互反馈

### Hover 状态
- 卡片: 向上移动 + 加深阴影
- 按钮: 颜色变深 + scale(0.95)
- 导航: 背景变浅 + 图标放大

### Active 状态
- 所有可点击元素: scale(0.95)

### Loading 状态
- 脉冲动画: animate-pulse
- 渐显: opacity transition

## 📋 对比前后

### 之前 (深色侧边栏)
- 深色背景 (#001529)
- 强对比度
- 标准圆角 (8px)
- 鲜艳色彩

### 现在 (苹果风格)
- ✅ 白色毛玻璃侧边栏
- ✅ 柔和的浅灰色系
- ✅ 大圆角 (12px-20px)
- ✅ 细腻的阴影系统
- ✅ SF 字体
- ✅ 流畅的动画
- ✅ 极致的细节

## 🚀 性能优化

- CSS transitions 限制在 opacity 和 transform
- 使用 will-change 提示浏览器
- backdrop-filter 适度使用
- 避免复杂的 box-shadow 动画

## 📱 最佳实践

1. **保持一致性** - 统一的间距、圆角、颜色
2. **留白艺术** - 给元素足够的呼吸空间
3. **细腻过渡** - 200ms 的标准过渡时间
4. **层次分明** - 用阴影和毛玻璃营造深度
5. **克制的颜色** - 以灰色为主，蓝色点缀

---

**设计参考**: Apple.com, iOS/iPadOS Human Interface Guidelines
**字体**: San Francisco (系统默认)
**配色**: Apple Design Resources
