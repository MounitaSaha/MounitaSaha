from datetime import datetime, date
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import json

from finance_data import get_financial_info, get_historical_data, get_recommendations, get_news
from utils import format_currency

TIME_FRAMES = [
    ('1d', '1 Day'),
    ('5d', '1 Week'),
    ('1mo', '1 Month'),
    ('3mo', '3 Months'),
    ('1y', '1 Year'),
    ('5y', '5 Years'),
    ('max', 'All'),
]


def build_plot_html(fig):
    return pio.to_html(fig, include_plotlyjs=False, full_html=False, config={'displayModeBar': True})


def _build_stock_table(df: pd.DataFrame) -> str:
    table_html = df.sort_values(['Sector', 'Stock']).copy()
    table_html['Price'] = table_html['Price'].apply(lambda v: format_currency(v) if not pd.isna(v) else 'N/A')
    table_html['Invested Value'] = table_html['Invested Value'].apply(format_currency)
    table_html['Current Value'] = table_html['Current Value'].apply(format_currency)
    table_html['Sector %'] = table_html['Sector %'].map(lambda v: f'{v:.1f}%')
    table_html['Overall %'] = table_html['Overall %'].map(lambda v: f'{v:.1f}%')
    return table_html.to_html(index=False, classes='dataframe', border=0, justify='center')


def _format_table(mover_df: pd.DataFrame) -> str:
    mover_df = mover_df.copy()
    mover_df['Gain %'] = mover_df['Daily Gain Numeric'].map(lambda v: f'{v:+.2f}%' if pd.notna(v) else 'N/A')
    return mover_df[['Stock', 'Gain %']].to_html(index=False, classes='dataframe', border=0, justify='center')


def _build_daily_movers(df: pd.DataFrame) -> tuple[str, str]:
    mover_df = df.copy()
    mover_df['Daily Gain Numeric'] = ((mover_df['Price'] - mover_df['Previous Close']) / mover_df['Previous Close'] * 100).where(
        mover_df['Previous Close'] != 0, pd.NA
    )

    top_daily_gainers = mover_df[mover_df['Previous Close'].notna()].sort_values(by='Daily Gain Numeric', ascending=False).head(10)
    top_daily_losers = mover_df[mover_df['Previous Close'].notna()].sort_values(by='Daily Gain Numeric', ascending=True).head(10)

    gainers_html = (
        '<section class="section-block"><h2>Top 10 Daily Gainers</h2>'
        + (_format_table(top_daily_gainers) if not top_daily_gainers.empty else '<div class="empty-state">No data available.</div>')
        + '</section>'
    )
    losers_html = (
        '<section class="section-block"><h2>Top 10 Daily Losers</h2>'
        + (_format_table(top_daily_losers) if not top_daily_losers.empty else '<div class="empty-state">No data available.</div>')
        + '</section>'
    )
    return gainers_html, losers_html


def _build_top_gainers(df: pd.DataFrame) -> str:
    gain_df = df.copy()
    gain_df['Gain Numeric'] = ((gain_df['Current Value'] - gain_df['Invested Value']) / gain_df['Invested Value'] * 100).where(
        gain_df['Invested Value'] != 0, pd.NA
    )
    top_gainers = gain_df[gain_df['Invested Value'] > 0].sort_values(by='Gain Numeric', ascending=False).head(10).copy()

    if top_gainers.empty:
        return '<div class="empty-state">No gainers to display.</div>'

    top_gainers['Price'] = top_gainers['Price'].apply(lambda v: format_currency(v) if not pd.isna(v) else 'N/A')
    top_gainers['Shares'] = top_gainers['Shares'].map(lambda v: f'{v:,.2f}')
    top_gainers['Invested Value'] = top_gainers['Invested Value'].apply(format_currency)
    top_gainers['Current Value'] = top_gainers['Current Value'].apply(format_currency)
    top_gainers['Gain %'] = top_gainers['Gain Numeric'].map(lambda v: f'{v:+.2f}%' if pd.notna(v) else 'N/A')
    top_gainers.rename(columns={'Current Value': 'Current Total Value'}, inplace=True)
    return top_gainers[['Stock', 'Price', 'Shares', 'Invested Value', 'Current Total Value', 'Gain %']].to_html(
        index=False, classes='dataframe', border=0, justify='center'
    )


