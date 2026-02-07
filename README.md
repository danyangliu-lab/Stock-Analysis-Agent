# 智能股票推荐 Agent 系统 v2.0

基于 Python 的智能股票推荐 Agent，覆盖 **美股**、**港股** 和 **A股** 三大市场。系统通过技术指标分析与基本面评估相结合的多维评分模型，自动筛选优质标的并生成推荐报告。

**v2.0 新增 Streamlit Web 图形界面**，采用 **Apple HIG 设计风格**（毛玻璃效果、渐变光晕背景、CSS 变量驱动的亮/暗色自适应主题），支持常驻运行，提供批量分析、单股详细分析、市场概览仪表盘等可视化功能，同时保留完整的命令行操作方式。

支持动态获取指数成分股（S&P500、NASDAQ100、恒生指数、恒生科技、沪深300、创业板、科创板），并内置 **中概股**（40只，市值>50亿美元）和 **AI 概念股**（81只，芯片/存储/数据中心/应用/能源等全产业链）专题股票池。

---

## 目录

- [系统架构](#系统架构)
- [v2.0 Web 图形界面](#v20-web-图形界面)
- [模块详解](#模块详解)
- [股票池覆盖范围](#股票池覆盖范围)
- [评分模型详解](#评分模型详解)
- [快速开始](#快速开始)
- [使用方式](#使用方式)
- [配置说明](#配置说明)
- [扩展指南](#扩展指南)
- [已知限制与注意事项](#已知限制与注意事项)
- [免责声明](#免责声明)

---

## 系统架构

### 项目结构

```
demo-agent/
├── app.py                               # Streamlit Web UI 入口 (v2.0 新增)
├── main.py                              # 命令行主入口
├── requirements.txt                     # Python 依赖
├── .gitignore                           # Git 忽略规则
└── stock_agent/                         # 核心包
    ├── __init__.py                      # 包初始化
    ├── config.py                        # 全局配置中心 (三市场差异化配置)
    ├── index_constituents.py            # 指数成分股动态获取 (Wikipedia + 缓存)
    ├── data_provider.py                 # 数据接口模块 (yfinance)
    ├── technical_analyzer.py            # 技术指标分析模块
    ├── fundamental_analyzer.py          # 基本面评估模块
    ├── strategy_engine.py               # 策略分析与筛选模块
    ├── recommendation.py                # 推荐输出模块
    └── agent.py                         # Agent 主控模块
```

### 数据流向

```
┌────────────────────────────────────────────────────────────────────┐
│  StockAgent (Main Controller)                                      │
│                                                                    │
│  AgentConfig                                                       │
│    MarketConfig      stock pool + dynamic/static mode              │
│    ScoringWeights    US 35:65 / HK 30:70 / CN 40:60                │
│    ThresholdConfig   filters + market thresholds                   │
└──────────────────────────────────┬─────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────┐
│  (1) IndexConstituents                                             │
│                                                                    │
│  Dynamic: Wikipedia -> JSON cache (24h TTL)                        │
│                                                                    │
│    US 700+          HK 100+         CN 500+                        │
│    S&P500           Hang Seng        CSI300                        │
│    NASDAQ100        Hang Seng Tech   ChiNext                       │
│    Chinese ADR x40                   STAR Market                   │
│    AI Sector   x81                   (cap >= 10B CNY)              │
│                                                                    │
│  Fallback: US 65 / HK 40 / CN 35                                   │
└──────────────────────────────────┬─────────────────────────────────┘
                                   │ symbols[]
                                   ▼
┌────────────────────────────────────────────────────────────────────┐
│  (2) DataProvider (yfinance)                                       │
│                                                                    │
│    per-stock request, 0.3s interval                                │
│    OHLCV history (120 cal days ~ 80 trading days)                  │
│    fundamentals via .info dict                                     │
│    retry x2, linear backoff                                        │
│    in-memory cache, 1h TTL                                         │
│                                                                    │
│  Output: dict[symbol -> StockData]                                 │
└─────────────────┬────────────────────────────────┬─────────────────┘
                  │                                │
                  ▼                                ▼
┌─────────────────────────────────┐  ┌─────────────────────────────────┐
│ (3) TechnicalAnalyzer           │  │ (4) FundamentalAnalyzer         │
│                                 │  │                                 │
│ 5 indicators (0-100)            │  │ 10 metrics (0-100)              │
│   MA trend                      │  │   PE / PB / ROE                 │
│   RSI (14d)                     │  │   Revenue & Earnings grw        │
│   MACD                          │  │   Profit margin / FCF           │
│   Bollinger Bands               │  │   Debt ratio / PEG              │
│   Volume trend                  │  │   Dividend (HK only)            │
│                                 │  │                                 │
│ Weighted by market              │  │ Weighted by market              │
│ -> technical score              │  │ + growth deep analysis          │
│ -> signal list                  │  │ -> fundamental score            │
└────────────────┬────────────────┘  └────────────────┬────────────────┘
                 │                                  │
                 └────────────────┬─────────────────┘
                                  │
                                  ▼
┌────────────────────────────────────────────────────────────────────┐
│  (5) StrategyEngine                                                │
│                                                                    │
│  score = tech x weight + fund x weight  (cap 100)                  │
│                                                                    │
│    >=80  Strong Buy  +++                                           │
│    >=65  Buy         ++                                            │
│    >=50  Hold        +                                             │
│     <50  Avoid       -                                             │
│                                                                    │
│  Filter: score >= min_score, top max_count                         │
│  Auto-generate recommendation reasons                              │
└──────────────────────────────────┬─────────────────────────────────┘
                                   │ recommendations[] + all_evaluations[]
                                   ▼
┌────────────────────────────────────────────────────────────────────┐
│  (6) Output                                                        │
│                                                                    │
│  ┌────────────────────────────┐    ┌────────────────────────────┐  │
│  │ RecommendationReporter     │    │ Streamlit Web UI           │  │
│  │ (CLI)                      │    │ (v2.0 Apple HIG)           │  │
│  │                            │    │                            │  │
│  │   Terminal table           │    │   Batch dashboard          │  │
│  │   JSON output              │    │   Single stock detail      │  │
│  │   Python dict              │    │   Market overview          │  │
│  └────────────────────────────┘    └────────────────────────────┘  │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### 完整执行流程

```
1. 股票池构建 (IndexConstituents → DataProvider._get_xx_symbols)
   ├── 动态模式 (use_dynamic_constituents=True):
   │   ├── 美股: Wikipedia 解析 S&P500 + NASDAQ100 + 中概股静态列表(40只) + AI概念股静态列表(81只)
   │   │        → 合并去重 → 约 700+ 只
   │   ├── 港股: Wikipedia 解析 恒生指数 + 恒生科技
   │   │        → 合并去重 → 约 100+ 只
   │   └── A股: Wikipedia 解析 沪深300 + 创业板 + 科创板
   │            → 创业板/科创板额外做市值过滤(>=100亿人民币) → 合并去重 → 约 500+ 只
   └── 静态模式 (use_dynamic_constituents=False 或动态获取失败):
       └── 使用 config.py 中的 fallback 列表 (美股65只/港股40只/A股35只)

2. 数据获取 (DataProvider.get_batch_data)
   ├── 逐只请求 yfinance，间隔 0.3s
   ├── 获取历史行情 (默认 120 自然日，约 80 个交易日 OHLCV)
   ├── 获取基本面 (.info 字典)
   ├── 失败自动重试 (最多 2 次，线性递增延时)
   └── 结果写入内存缓存 (1 小时 TTL)

3. 技术面分析 (TechnicalAnalyzer.analyze)
   ├── 计算 5 大技术指标 → 各自独立评分 0-100
   ├── 按市场权重加权汇总 → 技术面评分 0-100
   └── 生成信号文本 (如"MA5上穿MA20，出现金叉信号")

4. 基本面分析 (FundamentalAnalyzer.analyze)
   ├── 计算 10 项指标评分 → 各自独立评分 0-100
   ├── 按市场权重加权汇总 → 基本面基础分
   ├── 成长性深度分析 (营收增速+盈利增速+PEG) → 成长标签 + 加分
   └── 基本面评分 = 基础分 + 成长性加分 (上限 100)

5. 策略引擎 (StrategyEngine.evaluate → evaluate_batch → filter_recommendations)
   ├── 综合评分 = 技术面 × 权重 + 基本面 × 权重 (上限 100)
   ├── 推荐等级: >=80 强烈推荐 / >=65 推荐 / >=50 观望 / <50 不推荐
   ├── 自动生成推荐理由 (技术概览+基本面概览+成长标签+关键信号)
   ├── 按总分降序排列
   └── 筛选: 分数 >= min_score (默认60) 且取前 max_count (默认10) 只

6. 输出报告 (RecommendationReporter)
   ├── 终端表格报告: 推荐列表 + 理由详情 + 关键指标 + 全市场概览
   ├── JSON 结构化输出: 完整评估数据，含 metrics/growth_profile/technical_indicators
   └── Python 字典: list[dict] 格式供程序内部消费

7. Web 图形界面 (app.py, v2.0 新增)
   ├── Apple HIG 设计: 毛玻璃效果、渐变光晕背景、CSS 变量亮/暗色自适应
   ├── 直接调用 StockAgent.run() 和 analyze_single() 接口
   ├── 批量分析: 市场概览仪表盘 + 推荐排名表 + 理由详情卡片
   ├── 单股分析: 评分圆环 + 技术面/基本面子评分 + 成长性分析
   └── 状态管理: st.session_state 保持结果，支持常驻运行
```

---

## v2.0 Web 图形界面

v2.0 新增基于 **Streamlit** 的 Web 图形界面，采用 **Apple Human Interface Guidelines (HIG)** 设计风格，支持常驻运行，浏览器中即可操作全部分析功能。

### 设计风格

- **字体**: Inter（SF Pro 的 Web 替代方案）+ -apple-system 系统回退链
- **毛玻璃效果**: 侧边栏、顶部导航栏采用 `backdrop-filter: saturate(180%) blur(20px)` 磨砂半透明
- **圆角卡片**: 16-20px 圆角矩形，悬停上浮 2px + 阴影加深动画
- **渐变光晕背景**: 蓝色（右上）、绿色（左下）、橙色（右中）三色 `radial-gradient`，30s 缓慢漂移动画；底层 60px 网格纹理增加空间感
- **亮/暗色自适应**: 全部颜色通过 CSS 变量（`--text-primary`、`--bg-card`、`--border-color` 等）定义，暗色模式通过 `@media (prefers-color-scheme: dark)` 和 Streamlit `[data-theme="dark"]` 双重检测自动切换
- **配色方案**: Apple 系统色——蓝 `#007AFF`、红 `#FF3B30`、橙 `#FF9500`、绿 `#34C759`、灰 `#8E8E93`
- **响应式**: 桌面端 `max-width: 1200px` 居中，移动端自动缩小间距和字号

### 启动方式

```bash
# 推荐方式
python3 -m streamlit run app.py

# 或（如果 streamlit 已在 PATH 中）
streamlit run app.py
```

默认在 `http://localhost:8501` 启动，浏览器自动打开。

### 功能概览

`app.py` 实现了两个主要页面，通过侧边栏切换：

#### 页面一：批量分析

| 区域 | 功能 |
|------|------|
| **侧边栏配置** | 市场选择（全部/美股/港股/A股）、自定义股票代码、动态成分股开关、最低推荐分数、最大推荐数量 |
| **概览指标** | 4 个毛玻璃指标卡片：分析股票数、有效数据、推荐股票数、分析耗时（悬停上浮动效） |
| **市场概览仪表盘** | 按市场分栏展示：股票数量、平均分、最高分（颜色标识）、推荐等级分布条、成长标签分布 |
| **推荐排名表** | 带进度条可视化的排名表格，展示综合分/技术分/基本面分/成长标签/推荐等级 |
| **推荐理由详情** | 可展开的圆角卡片式详情（前 3 名默认展开），含评分圆环、推荐/成长标签、关键财务指标（PE/ROE/营收增速/盈利增速/PEG）和推荐理由信号列表 |
| **全市场评分一览** | 可展开的完整股票表格，支持按市场筛选和按评分排序 |

#### 页面二：单股详细分析

| 区域 | 功能 |
|------|------|
| **头部信息** | 毛玻璃卡片：股票代码、公司名称、市场、行业、推荐等级标签（颜色标识）、评分圆环 |
| **评分概览** | 4 个指标卡片：综合评分、技术面评分、基本面评分、成长加分 |
| **技术面分析** | 5 个技术指标子评分（MA/RSI/MACD/布林带/成交量）+ 指标数值 + 技术信号列表 |
| **基本面分析** | 各基本面指标子评分 + 关键财务指标（PE/PB/ROE/营收增速/盈利增速/利润率/负债率/PEG/股息率）+ 成长性分析 + 基本面信号 |
| **推荐理由** | 综合推荐理由汇总 |

### 界面与命令行对比

| 维度 | 命令行 (`main.py`) | Web UI (`app.py`) |
|------|--------------------|--------------------|
| 启动方式 | `python main.py` | `python3 -m streamlit run app.py` |
| 交互方式 | 参数输入，一次性运行 | 浏览器操作，常驻运行 |
| 参数配置 | 命令行参数 `--market`、`--min-score` 等 | 侧边栏滑块、下拉框、输入框 |
| 结果展示 | 终端文本表格 / JSON | Apple 风格可视化：毛玻璃卡片 + 评分圆环 + 进度条表格 + 可展开详情 |
| 市场概览 | 文本汇总 | 分栏仪表盘（推荐分布/成长分布） |
| 单股分析 | `--single NVDA` | 独立页面，完整技术面+基本面子评分 |
| 适用场景 | 脚本自动化、CI/CD、数据管道 | 日常查看、交互式探索 |

### 技术实现

- **Apple HIG 设计**: 全局 CSS 采用 Inter 字体 + Apple 系统色，毛玻璃侧边栏/导航栏（`backdrop-filter`），圆角卡片悬停动效（`translateY(-2px)`），评分圆环和彩色推荐/成长标签
- **亮暗色自适应**: 所有颜色通过 CSS 变量定义（`--text-primary`、`--bg-card`、`--border-color` 等），暗色模式通过 `@media (prefers-color-scheme: dark)` + Streamlit `[data-theme="dark"]` 双重检测自动切换，内联 HTML 样式同样使用 `var()` 引用
- **背景装饰**: 使用 `.stApp::before` 伪元素绘制三色渐变光晕（蓝/绿/橙 `radial-gradient`，30s 漂移动画）+ `.stApp::after` 绘制 60px 网格纹理，不受 Streamlit DOM 容器裁剪
- **状态管理**: 使用 `st.session_state` 保存分析结果、页面状态和分析耗时，页面刷新不丢失已有结果
- **按钮触发**: 通过 `st.session_state` key 传递按钮状态，避免变量作用域问题
- **数据复用**: Web UI 直接调用 `StockAgent` 的 `run()` 和 `analyze_single()` 接口，与命令行共享全部后端逻辑
- **进度提示**: 分析过程使用 `st.spinner` 显示加载状态
- **表格渲染**: 使用 `st.dataframe` + `st.column_config.ProgressColumn` 实现评分进度条可视化
- **隐藏默认元素**: 通过 CSS 隐藏 Streamlit 默认的 Deploy 按钮、汉堡菜单和页脚，兼容多个 Streamlit 版本

---

## 模块详解

### 1. 配置中心 (`config.py`)

采用 Python `dataclass` 实现，支持三大市场差异化配置。

#### 核心配置类

| 配置类 | 职责 |
|--------|------|
| `MarketConfig` | 股票池定义 + 动态/静态模式切换 + 缓存过期时间 |
| `MarketScoringProfile` | 单市场评分权重（技术面子指标权重、基本面子指标权重、综合占比、成长性加分上限） |
| `ScoringWeights` | 三市场 `MarketScoringProfile` 的聚合，提供 `get_profile(market)` |
| `MarketThresholds` | 单市场筛选阈值（PE 上限、PB 上限、ROE 下限、成长股判定线） |
| `ThresholdConfig` | 全局筛选参数 + 三市场差异化阈值 |
| `AgentConfig` | 顶层总配置入口，聚合上述所有配置 |

#### 三市场差异化设计

| 维度 | 美股(US) | 港股(HK) | A股(CN) | 设计理由 |
|------|----------|----------|---------|----------|
| 技术面 : 基本面权重 | 35% : 65% | 30% : 70% | 40% : 60% | A股散户多、资金面驱动强；港股机构主导、重估值 |
| 成长性加分上限 | 15 分 | 12 分 | 18 分 | A股对成长弹性敏感度更高 |
| PE 上限 | 60 | 40 | 50 | 美股科技股估值容忍度高；港股低估值偏好 |
| ROE 下限 | 8% | 5% | 6% | 美股盈利质量门槛高 |
| 基本面特色指标 | 重 `revenue_growth`(0.18) | 独有 `dividend_yield`(0.10) | 重 `earnings_growth`(0.17) | 港股高息策略；A股看盈利弹性 |

#### 代码示例

```python
from stock_agent.config import AgentConfig, ScoringWeights

config = AgentConfig()

# 获取美股评分配置
us_profile = config.weights.get_profile("US")
print(us_profile.technical_weight)      # 0.35
print(us_profile.fundamental_weight)    # 0.65
print(us_profile.growth_bonus_cap)      # 15.0

# 获取 A 股筛选阈值
cn_thresholds = config.thresholds.get_market_thresholds("CN")
print(cn_thresholds.max_pe_ratio)       # 50.0
print(cn_thresholds.high_growth_revenue) # 25.0
```

---

### 2. 指数成分股模块 (`index_constituents.py`)

从 Wikipedia 动态解析指数成分股 HTML 表格，结果缓存为本地 JSON 文件（默认 24 小时过期）。

#### 支持的指数/股票池

| 数据源 | 公共方法 | 说明 |
|--------|----------|------|
| **美股** | `get_us_symbols()` | S&P500 + NASDAQ100 + 中概股 + AI概念股 **合并去重** |
| S&P 500 | `get_sp500()` | 英文 Wikipedia 解析 |
| NASDAQ 100 | `get_nasdaq100()` | 英文 Wikipedia 解析 |
| 中概股 | `get_chinese_adr()` | **静态列表** 40 只市值>50亿美元的中国公司 |
| AI 概念股 | `get_ai_sector()` | **静态列表** 81 只 AI 产业链核心标的 |
| **港股** | `get_hk_symbols()` | 恒生指数 + 恒生科技 **合并去重** |
| 恒生指数 | `get_hsi()` | 英文 Wikipedia 解析 |
| 恒生科技 | `get_hstech()` | 中文 Wikipedia 解析 |
| **A股** | `get_cn_symbols()` | 沪深300 + 创业板 + 科创板 **合并去重** |
| 沪深 300 | `get_csi300()` | 英文 Wikipedia 解析 |
| 创业板 | `get_chinext()` | 中文 Wikipedia 解析（排除退市/暂缓上市） |
| 科创板 | `get_star()` | 中文 Wikipedia 解析（排除退市/暂缓上市） |

#### 中概股列表 (`CHINESE_ADR_SYMBOLS`)

覆盖互联网/电商（BABA、PDD、JD）、新能源汽车（NIO、XPEV、LI）、金融科技（FUTU、QFIN）、数据中心（GDS、VNET）等 40 只市值>50亿美元的中国公司。

#### AI 概念股列表 (`AI_SECTOR_SYMBOLS`)

按产业链分类的 81 只核心标的：

| 板块 | 代表股票 | 数量 |
|------|----------|------|
| AI 芯片/半导体 | NVDA, AMD, ARM, MRVL, TSM, ASML, QCOM | 18 只 |
| AI 存储/HBM | MU, WDC, STX | 3 只 |
| 数据中心基础设施 | ANET, VRT, EQIX, DELL, SMCI | 12 只 |
| 云计算/AI 平台 | MSFT, GOOGL, AMZN, PLTR, SNOW, DDOG | 15 只 |
| AI 应用/SaaS | ADBE, PANW, CRWD, SHOP, UBER | 18 只 |
| AI 机器人/自动驾驶 | TSLA, ISRG, SOUN, IONQ | 11 只 |
| AI 电力/能源 | VST, CEG, NRG, FSLR | 4 只 |

#### 缓存机制

```
stock_agent/.cache/
├── SP500.json          # S&P 500 成分股缓存
├── NASDAQ100.json      # NASDAQ 100 成分股缓存
├── HSI.json            # 恒生指数成分股缓存
├── HSTECH.json         # 恒生科技成分股缓存
├── CSI300.json         # 沪深 300 成分股缓存
├── CHINEXT.json        # 创业板成分股缓存
├── STAR.json           # 科创板成分股缓存
└── MCAP_CNY_*.json     # 市值过滤结果缓存
```

缓存目录为 `stock_agent/.cache/`，缓存文件均为 JSON 格式，包含 `timestamp`（写入时间）和 `symbols`（股票列表）。默认 24 小时过期，可通过 `--refresh-cache` 强制刷新。

---

### 3. 数据接口模块 (`data_provider.py`)

通过 **Yahoo Finance** (`yfinance`) 统一获取三大市场数据。

#### 核心类

**`StockData`** — 股票数据容器

```python
@dataclass
class StockData:
    symbol: str                          # 股票代码 (Yahoo Finance 格式)
    market: str                          # "US" / "HK" / "CN"
    history: pd.DataFrame | None = None  # OHLCV 历史数据
    info: dict[str, Any] = {}            # 基本面信息字典 (yfinance .info)
    fetch_time: datetime | None = None   # 数据获取时间
    error: str | None = None             # 错误信息

    @property
    def is_valid(self) -> bool:          # history 非空且无错误
        return self.history is not None and not self.history.empty and self.error is None
```

**市场自动识别规则**:
- `.HK` 后缀 → 港股 (`9988.HK`)
- `.SS` / `.SZ` 后缀 → A 股 (`600519.SS`, `000001.SZ`)
- 其他 → 美股 (`AAPL`)

**`DataProvider`** — 数据获取器

| 方法 | 说明 |
|------|------|
| `get_stock_data(symbol)` | 获取单只股票数据（行情+基本面） |
| `get_batch_data(symbols)` | 批量获取，每只间隔 0.3s |
| `get_us_stocks()` | 获取美股股票池完整数据 |
| `get_hk_stocks()` | 获取港股股票池完整数据 |
| `get_cn_stocks()` | 获取 A 股股票池完整数据 |
| `get_all_stocks()` | 获取三市场全部数据 |

#### 容错机制

- **自动重试**: 失败后最多重试 2 次，线性递增延时
- **内存缓存**: 1 小时 TTL，避免重复请求
- **批量限速**: 每只股票间隔 0.3 秒
- **容错隔离**: 单只股票失败不影响整体流程

#### 市值过滤

- **创业板/科创板**: >= 100 亿人民币
- **中概股**: >= 50 亿美元（静态列表已预筛选）

```python
def _filter_by_market_cap(
    self,
    symbols: list[str],
    min_cap: float,
    currency_mode: str = "CNY",  # "CNY" 或 "USD"
) -> list[str]:
    """市值过滤，支持人民币/美元两种基准，结果缓存"""
```

---

### 4. 技术指标分析模块 (`technical_analyzer.py`)

计算 **5 大技术指标**，各自独立评分 0–100，最终按市场权重加权汇总。

#### 技术指标详解

| 指标 | 默认权重 | 计算逻辑 | 评分逻辑 |
|------|----------|----------|----------|
| **MA 均线趋势** | 25% | MA5/MA20/MA60 | 价格站上均线加分；金叉+15分，死叉-15分 |
| **RSI (14日)** | 20% | 相对强弱指数 | 超卖(<30)→80分；超买(>70)→20分；中性→55分 |
| **MACD** | 25% | DIF/DEA/柱状图 | DIF>DEA 多头+15分；柱状图翻正+15分；零轴以上+10分 |
| **布林带** | 15% | 20日均线±2倍标准差 | 接近下轨→75分；接近上轨→25分；中轨附近→55分 |
| **成交量趋势** | 15% | VOL/VOL_MA5/VOL_MA20 | 放量上涨+20分；放量下跌-15分；量能萎缩-5分 |

#### 信号生成示例

```
技术面评分 78 (偏强)
├── MA5上穿MA20，出现金叉信号
├── RSI=42.5 偏低，有一定上涨空间
├── MACD: DIF > DEA，多头排列
└── 放量上涨，买盘力量增强
```

#### 代码结构

```python
class TechnicalAnalyzer:
    def analyze(self, stock: StockData) -> TechnicalResult:
        # 1. 计算各指标
        ma_score, ma_signals, ma_vals = self._score_ma_trend(df)
        rsi_score, rsi_signals, rsi_vals = self._score_rsi(df)
        macd_score, macd_signals, macd_vals = self._score_macd(df)
        boll_score, boll_signals, boll_vals = self._score_bollinger(df)
        vol_score, vol_signals, vol_vals = self._score_volume_trend(df)
        
        # 2. 按市场权重加权
        tech_weights = self.config.weights.get_profile(stock.market).technical
        total = sum(sub_scores[key] * weight for key, weight in tech_weights.items())
        
        return TechnicalResult(score=total, sub_scores=..., signals=..., indicators=...)
```

---

### 5. 基本面评估模块 (`fundamental_analyzer.py`)

评估 **10 项基本面指标**，按市场差异化权重汇总，并额外进行 **成长性深度分析** 给予加分。

#### 基本面指标详解

| 指标 | 美股权重 | 港股权重 | A股权重 | 评分逻辑 |
|------|----------|----------|---------|----------|
| **PE 市盈率** | 12% | 15% | 12% | 参照行业基准 PE 进行相对估值，低于基准 0.7 倍→80分 |
| **PB 市净率** | 5% | 10% | 8% | PB<1→80分（可能被低估）；PB>10→20分 |
| **ROE** | 15% | 15% | 15% | 卓越(>25%)→90分；优秀(15-25%)→80分 |
| **营收增长率** | 18% | 15% | 18% | 高速增长(>=高成长线)→90分；稳健(5-15%)→60分 |
| **净利润增速** | 15% | 10% | 17% | 高速增长(>=高成长线)→90分；大幅下滑(<-20%)→10分 |
| **净利润率** | 10% | 10% | 10% | 优秀(>20%)→85分；亏损→10分 |
| **自由现金流** | 10% | — | 5% | FCF Yield>6%→85分；负现金流→30分 |
| **负债/权益比** | 5% | 8% | 5% | <20%→90分（财务优良）；>200%→15分 |
| **PEG** | 10% | 7% | 10% | <0.5→90分（成长性价比极高）；>2.5→25分 |
| **股息率** | — | 10% | — | 港股专属：股息率>5%→90分 + 港股高息策略加分 |

#### 行业基准 PE

内置 11 个行业的 PE 基准值，用于相对估值：

```python
SECTOR_PE_BENCHMARKS = {
    "Technology": 30.0,
    "Financial Services": 15.0,
    "Healthcare": 25.0,
    "Consumer Cyclical": 22.0,
    "Energy": 12.0,
    # ...
}
```

#### 成长性深度分析

基于 **营收增速 + 盈利增速 + PEG** 三维度判定成长标签并给予加分：

| 成长标签 | 判定条件 | 基础加分 |
|----------|----------|----------|
| **超高成长** | 营收增速 >= 高成长线 且 盈利增速 >= 高成长线 | +12 分 |
| **高盈利成长** | 营收稳健 且 盈利增速 >= 高成长线 | +9 分 |
| **高营收成长** | 营收增速 >= 高成长线 | +7 分 |
| **稳健成长** | 营收增速 >= 最低成长线 且 盈利 > 0 | +4 分 |
| **低成长** | 增速低于阈值 | 0 分 |
| **双降** | 营收 < 0 且 盈利 < 0 | -5 分 |

**PEG 额外加分**:
- PEG < 0.8 → +4 分（成长性估值极具吸引力）
- PEG 0.8-1.2 → +2 分（估值与成长匹配合理）
- PEG > 2.0 → -2 分（成长性相对估值偏贵）

**自由现金流佐证**:
- 正现金流 → +1.5 分
- 负现金流 → -1 分

成长性加分上限由市场配置决定：美股 15 分、港股 12 分、A股 18 分。

---

### 6. 策略引擎 (`strategy_engine.py`)

整合技术面和基本面分析，生成综合评分、推荐等级和推荐理由。

#### 综合评分公式

```
综合评分 = 技术面评分 × 技术权重 + 基本面评分 × 基本面权重
         (基本面评分已包含成长性加分)

上限: 100 分
```

#### 推荐等级

| 分数区间 | 推荐等级 | 图标 |
|----------|----------|------|
| >= 80 | 强烈推荐 | ★★★ |
| 65-79 | 推荐 | ★★☆ |
| 50-64 | 观望 | ★☆☆ |
| < 50 | 不推荐 | ☆☆☆ |

#### 推荐理由生成

自动提取关键信号，生成简明推荐理由：

```python
def _generate_reasons(self, tech, fund, evaluation):
    reasons = []
    
    # 技术面概览
    reasons.append(f"技术面评分 {tech.score:.0f} (偏强/中性/偏弱)")
    
    # 基本面概览
    reasons.append(f"基本面评分 {fund.score:.0f} (优良/一般/较差)")
    
    # 成长标签
    if evaluation.growth_label not in ("未知", "低成长"):
        reasons.append(f"成长标签: {evaluation.growth_label} (加分 +X.X)")
    
    # 关键技术信号 (最多2条): 金叉/死叉/超卖/超买/放量上涨...
    # 关键基本面信号 (最多2条): 低估/高速增长/PEG吸引力...
    
    return reasons
```

#### 核心方法

```python
class StrategyEngine:
    def evaluate(self, stock: StockData) -> StockEvaluation:
        """单只股票综合评估"""
        
    def evaluate_batch(self, stocks: dict[str, StockData]) -> list[StockEvaluation]:
        """批量评估，按总分降序排列"""
        
    def filter_recommendations(self, evaluations) -> list[StockEvaluation]:
        """按 min_score 和 max_count 筛选推荐"""
```

---

### 7. 推荐输出模块 (`recommendation.py`)

支持 **3 种输出格式**。

#### 终端表格报告 (`print_report()`)

支持自定义标题（`title` 参数），默认标题为"智能股票推荐报告"。

```
==========================================================================================
  智能股票推荐报告
  生成时间: 2026-02-07 10:30:00
==========================================================================================

  推荐股票 (5 只)
------------------------------------------------------------------------------------------
  排名   代码        公司                市场  综合分  技术分  基本面分 成长       推荐
------------------------------------------------------------------------------------------
  1     NVDA        NVIDIA Corporation  US    82.5    78.0    85.3    超高成长   强烈推荐 ★★★
  2     PLTR        Palantir            US    76.2    72.5    78.6    高盈利成长 推荐 ★★☆
  3     PDD         拼多多              US    74.8    68.3    79.1    高营收成长 推荐 ★★☆
  ...

==========================================================================================
  推荐理由详情
==========================================================================================

  [1] NVDA - NVIDIA Corporation
      综合评分: 82.5  |  推荐等级: 强烈推荐  |  成长标签: 超高成长
      成长性加分: +15.0
      · 技术面评分 78 (偏强)
      · 基本面评分 85 (优良)
      · 成长标签: 超高成长 (加分 +15.0)
      · MA5上穿MA20，出现金叉信号
      · 营收增长率=122.4%，高速增长
      指标: PE=65.2 | ROE=45.0% | 营收增速=122.4% | 盈利增速=85.6% | PEG=1.05

  ...

==========================================================================================
  全市场概览
------------------------------------------------------------------------------------------
  美股: 85 只已分析, 平均分 62.3, 成长分布: 稳健成长(22), 低成长(18), 超高成长(8)
  港股: 45 只已分析, 平均分 58.1, 成长分布: 稳健成长(12), 低成长(10), 超高成长(2)
  A股: 68 只已分析, 平均分 55.7, 成长分布: 稳健成长(18), 低成长(15), 超高成长(5)
  总计: 198 只已分析, 推荐 5 只
==========================================================================================

  免责声明: 本报告仅供参考，不构成任何投资建议。
    投资有风险，入市需谨慎。过往表现不预示未来收益。
```

#### JSON 输出 (`to_json()`)

```json
{
  "generated_at": "2026-02-07T10:30:00",
  "summary": {
    "total_analyzed": 198,
    "total_recommended": 5
  },
  "recommendations": [
    {
      "symbol": "NVDA",
      "company_name": "NVIDIA Corporation",
      "market": "US",
      "sector": "Technology",
      "total_score": 82.5,
      "technical_score": 78.0,
      "fundamental_score": 85.3,
      "growth_label": "超高成长",
      "growth_bonus": 15.0,
      "recommendation": "强烈推荐",
      "reasons": ["..."],
      "metrics": {
        "pe_ratio": 65.2,
        "roe": 0.45,
        "revenue_growth": 1.224,
        "earnings_growth": 0.856,
        "peg_ratio": 1.05,
        "dividend_yield": null,
        "market_cap": 2800000000000
      },
      "growth_profile": {
        "revenue_growth": 122.4,
        "earnings_growth": 85.6,
        "peg_ratio": 1.05,
        "label": "超高成长",
        "bonus": 15.0
      },
      "technical_indicators": {
        "ma5": 875.32,
        "ma20": 842.15,
        "ma60": 780.50,
        "rsi_14": 58.6,
        "macd_dif": 12.35,
        "macd_dea": 10.22,
        "macd_hist": 4.26,
        "boll_position": 0.62,
        "volume_latest": 45230000
      }
    }
  ],
  "all_evaluations": ["... (所有被分析股票的完整评估数据)"]
}
```

#### Python 字典 (`to_dict_list()`)

返回 `list[dict]` 格式，供程序内部消费。

---

### 8. Agent 主控模块 (`agent.py`)

`StockAgent` 类协调完整的推荐流程。

#### 支持的分析模式

| 模式 | 调用方式 | 说明 |
|------|----------|------|
| 全市场分析 | `run()` 或 `run(market=None)` | 美股+港股+A股全部 |
| 单市场分析 | `run(market="US")` | 仅分析指定市场 |
| 指定股票 | `run(symbols=["AAPL", "NVDA"])` | 优先级最高 |
| 单只详细 | `analyze_single("NVDA")` | 打印完整分析报告 |
| JSON 输出 | `run(output_json=True)` | 输出 JSON 而非终端报告 |

#### 代码示例

```python
from stock_agent.agent import StockAgent
from stock_agent.config import AgentConfig

agent = StockAgent(AgentConfig())

# 全市场分析
result = agent.run()

# 仅分析美股
result = agent.run(market="US")

# 分析指定股票
result = agent.run(symbols=["BABA", "PDD", "PLTR", "ARM"])

# 单只股票详细分析
evaluation = agent.analyze_single("NVDA")
```

---

## 股票池覆盖范围

### 美股 (约 700+ 只)

| 来源 | 数量 | 说明 |
|------|------|------|
| S&P 500 | ~500 | 标普 500 成分股 |
| NASDAQ 100 | ~100 | 纳斯达克 100 成分股 |
| 中概股 | 40 | 市值>50亿美元的中国公司 |
| AI 概念股 | 81 | AI 产业链核心标的 |

### 港股 (约 100+ 只)

| 来源 | 数量 | 说明 |
|------|------|------|
| 恒生指数 | ~80 | 恒生指数成分股 |
| 恒生科技 | ~30 | 恒生科技指数成分股 |

### A股 (约 500+ 只)

| 来源 | 数量 | 说明 |
|------|------|------|
| 沪深 300 | ~300 | 沪深 300 成分股 |
| 创业板 | ~150 | 市值>=100亿人民币 |
| 科创板 | ~80 | 市值>=100亿人民币 |

---

## 评分模型详解

### 评分公式

```
技术面评分 = Σ(各技术指标评分 × 对应权重)    # 0-100
基本面评分 = Σ(各基本面指标评分 × 对应权重) + 成长性加分    # 0-100
综合评分   = 技术面评分 × 技术权重 + 基本面评分 × 基本面权重  # 0-100
```

### 美股权重分配示例

```
综合评分 (100%)
├── 技术面 (35%)
│   ├── MA均线趋势   25%
│   ├── RSI          20%
│   ├── MACD         25%
│   ├── 布林带       15%
│   └── 成交量趋势   15%
└── 基本面 (65%)
    ├── PE市盈率      12%
    ├── PB市净率      5%
    ├── ROE          15%
    ├── 营收增长率    18%
    ├── 净利润增速    15%
    ├── 净利润率      10%
    ├── 自由现金流    10%
    ├── 负债/权益比   5%
    └── PEG          10%
    + 成长性加分 (上限 15 分)
```

---

## 快速开始

### 环境要求

- Python 3.9+（使用了 `from __future__ import annotations`，兼容 3.9）

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行

```bash
# 方式一: Web 图形界面 (v2.0 推荐)
python3 -m streamlit run app.py

# 方式二: 命令行分析全部美股+港股+A股
python main.py

# 查看命令行帮助
python main.py --help
```

---

## 使用方式

### Web 图形界面 (v2.0 新增)

```bash
# 启动 Web UI
python3 -m streamlit run app.py
```

浏览器打开 `http://localhost:8501` 后：

1. **批量分析**: 左侧选择市场 → 调整参数 → 点击"开始批量分析"
2. **单股分析**: 左侧切换到"单股分析" → 输入股票代码（如 `NVDA`、`0700.HK`、`600519.SS`）→ 点击"开始分析"
3. **自定义代码**: 在"自定义股票代码"文本框中输入，每行一个代码，优先级高于市场选择

Web UI 支持常驻运行，分析结果保留在页面中，可随时调整参数重新分析。

### 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--market` | 分析市场: `US`(美股) / `HK`(港股) / `CN`(A股) / `ALL`(全部) | `ALL` |
| `--symbols` | 指定股票代码列表 | 无 |
| `--single` | 单只股票详细分析 | 无 |
| `--json` | 以 JSON 格式输出 | 否 |
| `--min-score` | 最低推荐分数 | `60` |
| `--top` | 最多推荐数量 | `10` |
| `--no-dynamic` | 禁用动态获取，使用静态 fallback 列表 | 否 |
| `--refresh-cache` | 强制刷新指数成分股缓存 | 否 |
| `-v, --verbose` | 显示详细日志 | 否 |

### 使用示例

```bash
# 仅分析美股
python main.py --market US

# 仅分析港股，推荐阈值70分，最多推荐5只
python main.py --market HK --min-score 70 --top 5

# 分析 A 股
python main.py --market CN

# 分析指定股票 (中概股 + AI 概念)
python main.py --symbols BABA PDD PLTR ARM SMCI VRT

# 单只股票详细报告
python main.py --single NVDA

# JSON 格式输出（适合程序化处理）
python main.py --market US --json

# 刷新缓存并分析
python main.py --refresh-cache

# 使用静态列表（跳过 Wikipedia 动态获取）
python main.py --no-dynamic

# 详细日志模式
python main.py -v
```

### 代码调用

```python
from stock_agent.agent import StockAgent
from stock_agent.config import AgentConfig, ThresholdConfig

# 使用默认配置
agent = StockAgent()

# 分析全部关注列表
result = agent.run()

# 仅分析美股
result = agent.run(market="US")

# 分析指定股票
result = agent.run(symbols=["AAPL", "MSFT", "0700.HK", "600519.SS"])

# 单只股票详细分析
evaluation = agent.analyze_single("NVDA")

# 自定义配置
config = AgentConfig(
    thresholds=ThresholdConfig(
        min_recommendation_score=70.0,
        max_recommendations=5,
    )
)
agent = StockAgent(config)
result = agent.run()
```

---

## 配置说明

### 自定义股票池

```python
from stock_agent.config import AgentConfig, MarketConfig

config = AgentConfig(
    market=MarketConfig(
        US_WATCHLIST=["AAPL", "GOOGL", "NVDA", "PLTR", "ARM"],
        HK_WATCHLIST=["0700.HK", "9988.HK"],
        CN_WATCHLIST=["600519.SS", "000001.SZ"],
        use_dynamic_constituents=False,  # 禁用动态获取
    )
)
```

### 调整评分权重

```python
from stock_agent.config import AgentConfig, ScoringWeights, MarketScoringProfile

# 创建自定义美股配置
custom_us = MarketScoringProfile(
    technical={
        "ma_trend": 0.30,
        "rsi": 0.15,
        "macd": 0.30,
        "bollinger": 0.15,
        "volume_trend": 0.10,
    },
    fundamental={
        "pe_ratio": 0.10,
        "roe": 0.20,
        "revenue_growth": 0.25,
        "peg_ratio": 0.15,
        # ...
    },
    technical_weight=0.4,   # 技术面权重提高到 40%
    fundamental_weight=0.6,
    growth_bonus_cap=20.0,  # 成长性加分上限提高
)

config = AgentConfig(
    weights=ScoringWeights(us=custom_us)
)
```

### 调整筛选阈值

```python
from stock_agent.config import AgentConfig, ThresholdConfig, MarketThresholds

config = AgentConfig(
    thresholds=ThresholdConfig(
        min_recommendation_score=70.0,  # 提高推荐门槛
        max_recommendations=5,          # 最多推荐5只
        rsi_oversold=25.0,              # RSI超卖线
        rsi_overbought=75.0,            # RSI超买线
        history_days=250,               # 获取更长历史数据
        us=MarketThresholds(
            max_pe_ratio=50.0,          # 降低美股 PE 容忍度
            high_growth_revenue=30.0,   # 提高高成长判定线
        ),
    )
)
```

---

## 扩展指南

### 添加新的技术指标

在 `technical_analyzer.py` 中：

1. 新增一个 `_score_xxx` 方法，返回 `(score, signals, vals)` 三元组
2. 在 `analyze` 方法中调用并加入 `sub_scores`
3. 在 `config.py` 的 `MarketScoringProfile.technical` 中加入对应权重

```python
def _score_atr(self, df: pd.DataFrame):
    """ATR 波动率指标"""
    # 计算 ATR
    atr = ...
    score = ...
    signals = [f"ATR={atr:.2f}，波动率..."]
    vals = {"atr_14": atr}
    return score, signals, vals
```

### 添加新的基本面指标

在 `fundamental_analyzer.py` 中：

1. 新增一个 `_score_xxx` 方法，返回 `(score, signals)` 二元组
2. 在 `analyze` 方法中调用并加入 `sub_scores`
3. 在 `config.py` 的 `MarketScoringProfile.fundamental` 中加入对应权重

### 添加新的市场

1. 在 `config.py` 中新增市场配置（`MarketConfig.XX_WATCHLIST`、`MarketScoringProfile`、`MarketThresholds`）
2. 在 `index_constituents.py` 中新增成分股获取方法
3. 在 `data_provider.py` 中新增市场识别规则和数据获取方法

### 接入新的数据源

继承或替换 `DataProvider`，只需保证返回 `StockData` 对象即可，分析模块无需改动。

---

## 已知限制与注意事项

1. **数据源依赖**: 所有数据来自 Yahoo Finance（免费 API），可能存在延迟、限流或数据缺失。高频调用时建议保持 `--no-dynamic` + 缓存策略。
2. **中概股/AI 概念股为静态列表**: 需定期人工维护更新（如新增/退市）。动态指数成分股（S&P500 等）依赖 Wikipedia 页面结构，页面改版可能导致解析失败（会自动回退到 fallback 列表）。
3. **市值过滤精度**: 通过 `yfinance.fast_info` 获取市值，部分股票可能因数据缺失而跳过过滤（默认保留）。
4. **行业基准 PE**: 仅内置 11 个大类行业基准，未覆盖的行业使用默认值 20.0，细分行业精度有限。
5. **技术指标数据需求**: 至少需要 30 个交易日的历史数据，新上市或停牌股票可能无法分析。
6. **A股代码格式**: 使用 Yahoo Finance 格式，上交所为 `.SS` 后缀，深交所为 `.SZ` 后缀（如 `600519.SS`、`000001.SZ`）。

---

## 免责声明

本系统仅供学习和研究目的使用，**不构成任何投资建议**。股票市场存在风险，投资需谨慎。使用者应自行承担因使用本系统做出投资决策所产生的任何后果。过往表现不预示未来收益。
