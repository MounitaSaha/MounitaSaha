import csv
import io
import json
import logging
import os
import webbrowser
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.io as pio
import yfinance as yf

logging.getLogger('yfinance').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = BASE_DIR / 'dashboard.html'

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
            if symbol.upper() in {'SMH', 'DRAM', 'ARKQ'}:
                sector = 'Technology'
            else:
                sector = industry or 'Unknown'
    except Exception:
        sector = 'Unknown'

    if not sector:
        sector = 'Unknown'

    SECTOR_CACHE[symbol] = sector
    return sector

SMALL_HOLDINGS_FILE = BASE_DIR / 'myfile.csv'


def parse_numeric_value(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    raw = str(value).strip()
    if not raw:
        return None

    raw = raw.replace('$', '').replace(',', '').strip()
    if raw.startswith('(') and raw.endswith(')'):
        raw = f'-{raw[1:-1]}'

    try:
        return float(raw)
    except ValueError:
        return None


def load_small_holdings(csv_path: Path):
    if not csv_path.exists():
        raise FileNotFoundError(f"Holdings file not found: {csv_path}")

    with csv_path.open('r', encoding='utf-8', errors='replace', newline='') as csv_file:
        reader = csv.reader(csv_file, delimiter=',', quotechar='"', skipinitialspace=True)
        try:
            header = next(reader)
        except StopIteration:
            return {}, {}, []

        required_columns = {'Stock', 'Quantity', 'Price'}
        normalized_header = [col.strip() for col in header]
        if not required_columns.issubset(normalized_header):
            raise ValueError(f"{csv_path.name} must contain columns: {', '.join(sorted(required_columns))}")

        idx = {name: normalized_header.index(name) for name in required_columns}
        shares = {}
        values = {}
        symbols = []
        for row in reader:
            if len(row) < len(normalized_header):
                continue

            symbol = str(row[idx['Stock']]).strip()
            if not symbol:
                continue

            quantity = parse_numeric_value(row[idx['Quantity']])
            price = parse_numeric_value(row[idx['Price']])
            if quantity is None or price is None:
                continue

            shares[symbol] = quantity
            values[symbol] = price
            symbols.append(symbol)

    return shares, values, symbols


SHARE_ALLOCATION, TRANSACTION_VALUES, SYMBOLS = load_small_holdings(SMALL_HOLDINGS_FILE)

TIME_FRAMES = [
    ('1d', '1 Day'),
    ('5d', '1 Week'),
    ('1mo', '1 Month'),
    ('3mo', '3 Months'),
    ('1y', '1 Year'),
    ('5y', '5 Years'),
    ('max', 'All'),
]


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


def format_currency(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 'N/A'
    return f'${value:,.2f}'


def format_number(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 'N/A'
    return f'{value:,.0f}'


def build_stock_dataframe():
    rows = []
    for symbol in SYMBOLS:
        shares = round(float(SHARE_ALLOCATION.get(symbol, 0.0)), 2)
        invested_value = round(float(TRANSACTION_VALUES.get(symbol, 0.0)), 2)
        current_price = get_price(symbol)
        current_value = round(shares * current_price, 2) if current_price is not None else 0.0
        rows.append({
            'Stock': symbol,
            'Sector': get_sector(symbol),
            'Shares': shares,
            'Price': current_price,
            'Invested Value': invested_value,
            'Current Value': current_value,
        })

    df = pd.DataFrame(rows)
    df['Invested Value'] = df['Invested Value'].fillna(0.0)
    df['Current Value'] = df['Current Value'].fillna(0.0)
    sector_totals = df.groupby('Sector')['Invested Value'].sum().to_dict()
    overall_total = float(df['Invested Value'].sum())
    sector_sum = df.groupby('Sector')['Invested Value'].transform('sum')
    df['Sector %'] = ((df['Invested Value'] / sector_sum) * 100).round(1).fillna(0.0)
    df['Overall %'] = ((df['Invested Value'] / overall_total) * 100).round(1).fillna(0.0)
    df['Price'] = df['Price'].apply(lambda x: x if x is not None else float('nan'))
    return df, sector_totals, overall_total


def build_plot_html(fig):
    return pio.to_html(fig, include_plotlyjs=False, full_html=False, config={'displayModeBar': True})


def build_dashboard(df: pd.DataFrame, sector_totals: dict, overall_total: float):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    title = 'Stock Portfolio Visualizer'
    subtitle = 'Interactive HTML dashboard for monitoring sector allocation, real-time prices, and stock-level trends.'

    total_current_value = float(df['Current Value'].sum())
    # Overall portfolio % gain
    if overall_total:
        total_gain_pct = (total_current_value - overall_total) / overall_total * 100
    else:
        total_gain_pct = 0.0
    summary_cards = [
        ('Total Investment', format_currency(overall_total)),
        ('Total Current Value', format_currency(total_current_value)),
        ('Total % Gain', f'{total_gain_pct:+.2f}%'),
        ('Sectors', len(sector_totals)),
        ('Tracked Stocks', len(df)),
        ('Generated', now),
    ]

    overview_fig = px.pie(
        names=list(sector_totals.keys()),
        values=list(sector_totals.values()),
        title='Overall Investment Allocation by Sector',
        hole=0.4,
        color_discrete_sequence=px.colors.qualitative.Plotly,
    )
    overview_fig.update_traces(textposition='inside', textinfo='percent+label')

    sector_fig = px.bar(
        df[df['Invested Value'] > 0],
        x='Sector',
        y='Invested Value',
        color='Stock',
        title='Sector-wise Investment Breakdown',
        labels={'Invested Value': 'Investment Value ($)'},
        color_discrete_sequence=px.colors.qualitative.Safe,
    )
    sector_fig.update_layout(barmode='stack', uniformtext_minsize=9, uniformtext_mode='hide')
    sector_fig.update_traces(hovertemplate='<b>%{fullData.name}</b><br>Sector: %{x}<br>Value: $%{y:,.2f}<extra></extra>')

    table_html = df.sort_values(['Sector', 'Stock']).copy()
    table_html['Price'] = table_html['Price'].apply(lambda v: format_currency(v) if not pd.isna(v) else 'N/A')
    table_html['Invested Value'] = table_html['Invested Value'].apply(format_currency)
    table_html['Current Value'] = table_html['Current Value'].apply(format_currency)
    table_html['Sector %'] = table_html['Sector %'].map(lambda v: f'{v:.1f}%')
    table_html['Overall %'] = table_html['Overall %'].map(lambda v: f'{v:.1f}%')
    table_html = table_html.to_html(index=False, classes='dataframe', border=0, justify='center')

    # Top 10 gainers table (by percentage gain)
    gain_df = df.copy()
    gain_df['Gain Numeric'] = ((gain_df['Current Value'] - gain_df['Invested Value']) / gain_df['Invested Value'] * 100).where(gain_df['Invested Value'] != 0, pd.NA)
    top_gainers = gain_df[gain_df['Invested Value'] > 0].sort_values(by='Gain Numeric', ascending=False).head(10).copy()
    if not top_gainers.empty:
        top_gainers['Price'] = top_gainers['Price'].apply(lambda v: format_currency(v) if not pd.isna(v) else 'N/A')
        top_gainers['Shares'] = top_gainers['Shares'].map(lambda v: f'{v:,.2f}')
        top_gainers['Invested Value'] = top_gainers['Invested Value'].apply(format_currency)
        top_gainers['Current Value'] = top_gainers['Current Value'].apply(format_currency)
        top_gainers['Gain %'] = top_gainers['Gain Numeric'].map(lambda v: f'{v:+.2f}%' if pd.notna(v) else 'N/A')
        top_gainers.rename(columns={'Current Value': 'Current Total Value'}, inplace=True)
        top_gainers_table_html = top_gainers[['Stock', 'Price', 'Shares', 'Invested Value', 'Current Total Value', 'Gain %']].to_html(index=False, classes='dataframe', border=0, justify='center')
    else:
        top_gainers_table_html = '<div class="empty-state">No gainers to display.</div>'

    stock_summary_df = df.copy()
    # Compute Gain % before formatting values (handle zero invested values) and sort by gain descending by default
    gain = (stock_summary_df['Current Value'] - stock_summary_df['Invested Value']) / stock_summary_df['Invested Value'] * 100
    stock_summary_df['Gain %'] = gain.where(stock_summary_df['Invested Value'] != 0, pd.NA)
    stock_summary_df.sort_values(by='Gain %', ascending=False, inplace=True)

    stock_summary_df['Price'] = stock_summary_df['Price'].apply(lambda v: format_currency(v) if not pd.isna(v) else 'N/A')
    stock_summary_df['Shares'] = stock_summary_df['Shares'].map(lambda v: f'{v:,.2f}')
    stock_summary_df['Invested Value'] = stock_summary_df['Invested Value'].apply(format_currency)
    stock_summary_df['Current Value'] = stock_summary_df['Current Value'].apply(format_currency)
    stock_summary_df['Gain %'] = stock_summary_df['Gain %'].map(lambda v: f'{v:+.2f}%' if pd.notna(v) else 'N/A')
    stock_summary_df['Overall %'] = stock_summary_df['Overall %'].map(lambda v: f'{v:.1f}%')

    # Rename Current Value column to Current Total Value for clarity
    stock_summary_df.rename(columns={'Current Value': 'Current Total Value'}, inplace=True)

    # Remove the Sector % column and include Gain % and Current Total Value in the table
    stock_summary_table_html = stock_summary_df[['Stock', 'Sector', 'Price', 'Shares', 'Invested Value', 'Current Total Value', 'Gain %', 'Overall %']].to_html(index=False, classes='dataframe', border=0, justify='center').replace('<table', '<table id="stock-summary-table"', 1)

    sector_rows = []
    for sector, invested in sorted(sector_totals.items(), key=lambda item: item[1], reverse=True):
        weight = (invested / overall_total * 100) if overall_total else 0.0
        sector_rows.append(
            f"<tr><td>{sector}</td><td>{format_currency(invested)}</td><td>{weight:.1f}%</td></tr>"
        )
    sector_table_html = (
        '<section class="section-block">'
        '<h2>Sector Allocation</h2>'
        '<table class="dataframe" style="width:100%; border-collapse: collapse;">'
        '<thead><tr><th style="text-align:left; padding:12px;">Sector</th>'
        '<th style="text-align:right; padding:12px;">Invested</th>'
        '<th style="text-align:right; padding:12px;">Weight</th></tr></thead>'
        '<tbody>' + ''.join(sector_rows) + '</tbody>'
        '</table>'
        '</section>'
    )

    stock_sections = []
    for symbol in SYMBOLS:
        details = []
        prices = df.loc[df['Stock'] == symbol, 'Price'].iloc[0]
        price_text = format_currency(prices) if not pd.isna(prices) else 'N/A'
        summary_value = df.loc[df['Stock'] == symbol, 'Invested Value'].iloc[0]
        sector = df.loc[df['Stock'] == symbol, 'Sector'].iloc[0]
        sector_pct = df.loc[df['Stock'] == symbol, 'Sector %'].iloc[0]
        overall_pct = df.loc[df['Stock'] == symbol, 'Overall %'].iloc[0]

        chart_selector_html = f'''
            <div class="timeframe-row">
                <label for="timeline-select-{symbol}">Timeline</label>
                <select id="timeline-select-{symbol}" onchange="showTimelineChart('{symbol}', this.value)">
                    {''.join(f'<option value="{period}">{label}</option>' for period, label in TIME_FRAMES)}
                </select>
            </div>
        '''
        charts_html = chart_selector_html
        for period, label in TIME_FRAMES:
            historical = get_historical_data(symbol, period)
            if historical is not None and not historical.empty:
                historical = historical.reset_index()
                fig = px.line(
                    historical,
                    x='Date',
                    y='Close',
                    title=f'{symbol} Price Trend — {label}',
                )
                fig.update_layout(xaxis_title='Date', yaxis_title='Price ($)')
                charts_html += (
                    f'<div class="chart-block chart-panel" id="chart-{symbol}-{period}" '
                    f'data-symbol="{symbol}" style="display:none;">{build_plot_html(fig)}</div>'
                )
            else:
                charts_html += (
                    f'<div class="chart-block chart-panel" id="chart-{symbol}-{period}" '
                    f'data-symbol="{symbol}" style="display:none;">'
                    f'<div class="empty-state">No {label} history available for {symbol}.</div></div>'
                )

        recs = get_recommendations(symbol)
        rec_rows = ''
        if recs:
            for rating, value in recs.items():
                rec_rows += f'<tr><td>{rating}</td><td>{value}</td></tr>'
        else:
            rec_rows = '<tr><td colspan="2">No analyst recommendations available.</td></tr>'

        news_items = get_news(symbol)
        news_html = ''
        if news_items:
            for item in news_items:
                news_html += f'<li><a href="{item["link"]}" target="_blank">{item["title"]}</a></li>'
        else:
            news_html = '<li>No recent news available.</li>'

        financial_data = {}
        ticker = yf.Ticker(symbol)
        try:
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                info = ticker.info
            financial_data = {
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
            financial_data = {}

        financial_rows = ''
        if financial_data:
            for metric, value in financial_data.items():
                financial_rows += f'<tr><td>{metric}</td><td>{format_currency(value) if isinstance(value, (int, float)) else value or "N/A"}</td></tr>'
        else:
            financial_rows = '<tr><td colspan="2">Financial details unavailable.</td></tr>'

        stock_sections.append(
            {
                'symbol': symbol,
                'sector': sector,
                'price': price_text,
                'value': format_currency(summary_value),
                'sector_pct': f'{sector_pct:.1f}%',
                'overall_pct': f'{overall_pct:.1f}%',
                'charts_html': charts_html,
                'recommendations_html': rec_rows,
                'news_html': news_html,
                'financial_html': financial_rows,
            }
        )

    stock_options_html = ''
    stock_details_html = ''
    for section in stock_sections:
        stock_options_html += (
            f'<option value="{section["symbol"]}" '
            f'data-sector="{section["sector"]}" '
            f'data-price="{section["price"]}" '
            f'data-value="{section["value"]}" '
            f'data-sector-pct="{section["sector_pct"]}" '
            f'data-overall-pct="{section["overall_pct"]}">'
            f'{section["symbol"]} — {section["sector"]}</option>'
        )

        stock_details_html += f'''
        <section class="stock-detail" id="detail-{section['symbol']}" style="display:none;">
            <div class="section-block">
                <h3>Price Trend Charts</h3>
                {section['charts_html']}
            </div>
            <div class="section-block two-column">
                <div>
                    <h3>Analyst Sentiment</h3>
                    <table class="detail-table">
                        <thead><tr><th>Rating</th><th>Count</th></tr></thead>
                        <tbody>{section['recommendations_html']}</tbody>
                    </table>
                </div>
                <div>
                    <h3>Latest News</h3>
                    <ul class="news-list">{section['news_html']}</ul>
                </div>
            </div>
            <div class="section-block">
                <h3>Financial Overview</h3>
                <table class="detail-table">
                    <tbody>{section['financial_html']}</tbody>
                </table>
            </div>
        </section>
        '''

    html = f'''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>{title}</title>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />
        <script src="https://cdn.plot.ly/plotly-2.31.1.min.js"></script>
        <style>
            :root {{
                color-scheme: dark;
                font-family: 'Inter', sans-serif;
                background: #09121f;
                color: #e5e9f2;
                line-height: 1.5;
            }}
            * {{ box-sizing: border-box; }}
            body {{ margin: 0; padding: 0; min-height: 100vh; }}
            .layout-shell {{ display: grid; grid-template-columns: 260px 1fr; gap: 24px; min-height: 100vh; }}
            .sidebar {{ position: sticky; top: 0; align-self: start; padding: 32px 24px; background: #08101f; border-right: 1px solid rgba(255,255,255,.08); height: 100vh; }}
            .sidebar h2 {{ margin: 0; color: #ffffff; font-size: 1.3rem; }}
            .sidebar p {{ margin: 8px 0 0; color: #94a3b8; line-height: 1.5; }}
            .sidebar-nav {{ display: grid; gap: 12px; margin-top: 32px; }}
            .sidebar-item {{ background: transparent; border: 1px solid rgba(255,255,255,.08); border-radius: 16px; color: #e2e8f0; padding: 14px 18px; text-align: left; cursor: pointer; font-size: 0.98rem; transition: background .2s, border-color .2s, transform .2s; }}
            .sidebar-item:hover, .sidebar-item.active {{ background: rgba(124,58,237,.18); border-color: #7c3aed; transform: translateX(2px); }}
            .content-shell {{ padding: 32px 0 32px 0; }}
            .page-shell {{ max-width: 100%; margin: 0; padding: 0; }}
            .content-section {{ display: none; }}
            .content-section.active {{ display: block; }}
            header {{ display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-end; justify-content: space-between; margin-bottom: 32px; }}
            header h1 {{ margin: 0; font-size: clamp(2rem, 2.5vw, 3rem); }}
            header p {{ margin: 0; color: #9fb3d2; max-width: 760px; }}
            .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 16px; margin-bottom: 32px; }}
            .kpi-card {{ background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.08); border-radius: 18px; padding: 22px; min-height: 114px; }}
            .kpi-card strong {{ display: block; margin-bottom: 10px; color: #c7d2ff; }}
            .kpi-card span {{ font-size: 1.5rem; color: #f8fafc; }}
            .charts-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 32px; }}
            .section-block {{ background: rgba(255,255,255,.03); border: 1px solid rgba(255,255,255,.08); border-radius: 22px; padding: 24px; margin-bottom: 24px; }}
            .section-block h2, .section-block h3 {{ margin-top: 0; color: #ffffff; }}
            .dataframe {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
            .dataframe th, .dataframe td {{ padding: 12px 14px; text-align: left; border-bottom: 1px solid rgba(255,255,255,.08); }}
            #stock-summary-table th {{ background: rgba(255,255,255,.04); color: #c7d2ff; cursor: pointer; user-select: none; }}
            #stock-summary-table th.sort-asc::after {{ content: ' ▲'; color: #a5b4fc; }}
            #stock-summary-table th.sort-desc::after {{ content: ' ▼'; color: #a5b4fc; }}
            .dataframe th {{ background: rgba(255,255,255,.04); color: #c7d2ff; }}
            .selector-row {{ display: flex; flex-wrap: wrap; gap: 16px; align-items: center; justify-content: space-between; margin-bottom: 20px; }}
            .selector-row select {{ min-width: 240px; border-radius: 14px; border: 1px solid rgba(255,255,255,.16); background: rgba(255,255,255,.04); color: #ffffff; padding: 12px 14px; }}
            .select-block label {{ display: block; margin-bottom: 8px; color: #c7d2ff; font-size: 0.95rem; }}
            .timeframe-row {{ display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-bottom: 16px; }}
            .timeframe-row label {{ color: #c7d2ff; min-width: 80px; }}
            .timeframe-row select {{ min-width: 180px; border-radius: 14px; border: 1px solid rgba(255,255,255,.16); background: rgba(255,255,255,.04); color: #ffffff; padding: 10px 14px; }}
            .stock-summary {{ padding: 20px 24px; margin-bottom: 24px; position: sticky; top: 20px; z-index: 5; }}
            .stock-summary .detail-summary {{ gap: 14px; }}
            .stock-card-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 14px; margin-bottom: 20px; }}
            .stock-card {{ background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.08); border-radius: 18px; padding: 18px; text-align: left; color: #ffffff; cursor: pointer; transition: transform .18s ease, border-color .18s ease; }}
            .stock-card:hover {{ transform: translateY(-2px); border-color: #7c3aed; }}
            .stock-card strong {{ display: block; font-size: 1.1rem; margin-bottom: 6px; }}
            .stock-card span {{ color: #9fb3d2; }}
            .detail-summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(155px, 1fr)); gap: 16px; margin-bottom: 24px; }}
            .detail-summary div {{ background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.08); border-radius: 16px; padding: 18px; }}
            .detail-summary strong {{ display: block; color: #9fb3d2; margin-bottom: 8px; }}
            .detail-summary p {{ margin: 0; font-size: 1.1rem; color: #ffffff; }}
            .two-column {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }}
            .detail-table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
            .detail-table td, .detail-table th {{ padding: 12px; border: 1px solid rgba(255,255,255,.08); }}
            .detail-table th {{ background: rgba(255,255,255,.05); text-align: left; color: #c7d2ff; }}
            .news-list {{ list-style: none; padding-left: 0; margin: 0; }}
            .news-list li {{ padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,.08); }}
            .news-list li a {{ color: #a5b4fc; text-decoration: none; }}
            .news-list li a:hover {{ text-decoration: underline; }}
            .chart-block {{ margin-bottom: 24px; }}
            .empty-state {{ min-height: 200px; display: grid; place-items: center; background: rgba(255,255,255,.04); border-radius: 14px; border: 1px dashed rgba(255,255,255,.12); color: #a3bffa; }}
            @media (max-width: 1024px) {{ .layout-shell {{ grid-template-columns: 1fr; }} .sidebar {{ position: relative; top: 0; height: auto; width: 100%; border-right: none; border-bottom: 1px solid rgba(255,255,255,.08); }} .charts-grid, .two-column {{ grid-template-columns: 1fr; }} }}
            @media (max-width: 640px) {{ .content-shell {{ padding: 24px 0; }} .page-shell {{ padding: 0; }} header {{ flex-direction: column; align-items: flex-start; }} }}
        </style>
    </head>
    <body>
        <div class="layout-shell">
            <aside class="sidebar">
                <div class="sidebar-header">
                    <h2>Portfolio Menu</h2>
                    <p>Switch between high-level details, sector breakup, and stock analysis.</p>
                </div>
                <nav class="sidebar-nav">
                    <button class="sidebar-item active" data-view="high-level" onclick="showView('high-level')">High level details</button>
                    <button class="sidebar-item" data-view="sector-breakup" onclick="showView('sector-breakup')">Sector wise breakup</button>
                    <button class="sidebar-item" data-view="stock-analysis" onclick="showView('stock-analysis')">Individual stock analysis</button>
                </nav>
            </aside>
            <main class="content-shell">
                <div class="page-shell">
                    <header>
                        <div>
                            <h1>{title}</h1>
                            <p>{subtitle}</p>
                        </div>
                    </header>

                    <section id="high-level" class="content-section active">
                        <div class="kpi-grid">
                            {''.join(f'<div class="kpi-card"><strong>{name}</strong><span>{value}</span></div>' for name, value in summary_cards)}
                        </div>
                        <section class="section-block">
                            <h2>Top 10 Gainers</h2>
                            {top_gainers_table_html}
                        </section>
                    </section>

                    <section id="sector-breakup" class="content-section">
                        {sector_table_html}
                        <div class="charts-grid">
                            <section class="section-block">{build_plot_html(overview_fig)}</section>
                            <section class="section-block">{build_plot_html(sector_fig)}</section>
                        </div>
                    </section>

                    <section id="stock-analysis" class="content-section">
                        <section class="section-block">
                            <h2>Individual Holdings</h2>
                            {stock_summary_table_html}
                        </section>
                        <section class="section-block">
                            <div class="selector-row">
                                <div><h2>Stock Explorer</h2><p>Select a symbol to inspect detailed performance, ratings, news, and financials.</p></div>
                                <div class="select-block">
                                    <label for="symbol-select">Choose symbol</label>
                                    <select id="symbol-select" onchange="showStockDetails(this.value)">
                                        {stock_options_html}
                                    </select>
                                </div>
                            </div>
                            <div class="section-block stock-summary">
                                <div class="detail-summary">
                                    <div><strong>Selected Symbol</strong><p id="summary-symbol"></p></div>
                                    <div><strong>Sector</strong><p id="summary-sector"></p></div>
                                    <div><strong>Last Price</strong><p id="summary-price"></p></div>
                                    <div><strong>Position Value</strong><p id="summary-value"></p></div>
                                    <div><strong>Sector Share</strong><p id="summary-sector-pct"></p></div>
                                    <div><strong>Overall Share</strong><p id="summary-overall-pct"></p></div>
                                </div>
                            </div>
                            {stock_details_html}
                        </section>
                    </section>
                </div>
            </main>
        </div>

        <script>
            function updateSummary(option) {{
                if (!option) return;
                document.getElementById('summary-symbol').textContent = option.value;
                document.getElementById('summary-sector').textContent = option.dataset.sector || 'N/A';
                document.getElementById('summary-price').textContent = option.dataset.price || 'N/A';
                document.getElementById('summary-value').textContent = option.dataset.value || 'N/A';
                document.getElementById('summary-sector-pct').textContent = option.dataset.sectorPct || 'N/A';
                document.getElementById('summary-overall-pct').textContent = option.dataset.overallPct || 'N/A';
            }}
            function showView(view) {{
                document.querySelectorAll('.content-section').forEach(function(section) {{
                    section.classList.toggle('active', section.id === view);
                }});
                document.querySelectorAll('.sidebar-item').forEach(function(button) {{
                    button.classList.toggle('active', button.dataset.view === view);
                }});
                if (view === 'stock-analysis') {{
                    const selector = document.getElementById('symbol-select');
                    if (selector) {{
                        showStockDetails(selector.value);
                    }}
                }} else {{
                    window.scrollTo({{ top: 0, behavior: 'smooth' }});
                }}
            }}
            function showTimelineChart(symbol, period) {{
                document.querySelectorAll(`.chart-panel[data-symbol="${{symbol}}"]`).forEach(function(panel) {{
                    panel.style.display = panel.id === `chart-${{symbol}}-${{period}}` ? 'block' : 'none';
                }});
                const timelineSelect = document.getElementById(`timeline-select-${{symbol}}`);
                if (timelineSelect) {{
                    timelineSelect.value = period;
                }}
            }}
            function showStockDetails(symbol) {{
                const selector = document.getElementById('symbol-select');
                if (selector && symbol) {{
                    selector.value = symbol;
                }}
                const selectedOption = selector.querySelector(`option[value="${{symbol}}"]`);
                updateSummary(selectedOption);
                document.querySelectorAll('.stock-detail').forEach(function(panel) {{
                    panel.style.display = panel.id === 'detail-' + symbol ? 'block' : 'none';
                }});
                showTimelineChart(symbol, '5d');
                window.scrollTo({{ top: document.querySelector('#detail-' + symbol)?.offsetTop - 20 || 0, behavior: 'smooth' }});
            }}
            function makeTableSortable(tableId) {{
                const table = document.getElementById(tableId);
                if (!table) return;

                const getCellValue = (row, index) => {{
                    const cell = row.children[index];
                    const text = cell.textContent.trim();
                        if (/^\\$?[\\d,]+(\\.\\d+)?%?$/.test(text)) {{
                }};

                const comparer = (idx, asc) => (a, b) => {{
                    const v1 = getCellValue(asc ? a : b, idx);
                    const v2 = getCellValue(asc ? b : a, idx);
                    return v1 > v2 ? 1 : v1 < v2 ? -1 : 0;
                }};

                Array.from(table.querySelectorAll('th')).forEach((th, index) => {{
                    th.addEventListener('click', () => {{
                        const tbody = table.tBodies[0];
                        const rows = Array.from(tbody.querySelectorAll('tr'));
                        const asc = !th.classList.contains('sort-asc');
                        table.querySelectorAll('th').forEach(header => header.classList.remove('sort-asc', 'sort-desc'));
                        th.classList.toggle('sort-asc', asc);
                        th.classList.toggle('sort-desc', !asc);
                        rows.sort(comparer(index, asc));
                        rows.forEach(row => tbody.appendChild(row));
                    }});
                }});
            }}

            document.addEventListener('DOMContentLoaded', function() {{
                const selector = document.getElementById('symbol-select');
                const defaultSymbol = selector ? selector.value : '{SYMBOLS[0]}';
                showView('high-level');
                showStockDetails(defaultSymbol);
                makeTableSortable('stock-summary-table');
            }});
        </script>
    </body>
    </html>
    '''

    OUTPUT_FILE.write_text(html, encoding='utf-8')
    print(f'Generated dashboard: {OUTPUT_FILE}')


def start_local_server(directory: Path, port: int = 0):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(directory), **kwargs)

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    return server, server.server_address[1]


def main():
    df, sector_totals, overall_total = build_stock_dataframe()
    build_dashboard(df, sector_totals, overall_total)

    server, port = start_local_server(BASE_DIR)
    url = f'http://127.0.0.1:{port}/{OUTPUT_FILE.name}'
    print(f'Serving dashboard at {url}')
    webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
        print('Local server stopped.')


if __name__ == '__main__':
    main()


