"""
推荐输出模块
将策略引擎的评估结果格式化输出为推荐报告，
支持终端表格输出和结构化 JSON 输出。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from .strategy_engine import StockEvaluation

logger = logging.getLogger(__name__)


class RecommendationReporter:
    """推荐报告生成器"""

    LEVEL_ICONS = {
        "强烈推荐": "★★★",
        "推荐": "★★☆",
        "观望": "★☆☆",
        "不推荐": "☆☆☆",
    }

    def print_report(
        self,
        recommendations: list[StockEvaluation],
        all_evaluations: list[StockEvaluation],
        title: str = "智能股票推荐报告",
    ) -> str:
        """
        生成并打印格式化的推荐报告。

        Returns:
            报告文本
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = []

        lines.append("")
        lines.append("=" * 90)
        lines.append(f"  {title}")
        lines.append(f"  生成时间: {now}")
        lines.append("=" * 90)

        # 推荐列表
        lines.append("")
        lines.append(f"  推荐股票 ({len(recommendations)} 只)")
        lines.append("-" * 90)

        if not recommendations:
            lines.append("  当前无符合条件的推荐股票。")
        else:
            lines.append(
                f"  {'排名':<5}{'代码':<12}{'公司':<18}{'市场':<5}"
                f"{'综合分':<8}{'技术分':<8}{'基本面':<8}{'成长':<10}{'推荐'}"
            )
            lines.append("-" * 90)

            for rank, ev in enumerate(recommendations, 1):
                name = ev.company_name[:16] if ev.company_name else ev.symbol
                icon = self.LEVEL_ICONS.get(ev.recommendation, "")
                growth = ev.growth_label if ev.growth_label else "-"
                lines.append(
                    f"  {rank:<5}{ev.symbol:<12}{name:<18}{ev.market:<5}"
                    f"{ev.total_score:<8.1f}{ev.technical_score:<8.1f}"
                    f"{ev.fundamental_score:<8.1f}{growth:<10}{ev.recommendation} {icon}"
                )

        # 详细推荐理由
        lines.append("")
        lines.append("=" * 90)
        lines.append("  推荐理由详情")
        lines.append("=" * 90)

        for rank, ev in enumerate(recommendations, 1):
            lines.append("")
            lines.append(f"  [{rank}] {ev.symbol} - {ev.company_name}")
            lines.append(f"      综合评分: {ev.total_score:.1f}  |  "
                         f"推荐等级: {ev.recommendation}  |  "
                         f"成长标签: {ev.growth_label or '-'}")
            if ev.growth_bonus != 0:
                lines.append(f"      成长性加分: {ev.growth_bonus:+.1f}")
            if ev.reasons:
                for reason in ev.reasons:
                    lines.append(f"      · {reason}")

            # 关键指标摘要
            if ev.fundamental and ev.fundamental.metrics:
                m = ev.fundamental.metrics
                parts = []
                if m.get("pe_ratio") is not None:
                    parts.append(f"PE={m['pe_ratio']:.1f}")
                if m.get("roe") is not None:
                    parts.append(f"ROE={m['roe'] * 100:.1f}%")
                if m.get("revenue_growth") is not None:
                    parts.append(f"营收增速={m['revenue_growth'] * 100:.1f}%")
                if m.get("earnings_growth") is not None:
                    parts.append(f"盈利增速={m['earnings_growth'] * 100:.1f}%")
                if m.get("peg_ratio") is not None:
                    parts.append(f"PEG={m['peg_ratio']:.2f}")
                if parts:
                    lines.append(f"      指标: {' | '.join(parts)}")
            lines.append("")

        # 全市场概览
        lines.append("=" * 90)
        lines.append("  全市场概览")
        lines.append("-" * 90)

        for mkt, label in [("US", "美股"), ("HK", "港股"), ("CN", "A股")]:
            evals = [e for e in all_evaluations if e.market == mkt]
            if evals:
                avg = sum(e.total_score for e in evals) / len(evals)
                # 统计成长标签分布
                growth_counts: dict[str, int] = {}
                for e in evals:
                    gl = e.growth_label or "未知"
                    growth_counts[gl] = growth_counts.get(gl, 0) + 1
                top_labels = sorted(growth_counts.items(), key=lambda x: -x[1])[:3]
                label_str = ", ".join(f"{k}({v})" for k, v in top_labels)
                lines.append(
                    f"  {label}: {len(evals)} 只已分析, 平均分 {avg:.1f}, "
                    f"成长分布: {label_str}"
                )

        lines.append(f"  总计: {len(all_evaluations)} 只已分析, "
                     f"推荐 {len(recommendations)} 只")
        lines.append("=" * 90)

        # 免责声明
        lines.append("")
        lines.append("  免责声明: 本报告仅供参考，不构成任何投资建议。")
        lines.append("    投资有风险，入市需谨慎。过往表现不预示未来收益。")
        lines.append("")

        report = "\n".join(lines)
        print(report)
        return report

    def to_json(
        self,
        recommendations: list[StockEvaluation],
        all_evaluations: list[StockEvaluation],
    ) -> str:
        """将推荐结果输出为 JSON 格式"""
        data = {
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_analyzed": len(all_evaluations),
                "total_recommended": len(recommendations),
            },
            "recommendations": [self._eval_to_dict(ev) for ev in recommendations],
            "all_evaluations": [self._eval_to_dict(ev) for ev in all_evaluations],
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    def to_dict_list(self, evaluations: list[StockEvaluation]) -> list[dict[str, Any]]:
        """转为字典列表"""
        return [self._eval_to_dict(ev) for ev in evaluations]

    @staticmethod
    def _eval_to_dict(ev: StockEvaluation) -> dict[str, Any]:
        result = {
            "symbol": ev.symbol,
            "company_name": ev.company_name,
            "market": ev.market,
            "sector": ev.sector,
            "total_score": ev.total_score,
            "technical_score": ev.technical_score,
            "fundamental_score": ev.fundamental_score,
            "growth_label": ev.growth_label,
            "growth_bonus": ev.growth_bonus,
            "recommendation": ev.recommendation,
            "reasons": ev.reasons,
        }

        if ev.fundamental and ev.fundamental.metrics:
            result["metrics"] = {
                k: v for k, v in ev.fundamental.metrics.items()
                if k not in ("company_name", "sector", "industry")
            }

        if ev.fundamental and ev.fundamental.growth:
            g = ev.fundamental.growth
            result["growth_profile"] = {
                "revenue_growth": g.revenue_growth,
                "earnings_growth": g.earnings_growth,
                "peg_ratio": g.peg_ratio,
                "label": g.growth_label,
                "bonus": g.growth_bonus,
            }

        if ev.technical and ev.technical.indicators:
            result["technical_indicators"] = ev.technical.indicators

        return result
