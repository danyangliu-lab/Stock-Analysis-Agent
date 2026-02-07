"""
全局配置模块
定义股票池、评分权重、阈值等配置项。
针对美股、港股、A股三个市场设计差异化策略参数。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MarketConfig:
    """市场配置"""

    # 是否动态获取指数成分股 (True: 从 Wikipedia 获取; False: 使用下方静态列表)
    use_dynamic_constituents: bool = True

    # 动态获取时缓存过期时间 (小时)
    cache_expiry_hours: int = 24

    # ---------- 以下为静态 fallback 列表 (动态获取失败时使用) ----------

    # 美股 fallback 列表 - 大盘蓝筹 + 中概股 + AI 概念核心标的
    US_WATCHLIST: list[str] = field(default_factory=lambda: [
        # --- 大盘蓝筹 ---
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
        "META", "TSLA", "BRK-B", "JPM", "V",
        "UNH", "MA", "HD", "PG", "JNJ",
        "COST", "ABBV", "CRM", "AMD", "NFLX",
        "LLY", "AVGO", "WMT", "PEP", "KO",
        "MRK", "TMO", "ADBE", "CSCO", "ACN",
        # --- 中概股 (市值>50亿美元) ---
        "BABA", "JD", "PDD", "BIDU", "NTES",
        "BILI", "TME", "NIO", "XPEV", "LI",
        "TAL", "EDU", "FUTU", "TCOM", "BEKE",
        "HTHT", "ZTO", "VIPS", "GDS", "VNET",
        # --- AI 概念核心 ---
        "ARM", "MRVL", "TSM", "ASML", "ANET",
        "SMCI", "PLTR", "SNOW", "MU", "VRT",
        "DELL", "ORCL", "NOW", "PANW", "CRWD",
    ])

    # 港股 fallback 列表 - 恒生指数 + 恒生科技指数核心成分股
    HK_WATCHLIST: list[str] = field(default_factory=lambda: [
        "0700.HK", "9988.HK", "9618.HK", "1810.HK", "3690.HK",
        "0005.HK", "1299.HK", "2318.HK", "0941.HK", "0388.HK",
        "2020.HK", "9999.HK", "1024.HK", "0027.HK", "0669.HK",
        "2269.HK", "6060.HK", "1211.HK", "9626.HK", "0981.HK",
        "0001.HK", "0003.HK", "0011.HK", "0016.HK", "0066.HK",
        "0175.HK", "0241.HK", "0267.HK", "0883.HK", "1038.HK",
        "1347.HK", "2015.HK", "0268.HK", "0772.HK", "0285.HK",
        "6618.HK", "2518.HK", "0522.HK", "9698.HK", "1833.HK",
    ])

    # A股 fallback 列表 - 沪深300/创业板/科创板核心成分股
    CN_WATCHLIST: list[str] = field(default_factory=lambda: [
        "600519.SS", "601318.SS", "600036.SS", "601166.SS", "600276.SS",
        "600900.SS", "601888.SS", "603259.SS", "600309.SS", "601012.SS",
        "000333.SZ", "000858.SZ", "000001.SZ", "000568.SZ", "000651.SZ",
        "300750.SZ", "300059.SZ", "300274.SZ", "300124.SZ", "300760.SZ",
        "300015.SZ", "300014.SZ", "300033.SZ", "300122.SZ", "300308.SZ",
        "688981.SS", "688111.SS", "688012.SS", "688041.SS", "688036.SS",
        "688008.SS", "688271.SS", "688599.SS", "688126.SS", "688303.SS",
    ])


# ============================================================================
# 市场差异化权重体系
# ============================================================================

@dataclass
class MarketScoringProfile:
    """单个市场的评分权重配置"""

    # 技术面各指标权重 (总和 = 1.0)
    technical: dict[str, float] = field(default_factory=dict)

    # 基本面各指标权重 (总和 = 1.0)
    fundamental: dict[str, float] = field(default_factory=dict)

    # 综合评分中技术面 vs 基本面的权重
    technical_weight: float = 0.4
    fundamental_weight: float = 0.6

    # 成长性加分上限 (0-20 的额外分)
    growth_bonus_cap: float = 15.0


def _default_us_profile() -> MarketScoringProfile:
    """美股评分配置: 重视盈利质量 + 成长性，技术面参考性强"""
    return MarketScoringProfile(
        technical={
            "ma_trend": 0.25,
            "rsi": 0.20,
            "macd": 0.25,
            "bollinger": 0.15,
            "volume_trend": 0.15,
        },
        fundamental={
            "pe_ratio": 0.12,
            "pb_ratio": 0.05,
            "roe": 0.15,
            "revenue_growth": 0.18,
            "earnings_growth": 0.15,
            "profit_margin": 0.10,
            "free_cashflow": 0.10,
            "debt_ratio": 0.05,
            "peg_ratio": 0.10,
        },
        technical_weight=0.35,
        fundamental_weight=0.65,
        growth_bonus_cap=15.0,
    )


def _default_hk_profile() -> MarketScoringProfile:
    """港股评分配置: 重视估值折价 + 股息，技术面权重稍低(流动性差异)"""
    return MarketScoringProfile(
        technical={
            "ma_trend": 0.25,
            "rsi": 0.20,
            "macd": 0.25,
            "bollinger": 0.15,
            "volume_trend": 0.15,
        },
        fundamental={
            "pe_ratio": 0.15,
            "pb_ratio": 0.10,
            "roe": 0.15,
            "revenue_growth": 0.15,
            "earnings_growth": 0.10,
            "profit_margin": 0.10,
            "dividend_yield": 0.10,
            "debt_ratio": 0.08,
            "peg_ratio": 0.07,
        },
        technical_weight=0.30,
        fundamental_weight=0.70,
        growth_bonus_cap=12.0,
    )


def _default_cn_profile() -> MarketScoringProfile:
    """A股评分配置: 重视政策/资金面驱动 + 成长弹性，技术面权重较高"""
    return MarketScoringProfile(
        technical={
            "ma_trend": 0.25,
            "rsi": 0.20,
            "macd": 0.25,
            "bollinger": 0.15,
            "volume_trend": 0.15,
        },
        fundamental={
            "pe_ratio": 0.12,
            "pb_ratio": 0.08,
            "roe": 0.15,
            "revenue_growth": 0.18,
            "earnings_growth": 0.17,
            "profit_margin": 0.10,
            "free_cashflow": 0.05,
            "debt_ratio": 0.05,
            "peg_ratio": 0.10,
        },
        technical_weight=0.40,
        fundamental_weight=0.60,
        growth_bonus_cap=18.0,
    )


@dataclass
class ScoringWeights:
    """评分权重配置 — 按市场区分"""

    # 各市场的评分 profile
    us: MarketScoringProfile = field(default_factory=_default_us_profile)
    hk: MarketScoringProfile = field(default_factory=_default_hk_profile)
    cn: MarketScoringProfile = field(default_factory=_default_cn_profile)

    def get_profile(self, market: str) -> MarketScoringProfile:
        """根据市场代码获取对应 profile"""
        return {"US": self.us, "HK": self.hk, "CN": self.cn}.get(market, self.us)


# ============================================================================
# 市场差异化阈值
# ============================================================================

@dataclass
class MarketThresholds:
    """单个市场的筛选阈值"""
    max_pe_ratio: float = 50.0
    max_pb_ratio: float = 10.0
    min_roe: float = 5.0
    # 成长股判定阈值
    high_growth_revenue: float = 25.0      # 营收增长 >= 此值视为高成长 (%)
    high_growth_earnings: float = 25.0     # 净利润增速 >= 此值视为高成长 (%)
    min_growth_revenue: float = 10.0       # 稳健成长最低营收增速 (%)


@dataclass
class ThresholdConfig:
    """筛选阈值配置"""
    # 最终推荐的最低分数 (0-100)
    min_recommendation_score: float = 60.0

    # 最多推荐数量
    max_recommendations: int = 10

    # 技术面阈值 (通用)
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0

    # 数据获取 - 历史数据天数
    history_days: int = 120

    # 各市场差异化阈值
    us: MarketThresholds = field(default_factory=lambda: MarketThresholds(
        max_pe_ratio=60.0,      # 美股容忍更高 PE (科技股估值)
        max_pb_ratio=15.0,
        min_roe=8.0,            # 美股 ROE 门槛更高
        high_growth_revenue=20.0,
        high_growth_earnings=20.0,
        min_growth_revenue=8.0,
    ))
    hk: MarketThresholds = field(default_factory=lambda: MarketThresholds(
        max_pe_ratio=40.0,      # 港股低估值偏好
        max_pb_ratio=8.0,
        min_roe=5.0,
        high_growth_revenue=20.0,
        high_growth_earnings=20.0,
        min_growth_revenue=8.0,
    ))
    cn: MarketThresholds = field(default_factory=lambda: MarketThresholds(
        max_pe_ratio=50.0,
        max_pb_ratio=10.0,
        min_roe=6.0,
        high_growth_revenue=25.0,    # A 股更看重高成长弹性
        high_growth_earnings=30.0,
        min_growth_revenue=10.0,
    ))

    def get_market_thresholds(self, market: str) -> MarketThresholds:
        return {"US": self.us, "HK": self.hk, "CN": self.cn}.get(market, self.us)


@dataclass
class AgentConfig:
    """Agent 总配置"""
    market: MarketConfig = field(default_factory=MarketConfig)
    weights: ScoringWeights = field(default_factory=ScoringWeights)
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)
