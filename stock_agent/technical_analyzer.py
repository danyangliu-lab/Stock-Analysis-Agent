"""
技术指标分析模块
计算 MA、RSI、MACD、布林带、成交量趋势等技术指标，
并基于指标状态给出 0-100 的技术面评分。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import AgentConfig
from .data_provider import StockData

logger = logging.getLogger(__name__)


@dataclass
class TechnicalResult:
    """技术分析结果"""
    symbol: str
    score: float = 0.0                              # 综合技术评分 0-100
    sub_scores: dict[str, float] = field(default_factory=dict)  # 各指标子评分
    signals: list[str] = field(default_factory=list)            # 信号描述
    indicators: dict[str, float] = field(default_factory=dict)  # 计算出的指标值
    error: str | None = None


class TechnicalAnalyzer:
    """技术指标分析器"""

    def __init__(self, config: AgentConfig):
        self.config = config

    def analyze(self, stock: StockData) -> TechnicalResult:
        """
        对单只股票进行技术面分析。
        根据 stock.market 自动使用对应市场的技术面权重。

        Args:
            stock: StockData 对象 (需含有效的 history DataFrame)

        Returns:
            TechnicalResult
        """
        result = TechnicalResult(symbol=stock.symbol)

        if not stock.is_valid:
            result.error = stock.error or "数据无效，无法进行技术分析"
            return result

        df = stock.history.copy()

        if len(df) < 30:
            result.error = f"历史数据不足 ({len(df)} 条)，至少需要 30 条"
            return result

        try:
            # 计算各技术指标并评分
            ma_score, ma_signals, ma_vals = self._score_ma_trend(df)
            rsi_score, rsi_signals, rsi_vals = self._score_rsi(df)
            macd_score, macd_signals, macd_vals = self._score_macd(df)
            boll_score, boll_signals, boll_vals = self._score_bollinger(df)
            vol_score, vol_signals, vol_vals = self._score_volume_trend(df)

            result.sub_scores = {
                "ma_trend": ma_score,
                "rsi": rsi_score,
                "macd": macd_score,
                "bollinger": boll_score,
                "volume_trend": vol_score,
            }

            result.signals = ma_signals + rsi_signals + macd_signals + boll_signals + vol_signals

            result.indicators.update(ma_vals)
            result.indicators.update(rsi_vals)
            result.indicators.update(macd_vals)
            result.indicators.update(boll_vals)
            result.indicators.update(vol_vals)

            # 使用市场专属的技术面权重
            tech_weights = self.config.weights.get_profile(stock.market).technical
            total = 0.0
            for key, weight in tech_weights.items():
                total += result.sub_scores.get(key, 50.0) * weight
            result.score = round(total, 2)

        except Exception as e:
            logger.error("技术分析异常 %s: %s", stock.symbol, str(e))
            result.error = f"技术分析异常: {str(e)}"

        return result

    # ==================== 均线趋势 ====================

    def _score_ma_trend(self, df: pd.DataFrame):
        close = df["Close"]
        ma5 = close.rolling(5).mean()
        ma20 = close.rolling(20).mean()
        ma60 = close.rolling(60).mean() if len(close) >= 60 else close.rolling(20).mean()

        signals = []
        score = 50.0
        latest_close = close.iloc[-1]
        latest_ma5 = ma5.iloc[-1]
        latest_ma20 = ma20.iloc[-1]
        latest_ma60 = ma60.iloc[-1]

        # 价格在均线上方加分
        if latest_close > latest_ma5:
            score += 10
        else:
            score -= 10

        if latest_close > latest_ma20:
            score += 10
            signals.append("价格站上MA20，中期趋势向好")
        else:
            score -= 10

        if latest_close > latest_ma60:
            score += 10
            signals.append("价格站上MA60，长期趋势向好")
        else:
            score -= 10

        # 金叉/死叉判断
        if len(ma5) >= 2 and len(ma20) >= 2:
            prev_diff = ma5.iloc[-2] - ma20.iloc[-2]
            curr_diff = ma5.iloc[-1] - ma20.iloc[-1]
            if prev_diff < 0 and curr_diff > 0:
                score += 15
                signals.append("MA5上穿MA20，出现金叉信号")
            elif prev_diff > 0 and curr_diff < 0:
                score -= 15
                signals.append("MA5下穿MA20，出现死叉信号")

        score = max(0, min(100, score))
        vals = {"ma5": round(latest_ma5, 2), "ma20": round(latest_ma20, 2), "ma60": round(latest_ma60, 2)}
        return score, signals, vals

    # ==================== RSI ====================

    def _score_rsi(self, df: pd.DataFrame, period: int = 14):
        close = df["Close"]
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)

        avg_gain = gain.rolling(window=period, min_periods=period).mean()
        avg_loss = loss.rolling(window=period, min_periods=period).mean()

        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        latest_rsi = rsi.iloc[-1]

        signals = []
        oversold = self.config.thresholds.rsi_oversold
        overbought = self.config.thresholds.rsi_overbought

        if np.isnan(latest_rsi):
            return 50.0, ["RSI 数据不足"], {"rsi_14": None}

        if latest_rsi < oversold:
            score = 80.0  # 超卖 → 买入机会
            signals.append(f"RSI={latest_rsi:.1f} 处于超卖区间，可能存在反弹机会")
        elif latest_rsi > overbought:
            score = 20.0  # 超买 → 风险
            signals.append(f"RSI={latest_rsi:.1f} 处于超买区间，注意回调风险")
        elif 40 <= latest_rsi <= 60:
            score = 55.0
            signals.append(f"RSI={latest_rsi:.1f} 处于中性区间")
        elif latest_rsi < 40:
            score = 65.0
            signals.append(f"RSI={latest_rsi:.1f} 偏低，有一定上涨空间")
        else:
            score = 40.0
            signals.append(f"RSI={latest_rsi:.1f} 偏高，动能偏强但需警惕")

        vals = {"rsi_14": round(latest_rsi, 2)}
        return score, signals, vals

    # ==================== MACD ====================

    def _score_macd(self, df: pd.DataFrame):
        close = df["Close"]
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        dif = ema12 - ema26
        dea = dif.ewm(span=9, adjust=False).mean()
        macd_hist = (dif - dea) * 2

        latest_dif = dif.iloc[-1]
        latest_dea = dea.iloc[-1]
        latest_hist = macd_hist.iloc[-1]

        signals = []
        score = 50.0

        # DIF 与 DEA 的关系
        if latest_dif > latest_dea:
            score += 15
            signals.append("MACD: DIF > DEA，多头排列")
        else:
            score -= 15
            signals.append("MACD: DIF < DEA，空头排列")

        # 柱状图方向
        if len(macd_hist) >= 2:
            if latest_hist > 0 and macd_hist.iloc[-2] < 0:
                score += 15
                signals.append("MACD柱状图由负转正，买入信号")
            elif latest_hist < 0 and macd_hist.iloc[-2] > 0:
                score -= 15
                signals.append("MACD柱状图由正转负，卖出信号")
            elif latest_hist > macd_hist.iloc[-2]:
                score += 5
            else:
                score -= 5

        # 零轴以上更强势
        if latest_dif > 0 and latest_dea > 0:
            score += 10

        score = max(0, min(100, score))
        vals = {
            "macd_dif": round(latest_dif, 4),
            "macd_dea": round(latest_dea, 4),
            "macd_hist": round(latest_hist, 4),
        }
        return score, signals, vals

    # ==================== 布林带 ====================

    def _score_bollinger(self, df: pd.DataFrame, period: int = 20, num_std: float = 2.0):
        close = df["Close"]
        mid = close.rolling(period).mean()
        std = close.rolling(period).std()
        upper = mid + num_std * std
        lower = mid - num_std * std

        latest_close = close.iloc[-1]
        latest_upper = upper.iloc[-1]
        latest_lower = lower.iloc[-1]
        latest_mid = mid.iloc[-1]

        signals = []
        band_width = latest_upper - latest_lower
        if band_width == 0:
            return 50.0, ["布林带宽度为零"], {"boll_upper": None, "boll_mid": None, "boll_lower": None}

        # 价格在布林带中的位置 (0=下轨, 1=上轨)
        position = (latest_close - latest_lower) / band_width

        if position < 0.1:
            score = 75.0
            signals.append("价格接近布林带下轨，可能存在反弹机会")
        elif position > 0.9:
            score = 25.0
            signals.append("价格接近布林带上轨，注意回调风险")
        elif 0.4 <= position <= 0.6:
            score = 55.0
            signals.append("价格处于布林带中轨附近，走势中性")
        elif position < 0.4:
            score = 60.0
            signals.append("价格偏向布林带下方，有一定反弹空间")
        else:
            score = 45.0
            signals.append("价格偏向布林带上方")

        vals = {
            "boll_upper": round(latest_upper, 2),
            "boll_mid": round(latest_mid, 2),
            "boll_lower": round(latest_lower, 2),
            "boll_position": round(position, 4),
        }
        return score, signals, vals

    # ==================== 成交量趋势 ====================

    def _score_volume_trend(self, df: pd.DataFrame):
        if "Volume" not in df.columns:
            return 50.0, ["无成交量数据"], {}

        volume = df["Volume"]
        vol_ma5 = volume.rolling(5).mean()
        vol_ma20 = volume.rolling(20).mean()

        latest_vol = volume.iloc[-1]
        latest_vol_ma5 = vol_ma5.iloc[-1]
        latest_vol_ma20 = vol_ma20.iloc[-1]

        close = df["Close"]
        price_change = (close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] if len(close) >= 2 else 0

        signals = []
        score = 50.0

        # 放量上涨 = 积极信号
        if latest_vol > latest_vol_ma20 * 1.5 and price_change > 0:
            score += 20
            signals.append("放量上涨，买盘力量增强")
        elif latest_vol > latest_vol_ma20 * 1.5 and price_change < 0:
            score -= 15
            signals.append("放量下跌，卖盘压力较大")
        elif latest_vol < latest_vol_ma20 * 0.5:
            score -= 5
            signals.append("成交量显著萎缩，市场关注度降低")

        # 量价配合
        if latest_vol_ma5 > latest_vol_ma20:
            score += 5
            signals.append("短期成交量活跃度上升")

        score = max(0, min(100, score))
        vals = {
            "volume_latest": int(latest_vol),
            "volume_ma5": int(latest_vol_ma5) if not np.isnan(latest_vol_ma5) else None,
            "volume_ma20": int(latest_vol_ma20) if not np.isnan(latest_vol_ma20) else None,
        }
        return score, signals, vals
