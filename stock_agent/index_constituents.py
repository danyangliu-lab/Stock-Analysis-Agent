"""
指数成分股动态获取模块
通过 Wikipedia 页面动态获取纳斯达克100、标普500、恒生指数、恒生科技指数、
沪深300、创业板全部上市公司、科创板全部上市公司的成分股列表。
具备文件缓存机制，避免频繁请求。
"""

from __future__ import annotations

import io
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd

logger = logging.getLogger(__name__)

# 本地缓存目录
_CACHE_DIR = Path(__file__).parent / ".cache"
_CACHE_EXPIRY_HOURS = 24  # 缓存过期时间


class IndexConstituents:
    """动态获取主要指数的成分股列表"""

    # Wikipedia 数据源 URL
    _SOURCES = {
        "SP500": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
        "NASDAQ100": "https://en.wikipedia.org/wiki/Nasdaq-100",
        "HSI": "https://en.wikipedia.org/wiki/Hang_Seng_Index",
        "HSTECH": "https://zh.wikipedia.org/wiki/%E6%81%92%E7%94%9F%E7%A7%91%E6%8A%80%E6%8C%87%E6%95%B8",
        "CSI300": "https://en.wikipedia.org/wiki/CSI_300_Index",
        "CHINEXT": "https://zh.wikipedia.org/wiki/%E6%B7%B1%E5%9C%B3%E8%AF%81%E5%88%B8%E4%BA%A4%E6%98%93%E6%89%80%E5%88%9B%E4%B8%9A%E6%9D%BF%E4%B8%8A%E5%B8%82%E5%85%AC%E5%8F%B8%E5%88%97%E8%A1%A8",
        "STAR": "https://zh.wikipedia.org/wiki/%E4%B8%8A%E6%B5%B7%E8%AF%81%E5%88%B8%E4%BA%A4%E6%98%93%E6%89%80%E7%A7%91%E5%88%9B%E6%9D%BF%E4%B8%8A%E5%B8%82%E5%85%AC%E5%8F%B8%E5%88%97%E8%A1%A8",
    }

    def __init__(self, cache_dir: Path | None = None, cache_expiry_hours: int = 24):
        self.cache_dir = cache_dir or _CACHE_DIR
        self.cache_expiry = timedelta(hours=cache_expiry_hours)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # 中概股列表 (市值 > 50 亿美元的中国公司在美上市)
    # ------------------------------------------------------------------
    CHINESE_ADR_SYMBOLS: list[str] = [
        # 互联网 / 电商
        "BABA",     # 阿里巴巴
        "JD",       # 京东
        "PDD",      # 拼多多
        "BIDU",     # 百度
        "NTES",     # 网易
        "BILI",     # 哔哩哔哩
        "TME",      # 腾讯音乐
        "VIPS",     # 唯品会
        "ZTO",      # 中通快递
        "MNSO",     # 名创优品
        "BZUN",     # 宝尊电商
        # 汽车 / 新能源
        "NIO",      # 蔚来
        "XPEV",     # 小鹏汽车
        "LI",       # 理想汽车
        "ZK",       # 零跑汽车
        # 教育 / 消费
        "TAL",      # 好未来
        "EDU",      # 新东方
        "YMM",      # 满帮集团 (运满满)
        "HTHT",     # 华住集团
        "LEGN",     # 传奇生物
        "FUTU",     # 富途控股
        "TIGR",     # 老虎证券
        "FINV",     # 信也科技
        "LX",       # 乐信
        "QFIN",     # 奇富科技 (360 数科)
        # 科技 / AI / 云
        "WB",       # 微博
        "IQ",       # 爱奇艺
        "DADA",     # 达达集团
        "KC",       # 金山云
        "ATHM",     # 汽车之家
        "GDS",      # 万国数据 (数据中心)
        "VNET",     # 世纪互联 (数据中心)
        "BEKE",     # 贝壳
        "TCOM",     # 携程
        "YY",       # 欢聚集团
        "HUYA",     # 虎牙
        "DOYU",     # 斗鱼
        "TUYA",     # 涂鸦智能
        "API",      # 声网
        "KRKR",     # 趣丸科技 (原 36Kr)
    ]

    # ------------------------------------------------------------------
    # AI 概念股列表 (美股 AI 产业链核心标的)
    # ------------------------------------------------------------------
    AI_SECTOR_SYMBOLS: list[str] = [
        # ============ AI 芯片 / 半导体 ============
        "NVDA",     # 英伟达 — GPU / AI 训练芯片绝对龙头
        "AMD",      # AMD — MI300X AI 加速器
        "AVGO",     # 博通 — 定制 AI ASIC / 网络芯片
        "INTC",     # 英特尔 — Gaudi AI 加速器
        "QCOM",     # 高通 — 端侧 AI 芯片
        "MRVL",     # Marvell — 定制 AI 芯片 / DPU
        "ARM",      # ARM — AI 芯片架构授权
        "TSM",      # 台积电 — AI 芯片代工
        "ASML",     # ASML — 光刻机 (AI 芯片制造核心)
        "LRCX",     # 泛林半导体 — 刻蚀设备
        "AMAT",     # 应用材料 — 半导体设备
        "KLAC",     # 科磊 — 检测设备
        "SNPS",     # 新思科技 — EDA 工具
        "CDNS",     # Cadence — EDA 工具
        "CRUS",     # 思佳讯 — 模拟/混合信号芯片
        "MBLY",     # Mobileye — 自动驾驶 AI 芯片
        "CRDO",     # Credo — AI 高速互联芯片
        "MCHP",     # 微芯科技 — MCU/边缘AI

        # ============ AI 存储 / HBM ============
        "MU",       # 美光 — HBM3E 存储
        "WDC",      # 西部数据 — 数据存储
        "STX",      # 希捷 — AI 数据存储

        # ============ AI 网络 / 数据中心基础设施 ============
        "ANET",     # Arista Networks — AI 数据中心交换机
        "CSCO",     # 思科 — 网络基础设施
        "JNPR",     # 瞻博网络 — AI 网络设备
        "VRT",      # Vertiv — 数据中心散热/电力
        "EQIX",     # Equinix — 数据中心 REIT
        "DLR",      # Digital Realty — 数据中心 REIT
        "AME",      # 阿美特克 — 电子仪器
        "ETN",      # 伊顿 — 数据中心电力管理
        "PWR",      # Quanta Services — 数据中心建设
        "DELL",     # 戴尔 — AI 服务器
        "SMCI",     # 超微电脑 — AI 服务器 / 液冷
        "HPE",      # 慧与科技 — AI 服务器

        # ============ 云计算 / AI 平台 ============
        "MSFT",     # 微软 — Azure AI / OpenAI 合作伙伴
        "GOOGL",    # 谷歌 — Gemini / TPU / 云 AI
        "AMZN",     # 亚马逊 — AWS AI / Trainium
        "META",     # Meta — LLaMA 大模型 / AI 广告
        "ORCL",     # 甲骨文 — OCI 云 AI
        "CRM",      # Salesforce — Einstein AI / Agentforce
        "NOW",      # ServiceNow — 企业 AI 自动化
        "SNOW",     # Snowflake — AI 数据云
        "PLTR",     # Palantir — AI 数据分析平台
        "DDOG",     # Datadog — AI 可观测性
        "MDB",      # MongoDB — AI 向量数据库
        "ESTC",     # Elastic — AI 搜索
        "PATH",     # UiPath — AI 自动化 / RPA
        "AI",       # C3.ai — 企业 AI 平台
        "BBAI",     # BigBear.ai — 决策智能

        # ============ AI 应用 / SaaS ============
        "ADBE",     # Adobe — Firefly AI 创意工具
        "PANW",     # Palo Alto — AI 安全
        "CRWD",     # CrowdStrike — AI 安全
        "ZS",       # Zscaler — 零信任安全 + AI
        "FTNT",     # Fortinet — AI 网络安全
        "WDAY",     # Workday — AI 人力资源
        "HUBS",     # HubSpot — AI 营销
        "VEEV",     # Veeva Systems — AI 生命科学
        "DKNG",     # DraftKings — AI 体育博彩
        "SHOP",     # Shopify — AI 电商工具
        "SQ",       # Block (Square) — AI 支付
        "UBER",     # Uber — AI 出行优化
        "ABNB",     # Airbnb — AI 推荐
        "PINS",     # Pinterest — AI 视觉搜索
        "SNAP",     # Snap — AI AR/AI 广告
        "RBLX",     # Roblox — AI 游戏/虚拟世界
        "U",        # Unity — AI 3D 引擎
        "TTD",      # The Trade Desk — AI 程序化广告

        # ============ AI 机器人 / 自动驾驶 ============
        "TSLA",     # 特斯拉 — FSD / 人形机器人 Optimus
        "ISRG",     # 直觉外科 — AI 手术机器人
        "TER",      # 泰瑞达 — 机器人 / 自动化测试
        "RIVN",     # Rivian — AI 自动驾驶
        "JOBY",     # Joby Aviation — eVTOL / AI 飞行
        "IONQ",     # IonQ — 量子计算 (AI 前沿)
        "RGTI",     # Rigetti — 量子计算
        "SOUN",     # SoundHound AI — 语音AI
        "UPST",     # Upstart — AI 贷款
        "DOCS",     # Doximity — AI 医疗
        "RXRX",     # Recursion Pharmaceuticals — AI 制药

        # ============ AI 电力 / 能源 (算力耗电受益) ============
        "VST",      # Vistra — AI 电力需求受益
        "CEG",      # Constellation Energy — 核电 / 数据中心供电
        "NRG",      # NRG Energy — 电力
        "FSLR",     # First Solar — 数据中心绿色能源
    ]

    def get_us_symbols(self) -> list[str]:
        """
        获取美股成分股列表（标普500 + 纳斯达克100 + 中概股 + AI概念股 去重合并）。
        Yahoo Finance 格式，如 "AAPL", "MSFT"。
        """
        sp500 = self._get_with_cache("SP500", self._fetch_sp500)
        nasdaq100 = self._get_with_cache("NASDAQ100", self._fetch_nasdaq100)
        chinese_adr = self.CHINESE_ADR_SYMBOLS
        ai_sector = self.AI_SECTOR_SYMBOLS
        # 合并去重，保持顺序
        seen: set[str] = set()
        merged: list[str] = []
        for sym in sp500 + nasdaq100 + chinese_adr + ai_sector:
            if sym not in seen:
                seen.add(sym)
                merged.append(sym)
        logger.info(
            "美股成分股合计: %d 只 (S&P500: %d, NASDAQ100: %d, 中概股: %d, AI概念: %d)",
            len(merged), len(sp500), len(nasdaq100), len(chinese_adr), len(ai_sector),
        )
        return merged

    def get_chinese_adr(self) -> list[str]:
        """获取中概股列表 (市值>50亿美元的中国公司)"""
        return list(self.CHINESE_ADR_SYMBOLS)

    def get_ai_sector(self) -> list[str]:
        """获取AI概念股列表"""
        return list(self.AI_SECTOR_SYMBOLS)

    def get_hk_symbols(self) -> list[str]:
        """
        获取港股成分股列表（恒生指数 + 恒生科技指数 去重合并）。
        Yahoo Finance 格式，如 "0700.HK", "9988.HK"。
        """
        hsi = self._get_with_cache("HSI", self._fetch_hsi)
        hstech = self._get_with_cache("HSTECH", self._fetch_hstech)
        # 合并去重，保持顺序
        seen: set[str] = set()
        merged: list[str] = []
        for sym in hsi + hstech:
            if sym not in seen:
                seen.add(sym)
                merged.append(sym)
        logger.info("港股成分股合计: %d 只 (恒生指数: %d, 恒生科技: %d)", len(merged), len(hsi), len(hstech))
        return merged

    def get_sp500(self) -> list[str]:
        """获取标普500成分股"""
        return self._get_with_cache("SP500", self._fetch_sp500)

    def get_nasdaq100(self) -> list[str]:
        """获取纳斯达克100成分股"""
        return self._get_with_cache("NASDAQ100", self._fetch_nasdaq100)

    def get_hsi(self) -> list[str]:
        """获取恒生指数成分股"""
        return self._get_with_cache("HSI", self._fetch_hsi)

    def get_hstech(self) -> list[str]:
        """获取恒生科技指数成分股"""
        return self._get_with_cache("HSTECH", self._fetch_hstech)

    def get_cn_symbols(self) -> list[str]:
        """
        获取A股成分股列表（沪深300 + 创业板全部 + 科创板全部 去重合并）。
        Yahoo Finance 格式，如 "600519.SS", "300750.SZ"。
        """
        csi300 = self._get_with_cache("CSI300", self._fetch_csi300)
        chinext = self._get_with_cache("CHINEXT", self._fetch_chinext)
        star = self._get_with_cache("STAR", self._fetch_star)
        # 合并去重，保持顺序
        seen: set[str] = set()
        merged: list[str] = []
        for sym in csi300 + chinext + star:
            if sym not in seen:
                seen.add(sym)
                merged.append(sym)
        logger.info(
            "A股成分股合计: %d 只 (沪深300: %d, 创业板: %d, 科创板: %d)",
            len(merged), len(csi300), len(chinext), len(star),
        )
        return merged

    def get_csi300(self) -> list[str]:
        """获取沪深300成分股"""
        return self._get_with_cache("CSI300", self._fetch_csi300)

    def get_chinext(self) -> list[str]:
        """获取创业板全部上市公司"""
        return self._get_with_cache("CHINEXT", self._fetch_chinext)

    def get_star(self) -> list[str]:
        """获取科创板全部上市公司"""
        return self._get_with_cache("STAR", self._fetch_star)

    # ------------------------------------------------------------------
    # 缓存逻辑
    # ------------------------------------------------------------------

    def _get_with_cache(self, key: str, fetcher: object) -> list[str]:
        """先查本地缓存，过期则重新获取"""
        cache_file = self.cache_dir / f"{key}.json"

        # 检查缓存
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                cached_time = datetime.fromisoformat(data["timestamp"])
                if datetime.now() - cached_time < self.cache_expiry:
                    symbols = data["symbols"]
                    logger.debug("使用缓存 %s: %d 只 (缓存时间: %s)", key, len(symbols), cached_time)
                    return symbols
                logger.debug("缓存 %s 已过期", key)
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning("缓存 %s 读取失败: %s", key, e)

        # 获取数据
        try:
            symbols = fetcher()  # type: ignore[operator]
            if symbols:
                # 写入缓存
                cache_data = {
                    "timestamp": datetime.now().isoformat(),
                    "index": key,
                    "count": len(symbols),
                    "symbols": symbols,
                }
                cache_file.write_text(json.dumps(cache_data, ensure_ascii=False, indent=2), encoding="utf-8")
                logger.info("已缓存 %s: %d 只成分股", key, len(symbols))
            return symbols
        except Exception as e:
            logger.error("获取 %s 成分股失败: %s", key, e)
            return []

    def clear_cache(self):
        """清除所有缓存文件"""
        if self.cache_dir.exists():
            for f in self.cache_dir.glob("*.json"):
                f.unlink()
            logger.info("成分股缓存已清空")

    # ------------------------------------------------------------------
    # 数据抓取实现
    # ------------------------------------------------------------------

    @staticmethod
    def _fetch_html(url: str) -> str:
        """带 User-Agent 的 HTTP 请求，避免被 Wikipedia 403 拒绝"""
        req = Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
        })
        with urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8")

    @staticmethod
    def _read_html_tables(url: str) -> list[pd.DataFrame]:
        """获取 URL 页面中的所有 HTML 表格"""
        html = IndexConstituents._fetch_html(url)
        return pd.read_html(io.StringIO(html))

    @staticmethod
    def _fetch_sp500() -> list[str]:
        """从 Wikipedia 获取标普500成分股"""
        url = IndexConstituents._SOURCES["SP500"]
        logger.info("正在从 Wikipedia 获取 S&P 500 成分股...")

        tables = IndexConstituents._read_html_tables(url)
        # 第一个表格就是成分股列表
        df = tables[0]

        # 列名可能是 "Symbol" 或 "Ticker symbol"
        symbol_col = None
        for col in df.columns:
            if "symbol" in str(col).lower() or "ticker" in str(col).lower():
                symbol_col = col
                break

        if symbol_col is None:
            raise ValueError("无法在 S&P 500 页面中找到股票代码列")

        symbols = df[symbol_col].astype(str).str.strip().tolist()
        # Yahoo Finance 中 BRK.B -> BRK-B, BF.B -> BF-B
        symbols = [s.replace(".", "-") for s in symbols if s and s != "nan"]
        logger.info("获取到 S&P 500 成分股: %d 只", len(symbols))
        return symbols

    @staticmethod
    def _fetch_nasdaq100() -> list[str]:
        """从 Wikipedia 获取纳斯达克100成分股"""
        url = IndexConstituents._SOURCES["NASDAQ100"]
        logger.info("正在从 Wikipedia 获取 NASDAQ 100 成分股...")

        tables = IndexConstituents._read_html_tables(url)
        # 通常第4个表格是成分股（前面有一些小表格）
        # 寻找包含 "Ticker" 或 "Symbol" 列的表格
        df = None
        for table in tables:
            cols_lower = [str(c).lower() for c in table.columns]
            if any("ticker" in c or "symbol" in c for c in cols_lower):
                if len(table) > 50:  # NASDAQ100 应有100行以上
                    df = table
                    break

        if df is None:
            # fallback: 取行数最多的表格
            df = max(tables, key=len)

        # 找到代码列
        symbol_col = None
        for col in df.columns:
            col_str = str(col).lower()
            if "ticker" in col_str or "symbol" in col_str:
                symbol_col = col
                break

        if symbol_col is None:
            # fallback: 取第一列
            symbol_col = df.columns[0]

        symbols = df[symbol_col].astype(str).str.strip().tolist()
        symbols = [s for s in symbols if s and s != "nan" and not s.startswith("^")]
        logger.info("获取到 NASDAQ 100 成分股: %d 只", len(symbols))
        return symbols

    @staticmethod
    def _fetch_hsi() -> list[str]:
        """从 Wikipedia 获取恒生指数成分股"""
        url = IndexConstituents._SOURCES["HSI"]
        logger.info("正在从 Wikipedia 获取恒生指数成分股...")

        tables = IndexConstituents._read_html_tables(url)

        # 恒生指数页面中，寻找包含港股代码的表格
        df = None
        for table in tables:
            cols_lower = [str(c).lower() for c in table.columns]
            # 恒生指数表格通常有 "Ticker" 或 "Stock code" 列
            if any("ticker" in c or "stock code" in c or "code" in c for c in cols_lower):
                if len(table) >= 20:  # 恒生指数约有80只成分股
                    df = table
                    break

        if df is None:
            # fallback: 取行数在20-120之间且列数>2的表格
            for table in tables:
                if 20 <= len(table) <= 120 and len(table.columns) > 2:
                    df = table
                    break

        if df is None:
            raise ValueError("无法在恒生指数页面中找到成分股表格")

        # 找到代码列
        code_col = None
        for col in df.columns:
            col_str = str(col).lower()
            if "ticker" in col_str or "stock code" in col_str or "code" in col_str:
                code_col = col
                break

        if code_col is None:
            # 尝试第一列
            code_col = df.columns[0]

        raw_codes = df[code_col].astype(str).str.strip().tolist()

        # 转为 Yahoo Finance 格式: "0700.HK"
        symbols = []
        for code in raw_codes:
            if not code or code == "nan":
                continue
            # 移除可能的前缀字符，只保留数字
            digits = "".join(c for c in code if c.isdigit())
            if digits:
                # 补零到4位
                yahoo_code = f"{int(digits):04d}.HK"
                symbols.append(yahoo_code)

        logger.info("获取到恒生指数成分股: %d 只", len(symbols))
        return symbols

    @staticmethod
    def _fetch_hstech() -> list[str]:
        """从中文 Wikipedia 获取恒生科技指数成分股"""
        import re

        url = IndexConstituents._SOURCES["HSTECH"]
        logger.info("正在从中文 Wikipedia 获取恒生科技指数成分股...")

        html = IndexConstituents._fetch_html(url)
        tables = pd.read_html(io.StringIO(html))

        # 成分股表格特征：3列，每个单元格包含 "00700 騰訊控股" 格式的文本
        # 对应 Table 1 (shape ~(1, 3))
        symbols: list[str] = []
        for table in tables:
            # 将整个表格的所有单元格文本拼接起来，查找港股代码
            all_text = " ".join(table.astype(str).values.flatten())
            # 匹配 5位数字代码（港股代码格式 00700, 09988 等）
            codes = re.findall(r"\b(\d{5})\b", all_text)
            if len(codes) >= 20:
                # 找到成分股表格
                for code in codes:
                    yahoo_code = f"{int(code):04d}.HK"
                    if yahoo_code not in symbols:
                        symbols.append(yahoo_code)
                break

        if not symbols:
            raise ValueError("无法在恒生科技指数页面中找到成分股数据")

        logger.info("获取到恒生科技指数成分股: %d 只", len(symbols))
        return symbols

    # ------------------------------------------------------------------
    # A 股相关
    # ------------------------------------------------------------------

    @staticmethod
    def _cn_code_to_yahoo(code: str) -> str:
        """将 A 股代码转为 Yahoo Finance 格式 (沪市 .SS, 深市 .SZ)"""
        code = code.strip()
        if code.startswith(("6",)):
            return f"{code}.SS"
        else:
            return f"{code}.SZ"

    @staticmethod
    def _fetch_csi300() -> list[str]:
        """从英文 Wikipedia 获取沪深300成分股"""
        url = IndexConstituents._SOURCES["CSI300"]
        logger.info("正在从 Wikipedia 获取沪深300成分股...")

        tables = IndexConstituents._read_html_tables(url)

        # 找到包含 Ticker 列且行数 >= 200 的表格
        df = None
        for table in tables:
            cols_lower = [str(c).lower() for c in table.columns]
            if any("ticker" in c for c in cols_lower) and len(table) >= 200:
                df = table
                break

        if df is None:
            raise ValueError("无法在 CSI 300 页面中找到成分股表格")

        # Ticker 列格式: "SSE: 600519" 或 "SZSE: 300750"
        ticker_col = None
        for col in df.columns:
            if "ticker" in str(col).lower():
                ticker_col = col
                break

        if ticker_col is None:
            raise ValueError("无法在 CSI 300 表格中找到 Ticker 列")

        symbols: list[str] = []
        for raw in df[ticker_col].astype(str):
            parts = raw.split(":")
            if len(parts) == 2:
                code = parts[1].strip()
                exchange = parts[0].strip().upper()
                if exchange == "SSE":
                    symbols.append(f"{code}.SS")
                elif exchange == "SZSE":
                    symbols.append(f"{code}.SZ")

        logger.info("获取到沪深300成分股: %d 只", len(symbols))
        return symbols

    @staticmethod
    def _is_delisted_or_suspended_table(table: pd.DataFrame) -> bool:
        """判断表格是否为退市/暂缓/终止上市的表格"""
        cols_str = " ".join(str(c) for c in table.columns)
        # 列名中包含 退市日期 / 备注 / 原因 → 非正常上市表
        if any(kw in cols_str for kw in ("退市", "备注", "原因", "终止")):
            return True
        return False

    @staticmethod
    def _fetch_chinext() -> list[str]:
        """从中文 Wikipedia 获取创业板全部上市公司 (排除退市/暂缓)"""
        import re

        url = IndexConstituents._SOURCES["CHINEXT"]
        logger.info("正在从中文 Wikipedia 获取创业板上市公司列表...")

        html = IndexConstituents._fetch_html(url)
        tables = pd.read_html(io.StringIO(html))

        symbols: list[str] = []
        seen: set[str] = set()
        for table in tables:
            cols_str = " ".join(str(c) for c in table.columns)
            if "代码" not in cols_str and "公司代码" not in cols_str:
                continue
            if IndexConstituents._is_delisted_or_suspended_table(table):
                continue

            code_col = None
            for c in table.columns:
                cs = str(c)
                if "公司代码" in cs or ("代码" in cs and "A股" not in cs):
                    code_col = c
                    break
            if code_col is None:
                for c in table.columns:
                    if "代码" in str(c):
                        code_col = c
                        break
            if code_col is None:
                continue

            for val in table[code_col].astype(str):
                val = val.strip()
                if re.match(r"^30[012]\d{3}$", val):
                    yahoo = f"{val}.SZ"
                    if yahoo not in seen:
                        seen.add(yahoo)
                        symbols.append(yahoo)

        if not symbols:
            raise ValueError("无法在创业板上市公司列表页面中找到股票数据")

        logger.info("获取到创业板上市公司: %d 只", len(symbols))
        return symbols

    @staticmethod
    def _fetch_star() -> list[str]:
        """从中文 Wikipedia 获取科创板全部上市公司 (排除退市/暂缓)"""
        import re

        url = IndexConstituents._SOURCES["STAR"]
        logger.info("正在从中文 Wikipedia 获取科创板上市公司列表...")

        html = IndexConstituents._fetch_html(url)
        tables = pd.read_html(io.StringIO(html))

        symbols: list[str] = []
        seen: set[str] = set()
        for table in tables:
            cols_str = " ".join(str(c) for c in table.columns)
            if "代码" not in cols_str and "公司代码" not in cols_str:
                continue
            if IndexConstituents._is_delisted_or_suspended_table(table):
                continue

            code_col = None
            for c in table.columns:
                cs = str(c)
                if "公司代码" in cs or ("代码" in cs and "A股" not in cs):
                    code_col = c
                    break
            if code_col is None:
                for c in table.columns:
                    if "代码" in str(c):
                        code_col = c
                        break
            if code_col is None:
                continue

            for val in table[code_col].astype(str):
                val = val.strip()
                if re.match(r"^68[89]\d{3}$", val):
                    yahoo = f"{val}.SS"
                    if yahoo not in seen:
                        seen.add(yahoo)
                        symbols.append(yahoo)

        if not symbols:
            raise ValueError("无法在科创板上市公司列表页面中找到股票数据")

        logger.info("获取到科创板上市公司: %d 只", len(symbols))
        return symbols
