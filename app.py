"""
智能股票推荐 Agent - Streamlit Web UI (Apple Design Style)
支持美股/港股/A股三大市场的图形化分析界面，可常驻运行。

启动: python3 -m streamlit run app.py
"""

import logging
import time
from datetime import datetime

import streamlit as st
import pandas as pd

from stock_agent.agent import StockAgent
from stock_agent.config import AgentConfig, MarketConfig, ThresholdConfig
from stock_agent.strategy_engine import StockEvaluation

# ============================================================================
# 页面配置
# ============================================================================
st.set_page_config(
    page_title="智能股票推荐",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================================
# Apple HIG 风格全局样式
# ============================================================================
APPLE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ============ CSS 变量: 亮色/暗色自动切换 ============ */
:root {
    --text-primary: #1d1d1f;
    --text-secondary: #86868b;
    --bg-primary: #ffffff;
    --bg-secondary: #f5f5f7;
    --bg-card: rgba(255, 255, 255, 0.8);
    --bg-card-hover: rgba(255, 255, 255, 0.95);
    --bg-metric-item: rgba(0, 0, 0, 0.03);
    --border-color: rgba(0, 0, 0, 0.08);
    --border-light: rgba(0, 0, 0, 0.04);
    --shadow-sm: 0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.03);
    --shadow-md: 0 2px 8px rgba(0,0,0,0.06), 0 8px 24px rgba(0,0,0,0.04);
    --shadow-lg: 0 4px 16px rgba(0,0,0,0.08), 0 12px 32px rgba(0,0,0,0.05);
    --sidebar-bg: rgba(246, 246, 246, 0.82);
    --header-bg: rgba(255, 255, 255, 0.72);
    --accent: #007AFF;
    --accent-hover: #0071E3;
    --dist-bar-bg: rgba(0, 0, 0, 0.04);
}

/* 深色模式 — 系统偏好 */
@media (prefers-color-scheme: dark) {
    :root {
        --text-primary: #f5f5f7;
        --text-secondary: #98989d;
        --bg-primary: #1c1c1e;
        --bg-secondary: #2c2c2e;
        --bg-card: rgba(44, 44, 46, 0.8);
        --bg-card-hover: rgba(58, 58, 60, 0.9);
        --bg-metric-item: rgba(255, 255, 255, 0.06);
        --border-color: rgba(255, 255, 255, 0.1);
        --border-light: rgba(255, 255, 255, 0.06);
        --shadow-sm: 0 1px 3px rgba(0,0,0,0.3), 0 4px 12px rgba(0,0,0,0.2);
        --shadow-md: 0 2px 8px rgba(0,0,0,0.4), 0 8px 24px rgba(0,0,0,0.3);
        --shadow-lg: 0 4px 16px rgba(0,0,0,0.5), 0 12px 32px rgba(0,0,0,0.35);
        --sidebar-bg: rgba(28, 28, 30, 0.88);
        --header-bg: rgba(28, 28, 30, 0.72);
        --accent: #0A84FF;
        --accent-hover: #409CFF;
        --dist-bar-bg: rgba(255, 255, 255, 0.08);
    }
}

/* 深色模式 — Streamlit data-theme 属性 (更可靠) */
[data-theme="dark"],
.stApp[data-theme="dark"] {
    --text-primary: #f5f5f7;
    --text-secondary: #98989d;
    --bg-primary: #1c1c1e;
    --bg-secondary: #2c2c2e;
    --bg-card: rgba(44, 44, 46, 0.8);
    --bg-card-hover: rgba(58, 58, 60, 0.9);
    --bg-metric-item: rgba(255, 255, 255, 0.06);
    --border-color: rgba(255, 255, 255, 0.1);
    --border-light: rgba(255, 255, 255, 0.06);
    --shadow-sm: 0 1px 3px rgba(0,0,0,0.3), 0 4px 12px rgba(0,0,0,0.2);
    --shadow-md: 0 2px 8px rgba(0,0,0,0.4), 0 8px 24px rgba(0,0,0,0.3);
    --shadow-lg: 0 4px 16px rgba(0,0,0,0.5), 0 12px 32px rgba(0,0,0,0.35);
    --sidebar-bg: rgba(28, 28, 30, 0.88);
    --header-bg: rgba(28, 28, 30, 0.72);
    --accent: #0A84FF;
    --accent-hover: #409CFF;
    --dist-bar-bg: rgba(255, 255, 255, 0.08);
}

/* ---- 全局基础 ---- */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'SF Pro Display',
                 'SF Pro Text', 'Helvetica Neue', Arial, sans-serif;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}

.main .block-container {
    max-width: 1200px;
    padding: 2rem 2.5rem 4rem 2.5rem;
}

/* ---- 隐藏默认元素 ---- */
footer { visibility: hidden; }
#MainMenu { visibility: hidden; }
/* 隐藏 Deploy 按钮 — 兼容多个 Streamlit 版本 */
.stDeployButton,
.stAppDeployButton,
button[data-testid="stBaseButton-headerNoPadding"],
[data-testid="stAppViewBlockContainer"] header button,
.stToolbar [data-testid="stBaseButton-headerNoPadding"] {
    display: none !important;
    visibility: hidden !important;
}
header[data-testid="stHeader"] {
    background: var(--header-bg);
    backdrop-filter: saturate(180%) blur(20px);
    -webkit-backdrop-filter: saturate(180%) blur(20px);
}

