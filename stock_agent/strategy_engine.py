"""
策略分析与筛选模块
整合技术面和基本面评分，按市场差异化权重生成综合评分，
结合成长性标签进行筛选排序。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .config import AgentConfig, MarketScoringProfile
from .data_provider import StockData
from .fundamental_analyzer import FundamentalAnalyzer, FundamentalResult
from .technical_analyzer import TechnicalAnalyzer, TechnicalResult

logger = logging.getLogger(__name__)


@dataclass
class StockEvaluation:
    """单只股票的综合评估结果"""
    symbol: str
    company_name: str = ""
    market: str = ""
    sector: str = ""

    # 评分
    technical_score: float = 0.0
    fundamental_score: float = 0.0
    total_score: float = 0.0

    # 成长性
    growth_label: str = ""
    growth_bonus: float = 0.0

    # 详细分析
    technical: TechnicalResult | None = None
    fundamental: FundamentalResult | None = None

    # 推荐相关
    recommendation: str = ""   # "强烈推荐" / "推荐" / "观望" / "不推荐"
    reasons: list[str] = field(default_factory=list)

    @property
    def current_price(self) -> float | None:
        if self.technical and self.technical.indicators:
            return self.technical.indicators.get("ma5")
        return None


class StrategyEngine:
    """策略引擎：综合技术面和基本面给出最终评分与推荐（市场差异化）"""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.tech_analyzer = TechnicalAnalyzer(config)
        self.fund_analyzer = FundamentalAnalyzer(config)

    def evaluate(self, stock: StockData) -> StockEvaluation:
        """
        对单只股票进行综合评估。
        根据 stock.market 自动使用对应的评分权重。
        """
        tech_result = self.tech_analyzer.analyze(stock)
        fund_result = self.fund_analyzer.analyze(stock)

        evaluation = StockEvaluation(
            symbol=stock.symbol,
            market=stock.market,
            technical=tech_result,
            fundamental=fund_result,
        )

        # 从基本面数据填充公司信息
        if fund_result.metrics:
            evaluation.company_name = str(fund_result.metrics.get("company_name", stock.symbol))
            evaluation.sector = str(fund_result.metrics.get("sector", "Unknown"))

        # 成长性信息
        if fund_result.growth:
            evaluation.growth_label = fund_result.growth.growth_label
            evaluation.growth_bonus = fund_result.growth.growth_bonus

        # 获取市场专属权重
        profile: MarketScoringProfile = self.config.weights.get_profile(stock.market)

        evaluation.technical_score = tech_result.score
        evaluation.fundamental_score = fund_result.score

        # 综合评分 = 技术面 * 权重 + 基本面 * 权重
        # (基本面分数已经包含了成长性加分)
        raw_score = (
            tech_result.score * profile.technical_weight
            + fund_result.score * profile.fundamental_weight
        )
        evaluation.total_score = round(min(raw_score, 100.0), 2)

        # 生成推荐等级和理由
        evaluation.recommendation = self._get_recommendation_level(evaluation.total_score)
        evaluation.reasons = self._generate_reasons(tech_result, fund_result, evaluation)

        return evaluation

    def evaluate_batch(self, stocks: dict[str, StockData]) -> list[StockEvaluation]:
        """批量评估并按总分排序"""
        evaluations = []
        for symbol, stock_data in stocks.items():
            try:
                ev = self.evaluate(stock_data)
                evaluations.append(ev)
            except Exception as e:
                logger.error("评估 %s 时出错: %s", symbol, str(e))

        evaluations.sort(key=lambda x: x.total_score, reverse=True)
        return evaluations

    def filter_recommendations(self, evaluations: list[StockEvaluation]) -> list[StockEvaluation]:
        """根据阈值筛选推荐股票"""
        min_score = self.config.thresholds.min_recommendation_score
        max_count = self.config.thresholds.max_recommendations

        recommended = [
            ev for ev in evaluations
            if ev.total_score >= min_score
        ]

        return recommended[:max_count]

    def _get_recommendation_level(self, score: float) -> str:
        """根据总分确定推荐等级"""
        if score >= 80:
            return "强烈推荐"
        elif score >= 65:
            return "推荐"
        elif score >= 50:
            return "观望"
        else:
            return "不推荐"

    def _generate_reasons(
        self,
        tech: TechnicalResult,
        fund: FundamentalResult,
        evaluation: StockEvaluation,
    ) -> list[str]:
        """生成推荐理由摘要"""
        reasons = []

        # 技术面概览
        if tech.score >= 65:
            reasons.append(f"技术面评分 {tech.score:.0f} (偏强)")
        elif tech.score >= 45:
            reasons.append(f"技术面评分 {tech.score:.0f} (中性)")
        else:
            reasons.append(f"技术面评分 {tech.score:.0f} (偏弱)")

        # 基本面概览
        if fund.score >= 65:
            reasons.append(f"基本面评分 {fund.score:.0f} (优良)")
        elif fund.score >= 45:
            reasons.append(f"基本面评分 {fund.score:.0f} (一般)")
        else:
            reasons.append(f"基本面评分 {fund.score:.0f} (较差)")

        # 成长性标签
        if evaluation.growth_label and evaluation.growth_label not in ("未知", "低成长"):
            reasons.append(f"成长标签: {evaluation.growth_label} (加分 {evaluation.growth_bonus:+.1f})")

        # 挑选最关键的技术信号 (最多2条)
        key_tech_signals = [s for s in tech.signals if any(
            kw in s for kw in ["金叉", "死叉", "超卖", "超买", "放量上涨", "放量下跌", "反弹", "回调"]
        )]
        reasons.extend(key_tech_signals[:2])

        # 挑选最关键的基本面信号 (最多2条)
        key_fund_signals = [s for s in fund.signals if any(
            kw in s for kw in [
                "低估", "高速增长", "优秀", "卓越", "亏损", "显著",
                "吸引力", "超高成长", "高盈利成长", "高营收成长", "双降", "PEG",
            ]
        )]
        reasons.extend(key_fund_signals[:2])

        return reasons