def _build_stock_analysis_summary(df: pd.DataFrame) -> str:
    summary_df = df.copy()
    summary_df['Gain Numeric'] = ((summary_df['Current Value'] - summary_df['Invested Value']) / summary_df['Invested Value'] * 100).where(
        summary_df['Invested Value'] != 0, pd.NA
    )
    active_df = summary_df[summary_df['Invested Value'] > 0].copy()
    top_overall_gainers = active_df.sort_values(by='Gain Numeric', ascending=False).head(5)
    top_overall_losers = active_df.sort_values(by='Gain Numeric', ascending=True).head(5)

    total_invested = float(df['Invested Value'].sum())
    total_current = float(df['Current Value'].sum())

    top_overall_gainers['Gain %'] = top_overall_gainers['Gain Numeric'].map(lambda v: f'{v:+.2f}%' if pd.notna(v) else 'N/A')
    top_overall_losers['Gain %'] = top_overall_losers['Gain Numeric'].map(lambda v: f'{v:+.2f}%' if pd.notna(v) else 'N/A')

    gainers_html = top_overall_gainers[['Stock', 'Gain %']].to_html(index=False, classes='dataframe', border=0, justify='center') if not top_overall_gainers.empty else '<div class="empty-state">No gainers available.</div>'
    losers_html = top_overall_losers[['Stock', 'Gain %']].to_html(index=False, classes='dataframe', border=0, justify='center') if not top_overall_losers.empty else '<div class="empty-state">No losers available.</div>'

    return (
        '<section class="section-block">'
        '<div class="detail-summary">'
        f'<div><strong>Total Invested</strong><p>{format_currency(total_invested)}</p></div>'
        f'<div><strong>Total Current Value</strong><p>{format_currency(total_current)}</p></div>'
        '</div>'
        '<div class="two-column">'
        '<div>'
        '<h3>Top 5 Overall Gain</h3>'
        f'{gainers_html}'
        '</div>'
        '<div>'
        '<h3>Top 5 Overall Loss</h3>'
        f'{losers_html}'
        '</div>'
        '</div>'
        '</section>'
    )


