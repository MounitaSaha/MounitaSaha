import io
from contextlib import redirect_stderr, redirect_stdout

import pandas as pd
import yfinance as yf

SECTOR_CACHE = {}


def get_sector(symbol: str):
    if symbol in SECTOR_CACHE:
        return SECTOR_CACHE[symbol]

    ticker = yf.Ticker(symbol)
    sector = None
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            info = ticker.info
        sector = info.get('sector')
        industry = info.get('industry')
        if sector == 'Technology' and industry:
            sector = industry
        elif not sector:
            if symbol.upper() in {'SMH', 'ARKQ'}:
                sector = 'Semiconductor'
            elif symbol.upper() in {'DRAM', 'MU', 'SNDK', 'WDC'}:
                sector = 'Memory'
            else:
                sector = industry or 'Unknown'
    except Exception:
        sector = 'Unknown'

    if not sector:
        sector = 'Unknown'

    SECTOR_CACHE[symbol] = sector
    return sector


def get_price(symbol: str):
    ticker = yf.Ticker(symbol)
    price = None

    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            fast_info = getattr(ticker, 'fast_info', None) or {}
            price = fast_info.get('last_price') or fast_info.get('previous_close')
    except Exception:
        price = None

    if price is None:
        try:
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                info = ticker.info
            price = info.get('regularMarketPrice') or info.get('currentPrice') or info.get('previousClose')
        except Exception:
            price = None

    if price is None:
        try:
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                history = ticker.history(period='2d', interval='1d')
                if not history.empty:
                    price = float(history['Close'].iloc[-1])
        except Exception:
            price = None

    return price


def get_price_info(symbol: str):
    ticker = yf.Ticker(symbol)
    current_price = None
    previous_close = None

    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            fast_info = getattr(ticker, 'fast_info', None) or {}
            current_price = fast_info.get('last_price')
            previous_close = fast_info.get('previous_close')
    except Exception:
        pass

    if previous_close is None or current_price is None:
        try:
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                info = ticker.info
            if current_price is None:
                current_price = info.get('regularMarketPrice') or info.get('currentPrice')
            if previous_close is None:
                previous_close = info.get('previousClose')
        except Exception:
            pass

    if previous_close is None:
        try:
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                history = ticker.history(period='2d', interval='1d')
                if history is not None and not history.empty and len(history) >= 2:
                    previous_close = float(history['Close'].iloc[-2])
                elif history is not None and not history.empty:
                    previous_close = float(history['Close'].iloc[-1])
        except Exception:
            pass

    if current_price is None:
        current_price = previous_close

    return current_price, previous_close


def get_historical_data(symbol: str, period: str):
    ticker = yf.Ticker(symbol)
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            data = ticker.history(period=period, interval='1d')
        return data if data is not None and not data.empty else None
    except Exception:
        return None


def get_recommendations(symbol: str):
    ticker = yf.Ticker(symbol)
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            recs = ticker.recommendations
        if recs is not None and not recs.empty:
            latest = recs.iloc[-1]
            return {
                'Strong Buy': latest.get('strongBuy', 0),
                'Buy': latest.get('buy', 0),
                'Hold': latest.get('hold', 0),
                'Sell': latest.get('sell', 0),
                'Strong Sell': latest.get('strongSell', 0),
            }
        return {}
    except Exception:
        return {}


def get_financial_info(symbol: str):
    ticker = yf.Ticker(symbol)
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            info = ticker.info
        return {
            'EPS (Trailing)': info.get('trailingEps'),
            'EPS (Forward)': info.get('forwardEps'),
            'PE Ratio': info.get('trailingPE'),
            'Forward PE': info.get('forwardPE'),
            'Market Cap': info.get('marketCap'),
            'Dividend Yield': info.get('dividendYield'),
            'Revenue': info.get('totalRevenue'),
            'Net Income': info.get('netIncomeToCommon'),
        }
    except Exception:
        return {}


def get_news(symbol: str):
    ticker = yf.Ticker(symbol)
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            news = ticker.news
        if news:
            return [
                {'title': item.get('title', ''), 'link': item.get('link', '')}
                for item in news[:5]
                if item.get('title') and item.get('link')
            ]
        return []
    except Exception:
        return []
