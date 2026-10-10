"""Publish market quotes from the configured data feed to Redis."""
import asyncio
import json
import math
from datetime import timedelta
from datetime import datetime, timezone

import httpx
import redis.asyncio as aioredis

from config import settings
from services.instruments import INSTRUMENTS
from services.stock_data_service import get_stock_provider

SYMBOL_ALIAS = {"^NSEI": "NIFTY50"}
POLL_INTERVAL = 60
TWELVE_DATA_POLL_INTERVAL = 900
MARKET_SYMBOLS = [*INSTRUMENTS, "^NSEI", "^BSESN"]
INDEX_ALIAS = {"^NSEI": "NIFTY 50", "^BSESN": "SENSEX"}


def quote_poll_interval(provider_name: str) -> int:
    return TWELVE_DATA_POLL_INTERVAL if provider_name.lower() in {"twelve_data", "twelvedata", "twelve-data"} else POLL_INTERVAL


class PricePoller:
    def __init__(self, redis: aioredis.Redis):
        self.redis = redis
        self._running = False
        self.first_snapshot = asyncio.Event()
        self.poll_interval = quote_poll_interval(settings.market_data_provider)

    async def start(self):
        """Refresh the configured market quote cache until shutdown."""
        self._running = True
        print(f"{settings.market_data_provider} quote poller: starting first fetch...")
        while self._running:
            try:
                await self._fetch_and_cache()
            except Exception as error:
                print(f"Demo quote poller error: {error}")
            await asyncio.sleep(self.poll_interval)

    def stop(self):
        self._running = False

    async def _fetch_and_cache(self):
        """Fetch configured quotes without substituting demo values."""
        provider_name = settings.market_data_provider.lower()
        if provider_name == "yahoo":
            provider = get_stock_provider("yahoo")
            results = await asyncio.gather(*(self._get_provider_quote(provider, symbol) for symbol in MARKET_SYMBOLS))
            prices = {symbol: price for symbol, price in results if price is not None}
            source = "yahoo_finance"
        elif provider_name in {"twelve_data", "twelvedata", "twelve-data"}:
            if not settings.twelve_data_api_key:
                raise ValueError("TWELVE_DATA_API_KEY is required when MARKET_DATA_PROVIDER=twelve_data.")
            provider = get_stock_provider("twelve_data", api_key=settings.twelve_data_api_key)
            results = await asyncio.gather(*(self._get_provider_quote(provider, symbol) for symbol in MARKET_SYMBOLS))
            prices = {symbol: price for symbol, price in results if price is not None}
            source = "twelve_data"
        elif provider_name == "demo":
            async with httpx.AsyncClient(timeout=5.0) as http:
                results = await asyncio.gather(*(self._get_demo_quote(http, symbol) for symbol in INSTRUMENTS))
            prices = {symbol: price for symbol, price in results if price is not None}
            source = "fixed_demo_fallback"
        else:
            raise ValueError("MARKET_DATA_PROVIDER must be 'demo', 'yahoo', or 'twelve_data'.")

        if not prices:
            print(f"{settings.market_data_provider} quote feed returned no prices")
            return

        snapshot = {}
        sources = {}
        pipe = self.redis.pipeline()
        for symbol, price in prices.items():
            redis_key = INDEX_ALIAS.get(symbol, SYMBOL_ALIAS.get(symbol, symbol))
            pipe.set(f"price:{redis_key}", str(price), ex=max(180, self.poll_interval + 120))
            snapshot[redis_key] = price
            sources[redis_key] = source
            point = json.dumps({"time": datetime.now(timezone.utc).isoformat(), "price": price})
            history_key = f"market:history:{redis_key}"
            pipe.rpush(history_key, point)
            pipe.ltrim(history_key, -2500, -1)
            pipe.expire(history_key, int(timedelta(days=7).total_seconds()))

        pipe.set(
            "price:snapshot",
            json.dumps({
                "prices": snapshot,
                "sources": sources,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "provider": source,
                "mode": "external_market_data" if source != "fixed_demo_fallback" else "demo",
            }),
            ex=max(180, self.poll_interval + 120),
        )

        await pipe.execute()
        self.first_snapshot.set()
        print(f"{source} quotes updated: {', '.join(f'{symbol}={price}' for symbol, price in snapshot.items())}")

    @staticmethod
    async def _get_provider_quote(provider, symbol: str):
        try:
            quote = await provider.get_quote(symbol)
            price = float(quote.get("ltp") or 0)
            return (symbol, round(price, 2)) if math.isfinite(price) and price > 0 else (symbol, None)
        except Exception as error:
            print(f"Market quote unavailable for {symbol}: {error}")
            return symbol, None

    @staticmethod
    async def _get_demo_quote(http: httpx.AsyncClient, symbol: str):
        try:
            response = await http.get(
                f"{settings.mock_api_url}/quote/{symbol}",
                params={"fallback_only": "true"},
            )
            response.raise_for_status()
            quote = response.json()
            if not isinstance(quote, dict):
                return symbol, None
            price = float(quote.get("ltp") or 0)
            return (symbol, round(price, 2)) if price > 0 else (symbol, None)
        except (httpx.HTTPError, AttributeError, TypeError, ValueError) as error:
            print(f"Demo quote unavailable for {symbol}: {error}")
            return symbol, None