def _render_sector_table(sector_totals: dict, overall_total: float) -> str:
    sector_rows = []
    for sector, invested in sorted(sector_totals.items(), key=lambda item: item[1], reverse=True):
        weight = (invested / overall_total * 100) if overall_total else 0.0
        sector_rows.append(
            f"<tr><td>{sector}</td><td>{format_currency(invested)}</td><td>{weight:.1f}%</td></tr>"
        )

    return (
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


def _render_stock_sections(df: pd.DataFrame) -> tuple[str, str]:
    stock_sections = []
    stock_options_html = ''

    for symbol in df['Stock']:
        summary = df.loc[df['Stock'] == symbol].iloc[0]
        price_text = format_currency(summary['Price']) if not pd.isna(summary['Price']) else 'N/A'
        financial_data = {}

        charts_html = (
            '<div class="timeframe-row">'
            f'<label for="timeline-select-{symbol}">Timeline</label>'
            f'<select id="timeline-select-{symbol}" onchange="showTimelineChart(\'{symbol}\', this.value)">'
            + ''.join(f'<option value="{period}">{label}</option>' for period, label in TIME_FRAMES)
            + '</select></div>'
        )

        for period, label in TIME_FRAMES:
            historical = get_historical_data(symbol, period)
            if historical is not None and not historical.empty:
                historical = historical.reset_index()
                fig = px.line(historical, x='Date', y='Close', title=f'{symbol} Price Trend — {label}')
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
        recommendation_rows = ''
        if recs:
            recommendation_rows = ''.join(f'<tr><td>{rating}</td><td>{value}</td></tr>' for rating, value in recs.items())
        else:
            recommendation_rows = '<tr><td colspan="2">No analyst recommendations available.</td></tr>'

        news_items = get_news(symbol)
        news_html = ''.join(
            f'<li><a href="{item["link"]}" target="_blank">{item["title"]}</a></li>' for item in news_items
        ) or '<li>No recent news available.</li>'

        financial_data = get_financial_info(symbol)

        financial_rows = ''.join(
            f'<tr><td>{metric}</td><td>{format_currency(value) if isinstance(value, (int, float)) else value or "N/A"}</td></tr>'
            for metric, value in financial_data.items()
        ) or '<tr><td colspan="2">Financial details unavailable.</td></tr>'

        stock_sections.append({
            'symbol': symbol,
            'sector': summary['Sector'],
            'price': price_text,
            'value': format_currency(summary['Invested Value']),
            'sector_pct': f"{summary['Sector %']:.1f}%",
            'overall_pct': f"{summary['Overall %']:.1f}%",
            'charts_html': charts_html,
            'recommendations_html': recommendation_rows,
            'news_html': news_html,
            'financial_html': financial_rows,
        })

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

    stock_details_html = ''.join(
        f'''
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
        for section in stock_sections
    )

    return stock_options_html, stock_details_html


def _build_timeseries_section(timeline_df: pd.DataFrame) -> tuple[str, str]:
    """Build time-series gain/loss analysis section.
    
    Args:
        timeline_df: DataFrame with columns [snapshot_date, total_invested, num_instruments]
    
    Returns:
        Tuple of (slider_section_html, timeseries_chart_html)
    """
    if timeline_df.empty:
        return '', ''
    
    # Convert snapshot_date to proper datetime
    timeline_df = timeline_df.copy()
    if 'snapshot_date' in timeline_df.columns:
        timeline_df['snapshot_date'] = pd.to_datetime(timeline_df['snapshot_date'])
    
    # Get date range
    min_date = timeline_df['snapshot_date'].min()
    max_date = timeline_df['snapshot_date'].max()
    
    # Create investment growth chart
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=timeline_df['snapshot_date'],
        y=timeline_df['total_invested'],
        mode='lines',
        name='Total Invested',
        line=dict(color='#60a5fa', width=2),
        fill='tozeroy',
        fillcolor='rgba(96, 165, 250, 0.1)',
        hovertemplate='<b>Date:</b> %{x|%Y-%m-%d}<br><b>Total Invested:</b> $%{y:,.2f}<extra></extra>'
    ))
    
    fig.update_layout(
        title='Portfolio Investment Growth Over Time',
        xaxis_title='Date',
        yaxis_title='Total Invested ($)',
        hovermode='x unified',
        plot_bgcolor='rgba(15,23,42,.5)',
        paper_bgcolor='rgba(15,23,42,.0)',
        font=dict(color='#e2e8f0'),
        margin=dict(l=60, r=20, t=40, b=60),
        height=350
    )
    
    chart_html = build_plot_html(fig)
    
    # Create date range data as JSON for slider
    dates = timeline_df['snapshot_date'].dt.strftime('%Y-%m-%d').tolist()
    invested = timeline_df['total_invested'].tolist()
    num_instruments = timeline_df['num_instruments'].astype(int).tolist()
    
    slider_data = {
        'dates': dates,
        'invested': invested,
        'instruments': num_instruments,
        'minDate': min_date.strftime('%Y-%m-%d'),
        'maxDate': max_date.strftime('%Y-%m-%d'),
    }
    
    slider_html = f'''
    <div class="timeseries-controls">
        <h3>Portfolio Timeline Analysis</h3>
        <div class="timerange-selector">
            <label for="date-range-start">Start Date:</label>
            <input type="date" id="date-range-start" value="{min_date.strftime('%Y-%m-%d')}" 
                   min="{min_date.strftime('%Y-%m-%d')}" max="{max_date.strftime('%Y-%m-%d')}" 
                   onchange="updateTimeseriesChart()">
            
            <label for="date-range-end" style="margin-left: 20px;">End Date:</label>
            <input type="date" id="date-range-end" value="{max_date.strftime('%Y-%m-%d')}" 
                   min="{min_date.strftime('%Y-%m-%d')}" max="{max_date.strftime('%Y-%m-%d')}" 
                   onchange="updateTimeseriesChart()">
            
            <button onclick="resetTimeRange()" style="margin-left: 20px;">Reset</button>
        </div>
        
        <div class="timerange-info" id="timerange-info" style="margin-top: 12px; padding: 12px; background: rgba(96,165,250,.1); border-radius: 8px; color: #cbd5e1;">
            Showing full date range
        </div>
    </div>
    '''
    
    return slider_html, chart_html, slider_data


def _build_gain_loss_summary(timeline_df: pd.DataFrame) -> str:
    """Build a gains/losses summary card."""
    if timeline_df.empty:
        return ''
    
    timeline_df = timeline_df.copy()
    if 'snapshot_date' in timeline_df.columns:
        timeline_df['snapshot_date'] = pd.to_datetime(timeline_df['snapshot_date'])
    
    start_invested = timeline_df['total_invested'].iloc[0]
    end_invested = timeline_df['total_invested'].iloc[-1]
    total_added = end_invested - start_invested
    pct_growth = (total_added / start_invested * 100) if start_invested > 0 else 0
    num_stocks = timeline_df['num_instruments'].iloc[-1]
    
    # Color based on growth
    color_class = 'positive' if total_added >= 0 else 'negative'
    
    return f'''
    <section class="section-block timeseries-summary">
        <h2>Portfolio Growth Summary</h2>
        <div class="detail-summary">
            <div>
                <strong>Period Start Investment</strong>
                <p>{format_currency(start_invested)}</p>
            </div>
            <div>
                <strong>Period End Investment</strong>
                <p>{format_currency(end_invested)}</p>
            </div>
            <div>
                <strong>Capital Added</strong>
                <p class="{color_class}">{format_currency(total_added)} ({pct_growth:+.1f}%)</p>
            </div>
            <div>
                <strong>Current Holdings</strong>
                <p>{int(num_stocks)} stocks</p>
            </div>
        </div>
    </section>
    '''


def build_dashboard(df: pd.DataFrame, sector_totals: dict, overall_total: float, output_file: Path, timeline_df: pd.DataFrame = None):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    title = 'Stock Portfolio Visualizer'
    subtitle = 'Interactive HTML dashboard for monitoring sector allocation, real-time prices, and stock-level trends.'

    total_current_value = float(df['Current Value'].sum())
    total_gain_value = total_current_value - overall_total
    total_gain_pct = ((total_gain_value) / overall_total * 100) if overall_total else 0.0

    summary_cards = [
        ('Total Investment', format_currency(overall_total)),
        ('Total Current Value', format_currency(total_current_value)),
        ('Total Gain', format_currency(total_gain_value)),
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

    daily_gainers_html, daily_losers_html = _build_daily_movers(df)
    top_gainers_table_html = _build_top_gainers(df)
    default_symbol = df['Stock'].iloc[0] if not df.empty else ''
    stock_analysis_summary_html = _build_stock_analysis_summary(df)
    stock_summary_table_html = _build_stock_summary_table(df)
    sector_table_html = _render_sector_table(sector_totals, overall_total)
    stock_options_html, stock_details_html = _render_stock_sections(df)
    
    # Generate time-series section if timeline data provided
    timeseries_slider_html = ''
    timeseries_chart_html = ''
    timeseries_summary_html = ''
    timeseries_data_json = '{}'
    
    if timeline_df is not None and not timeline_df.empty:
        timeseries_slider_html, timeseries_chart_html, slider_data = _build_timeseries_section(timeline_df)
        timeseries_summary_html = _build_gain_loss_summary(timeline_df)
        timeseries_data_json = json.dumps(slider_data)

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
                background: radial-gradient(circle at top, #12203b 0%, #09121f 50%, #040810 100%);
                color: #e5e9f2;
                line-height: 1.45;
                font-size: 14px;
            }}
            * {{ box-sizing: border-box; }}
            body {{ margin: 0; padding: 0; min-height: 100vh; background: transparent; }}
            .layout-shell {{ display: grid; grid-template-columns: 260px 1fr; gap: 24px; min-height: 100vh; }}
            .sidebar {{ position: sticky; top: 0; align-self: start; padding: 28px 22px; background: linear-gradient(180deg, rgba(8,16,31,.96), rgba(7,12,25,.88)); border-right: 1px solid rgba(255,255,255,.08); height: 100vh; }}
            .sidebar h2 {{ margin: 0; color: #ffffff; font-size: 1.05rem; letter-spacing: 0.01em; }}
            .sidebar p {{ margin: 10px 0 0; color: #9ca3af; line-height: 1.6; font-size: 0.92rem; }}
            .sidebar-nav {{ display: grid; gap: 12px; margin-top: 30px; }}
            .sidebar-item {{ background: transparent; border: 1px solid rgba(148,163,184,.18); border-radius: 14px; color: #cbd5e1; padding: 12px 16px; text-align: left; cursor: pointer; font-size: 0.92rem; transition: background .2s, border-color .2s, transform .2s; }}
            .sidebar-item:hover, .sidebar-item.active {{ background: rgba(79,70,229,.18); border-color: rgba(79,70,229,.45); transform: translateX(1px); }}
            .content-shell {{ padding: 32px 0 32px 0; }}
            .page-shell {{ max-width: 100%; margin: 0; padding: 0; }}
            .content-section {{ display: none; }}
            .content-section.active {{ display: block; }}
            header {{ display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-end; justify-content: space-between; margin-bottom: 28px; }}
            header h1 {{ margin: 0; font-size: clamp(1.8rem, 2.1vw, 2.4rem); letter-spacing: -0.04em; }}
            header p {{ margin: 0; color: #94a3b8; max-width: 760px; font-size: 0.96rem; line-height: 1.6; }}
            .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 28px; }}
            .kpi-card {{ background: linear-gradient(135deg, rgba(30,58,138,.24), rgba(14,165,233,.12)); border: 1px solid rgba(56,189,248,.18); border-radius: 20px; padding: 18px 20px; min-height: 104px; box-shadow: 0 18px 45px rgba(6, 12, 24, 0.18); }}
            .kpi-card strong {{ display: block; margin-bottom: 8px; color: #60a5fa; font-size: 0.92rem; }}
            .kpi-card span {{ font-size: 1.25rem; color: #f8fafc; line-height: 1.2; }}
            .charts-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 32px; }}
            .section-block {{ background: rgba(8, 19, 38, 0.95); border: 1px solid rgba(96, 165, 250, 0.14); border-radius: 22px; padding: 22px 24px; margin-bottom: 24px; box-shadow: 0 20px 45px rgba(6, 12, 24, 0.18); }}
            .section-block h2, .section-block h3 {{ margin-top: 0; color: #f8fafc; font-size: 1.1rem; letter-spacing: -0.03em; }}
            .dataframe {{ width: 100%; border-collapse: collapse; margin-top: 18px; font-size: 0.92rem; }}
            .dataframe th, .dataframe td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid rgba(148,163,184,.12); }}
            .dataframe tr:nth-child(even) {{ background: rgba(148,163,184,.05); }}
            .dataframe tr:hover {{ background: rgba(59,130,246,.12); }}
            #stock-summary-table th {{ background: linear-gradient(180deg, rgba(15,23,42,.96), rgba(30,41,59,.96)); color: #cbd5e1; cursor: pointer; user-select: none; }}
            #stock-summary-table th.sort-asc::after {{ content: ' ▲'; color: #93c5fd; }}
            #stock-summary-table th.sort-desc::after {{ content: ' ▼'; color: #93c5fd; }}
            .dataframe th {{ background: linear-gradient(180deg, rgba(15,23,42,.95), rgba(35, 50, 75, .95)); color: #cbd5e1; }}
            .dataframe td {{ color: #e2e8f0; }}
            .selector-row {{ display: flex; flex-wrap: wrap; gap: 16px; align-items: center; justify-content: space-between; margin-bottom: 20px; }}
            .selector-row select {{ min-width: 240px; border-radius: 14px; border: 1px solid rgba(56,189,248,.28); background: rgba(15,23,42,.96); color: #e2e8f0; padding: 12px 14px; }}
            .select-block label {{ display: block; margin-bottom: 8px; color: #94a3b8; font-size: 0.9rem; }}
            .timeframe-row {{ display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-bottom: 16px; }}
            .timeframe-row label {{ color: #c7d2ff; min-width: 80px; }}
            .timeframe-row select {{ min-width: 180px; border-radius: 14px; border: 1px solid rgba(255,255,255,.16); background: rgba(255,255,255,.04); color: #ffffff; padding: 10px 14px; }}
            .stock-summary {{ padding: 18px 22px; margin-bottom: 24px; position: sticky; top: 20px; z-index: 5; background: rgba(9, 18, 34, 0.92); border: 1px solid rgba(96, 165, 250, 0.12); border-radius: 18px; }}
            .stock-summary .detail-summary {{ gap: 14px; }}
            .stock-card-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 14px; margin-bottom: 20px; }}
            .stock-card {{ background: linear-gradient(135deg, rgba(79,70,229,.16), rgba(2,132,199,.12)); border: 1px solid rgba(148,163,184,.18); border-radius: 18px; padding: 16px; text-align: left; color: #eff6ff; cursor: pointer; transition: transform .18s ease, border-color .18s ease, box-shadow .18s ease; }}
            .stock-card:hover {{ transform: translateY(-2px); border-color: rgba(96,165,250,.6); box-shadow: 0 14px 30px rgba(15,23,42,.24); }}
            .stock-card strong {{ display: block; font-size: 1rem; margin-bottom: 6px; }}
            .stock-card span {{ color: #cbd5e1; }}
            .detail-summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(155px, 1fr)); gap: 16px; margin-bottom: 24px; }}
            .detail-summary div {{ background: rgba(15, 23, 42, 0.92); border: 1px solid rgba(148,163,184,.18); border-radius: 16px; padding: 16px; }}
            .detail-summary strong {{ display: block; color: #cbd5e1; margin-bottom: 8px; font-size: 0.94rem; }}
            .detail-summary p {{ margin: 0; font-size: 0.95rem; color: #e2e8f0; }}
            .two-column {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }}
            .detail-table {{ width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 0.92rem; }}
            .detail-table td, .detail-table th {{ padding: 10px; border: 1px solid rgba(148,163,184,.14); }}
            .detail-table th {{ background: rgba(30, 41, 59, .95); text-align: left; color: #cbd5e1; }}
            .news-list {{ list-style: none; padding-left: 0; margin: 0; }}
            .news-list li {{ padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,.08); }}
            .news-list li a {{ color: #a5b4fc; text-decoration: none; }}
            .news-list li a:hover {{ text-decoration: underline; }}
            .chart-block {{ margin-bottom: 24px; }}
            .empty-state {{ min-height: 200px; display: grid; place-items: center; background: rgba(15, 23, 42, 0.82); border-radius: 14px; border: 1px dashed rgba(56,189,248,.35); color: #bfdbfe; }}
            .timeseries-controls {{ margin-bottom: 24px; padding: 20px; background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(96, 165, 250, 0.2); border-radius: 16px; }}
            .timeseries-controls h3 {{ margin-top: 0; color: #f8fafc; }}
            .timerange-selector {{ display: flex; flex-wrap: wrap; gap: 16px; align-items: center; margin-top: 12px; }}
            .timerange-selector label {{ color: #cbd5e1; min-width: 80px; }}
            .timerange-selector input[type="date"] {{ border-radius: 8px; border: 1px solid rgba(56,189,248,.28); background: rgba(15,23,42,.96); color: #e2e8f0; padding: 8px 12px; font-size: 0.9rem; }}
            .timerange-selector button {{ background: linear-gradient(135deg, rgba(79,70,229,.24), rgba(56,189,248,.12)); border: 1px solid rgba(79,70,229,.4); color: #e2e8f0; padding: 8px 16px; border-radius: 8px; cursor: pointer; font-size: 0.9rem; transition: all .2s; }}
            .timerange-selector button:hover {{ background: linear-gradient(135deg, rgba(79,70,229,.35), rgba(56,189,248,.2)); border-color: rgba(79,70,229,.6); }}
            .timerange-info {{ font-size: 0.9rem; }}
            .timeseries-summary {{ margin-bottom: 24px; }}
            .positive {{ color: #34d399; }}
            .negative {{ color: #f87171; }}
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
                        
                        {timeseries_summary_html}
                        
                        <section class="section-block">
                            {timeseries_slider_html}
                            {timeseries_chart_html}
                        </section>
                        
                        {daily_gainers_html}
                        {daily_losers_html}
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
                        {stock_analysis_summary_html}
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
                        return parseFloat(text.replace(/[^0-9.-]/g, '')) || 0;
                    }}
                    return text.toLowerCase();
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
                const defaultSymbol = selector ? selector.value : '{default_symbol}';
                showView('high-level');
                showStockDetails(defaultSymbol);
                makeTableSortable('stock-summary-table');
            }});
        </script>
    </body>
    </html>
    '''

    output_file.write_text(html, encoding='utf-8')
    print(f'Generated dashboard: {output_file}')


def _build_stock_summary_table(df: pd.DataFrame) -> str:
    stock_summary_df = df.copy()
    gain = (stock_summary_df['Current Value'] - stock_summary_df['Invested Value']) / stock_summary_df['Invested Value'] * 100
    stock_summary_df['Gain %'] = gain.where(stock_summary_df['Invested Value'] != 0, pd.NA)
    stock_summary_df.sort_values(by='Gain %', ascending=False, inplace=True)
    stock_summary_df['Price'] = stock_summary_df['Price'].apply(lambda v: format_currency(v) if not pd.isna(v) else 'N/A')
    stock_summary_df['Shares'] = stock_summary_df['Shares'].map(lambda v: f'{v:,.2f}')
    stock_summary_df['Invested Value'] = stock_summary_df['Invested Value'].apply(format_currency)
    stock_summary_df['Current Value'] = stock_summary_df['Current Value'].apply(format_currency)
    stock_summary_df['Gain %'] = stock_summary_df['Gain %'].map(lambda v: f'{v:+.2f}%' if pd.notna(v) else 'N/A')
    stock_summary_df['Overall %'] = stock_summary_df['Overall %'].map(lambda v: f'{v:.1f}%')
    stock_summary_df.rename(columns={'Current Value': 'Current Total Value'}, inplace=True)
    return stock_summary_df[['Stock', 'Sector', 'Price', 'Shares', 'Invested Value', 'Current Total Value', 'Gain %', 'Overall %']].to_html(
        index=False, classes='dataframe', border=0, justify='center'
    ).replace('<table', '<table id="stock-summary-table"', 1)
