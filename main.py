"""
智能股票推荐 Agent - 主入口
支持命令行参数控制分析范围和输出格式
"""

import argparse
import logging
import sys

from stock_agent.agent import StockAgent
from stock_agent.config import AgentConfig, MarketConfig, ThresholdConfig


def setup_logging(verbose: bool = False):
    """配置日志"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description="智能股票推荐 Agent - 美股/港股/A股选股系统",
    )
    _ = parser.add_argument(
        "--market",
        choices=["US", "HK", "CN", "ALL"],
        default="ALL",
        help="分析市场: US(美股), HK(港股), CN(A股), ALL(全部) (默认: ALL)",
    )
    _ = parser.add_argument(
        "--symbols",
        nargs="+",
        default=None,
        help="指定分析的股票代码 (如: AAPL MSFT 0700.HK 600519.SS)",
    )
    _ = parser.add_argument(
        "--single",
        type=str,
        default=None,
        help="分析单只股票并显示详细报告 (如: AAPL)",
    )
    _ = parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出结果",
    )
    _ = parser.add_argument(
        "--min-score",
        type=float,
        default=60.0,
        help="最低推荐分数 (默认: 60)",
    )
    _ = parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="最多推荐数量 (默认: 10)",
    )
    _ = parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示详细日志",
    )
    _ = parser.add_argument(
        "--no-dynamic",
        action="store_true",
        help="禁用动态获取指数成分股，使用静态 fallback 列表",
    )
    _ = parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="强制刷新指数成分股缓存",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    setup_logging(args.verbose)

    # 构建配置
    market_config = MarketConfig(
        use_dynamic_constituents=not args.no_dynamic,
    )
    config = AgentConfig(
        market=market_config,
        thresholds=ThresholdConfig(
            min_recommendation_score=args.min_score,
            max_recommendations=args.top,
        ),
    )

    agent = StockAgent(config)

    # 刷新缓存
    if args.refresh_cache:
        from stock_agent.index_constituents import IndexConstituents
        idx = IndexConstituents(cache_expiry_hours=config.market.cache_expiry_hours)
        idx.clear_cache()
        logging.getLogger(__name__).info("成分股缓存已刷新")

    # 单只股票详细分析
    if args.single:
        agent.analyze_single(args.single)
        return

    # 批量分析
    market = None if args.market == "ALL" else args.market
    result = agent.run(
        market=market,
        symbols=args.symbols,
        output_json=args.json,
    )

    if result.get("error"):
        print(f"\n错误: {result['error']}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
