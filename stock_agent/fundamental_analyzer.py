"""
基本面评估模块
评估 PE、PB、ROE、营收增长率、净利润增速、自由现金流、PEG、股息率等基本面指标，
针对美股/港股/A股三个市场采用差异化权重和阈值，
并深度分析成长性（营收增速、盈利增速、PEG）给出 0-100 的基本面评分 + 成长性加分。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .config import AgentConfig, MarketScoringProfile, MarketThresholds
from .data_provider import StockData

logger = logging.getLogger(__name__)


# 行业基准 PE (简化版，用于相对估值)
SECTOR_PE_BENCHMARKS = {
    "Technology": 30.0,
    "Financial Services": 15.0,
    "Healthcare": 25.0,
    "Consumer Cyclical": 22.0,
    "Consumer Defensive": 20.0,
    "Communication Services": 20.0,
    "Industrials": 20.0,
    "Energy": 12.0,
    "Basic Materials": 15.0,
    "Real Estate": 18.0,
    "Utilities": 16.0,
}

DEFAULT_PE_BENCHMARK = 20.0


@dataclass
class GrowthProfile:
    """成长性分析汇总"""
    revenue_growth: float | None = None       # 营收增长率 (%)
    earnings_growth: float | None = None      # 净利润增速 (%)
    peg_ratio: float | None = None            # PEG
    free_cashflow_per_share: float | None = None  # 每股自由现金流
    growth_label: str = "未知"                 # 成长标签
    growth_bonus: float = 0.0                  # 成长性加分 (0-20)
    growth_signals: list[str] = field(default_factory=list)


@dataclass
class FundamentalResult:
    """基本面分析结果"""
    symbol: str
    score: float = 0.0
    sub_scores: dict[str, float] = field(default_factory=dict)
    signals: list[str] = field(default_factory=list)
    metrics: dict[str, float | None] = field(default_factory=dict)
    growth: GrowthProfile | None = None
    error: str | None = None


class FundamentalAnalyzer:
    """基本面分析器 — 支持市场差异化策略"""

    def __init__(self, config: AgentConfig):
        self.config = config

    def analyze(self, stock: StockData) -> FundamentalResult:
        """
        对单只股票进行基本面分析。
        根据 stock.market 自动选择对应的权重和阈值。

        Returns:
            FundamentalResult
        """
        result = FundamentalResult(symbol=stock.symbol)

        if not stock.info:
            result.error = "无基本面数据"
            result.score = 50.0
            return result

        info = stock.info
        market = stock.market  # "US" / "HK" / "CN"

        # 获取市场专属配置
        profile: MarketScoringProfile = self.config.weights.get_profile(market)
        thresholds: MarketThresholds = self.config.thresholds.get_market_thresholds(market)

        try:
            # ---- 计算各子项评分 ----
            pe_score, pe_signals = self._score_pe(info, thresholds)
            pb_score, pb_signals = self._score_pb(info, thresholds)
            roe_score, roe_signals = self._score_roe(info, thresholds)
            rev_score, rev_signals = self._score_revenue_growth(info, thresholds)
            earn_score, earn_signals = self._score_earnings_growth(info, thresholds)
            pm_score, pm_signals = self._score_profit_margin(info)
            debt_score, debt_signals = self._score_debt_ratio(info)
            fcf_score, fcf_signals = self._score_free_cashflow(info)
            peg_score, peg_signals = self._score_peg(info)
            div_score, div_signals = self._score_dividend_yield(info, market)

            result.sub_scores = {
                "pe_ratio": pe_score,
                "pb_ratio": pb_score,
                "roe": roe_score,
                "revenue_growth": rev_score,
                "earnings_growth": earn_score,
                "profit_margin": pm_score,
                "debt_ratio": debt_score,
                "free_cashflow": fcf_score,
                "peg_ratio": peg_score,
                "dividend_yield": div_score,
            }

            result.signals = (
                pe_signals + pb_signals + roe_signals
                + rev_signals + earn_signals + pm_signals
                + debt_signals + fcf_signals + peg_signals + div_signals
            )

            result.metrics = {
                "pe_ratio": self._safe_get(info, "trailingPE"),
                "forward_pe": self._safe_get(info, "forwardPE"),
                "pb_ratio": self._safe_get(info, "priceToBook"),
                "roe": self._safe_get(info, "returnOnEquity"),
                "revenue_growth": self._safe_get(info, "revenueGrowth"),
                "earnings_growth": self._safe_get(info, "earningsGrowth"),
                "profit_margin": self._safe_get(info, "profitMargins"),
                "debt_to_equity": self._safe_get(info, "debtToEquity"),
                "free_cashflow": self._safe_get(info, "freeCashflow"),
                "peg_ratio": self._safe_get(info, "pegRatio"),
                "dividend_yield": self._safe_get(info, "dividendYield"),
                "market_cap": self._safe_get(info, "marketCap"),
                "sector": info.get("sector", "Unknown"),
                "industry": info.get("industry", "Unknown"),
                "company_name": info.get("shortName", stock.symbol),
            }

            # ---- 加权综合评分 ----
            fund_weights = profile.fundamental
            total = 0.0
            total_weight_used = 0.0
            for key, weight in fund_weights.items():
                if key in result.sub_scores:
                    total += result.sub_scores[key] * weight
                    total_weight_used += weight

            # 若部分指标缺失，按已有权重归一化
            if total_weight_used > 0 and total_weight_used < 0.99:
                total = total / total_weight_used

            result.score = round(total, 2)

            # ---- 成长性深度分析 & 加分 ----
            growth = self._analyze_growth(info, thresholds, profile)
            result.growth = growth
            result.signals.extend(growth.growth_signals)

            # 将成长加分叠加到 score 上 (上限由 profile 配置)
            result.score = round(min(result.score + growth.growth_bonus, 100.0), 2)

        except Exception as e:
            logger.error("基本面分析异常 %s: %s", stock.symbol, str(e))
            result.error = f"基本面分析异常: {str(e)}"
            result.score = 50.0

        return result

    # ================================================================
    # 成长性深度分析
    # ================================================================

    def _analyze_growth(
        self,
        info: dict[str, Any],
        thresholds: MarketThresholds,
        profile: MarketScoringProfile,
    ) -> GrowthProfile:
        """综合分析成长性并计算加分"""
        gp = GrowthProfile()

        rev_g = self._safe_get(info, "revenueGrowth")
        earn_g = self._safe_get(info, "earningsGrowth")
        peg = self._safe_get(info, "pegRatio")
        fcf = self._safe_get(info, "freeCashflow")
        shares = self._safe_get(info, "sharesOutstanding")

        if rev_g is not None:
            gp.revenue_growth = round(rev_g * 100, 2)
        if earn_g is not None:
            gp.earnings_growth = round(earn_g * 100, 2)
        gp.peg_ratio = peg
        if fcf is not None and shares is not None and shares > 0:
            gp.free_cashflow_per_share = round(fcf / shares, 2)

        # ---- 成长标签判定 ----
        bonus = 0.0

        high_rev = thresholds.high_growth_revenue
        high_earn = thresholds.high_growth_earnings
        min_rev = thresholds.min_growth_revenue

        rev_pct = gp.revenue_growth
        earn_pct = gp.earnings_growth

        # 1) 超高成长 (营收+盈利双高增)
        if rev_pct is not None and earn_pct is not None:
            if rev_pct >= high_rev and earn_pct >= high_earn:
                gp.growth_label = "超高成长"
                bonus += 12.0
                gp.growth_signals.append(
                    f"[超高成长] 营收增速{rev_pct:.1f}%+盈利增速{earn_pct:.1f}%双高增"
                )
            elif rev_pct >= min_rev and earn_pct >= high_earn:
                gp.growth_label = "高盈利成长"
                bonus += 9.0
                gp.growth_signals.append(
                    f"[高盈利成长] 盈利增速{earn_pct:.1f}%突出，营收增速{rev_pct:.1f}%稳健"
                )
            elif rev_pct >= high_rev and (earn_pct is None or earn_pct >= 0):
                gp.growth_label = "高营收成长"
                bonus += 7.0
                gp.growth_signals.append(
                    f"[高营收成长] 营收增速{rev_pct:.1f}%强劲"
                )
            elif rev_pct >= min_rev and earn_pct is not None and earn_pct >= 0:
                gp.growth_label = "稳健成长"
                bonus += 4.0
                gp.growth_signals.append(
                    f"[稳健成长] 营收增速{rev_pct:.1f}%，盈利增速{earn_pct:.1f}%"
                )
            elif rev_pct < 0 and earn_pct < 0:
                gp.growth_label = "双降"
                bonus -= 5.0
                gp.growth_signals.append(
                    f"[双降] 营收{rev_pct:.1f}%、盈利{earn_pct:.1f}%均下滑"
                )
            else:
                gp.growth_label = "低成长"
                gp.growth_signals.append(
                    f"[低成长] 营收增速{rev_pct:.1f}%，盈利增速{earn_pct:.1f}%"
                )
        elif rev_pct is not None:
            if rev_pct >= high_rev:
                gp.growth_label = "高营收成长"
                bonus += 6.0
                gp.growth_signals.append(f"[高营收成长] 营收增速{rev_pct:.1f}%")
            elif rev_pct >= min_rev:
                gp.growth_label = "稳健成长"
                bonus += 3.0
            elif rev_pct < -5:
                gp.growth_label = "营收下滑"
                bonus -= 3.0
                gp.growth_signals.append(f"营收增速{rev_pct:.1f}%，增长承压")
            else:
                gp.growth_label = "低成长"

        # 2) PEG 加分/扣分
        if peg is not None:
            if 0 < peg < 0.8:
                bonus += 4.0
                gp.growth_signals.append(f"PEG={peg:.2f}，成长性估值极具吸引力")
            elif 0.8 <= peg <= 1.2:
                bonus += 2.0
                gp.growth_signals.append(f"PEG={peg:.2f}，估值与成长匹配合理")
            elif 1.2 < peg <= 2.0:
                pass  # 中性
            elif peg > 2.0:
                bonus -= 2.0
                gp.growth_signals.append(f"PEG={peg:.2f}，成长性相对估值偏贵")

        # 3) 自由现金流佐证 (正现金流加分)
        if fcf is not None:
            if fcf > 0:
                bonus += 1.5
                gp.growth_signals.append("自由现金流为正，成长质量有保障")
            else:
                bonus -= 1.0

        # 限制在 profile 配置的上限
        cap = profile.growth_bonus_cap
        gp.growth_bonus = round(max(-cap, min(cap, bonus)), 2)

        return gp

    # ================================================================
    # 子项评分方法
    # ================================================================

    def _score_pe(self, info: dict[str, Any], thresholds: MarketThresholds):
        pe = self._safe_get(info, "trailingPE")
        forward_pe = self._safe_get(info, "forwardPE")
        sector = info.get("sector", "")
        benchmark_pe = SECTOR_PE_BENCHMARKS.get(sector, DEFAULT_PE_BENCHMARK)

        signals = []

        if pe is None or pe <= 0:
            if forward_pe and forward_pe > 0:
                pe = forward_pe
                signals.append(f"使用前瞻PE={pe:.1f}进行评估")
            else:
                return 40.0, ["PE数据缺失，无法评估估值水平"]

        max_pe = thresholds.max_pe_ratio
        if pe > max_pe:
            score = 15.0
            signals.append(f"PE={pe:.1f} 显著高于阈值{max_pe}，估值偏高")
        elif pe > benchmark_pe * 1.5:
            score = 25.0
            signals.append(f"PE={pe:.1f} 高于行业基准{benchmark_pe:.0f}的1.5倍，估值较高")
        elif pe > benchmark_pe:
            score = 45.0
            signals.append(f"PE={pe:.1f} 略高于行业基准{benchmark_pe:.0f}")
        elif pe > benchmark_pe * 0.7:
            score = 65.0
            signals.append(f"PE={pe:.1f} 接近行业基准{benchmark_pe:.0f}，估值合理")
        elif pe > benchmark_pe * 0.5:
            score = 80.0
            signals.append(f"PE={pe:.1f} 低于行业基准{benchmark_pe:.0f}，估值具有吸引力")
        else:
            score = 85.0
            signals.append(f"PE={pe:.1f} 显著低于行业基准{benchmark_pe:.0f}，可能被低估")

        return score, signals

    def _score_pb(self, info: dict[str, Any], thresholds: MarketThresholds):
        pb = self._safe_get(info, "priceToBook")
        signals = []

        if pb is None:
            return 50.0, ["PB数据缺失"]

        max_pb = thresholds.max_pb_ratio
        if pb < 0:
            return 20.0, ["PB为负值，净资产为负，风险较高"]
        elif pb > max_pb:
            score = 20.0
            signals.append(f"PB={pb:.2f} 偏高，超过阈值{max_pb}")
        elif pb > 5:
            score = 35.0
            signals.append(f"PB={pb:.2f} 较高")
        elif pb > 3:
            score = 50.0
            signals.append(f"PB={pb:.2f} 中等")
        elif pb > 1:
            score = 70.0
            signals.append(f"PB={pb:.2f} 合理")
        else:
            score = 80.0
            signals.append(f"PB={pb:.2f} 低于净资产，可能被低估")

        return score, signals

    def _score_roe(self, info: dict[str, Any], thresholds: MarketThresholds):
        roe = self._safe_get(info, "returnOnEquity")
        signals = []

        if roe is None:
            return 50.0, ["ROE数据缺失"]

        roe_pct = roe * 100
        min_roe = thresholds.min_roe

        if roe_pct < 0:
            score = 10.0
            signals.append(f"ROE={roe_pct:.1f}% 为负，盈利能力差")
        elif roe_pct < min_roe:
            score = 30.0
            signals.append(f"ROE={roe_pct:.1f}% 低于阈值{min_roe}%")
        elif roe_pct < 10:
            score = 50.0
            signals.append(f"ROE={roe_pct:.1f}% 一般")
        elif roe_pct < 15:
            score = 65.0
            signals.append(f"ROE={roe_pct:.1f}% 良好")
        elif roe_pct < 25:
            score = 80.0
            signals.append(f"ROE={roe_pct:.1f}% 优秀")
        else:
            score = 90.0
            signals.append(f"ROE={roe_pct:.1f}% 卓越，盈利能力极强")

        return score, signals

    def _score_revenue_growth(self, info: dict[str, Any], thresholds: MarketThresholds):
        growth = self._safe_get(info, "revenueGrowth")
        signals = []

        if growth is None:
            return 50.0, ["营收增长率数据缺失"]

        growth_pct = growth * 100
        high_g = thresholds.high_growth_revenue

        if growth_pct < -10:
            score = 15.0
            signals.append(f"营收增长率={growth_pct:.1f}%，显著下滑")
        elif growth_pct < 0:
            score = 30.0
            signals.append(f"营收增长率={growth_pct:.1f}%，略有下滑")
        elif growth_pct < 5:
            score = 45.0
            signals.append(f"营收增长率={growth_pct:.1f}%，增长缓慢")
        elif growth_pct < 15:
            score = 60.0
            signals.append(f"营收增长率={growth_pct:.1f}%，稳健增长")
        elif growth_pct < high_g:
            score = 75.0
            signals.append(f"营收增长率={growth_pct:.1f}%，增长较快")
        else:
            score = 90.0
            signals.append(f"营收增长率={growth_pct:.1f}%，高速增长")

        return score, signals

    def _score_earnings_growth(self, info: dict[str, Any], thresholds: MarketThresholds):
        """净利润增速评分"""
        growth = self._safe_get(info, "earningsGrowth")
        signals = []

        if growth is None:
            return 50.0, ["净利润增速数据缺失"]

        growth_pct = growth * 100
        high_g = thresholds.high_growth_earnings

        if growth_pct < -20:
            score = 10.0
            signals.append(f"净利润增速={growth_pct:.1f}%，大幅下滑")
        elif growth_pct < -5:
            score = 25.0
            signals.append(f"净利润增速={growth_pct:.1f}%，明显下滑")
        elif growth_pct < 0:
            score = 35.0
            signals.append(f"净利润增速={growth_pct:.1f}%，略有下滑")
        elif growth_pct < 10:
            score = 50.0
            signals.append(f"净利润增速={growth_pct:.1f}%，增长平缓")
        elif growth_pct < high_g:
            score = 70.0
            signals.append(f"净利润增速={growth_pct:.1f}%，稳健增长")
        else:
            score = 90.0
            signals.append(f"净利润增速={growth_pct:.1f}%，高速增长")

        return score, signals

    def _score_profit_margin(self, info: dict[str, Any]):
        margin = self._safe_get(info, "profitMargins")
        signals = []

        if margin is None:
            return 50.0, ["利润率数据缺失"]

        margin_pct = margin * 100

        if margin_pct < 0:
            score = 10.0
            signals.append(f"净利润率={margin_pct:.1f}%，处于亏损状态")
        elif margin_pct < 5:
            score = 35.0
            signals.append(f"净利润率={margin_pct:.1f}%，盈利较薄")
        elif margin_pct < 10:
            score = 50.0
            signals.append(f"净利润率={margin_pct:.1f}%，盈利一般")
        elif margin_pct < 20:
            score = 70.0
            signals.append(f"净利润率={margin_pct:.1f}%，盈利良好")
        else:
            score = 85.0
            signals.append(f"净利润率={margin_pct:.1f}%，盈利能力优秀")

        return score, signals

    def _score_debt_ratio(self, info: dict[str, Any]):
        debt_equity = self._safe_get(info, "debtToEquity")
        signals = []

        if debt_equity is None:
            return 50.0, ["资产负债数据缺失"]

        if debt_equity > 200:
            score = 15.0
            signals.append(f"负债/权益比={debt_equity:.0f}%，杠杆极高，风险较大")
        elif debt_equity > 100:
            score = 35.0
            signals.append(f"负债/权益比={debt_equity:.0f}%，杠杆较高")
        elif debt_equity > 50:
            score = 55.0
            signals.append(f"负债/权益比={debt_equity:.0f}%，财务结构一般")
        elif debt_equity > 20:
            score = 75.0
            signals.append(f"负债/权益比={debt_equity:.0f}%，财务结构健康")
        else:
            score = 90.0
            signals.append(f"负债/权益比={debt_equity:.0f}%，财务结构优良")

        return score, signals

    def _score_free_cashflow(self, info: dict[str, Any]):
        """自由现金流评分"""
        fcf = self._safe_get(info, "freeCashflow")
        market_cap = self._safe_get(info, "marketCap")
        signals = []

        if fcf is None:
            return 50.0, ["自由现金流数据缺失"]

        if market_cap and market_cap > 0:
            fcf_yield = fcf / market_cap * 100  # FCF yield %
            if fcf_yield < -2:
                score = 15.0
                signals.append(f"自由现金流收益率={fcf_yield:.1f}%，现金流为负")
            elif fcf_yield < 0:
                score = 30.0
                signals.append(f"自由现金流收益率={fcf_yield:.1f}%，略负")
            elif fcf_yield < 3:
                score = 55.0
                signals.append(f"自由现金流收益率={fcf_yield:.1f}%，一般")
            elif fcf_yield < 6:
                score = 70.0
                signals.append(f"自由现金流收益率={fcf_yield:.1f}%，良好")
            else:
                score = 85.0
                signals.append(f"自由现金流收益率={fcf_yield:.1f}%，优秀")
        else:
            if fcf > 0:
                score = 65.0
                signals.append("自由现金流为正")
            else:
                score = 30.0
                signals.append("自由现金流为负，需关注现金流风险")

        return score, signals

    def _score_peg(self, info: dict[str, Any]):
        """PEG 评分"""
        peg = self._safe_get(info, "pegRatio")
        signals = []

        if peg is None:
            return 50.0, ["PEG数据缺失"]

        if peg < 0:
            score = 25.0
            signals.append(f"PEG={peg:.2f}，负值(亏损或负增长)")
        elif peg < 0.5:
            score = 90.0
            signals.append(f"PEG={peg:.2f}，估值极低，成长性价比极高")
        elif peg < 1.0:
            score = 80.0
            signals.append(f"PEG={peg:.2f}，估值合理偏低")
        elif peg < 1.5:
            score = 65.0
            signals.append(f"PEG={peg:.2f}，估值合理")
        elif peg < 2.5:
            score = 45.0
            signals.append(f"PEG={peg:.2f}，估值偏高")
        else:
            score = 25.0
            signals.append(f"PEG={peg:.2f}，估值过高")

        return score, signals

    def _score_dividend_yield(self, info: dict[str, Any], market: str):
        """股息率评分 — 港股权重更高"""
        div_yield = self._safe_get(info, "dividendYield")
        signals = []

        if div_yield is None:
            return 50.0, ["股息率数据缺失"]

        div_pct = div_yield * 100

        if div_pct <= 0:
            score = 40.0
            signals.append("无股息")
        elif div_pct < 1:
            score = 50.0
            signals.append(f"股息率={div_pct:.2f}%，较低")
        elif div_pct < 3:
            score = 65.0
            signals.append(f"股息率={div_pct:.2f}%，中等")
        elif div_pct < 5:
            score = 80.0
            signals.append(f"股息率={div_pct:.2f}%，较高")
        else:
            score = 90.0
            signals.append(f"股息率={div_pct:.2f}%，高股息")

        # 港股更看重股息
        if market == "HK" and div_pct >= 3:
            score = min(score + 5, 95)
            signals.append("港股高股息策略加分")

        return score, signals

    # ==================== 工具方法 ====================

    @staticmethod
    def _safe_get(info: dict[str, Any], key: str) -> float | None:
        """安全获取数值型字段，处理 None/NaN/非数值情况"""
        val = info.get(key)
        if val is None:
            return None
        try:
            val = float(val)
            return val if not np.isnan(val) else None
        except (ValueError, TypeError):
            return None