/* ---- 侧边栏 ---- */
section[data-testid="stSidebar"] {
    background: var(--sidebar-bg);
    backdrop-filter: saturate(180%) blur(20px);
    -webkit-backdrop-filter: saturate(180%) blur(20px);
    border-right: 0.5px solid var(--border-color);
}
section[data-testid="stSidebar"] .block-container {
    padding-top: 2rem;
}

/* ---- 标题 ---- */
h1 {
    font-weight: 700 !important;
    font-size: 2rem !important;
    letter-spacing: -0.025em !important;
    color: var(--text-primary) !important;
}
h2 {
    font-weight: 600 !important;
    font-size: 1.35rem !important;
    letter-spacing: -0.02em !important;
    color: var(--text-primary) !important;
}
h3 {
    font-weight: 600 !important;
    font-size: 1.1rem !important;
    color: var(--text-primary) !important;
}

/* ---- Metric 卡片 ---- */
div[data-testid="stMetric"] {
    background: var(--bg-card);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 0.5px solid var(--border-color);
    border-radius: 16px;
    padding: 18px 20px;
    box-shadow: var(--shadow-sm);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
div[data-testid="stMetric"]:hover {
    transform: translateY(-1px);
    box-shadow: var(--shadow-md);
}
div[data-testid="stMetric"] label {
    color: var(--text-secondary) !important;
    font-size: 0.78rem !important;
    font-weight: 500 !important;
    text-transform: uppercase;
    letter-spacing: 0.03em;
}
div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
    color: var(--text-primary) !important;
    font-weight: 600 !important;
    font-size: 1.5rem !important;
}

/* ---- 按钮 ---- */
button[kind="primary"],
.stButton > button[kind="primary"] {
    background: var(--accent) !important;
    color: white !important;
    border: none !important;
    border-radius: 12px !important;
    font-weight: 500 !important;
    font-size: 0.92rem !important;
    padding: 0.6rem 1.5rem !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 1px 3px rgba(0, 122, 255, 0.2) !important;
}
button[kind="primary"]:hover,
.stButton > button[kind="primary"]:hover {
    background: var(--accent-hover) !important;
    box-shadow: 0 2px 8px rgba(0, 122, 255, 0.3) !important;
    transform: scale(1.01);
}
button[kind="primary"]:active,
.stButton > button[kind="primary"]:active {
    transform: scale(0.98);
}

/* ---- 输入框 ---- */
input[type="text"], textarea,
div[data-baseweb="input"] input,
div[data-baseweb="textarea"] textarea {
    border-radius: 10px !important;
    border: 1px solid var(--border-color) !important;
    font-size: 0.9rem !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
}
input[type="text"]:focus, textarea:focus,
div[data-baseweb="input"] input:focus,
div[data-baseweb="textarea"] textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.15) !important;
}

/* ---- 选择框 ---- */
div[data-baseweb="select"] > div {
    border-radius: 10px !important;
    border: 1px solid var(--border-color) !important;
}

/* ---- Slider ---- */
div[data-testid="stSlider"] div[data-baseweb="slider"] div[role="slider"] {
    background: var(--accent) !important;
}

/* ---- Divider ---- */
hr {
    border: none !important;
    border-top: 0.5px solid var(--border-color) !important;
    margin: 1.5rem 0 !important;
}

/* ---- Expander ---- */
div[data-testid="stExpander"] {
    background: var(--bg-card);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 0.5px solid var(--border-color) !important;
    border-radius: 16px !important;
    overflow: hidden;
    box-shadow: var(--shadow-sm);
    margin-bottom: 12px;
    transition: box-shadow 0.2s ease;
}
div[data-testid="stExpander"]:hover {
    box-shadow: var(--shadow-md);
}
div[data-testid="stExpander"] summary {
    font-weight: 500 !important;
    font-size: 0.95rem !important;
    padding: 14px 18px !important;
}

/* ---- DataFrame ---- */
div[data-testid="stDataFrame"] {
    border-radius: 16px;
    overflow: hidden;
    border: 0.5px solid var(--border-color);
    box-shadow: var(--shadow-sm);
}

/* ---- Alert ---- */
div[data-testid="stAlert"] {
    border-radius: 12px !important;
    border: none !important;
    font-size: 0.9rem !important;
}

/* ---- 自定义卡片 ---- */
.apple-card {
    background: var(--bg-card);
    backdrop-filter: saturate(180%) blur(20px);
    -webkit-backdrop-filter: saturate(180%) blur(20px);
    border: 0.5px solid var(--border-color);
    border-radius: 20px;
    padding: 24px 28px;
    margin-bottom: 16px;
    box-shadow: var(--shadow-sm);
    transition: transform 0.25s ease, box-shadow 0.25s ease;
}
.apple-card:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-lg);
}

.apple-card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
}
.apple-card-title {
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text-primary);
    letter-spacing: -0.01em;
}
.apple-card-subtitle {
    font-size: 0.82rem;
    color: var(--text-secondary);
    font-weight: 400;
    margin-top: 2px;
}

