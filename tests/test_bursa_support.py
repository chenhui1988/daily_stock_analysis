# -*- coding: utf-8 -*-
"""Regression tests for Bursa Malaysia (.KL) first-phase support."""

from __future__ import annotations

import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd

if "litellm" not in sys.modules:
    sys.modules["litellm"] = MagicMock()

from bot.commands.analyze import AnalyzeCommand
from bot.commands.ask import AskCommand
from data_provider.base import DataFetcherManager, normalize_stock_code
from data_provider.yfinance_fetcher import YfinanceFetcher
from src.agent.orchestrator import _extract_stock_code
from src.services.image_stock_extractor import _parse_codes_from_text
from src.services.portfolio_service import PortfolioService
from src.services.stock_code_utils import is_code_like, normalize_code


def _sample_daily_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": "2026-03-17",
                "open": 1.0,
                "high": 1.1,
                "low": 0.9,
                "close": 1.05,
                "volume": 1000,
                "amount": 1050,
                "pct_chg": 0.0,
            }
        ]
    )


class _DummyFetcher:
    def __init__(self, name: str, priority: int, *, daily_result=None, quote_result=None):
        self.name = name
        self.priority = priority
        self.daily_result = daily_result
        self.quote_result = quote_result
        self.daily_calls = []
        self.quote_calls = []

    def get_daily_data(self, *args, **kwargs):
        self.daily_calls.append((args, kwargs))
        return self.daily_result

    def get_realtime_quote(self, *args, **kwargs):
        self.quote_calls.append((args, kwargs))
        return self.quote_result


class TestBursaCodeSupport(unittest.TestCase):
    def test_stock_code_utils_accept_kl(self):
        self.assertTrue(is_code_like("5183.KL"))
        self.assertEqual(normalize_code("5183.kl"), "5183.KL")

    def test_data_provider_normalize_preserves_kl(self):
        self.assertEqual(normalize_stock_code("5183.kl"), "5183.KL")

    def test_yfinance_symbol_passthrough_for_kl(self):
        fetcher = YfinanceFetcher()
        self.assertEqual(fetcher._convert_stock_code("5183.KL"), "5183.KL")

    def test_bot_commands_accept_kl(self):
        self.assertIsNone(AnalyzeCommand().validate_args(["5183.KL"]))
        self.assertIsNone(AskCommand().validate_args(["5183.KL"]))

    def test_text_extractors_accept_kl(self):
        self.assertEqual(_extract_stock_code("请分析 5183.KL"), "5183.KL")
        codes = _parse_codes_from_text("关注 5183.KL 和 AAPL")
        self.assertIn("5183.KL", codes)
        self.assertIn("AAPL", codes)

    def test_portfolio_market_defaults_cover_my(self):
        self.assertEqual(PortfolioService._normalize_market("MY"), "my")
        self.assertEqual(PortfolioService._default_currency_for_market("my"), "MYR")


class TestBursaRouting(unittest.TestCase):
    def test_manager_routes_bursa_daily_only_to_yfinance(self):
        cn_first = _DummyFetcher("EfinanceFetcher", 0, daily_result=_sample_daily_frame())
        yfinance = _DummyFetcher("YfinanceFetcher", 1, daily_result=_sample_daily_frame())

        manager = DataFetcherManager(fetchers=[cn_first, yfinance])
        df, source = manager.get_daily_data("5183.KL", days=5)

        self.assertEqual(source, "YfinanceFetcher")
        self.assertFalse(df.empty)
        self.assertEqual(cn_first.daily_calls, [])
        self.assertEqual(
            yfinance.daily_calls,
            [((), {"stock_code": "5183.KL", "start_date": None, "end_date": None, "days": 5})],
        )

    @patch("src.config.get_config")
    def test_manager_routes_bursa_realtime_only_to_yfinance(self, mock_get_config):
        mock_get_config.return_value = SimpleNamespace(
            enable_realtime_quote=True,
            realtime_source_priority="tencent,akshare_sina,efinance,akshare_em,tushare",
        )

        cn_first = _DummyFetcher("EfinanceFetcher", 0, quote_result={"should": "not be called"})
        yfinance = _DummyFetcher("YfinanceFetcher", 1, quote_result={"ok": True})

        manager = DataFetcherManager(fetchers=[cn_first, yfinance])
        quote = manager.get_realtime_quote("5183.kl")

        self.assertEqual(quote, {"ok": True})
        self.assertEqual(cn_first.quote_calls, [])
        self.assertEqual(yfinance.quote_calls, [(("5183.KL",), {})])


if __name__ == "__main__":
    unittest.main()
