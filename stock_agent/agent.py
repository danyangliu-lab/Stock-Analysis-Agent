"""
智能股票推荐 Agent 主控模块
协调数据获取、策略分析、推荐输出的完整流程。
"""

from __future__ import annotations

import logging

from .config import AgentConfig
from .data_provider import DataProvider, StockData
from .recommendation import RecommendationReporter
from .strategy_engine import StockEvaluation, StrategyEngine

logger = logging.getLogger(__name__)


class StockAgent:
    """
    智能股票推荐 Agent

    用法示例:
        agent = StockAgent()
        agent.run()                           # 分析全部关注列表
        agent.run(market="US")                # 仅分析美股
        agent.run(symbols=["AAPL", "MSFT"])   # 分析指定股票
    """

    def __init__(self, config: AgentConfig | None = None):
        self.config = config or AgentConfig()
        self.data_provider = DataProvider(self.config)
        self.strategy = StrategyEngine(self.config)
        self.reporter = RecommendationReporter()

    def run(
        self,
        market: str | None = None,
        symbols: list[str] | None = None,
        output_json: bool = False,
    ) -> dict:
        """
        执行完整的推荐流程。

        Args:
            market: "US" / "HK" / "CN" / None(全部)
            symbols: 指定股票列表 (优先级高于 market)
            output_json: 是否输出 JSON

        Returns:
            包含推荐结果的字典
        """
        logger.info("=== 智能股票推荐 Agent 启动 ===")

        # 1. 数据获取
        stocks = self._fetch_data(market, symbols)
        if not stocks:
            logger.error("未获取到任何有效数据，流程终止")
            return {"error": "未获取到数据", "recommendations": []}

        valid_count = sum(1 for s in stocks.values() if s.is_valid)
        logger.info("数据获取完成: %d/%d 有效", valid_count, len(stocks))

        # 2. 策略分析
        all_evaluations = self.strategy.evaluate_batch(stocks)
        logger.info("策略分析完成: %d 只股票已评估", len(all_evaluations))

        # 3. 筛选推荐
        recommendations = self.strategy.filter_recommendations(all_evaluations)
        logger.info("筛选完成: %d 只股票达到推荐标准", len(recommendations))

        # 4. 输出报告
        if output_json:
            json_str = self.reporter.to_json(recommendations, all_evaluations)
            print(json_str)
        else:
            self.reporter.print_report(recommendations, all_evaluations)

        return {
            "recommendations": self.reporter.to_dict_list(recommendations),
            "all_evaluations": self.reporter.to_dict_list(all_evaluations),
            "summary": {
                "total_analyzed": len(all_evaluations),
                "total_recommended": len(recommendations),
                "valid_data": valid_count,
            },
        }

    def analyze_single(self, symbol: str) -> StockEvaluation:
        """分析单只股票并打印详细报告"""
        stock = self.data_provider.get_stock_data(symbol)
        evaluation = self.strategy.evaluate(stock)

        self.reporter.print_report(
            recommendations=[evaluation] if evaluation.total_score >= self.config.thresholds.min_recommendation_score else [],
            all_evaluations=[evaluation],
            title=f"{symbol} 分析报告",
        )
        return evaluation

    def _fetch_data(
        self,
        market: str | None,
        symbols: list[str] | None,
    ) -> dict[str, StockData]:
        """根据参数选择数据获取方式"""
        if symbols:
            logger.info("获取指定股票数据: %s", symbols)
            return self.data_provider.get_batch_data(symbols)
        elif market == "US":
            logger.info("获取美股关注列表数据")
            return self.data_provider.get_us_stocks()
        elif market == "HK":
            logger.info("获取港股关注列表数据")
            return self.data_provider.get_hk_stocks()
        elif market == "CN":
            logger.info("获取A股关注列表数据")
            return self.data_provider.get_cn_stocks()
        else:
            logger.info("获取全部关注列表数据")
            return self.data_provider.get_all_stocks()
