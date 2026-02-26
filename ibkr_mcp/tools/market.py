from __future__ import annotations

from typing import Any

import yfinance as yf
from ib_async import Stock
from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ibkr_mcp.server import AppContext, mcp

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False)


@mcp.tool(annotations=READ_ONLY)
async def get_quote(
    symbol: str,
    currency: str = "USD",
    exchange: str = "SMART",
    ctx: Context = None,
) -> dict[str, Any]:
    """Get a real-time quote for a stock or ETF.

    Args:
        symbol: Ticker symbol (e.g. "MSFT", "VWCE")
        currency: Currency of the contract (default: USD)
        exchange: Exchange to route to (default: SMART)

    Returns last price, close, bid, and ask.
    """
    app: AppContext = ctx.request_context.lifespan_context
    contract = Stock(symbol, exchange, currency)
    return await app.broker.get_market_price(contract)


@mcp.tool(annotations=READ_ONLY)
async def get_historical_bars(
    symbol: str,
    duration: str = "1 M",
    bar_size: str = "1 day",
    currency: str = "USD",
    exchange: str = "SMART",
    ctx: Context = None,
) -> list[dict[str, Any]]:
    """Get historical OHLCV bars for a stock or ETF.

    Args:
        symbol: Ticker symbol
        duration: Time span (e.g. "1 M", "3 M", "1 Y", "5 D")
        bar_size: Bar size (e.g. "1 day", "1 hour", "5 mins")
        currency: Currency of the contract (default: USD)
        exchange: Exchange to route to (default: SMART)

    Returns a list of bars with date, open, high, low, close, volume.
    """
    app: AppContext = ctx.request_context.lifespan_context
    contract = Stock(symbol, exchange, currency)
    return await app.broker.get_historical_bars(contract, duration, bar_size)


@mcp.tool(annotations=READ_ONLY)
async def get_quote_yahoo(
    symbol: str,
    period: str = "5d",
) -> dict[str, Any]:
    """Get a quote for any stock or ETF using Yahoo Finance — no IBKR market data subscription needed.

    Use this when IBKR doesn't have market data for a symbol (e.g. European ETFs like VWCE.DE).
    For Yahoo Finance, European tickers need a suffix: VWCE.DE (Xetra), AGGG.L (London), etc.

    Args:
        symbol: Yahoo Finance ticker (e.g. "MSFT", "VWCE.DE", "AGGG.L", "EURUSD=X")
        period: History period for context (e.g. "5d", "1mo", "3mo", "1y")

    Returns current price, change, volume, 52-week range, and recent history.
    """
    ticker = yf.Ticker(symbol)
    info = ticker.info or {}
    hist = ticker.history(period=period)

    result: dict[str, Any] = {
        "symbol": symbol,
        "name": info.get("shortName") or info.get("longName", ""),
        "currency": info.get("currency", ""),
        "price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "previous_close": info.get("previousClose"),
        "open": info.get("open") or info.get("regularMarketOpen"),
        "day_high": info.get("dayHigh") or info.get("regularMarketDayHigh"),
        "day_low": info.get("dayLow") or info.get("regularMarketDayLow"),
        "volume": info.get("volume") or info.get("regularMarketVolume"),
        "market_cap": info.get("marketCap"),
        "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
        "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
    }

    if not hist.empty:
        recent = []
        for date, row in hist.tail(5).iterrows():
            recent.append({
                "date": str(date.date()),
                "close": round(row["Close"], 4),
                "volume": int(row["Volume"]),
            })
        result["recent_history"] = recent

    return result


@mcp.tool(annotations=READ_ONLY)
async def get_fx_rate(
    pair: str = "EURUSD",
) -> dict[str, Any]:
    """Get a forex exchange rate using Yahoo Finance.

    Args:
        pair: Currency pair (e.g. "EURUSD", "GBPUSD", "USDJPY")

    Returns the current exchange rate and recent history.
    """
    symbol = f"{pair}=X"
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="5d")

    result: dict[str, Any] = {
        "pair": pair,
        "symbol": symbol,
    }

    if not hist.empty:
        latest = hist.iloc[-1]
        result["rate"] = round(latest["Close"], 6)
        result["date"] = str(hist.index[-1].date())
        recent = []
        for date, row in hist.iterrows():
            recent.append({
                "date": str(date.date()),
                "close": round(row["Close"], 6),
            })
        result["recent_history"] = recent

    return result


@mcp.tool(annotations=READ_ONLY)
async def search_contracts(pattern: str, ctx: Context = None) -> list[dict[str, Any]]:
    """Search for IBKR contracts by symbol or name.

    Args:
        pattern: Search string (e.g. "VWCE", "Vanguard", "MSFT")

    Returns matching contracts with conId, symbol, type, exchange, and currency.
    Use the conId to reference specific contracts in other operations.
    """
    app: AppContext = ctx.request_context.lifespan_context
    matches = await app.broker.search_contracts(pattern)
    return [m.to_dict() for m in matches]
