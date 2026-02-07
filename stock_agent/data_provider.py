"""
数据接口模块
负责从外部数据源获取美股/港股/A股的行情数据和基本面数据。
支持实时数据和历史数据获取，具备重试与容错机制。
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import yfinance as yf

from .config import AgentConfig
from .index_constituents import IndexConstituents

logger = logging.getLogger(__name__)


@dataclass
class StockData:
    """单只股票的完整数据容器"""
    symbol: str
    market: str  # "US", "HK", or "CN"
    history: pd.DataFrame | None = None
    info: dict[str, Any] = field(default_factory=dict)
    fetch_time: datetime | None = None
    error: str | None = None

    @property
    def is_valid(self) -> bool:
        return self.history is not None and not self.history.empty and self.error is None


class DataProvider:
    """
    数据提供者：从 Yahoo Finance 获取美股/港股/A股数据。
    具备缓存、重试和容错能力。
    """

    # 创业板/科创板市值过滤阈值 (人民币)
    CN_MIN_MARKET_CAP_CNY: float = 100e8  # 100 亿人民币
    # 中概股市值过滤阈值 (美元)
    ADR_MIN_MARKET_CAP_USD: float = 50e8  # 50 亿美元

    def __init__(self, config: AgentConfig, max_retries: int = 2, retry_delay: float = 1.0):
        self.config = config
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._cache: dict[str, StockData] = {}
        self._index = IndexConstituents(
            cache_expiry_hours=config.market.cache_expiry_hours,
        ) if config.market.use_dynamic_constituents else None

    def get_stock_data(self, symbol: str, use_cache: bool = True) -> StockData:
        """
        获取单只股票的历史行情 + 基本面数据。

        Args:
            symbol: 股票代码 (如 "AAPL" 或 "0700.HK")
            use_cache: 是否使用缓存

        Returns:
            StockData 对象
        """
        if use_cache and symbol in self._cache:
            cached = self._cache[symbol]
            if cached.fetch_time and (datetime.now() - cached.fetch_time).seconds < 3600:
                logger.debug("使用缓存数据: %s", symbol)
                return cached

        market = "HK" if symbol.endswith(".HK") else "CN" if symbol.endswith((".SS", ".SZ")) else "US"
        stock_data = StockData(symbol=symbol, market=market)

        for attempt in range(1, self.max_retries + 1):
            try:
                ticker = yf.Ticker(symbol)

                end_date = datetime.now()
                start_date = end_date - timedelta(days=self.config.thresholds.history_days)
                history = ticker.history(
                    start=start_date.strftime("%Y-%m-%d"),
                    end=end_date.strftime("%Y-%m-%d"),
                )

                if history.empty:
                    raise ValueError(f"未获取到 {symbol} 的历史数据")

                stock_data.history = history
                stock_data.info = ticker.info or {}
                stock_data.fetch_time = datetime.now()

                logger.info("成功获取 %s 数据, 历史记录 %d 条", symbol, len(history))
                break

            except Exception as e:
                logger.warning("获取 %s 数据失败 (第%d次): %s", symbol, attempt, str(e))
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay * attempt)
                else:
                    stock_data.error = f"数据获取失败: {str(e)}"

        self._cache[symbol] = stock_data
        return stock_data

    def get_batch_data(self, symbols: list[str]) -> dict[str, StockData]:
        """批量获取多只股票数据"""
        results = {}
        total = len(symbols)

        for i, symbol in enumerate(symbols, 1):
            logger.info("正在获取数据 [%d/%d]: %s", i, total, symbol)
            results[symbol] = self.get_stock_data(symbol)
            if i < total:
                time.sleep(0.3)

        valid_count = sum(1 for sd in results.values() if sd.is_valid)
        logger.info("批量获取完成: %d/%d 成功", valid_count, total)
        return results

    def _filter_by_market_cap(
        self,
        symbols: list[str],
        min_cap: float,
        currency_mode: str = "CNY",
    ) -> list[str]:
        """
        通过 yfinance fast_info 获取市值，过滤掉市值低于阈值的股票。
        结果会缓存到 index_constituents 的缓存目录中。

        Args:
            symbols: 待过滤的股票代码列表
            min_cap: 最低市值阈值
            currency_mode: "CNY" 以人民币为基准; "USD" 以美元为基准

        Returns:
            满足市值要求的股票代码列表
        """
        if not symbols:
            return symbols

        # 检查缓存
        cache_key = f"MCAP_{currency_mode}_{int(min_cap)}"
        if self._index:
            import json
            from datetime import datetime as dt
            cache_file = self._index.cache_dir / f"{cache_key}.json"
            if cache_file.exists():
                try:
                    data = json.loads(cache_file.read_text(encoding="utf-8"))
                    cached_time = dt.fromisoformat(data["timestamp"])
                    if dt.now() - cached_time < self._index.cache_expiry:
                        cached_symbols = data["symbols"]
                        logger.info(
                            "使用市值筛选缓存 (%s): %d 只 (缓存时间: %s)",
                            cache_key, len(cached_symbols), cached_time,
                        )
                        return cached_symbols
                except (json.JSONDecodeError, KeyError, ValueError):
                    pass

        label = f"{min_cap / 1e8:.0f} 亿{'元' if currency_mode == 'CNY' else '美元'}"
        logger.info("正在对 %d 只股票进行市值筛选 (>= %s)...", len(symbols), label)

        passed: list[str] = []
        skipped = 0

        for idx, sym in enumerate(symbols):
            try:
                ticker = yf.Ticker(sym)
                fi = ticker.fast_info
                market_cap = fi.get("marketCap", None) if hasattr(fi, "get") else getattr(fi, "market_cap", None)
                if market_cap is None:
                    passed.append(sym)
                    continue
                currency = fi.get("currency", "USD") if hasattr(fi, "get") else getattr(fi, "currency", "USD")

                if currency_mode == "USD":
                    # 将非美元市值转为美元
                    cap_usd = market_cap
                    if currency in ("CNY", "RMB"):
                        cap_usd = market_cap / 7.2
                    elif currency == "HKD":
                        cap_usd = market_cap / 7.8
                    if cap_usd >= min_cap:
                        passed.append(sym)
                    else:
                        skipped += 1
                else:
                    # CNY 模式 (原逻辑)
                    cap_cny = market_cap
                    if currency not in ("CNY", "RMB"):
                        cap_cny = market_cap * 7.2
                    if cap_cny >= min_cap:
                        passed.append(sym)
                    else:
                        skipped += 1
            except Exception:
                passed.append(sym)

            # 进度日志 (每 200 只输出一次)
            if (idx + 1) % 200 == 0:
                logger.info("市值筛选进度: %d/%d ...", idx + 1, len(symbols))

        logger.info(
            "市值筛选完成: %d 只通过, %d 只被过滤 (< %s)",
            len(passed), skipped, label,
        )

        # 写入缓存
        if self._index and passed:
            import json
            from datetime import datetime as dt
            cache_file = self._index.cache_dir / f"{cache_key}.json"
            cache_data = {
                "timestamp": dt.now().isoformat(),
                "min_cap": min_cap,
                "currency_mode": currency_mode,
                "count": len(passed),
                "symbols": passed,
            }
            cache_file.write_text(json.dumps(cache_data, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info("市值筛选结果已缓存: %d 只", len(passed))

        return passed

    def _get_us_symbols(self) -> list[str]:
        """获取美股股票列表 (指数成分 + 中概股 + AI概念)，动态获取失败时回退到静态列表"""
        if self._index:
            try:
                symbols = self._index.get_us_symbols()
                if symbols:
                    return symbols
            except Exception as e:
                logger.warning("动态获取美股成分股失败，使用 fallback 列表: %s", e)
        # fallback: 静态列表 + 中概股(市值>50亿美元) + AI概念
        return self.config.market.US_WATCHLIST

    def _get_hk_symbols(self) -> list[str]:
        """获取港股股票列表，动态获取失败时回退到静态列表"""
        if self._index:
            try:
                symbols = self._index.get_hk_symbols()
                if symbols:
                    return symbols
            except Exception as e:
                logger.warning("动态获取港股成分股失败，使用 fallback 列表: %s", e)
        return self.config.market.HK_WATCHLIST

    def get_us_stocks(self) -> dict[str, StockData]:
        """获取美股成分股的全部数据"""
        symbols = self._get_us_symbols()
        logger.info("美股分析列表: %d 只股票", len(symbols))
        return self.get_batch_data(symbols)

    def get_hk_stocks(self) -> dict[str, StockData]:
        """获取港股成分股的全部数据"""
        symbols = self._get_hk_symbols()
        logger.info("港股分析列表: %d 只股票", len(symbols))
        return self.get_batch_data(symbols)

    def _get_cn_symbols(self) -> list[str]:
        """获取A股股票列表，动态获取失败时回退到静态列表。
        创业板/科创板会按市值 >= 100 亿人民币进行过滤。"""
        if self._index:
            try:
                csi300 = self._index.get_csi300()
                chinext = self._index.get_chinext()
                star = self._index.get_star()

                # 对创业板和科创板进行市值过滤
                chinext_star = chinext + star
                if chinext_star:
                    chinext_star = self._filter_by_market_cap(
                        chinext_star, self.CN_MIN_MARKET_CAP_CNY, currency_mode="CNY",
                    )

                # 合并去重 (沪深300 不做市值过滤)
                seen: set[str] = set()
                merged: list[str] = []
                for sym in csi300 + chinext_star:
                    if sym not in seen:
                        seen.add(sym)
                        merged.append(sym)

                logger.info(
                    "A股筛选后: %d 只 (沪深300: %d, 创业板+科创板市值>=100亿: %d)",
                    len(merged), len(csi300), len(chinext_star),
                )
                if merged:
                    return merged
            except Exception as e:
                logger.warning("动态获取A股成分股失败，使用 fallback 列表: %s", e)
        return self.config.market.CN_WATCHLIST

    def get_cn_stocks(self) -> dict[str, StockData]:
        """获取A股成分股的全部数据"""
        symbols = self._get_cn_symbols()
        logger.info("A股分析列表: %d 只股票", len(symbols))
        return self.get_batch_data(symbols)

    def get_all_stocks(self) -> dict[str, StockData]:
        """获取所有成分股的数据"""
        us_symbols = self._get_us_symbols()
        hk_symbols = self._get_hk_symbols()
        cn_symbols = self._get_cn_symbols()
        all_symbols = us_symbols + hk_symbols + cn_symbols
        logger.info(
            "全部分析列表: %d 只股票 (美股 %d, 港股 %d, A股 %d)",
            len(all_symbols), len(us_symbols), len(hk_symbols), len(cn_symbols),
        )
        return self.get_batch_data(all_symbols)

    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        logger.info("数据缓存已清空")