/* ---- 评分圆环 ---- */
.score-ring {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 56px;
    height: 56px;
    border-radius: 50%;
    font-size: 1.15rem;
    font-weight: 700;
    color: white;
    flex-shrink: 0;
}

/* ---- 推荐标签 ---- */
.rec-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.02em;
}
.rec-badge-strong { background: rgba(255,59,48,0.15); color: #FF453A; }
.rec-badge-buy    { background: rgba(255,149,0,0.15); color: #FF9F0A; }
.rec-badge-hold   { background: rgba(0,122,255,0.15); color: #0A84FF; }
.rec-badge-avoid  { background: rgba(142,142,147,0.15); color: #98989D; }

/* ---- 成长标签 ---- */
.growth-tag {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 500;
    background: rgba(52,199,89,0.15);
    color: #30D158;
}
.growth-tag-down { background: rgba(255,59,48,0.15); color: #FF453A; }
.growth-tag-low  { background: rgba(142,142,147,0.15); color: #98989D; }

/* ---- 指标行 ---- */
.metric-row {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    margin-top: 12px;
}
.metric-item {
    flex: 1;
    min-width: 100px;
    background: var(--bg-metric-item);
    border-radius: 12px;
    padding: 12px 14px;
    text-align: center;
}
.metric-item-label {
    font-size: 0.72rem;
    color: var(--text-secondary);
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 4px;
}
.metric-item-value {
    font-size: 1.05rem;
    font-weight: 600;
    color: var(--text-primary);
}

/* ---- 信号列表 ---- */
.signal-item {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    padding: 8px 0;
    border-bottom: 0.5px solid var(--border-light);
    font-size: 0.88rem;
    color: var(--text-primary);
    line-height: 1.5;
}
.signal-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--accent);
    margin-top: 7px;
    flex-shrink: 0;
}

/* ---- 市场卡片 ---- */
.market-card {
    background: var(--bg-card);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 0.5px solid var(--border-color);
    border-radius: 20px;
    padding: 24px;
    box-shadow: var(--shadow-sm);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
    height: 100%;
}
.market-card:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
}
.market-card-title {
    font-size: 1.05rem;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 16px;
}
.market-stat {
    display: flex;
    justify-content: space-between;
    padding: 6px 0;
    border-bottom: 0.5px solid var(--border-light);
    font-size: 0.85rem;
}
.market-stat:last-child { border-bottom: none; }
.market-stat-label { color: var(--text-secondary); }
.market-stat-value { color: var(--text-primary); font-weight: 600; }

/* ---- 分布条 ---- */
.dist-bar {
    display: flex;
    height: 6px;
    border-radius: 3px;
    overflow: hidden;
    margin-top: 8px;
    margin-bottom: 12px;
    background: var(--dist-bar-bg);
}
.dist-bar-seg { height: 100%; transition: width 0.4s ease; }

/* ---- 页脚 ---- */
.apple-footer {
    text-align: center;
    padding: 24px 0 8px;
    font-size: 0.78rem;
    color: var(--text-secondary);
    line-height: 1.6;
}

/* ---- 空状态 ---- */
.empty-state {
    text-align: center;
    padding: 100px 40px 80px;
    position: relative;
}
.empty-state::before {
    content: '';
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 320px;
    height: 320px;
    background: radial-gradient(circle, rgba(0,122,255,0.06) 0%, transparent 70%);
    border-radius: 50%;
    pointer-events: none;
    z-index: 0;
}
.empty-state-icon {
    font-size: 4rem;
    margin-bottom: 20px;
    opacity: 0.8;
    position: relative;
    z-index: 1;
    animation: emptyFloat 3s ease-in-out infinite;
}
@keyframes emptyFloat {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-8px); }
}
.empty-state-title {
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 10px;
    position: relative;
    z-index: 1;
}
.empty-state-desc {
    font-size: 0.92rem;
    color: var(--text-secondary);
    max-width: 400px;
    margin: 0 auto;
    line-height: 1.6;
    position: relative;
    z-index: 1;
}
.empty-state-hint {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    margin-top: 24px;
    padding: 8px 16px;
    background: var(--bg-metric-item);
    border-radius: 20px;
    font-size: 0.8rem;
    color: var(--text-secondary);
    position: relative;
    z-index: 1;
}

/* ---- 背景装饰 (用伪元素 + box-shadow 实现，不受容器裁剪) ---- */
.stApp::before {
    content: '';
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
    z-index: 0;
    background:
        radial-gradient(ellipse 500px 500px at 85% 5%, rgba(0,122,255,0.07) 0%, transparent 70%),
        radial-gradient(ellipse 450px 450px at 10% 90%, rgba(52,199,89,0.06) 0%, transparent 70%),
        radial-gradient(ellipse 350px 350px at 75% 55%, rgba(255,149,0,0.05) 0%, transparent 70%);
    animation: bgShift 30s ease-in-out infinite alternate;
}
.stApp::after {
    content: '';
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
    z-index: 0;
    opacity: 0.35;
    background-image:
        linear-gradient(var(--border-light) 1px, transparent 1px),
        linear-gradient(90deg, var(--border-light) 1px, transparent 1px);
    background-size: 60px 60px;
}
@keyframes bgShift {
    0%   { background-position: 0% 0%, 0% 100%, 100% 50%; }
    100% { background-position: 5% 3%, 3% 95%, 90% 48%; }
}

/* ---- 响应式 ---- */
@media (max-width: 768px) {
    .main .block-container { padding: 1rem 1rem 3rem 1rem; }
    h1 { font-size: 1.6rem !important; }
    .apple-card { padding: 16px 18px; border-radius: 16px; }
    .metric-row { gap: 8px; }
    .metric-item { min-width: 80px; padding: 10px 8px; }
    div[data-testid="stMetric"] { padding: 14px 16px; border-radius: 14px; }
}
</style>
"""

st.markdown(APPLE_CSS, unsafe_allow_html=True)


# ============================================================================
# 日志配置
# ============================================================================
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


setup_logging()


# ============================================================================
# Apple 配色系统
# ============================================================================
COLORS = {
    "blue":    "#007AFF",
    "green":   "#34C759",
    "orange":  "#FF9500",
    "red":     "#FF3B30",
    "gray":    "#8E8E93",
    "text":    "#1d1d1f",
    "subtext": "#86868b",
}


# ============================================================================
# 工具函数
# ============================================================================
def get_rec_color(rec: str) -> str:
    return {
        "强烈推荐": COLORS["red"],
        "推荐":     COLORS["orange"],
        "观望":     COLORS["blue"],
        "不推荐":   COLORS["gray"],
    }.get(rec, COLORS["gray"])


def get_rec_badge(rec: str) -> str:
    cls_map = {
        "强烈推荐": "rec-badge-strong",
        "推荐":     "rec-badge-buy",
        "观望":     "rec-badge-hold",
        "不推荐":   "rec-badge-avoid",
    }
    cls = cls_map.get(rec, "rec-badge-avoid")
    return f'<span class="rec-badge {cls}">{rec}</span>'


def get_market_label(market: str) -> str:
    return {"US": "美股", "HK": "港股", "CN": "A股"}.get(market, market)


def get_market_flag(market: str) -> str:
    return {"US": "🇺🇸", "HK": "🇭🇰", "CN": "🇨🇳"}.get(market, "")


def get_growth_tag(label: str) -> str:
    if not label or label == "未知":
        return ""
    if label == "双降":
        cls = "growth-tag growth-tag-down"
    elif label in ("低成长",):
        cls = "growth-tag growth-tag-low"
    else:
        cls = "growth-tag"
    return f'<span class="{cls}">{label}</span>'


def format_pct(val) -> str:
    if val is None:
        return "–"
    return f"{val * 100:.1f}%"


def format_number(val, decimals: int = 2) -> str:
    if val is None:
        return "–"
    return f"{val:.{decimals}f}"


def score_ring_color(score: float) -> str:
    if score >= 80:
        return COLORS["green"]
    elif score >= 65:
        return COLORS["orange"]
    elif score >= 50:
        return COLORS["blue"]
    return COLORS["red"]


def render_score_ring(score: float, size: int = 56) -> str:
    color = score_ring_color(score)
    return (
        f'<span class="score-ring" style="width:{size}px;height:{size}px;'
        f'background:{color};font-size:{size*0.33}px">{score:.0f}</span>'
    )


def render_metric_item(label: str, value: str) -> str:
    return (
        f'<div class="metric-item">'
        f'<div class="metric-item-label">{label}</div>'
        f'<div class="metric-item-value">{value}</div>'
        f'</div>'
    )


def render_signal(text: str) -> str:
    return f'<div class="signal-item"><span class="signal-dot"></span><span>{text}</span></div>'


def build_agent(
    use_dynamic: bool,
    min_score: float,
    max_recommendations: int,
) -> StockAgent:
    config = AgentConfig(
        market=MarketConfig(use_dynamic_constituents=use_dynamic),
        thresholds=ThresholdConfig(
            min_recommendation_score=min_score,
            max_recommendations=max_recommendations,
        ),
    )
    return StockAgent(config)


# ============================================================================
# Session State 初始化
# ============================================================================
for key, default in [
    ("results", None),
    ("single_result", None),
    ("analysis_time", None),
    ("page", "batch"),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ============================================================================
# 侧边栏 — Apple 简洁风格
# ============================================================================
with st.sidebar:
    st.markdown(
        '<div style="padding:8px 0 4px">'
        '<span style="font-size:1.4rem;font-weight:700;color:var(--text-primary);letter-spacing:-0.03em">'
        '智能股票推荐</span>'
        f'<br><span style="font-size:0.78rem;color:var(--text-secondary)">v2.0.0 · {datetime.now().strftime("%Y-%m-%d")}</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.divider()

    page = st.radio(
        "功能",
        ["批量分析", "单股分析"],
        horizontal=True,
        key="page_radio",
        label_visibility="collapsed",
    )
    st.session_state.page = "batch" if page == "批量分析" else "single"

    st.divider()

    st.markdown('<span style="font-size:0.82rem;font-weight:600;color:var(--text-secondary);text-transform:uppercase;letter-spacing:0.05em">参数设置</span>', unsafe_allow_html=True)
    st.markdown("", unsafe_allow_html=True)

    use_dynamic = st.toggle(
        "动态获取成分股",
        value=True,
        help="从 Wikipedia 动态获取最新成分股列表",
    )

    min_score = st.slider(
        "最低推荐分",
        min_value=30.0,
        max_value=90.0,
        value=60.0,
        step=5.0,
    )

    max_recommendations = st.slider(
        "推荐数量上限",
        min_value=3,
        max_value=30,
        value=10,
        step=1,
    )

    st.divider()

    if st.session_state.page == "batch":
        market_option = st.selectbox(
            "市场",
            ["全部市场", "美股", "港股", "A股"],
            key="market_option",
        )

        custom_symbols = st.text_area(
            "自定义代码",
            placeholder="每行一个，如：\nAAPL\n0700.HK\n600519.SS",
            help="优先级高于市场选择",
            height=90,
            key="custom_symbols",
        )

        st.button(
            "开始分析",
            use_container_width=True,
            type="primary",
            key="run_batch",
        )
    else:
        single_symbol = st.text_input(
            "股票代码",
            placeholder="AAPL / 0700.HK / 600519.SS",
            key="single_symbol",
        )

        st.button(
            "开始分析",
            use_container_width=True,
            type="primary",
            key="run_single",
        )

    st.divider()
    st.markdown(
        '<div style="font-size:0.75rem;color:var(--text-secondary);line-height:1.5;padding:0 4px">'
        '本系统仅供学习研究，不构成投资建议。'
        '</div>',
        unsafe_allow_html=True,
    )


# ============================================================================
# 分析执行
# ============================================================================
def run_batch_analysis():
    agent = build_agent(use_dynamic, min_score, max_recommendations)
    symbols = None
    market = None
    custom_text = st.session_state.get("custom_symbols", "").strip()
    if custom_text:
        symbols = [s.strip().upper() for s in custom_text.split("\n") if s.strip()]
    else:
        market_map = {"全部市场": None, "美股": "US", "港股": "HK", "A股": "CN"}
        market = market_map.get(st.session_state.get("market_option", "全部市场"))

    start_time = time.time()
    result = agent.run(market=market, symbols=symbols)
    elapsed = time.time() - start_time

    st.session_state.results = result
    st.session_state.analysis_time = elapsed


def run_single_analysis():
    agent = build_agent(use_dynamic, min_score, max_recommendations)
    symbol = st.session_state.get("single_symbol", "").strip().upper()

    start_time = time.time()
    evaluation = agent.analyze_single(symbol)
    elapsed = time.time() - start_time

    st.session_state.single_result = evaluation
    st.session_state.analysis_time = elapsed


# ============================================================================
# 批量分析页面
# ============================================================================
def render_batch_page():
    st.markdown("# 推荐报告")

    results = st.session_state.results
    if results is None:
        st.markdown(
            '<div class="empty-state">'
            '<div class="empty-state-icon">📊</div>'
            '<div class="empty-state-title">准备就绪</div>'
            '<div class="empty-state-desc">在左侧配置参数后，点击「开始分析」以生成推荐报告。<br>支持美股、港股、A股三大市场。</div>'
            '<div class="empty-state-hint">💡 提示：可输入自定义代码以分析特定股票</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    if results.get("error"):
        st.error(f"分析失败：{results['error']}")
        return

    summary = results.get("summary", {})
    recommendations = results.get("recommendations", [])
    all_evaluations = results.get("all_evaluations", [])

    # ---- 概览指标 ----
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("分析总数", summary.get("total_analyzed", 0))
    with col2:
        st.metric("有效数据", summary.get("valid_data", 0))
    with col3:
        st.metric("推荐数量", summary.get("total_recommended", 0))
    with col4:
        elapsed = st.session_state.analysis_time
        st.metric("耗时", f"{elapsed:.1f}s" if elapsed else "–")

    st.markdown("")

    # ---- 市场概览 ----
    render_market_overview(all_evaluations)

    st.markdown("")

    # ---- 推荐排名 ----
    st.markdown("## 推荐排名")

    if not recommendations:
        st.info("当前无符合条件的推荐股票。")
    else:
        render_recommendation_table(recommendations)

        st.markdown("")

        # ---- 推荐详情 ----
        st.markdown("## 推荐详情")
        render_recommendation_details(recommendations)

    st.markdown("")

    # ---- 全市场一览 ----
    with st.expander("全部股票评分一览", expanded=False):
        render_all_evaluations_table(all_evaluations)


# ============================================================================
# 市场概览
# ============================================================================
def render_market_overview(all_evaluations: list[dict]):
    st.markdown("## 市场概览")

    if not all_evaluations:
        st.info("暂无数据")
        return

    markets = {}
    for ev in all_evaluations:
        mkt = ev.get("market", "Unknown")
        if mkt not in markets:
            markets[mkt] = []
        markets[mkt].append(ev)

    cols = st.columns(len(markets))
    for idx, (mkt, evals) in enumerate(sorted(markets.items())):
        with cols[idx]:
            flag = get_market_flag(mkt)
            label = get_market_label(mkt)
            avg_score = sum(e["total_score"] for e in evals) / len(evals)
            max_score_val = max(e["total_score"] for e in evals)

            rec_counts = {}
            for e in evals:
                r = e.get("recommendation", "未知")
                rec_counts[r] = rec_counts.get(r, 0) + 1

            growth_counts = {}
            for e in evals:
                gl = e.get("growth_label", "未知") or "未知"
                growth_counts[gl] = growth_counts.get(gl, 0) + 1

            # 推荐分布条
            total = len(evals)
            seg_colors = {"强烈推荐": COLORS["red"], "推荐": COLORS["orange"], "观望": COLORS["blue"], "不推荐": COLORS["gray"]}
            bar_segs = ""
            for rl in ["强烈推荐", "推荐", "观望", "不推荐"]:
                cnt = rec_counts.get(rl, 0)
                if cnt > 0:
                    pct = cnt / total * 100
                    bar_segs += f'<div class="dist-bar-seg" style="width:{pct}%;background:{seg_colors[rl]}"></div>'

            # 推荐分布文字
            rec_text = ""
            for rl in ["强烈推荐", "推荐", "观望", "不推荐"]:
                cnt = rec_counts.get(rl, 0)
                if cnt > 0:
                    rec_text += f'<div class="market-stat"><span class="market-stat-label">{rl}</span><span class="market-stat-value">{cnt}</span></div>'

            # 成长分布
            top_labels = sorted(growth_counts.items(), key=lambda x: -x[1])[:3]
            growth_text = ""
            for gn, gc in top_labels:
                growth_text += f'<div class="market-stat"><span class="market-stat-label">{gn}</span><span class="market-stat-value">{gc}</span></div>'

            st.markdown(
                f'<div class="market-card">'
                f'<div class="market-card-title">{flag} {label}</div>'
                f'<div class="market-stat"><span class="market-stat-label">股票数量</span><span class="market-stat-value">{total}</span></div>'
                f'<div class="market-stat"><span class="market-stat-label">平均分</span><span class="market-stat-value">{avg_score:.1f}</span></div>'
                f'<div class="market-stat"><span class="market-stat-label">最高分</span><span class="market-stat-value" style="color:{score_ring_color(max_score_val)}">{max_score_val:.1f}</span></div>'
                f'<div class="dist-bar">{bar_segs}</div>'
                f'{rec_text}'
                f'<div style="margin-top:12px;font-size:0.78rem;color:var(--text-secondary);font-weight:600;text-transform:uppercase;letter-spacing:0.04em">成长分布</div>'
                f'{growth_text}'
                f'</div>',
                unsafe_allow_html=True,
            )


# ============================================================================
# 推荐排名表
# ============================================================================
def render_recommendation_table(recommendations: list[dict]):
    rows = []
    for rank, rec in enumerate(recommendations, 1):
        rows.append({
            "排名": rank,
            "代码": rec["symbol"],
            "公司": rec.get("company_name", "")[:20],
            "市场": rec.get("market", ""),
            "综合分": rec["total_score"],
            "技术分": rec.get("technical_score", 0),
            "基本面": rec.get("fundamental_score", 0),
            "成长": rec.get("growth_label", "–") or "–",
            "推荐": rec.get("recommendation", ""),
        })

    df = pd.DataFrame(rows)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "排名": st.column_config.NumberColumn(width="small"),
            "代码": st.column_config.TextColumn(width="medium"),
            "公司": st.column_config.TextColumn(width="medium"),
            "市场": st.column_config.TextColumn(width="small"),
            "综合分": st.column_config.ProgressColumn(
                min_value=0, max_value=100, format="%.1f",
            ),
            "技术分": st.column_config.ProgressColumn(
                min_value=0, max_value=100, format="%.1f",
            ),
            "基本面": st.column_config.ProgressColumn(
                min_value=0, max_value=100, format="%.1f",
            ),
            "成长": st.column_config.TextColumn(width="small"),
            "推荐": st.column_config.TextColumn(width="small"),
        },
    )


# ============================================================================
# 推荐详情卡片
# ============================================================================
def render_recommendation_details(recommendations: list[dict]):
    for rank, rec in enumerate(recommendations, 1):
        symbol = rec["symbol"]
        name = rec.get("company_name", symbol)
        score = rec["total_score"]
        tech_score = rec.get("technical_score", 0)
        fund_score = rec.get("fundamental_score", 0)
        rec_level = rec.get("recommendation", "")
        growth = rec.get("growth_label", "") or "–"
        growth_bonus = rec.get("growth_bonus", 0)
        reasons = rec.get("reasons", [])
        metrics = rec.get("metrics", {})
        market = rec.get("market", "")

        badge = get_rec_badge(rec_level)
        growth_html = get_growth_tag(growth) if growth != "–" else '<span style="color:var(--text-secondary)">–</span>'
        ring = render_score_ring(score)

        # 指标行
        metrics_html = ""
        if metrics:
            items = ""
            for lbl, key, fmt_fn in [
                ("PE", "pe_ratio", lambda v: format_number(v)),
                ("ROE", "roe", lambda v: format_pct(v)),
                ("营收增速", "revenue_growth", lambda v: format_pct(v)),
                ("盈利增速", "earnings_growth", lambda v: format_pct(v)),
                ("PEG", "peg_ratio", lambda v: format_number(v)),
            ]:
                val = metrics.get(key)
                items += render_metric_item(lbl, fmt_fn(val))
            metrics_html = f'<div class="metric-row">{items}</div>'

        # 理由
        reasons_html = ""
        if reasons:
            for r in reasons:
                reasons_html += render_signal(r)

        with st.expander(
            f"#{rank}  {symbol} — {name}　　{rec_level}　　{score:.1f}分",
            expanded=(rank <= 3),
        ):
            st.markdown(
                f'<div class="apple-card" style="margin:0">'
                f'<div class="apple-card-header">'
                f'<div>'
                f'<div class="apple-card-title">{symbol} <span style="font-weight:400;color:var(--text-secondary)">· {name}</span></div>'
                f'<div class="apple-card-subtitle">{get_market_flag(market)} {get_market_label(market)}　{badge}　{growth_html}</div>'
                f'</div>'
                f'{ring}'
                f'</div>'
                f'<div class="metric-row">'
                f'{render_metric_item("综合", f"{score:.1f}")}'
                f'{render_metric_item("技术面", f"{tech_score:.1f}")}'
                f'{render_metric_item("基本面", f"{fund_score:.1f}")}'
                f'{render_metric_item("成长加分", f"{growth_bonus:+.1f}")}'
                f'</div>'
                f'{metrics_html}'
                f'<div style="margin-top:16px">{reasons_html}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


# ============================================================================
# 全市场评分一览
# ============================================================================
def render_all_evaluations_table(all_evaluations: list[dict]):
    if not all_evaluations:
        st.info("暂无数据")
        return

    rows = []
    for ev in all_evaluations:
        rows.append({
            "代码": ev["symbol"],
            "公司": ev.get("company_name", "")[:16],
            "市场": ev.get("market", ""),
            "行业": ev.get("sector", "")[:12],
            "综合分": ev["total_score"],
            "技术分": ev.get("technical_score", 0),
            "基本面": ev.get("fundamental_score", 0),
            "成长": ev.get("growth_label", "–") or "–",
            "推荐": ev.get("recommendation", ""),
        })

    df = pd.DataFrame(rows)

    filter_col1, filter_col2 = st.columns([2, 1])
    with filter_col1:
        markets = df["市场"].unique().tolist()
        selected_markets = st.multiselect("筛选市场", markets, default=markets)
    with filter_col2:
        sort_col = st.selectbox("排序依据", ["综合分", "技术分", "基本面"])

    if selected_markets:
        df = df[df["市场"].isin(selected_markets)]
    df = df.sort_values(sort_col, ascending=False)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        height=500,
        column_config={
            "综合分": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f"),
            "技术分": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f"),
            "基本面": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f"),
        },
    )

    st.markdown(f'<div style="text-align:right;font-size:0.78rem;color:var(--text-secondary);padding:4px 8px">共 {len(df)} 只</div>', unsafe_allow_html=True)


# ============================================================================
# 单股分析页面
# ============================================================================
def render_single_page():
    st.markdown("# 个股分析")

    evaluation: StockEvaluation | None = st.session_state.single_result
    if evaluation is None:
        st.markdown(
            '<div class="empty-state">'
            '<div class="empty-state-icon">🔍</div>'
            '<div class="empty-state-title">输入股票代码</div>'
            '<div class="empty-state-desc">在左侧输入代码后，点击「开始分析」查看详细报告。<br>支持美股 (AAPL)、港股 (0700.HK)、A股 (600519.SS) 格式。</div>'
            '<div class="empty-state-hint">💡 提示：输入后按回车也可以直接分析</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    ev = evaluation

    # ---- 头部卡片 ----
    rec_badge = get_rec_badge(ev.recommendation)
    ring = render_score_ring(ev.total_score, 64)
    elapsed = st.session_state.analysis_time
    time_str = f"{elapsed:.1f}s" if elapsed else "–"

    st.markdown(
        f'<div class="apple-card">'
        f'<div class="apple-card-header">'
        f'<div>'
        f'<div style="font-size:1.5rem;font-weight:700;color:var(--text-primary);letter-spacing:-0.02em">{ev.symbol}</div>'
        f'<div style="font-size:0.95rem;color:var(--text-secondary);margin-top:4px">{ev.company_name}</div>'
        f'<div style="margin-top:8px">'
        f'{get_market_flag(ev.market)} <span style="font-size:0.85rem;color:var(--text-secondary)">{get_market_label(ev.market)} · {ev.sector}</span>'
        f'　{rec_badge}'
        f'</div>'
        f'</div>'
        f'{ring}'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ---- 评分概览 ----
    sc1, sc2, sc3, sc4 = st.columns(4)
    with sc1:
        st.metric("综合评分", f"{ev.total_score:.1f}")
    with sc2:
        st.metric("技术面", f"{ev.technical_score:.1f}")
    with sc3:
        st.metric("基本面", f"{ev.fundamental_score:.1f}")
    with sc4:
        bonus = f"{ev.growth_bonus:+.1f}" if ev.growth_bonus else "0"
        st.metric("成长加分", bonus)

    st.markdown("")

    # ---- 技术面分析 ----
    st.markdown("## 技术面分析")
    if ev.technical:
        if ev.technical.sub_scores:
            indicator_names = {
                "ma_trend": "MA 趋势", "rsi": "RSI", "macd": "MACD",
                "bollinger": "布林带", "volume_trend": "成交量",
            }
            items = ""
            for key, val in ev.technical.sub_scores.items():
                name = indicator_names.get(key, key)
                items += render_metric_item(name, f"{val:.1f}")
            st.markdown(f'<div class="metric-row">{items}</div>', unsafe_allow_html=True)

        if ev.technical.indicators:
            st.markdown("")
            indicators = ev.technical.indicators
            items = ""
            for name, key in [("MA5", "ma5"), ("MA20", "ma20"), ("MA60", "ma60"), ("RSI", "rsi"), ("MACD", "macd")]:
                items += render_metric_item(name, format_number(indicators.get(key)))
            st.markdown(f'<div class="metric-row">{items}</div>', unsafe_allow_html=True)

        if ev.technical.signals:
            st.markdown("")
            signals_html = "".join(render_signal(s) for s in ev.technical.signals)
            st.markdown(signals_html, unsafe_allow_html=True)

        if ev.technical.error:
            st.warning(f"技术面分析异常：{ev.technical.error}")
    else:
        st.info("无技术面数据")

    st.markdown("")

    # ---- 基本面分析 ----
    st.markdown("## 基本面分析")
    if ev.fundamental:
        if ev.fundamental.sub_scores:
            indicator_names = {
                "pe_ratio": "PE", "pb_ratio": "PB", "roe": "ROE",
                "revenue_growth": "营收增长", "earnings_growth": "盈利增长",
                "profit_margin": "利润率", "free_cashflow": "现金流",
                "debt_ratio": "负债率", "peg_ratio": "PEG", "dividend_yield": "股息率",
            }
            items = ""
            for key, val in ev.fundamental.sub_scores.items():
                name = indicator_names.get(key, key)
                items += render_metric_item(name, f"{val:.1f}")
            st.markdown(f'<div class="metric-row">{items}</div>', unsafe_allow_html=True)

        if ev.fundamental.metrics:
            st.markdown("")
            m = ev.fundamental.metrics
            items = ""
            for lbl, key, fn in [
                ("PE", "pe_ratio", format_number),
                ("PB", "pb_ratio", format_number),
                ("ROE", "roe", format_pct),
                ("营收增速", "revenue_growth", format_pct),
                ("盈利增速", "earnings_growth", format_pct),
                ("利润率", "profit_margin", format_pct),
                ("负债率", "debt_ratio", format_pct),
                ("PEG", "peg_ratio", format_number),
                ("股息率", "dividend_yield", format_pct),
            ]:
                items += render_metric_item(lbl, fn(m.get(key)))
            st.markdown(f'<div class="metric-row">{items}</div>', unsafe_allow_html=True)

        if ev.fundamental.growth:
            g = ev.fundamental.growth
            st.markdown("")
            st.markdown("### 成长性分析")
            items = ""
            items += render_metric_item("营收增长", format_pct(g.revenue_growth / 100 if g.revenue_growth else None))
            items += render_metric_item("盈利增长", format_pct(g.earnings_growth / 100 if g.earnings_growth else None))
            items += render_metric_item("标签", g.growth_label)
            items += render_metric_item("加分", f"{g.growth_bonus:+.1f}")
            st.markdown(f'<div class="metric-row">{items}</div>', unsafe_allow_html=True)

            if g.growth_signals:
                st.markdown("")
                signals_html = "".join(render_signal(s) for s in g.growth_signals)
                st.markdown(signals_html, unsafe_allow_html=True)

        if ev.fundamental.signals:
            st.markdown("")
            signals_html = "".join(render_signal(s) for s in ev.fundamental.signals)
            st.markdown(signals_html, unsafe_allow_html=True)

        if ev.fundamental.error:
            st.warning(f"基本面分析异常：{ev.fundamental.error}")
    else:
        st.info("无基本面数据")

    st.markdown("")

    # ---- 推荐理由 ----
    st.markdown("## 推荐理由")
    if ev.reasons:
        signals_html = "".join(render_signal(r) for r in ev.reasons)
        st.markdown(signals_html, unsafe_allow_html=True)
    else:
        st.info("无推荐理由")


# ============================================================================
# 主路由
# ============================================================================
if st.session_state.page == "batch":
    if st.session_state.get("run_batch"):
        with st.spinner("正在获取数据并分析…"):
            run_batch_analysis()
    render_batch_page()
else:
    if st.session_state.get("run_single"):
        symbol_input = st.session_state.get("single_symbol", "").strip()
        if symbol_input:
            with st.spinner(f"正在分析 {symbol_input.upper()}…"):
                run_single_analysis()
        else:
            st.warning("请输入股票代码")
    render_single_page()

# ---- 页脚 ----
st.markdown(
    '<div class="apple-footer">'
    '本系统仅供学习和研究目的，不构成任何投资建议。<br>'
    '投资有风险，入市需谨慎。'
    '</div>',
    unsafe_allow_html=True,
)
