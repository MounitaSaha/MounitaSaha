#!/usr/bin/env python3
"""
Complete example demonstrating time-series portfolio analysis.
Shows all three use cases:
1. Time window based analysis
2. Loss/gain analysis over time
3. Investment amount on time scale
"""

from pathlib import Path
from datetime import date, timedelta
from time_series_db import TimeSeriesDB
from portfolio_analysis import PortfolioAnalyzer
import pandas as pd


def example_1_time_window_analysis(db_path=None):
    """Use Case 1: Time window based analysis."""
    print("\n" + "="*80)
    print("USE CASE 1: TIME WINDOW BASED ANALYSIS")
    print("="*80)
    
    analyzer = PortfolioAnalyzer(db_path or Path("test_portfolio.db"))
    
    # Analyze different time windows
    windows = [
        ("Last 7 days", date.today() - timedelta(days=7)),
        ("Last 30 days", date.today() - timedelta(days=30)),
        ("Since May 1", date(2026, 5, 1)),
    ]
    
    for label, start_date in windows:
        print(f"\n📊 {label}:")
        print("-" * 80)
        
        # Get investment timeline for this window
        timeline = analyzer.db.get_investment_timeline(
            start_date=start_date,
            end_date=date.today()
        )
        
        if not timeline.empty:
            print(f"Starting investment: ${timeline.iloc[0]['total_invested']:,.2f}")
            print(f"Ending investment:   ${timeline.iloc[-1]['total_invested']:,.2f}")
            print(f"Total added:         ${timeline.iloc[-1]['total_invested'] - timeline.iloc[0]['total_invested']:,.2f}")
            print(f"Days tracked:        {len(timeline)}")
            print(f"Avg holdings:        {timeline['num_instruments'].mean():.0f} stocks")


def example_2_gain_loss_analysis(db_path=None):
    """Use Case 2: Loss/gain analysis over time."""
    print("\n\n" + "="*80)
    print("USE CASE 2: LOSS/GAIN ANALYSIS OVER TIME")
    print("="*80)
    
    db = TimeSeriesDB(db_path or Path("test_portfolio.db"))
    
    # IMPORTANT: Add your current stock prices here
    # In real usage, fetch from get_price_info() in finance_data.py
    current_prices = {
        'NVDA': 915.50,   # Example prices - update with real data
        'TSLA': 875.00,
        'GOOGL': 185.25,
        'AMZN': 180.50,
        'MSFT': 425.00,
        'SMH': 550.00,
        'AMD': 155.00,
        'MU': 95.00,
        'DRAM': 55.00,
        'AVGO': 140.00,
        'TSM': 190.00,
        'SNDK': 1350.00,
        'PANW': 280.00,
        'RKLB': 100.00,
        'INTC': 28.50,
        'DOCN': 165.00,
    }
    
    # Get gains/losses for last 30 days
    start_date = date.today() - timedelta(days=30)
    gains_df = db.get_gains_losses(
        start_date=start_date,
        end_date=date.today(),
        current_prices=current_prices
    )
    
    if not gains_df.empty:
        # Show latest positions only
        latest_date = gains_df['snapshot_date'].max()
        latest = gains_df[gains_df['snapshot_date'] == latest_date].copy()
        latest = latest[latest['total_quantity'] > 0].sort_values('total_invested', ascending=False)
        
        print(f"\n💹 P&L SUMMARY as of {latest_date}:")
        print("-" * 80)
        print(f"{'Instrument':<10} {'Qty':<10} {'Avg Cost':<12} {'Invested':<15} {'Current Val':<15} {'Gain/Loss':<15} {'Return %':<10}")
        print("-" * 80)
        
        total_invested = 0
        total_value = 0
        
        for _, row in latest.iterrows():
            if pd.isna(row['unrealized_gain']):
                continue
            
            print(f"{row['instrument']:<10} "
                  f"{row['total_quantity']:<10.2f} "
                  f"${row['avg_cost_basis']:<11.2f} "
                  f"${row['total_invested']:<14,.2f} "
                  f"${row['current_value']:<14,.2f} "
                  f"${row['unrealized_gain']:<14,.2f} "
                  f"{row['unrealized_pct']:<9.1f}%")
            
            total_invested += row['total_invested']
            total_value += row['current_value']
        
        print("-" * 80)
        total_gain = total_value - total_invested
        total_pct = (total_gain / total_invested * 100) if total_invested > 0 else 0
        print(f"{'TOTAL':<10} {'':<10} {'':<12} "
              f"${total_invested:<14,.2f} "
              f"${total_value:<14,.2f} "
              f"${total_gain:<14,.2f} "
              f"{total_pct:<9.1f}%")
        
        print(f"\n✅ Net Unrealized Gain: ${total_gain:+,.2f} ({total_pct:+.1f}%)")
    
    db.close()


def example_3_investment_timeline(db_path=None):
    """Use Case 3: Investment amount on time scale."""
    print("\n\n" + "="*80)
    print("USE CASE 3: INVESTMENT AMOUNT ON TIME SCALE")
    print("="*80)
    
    analyzer = PortfolioAnalyzer(db_path or Path("test_portfolio.db"))
    
    # Get full investment timeline
    timeline = analyzer.db.get_investment_timeline()
    
    if not timeline.empty:
        print("\n💰 MONTHLY INVESTMENT SUMMARY:")
        print("-" * 80)
        
        # Aggregate by month
        timeline['year_month'] = pd.to_datetime(timeline['snapshot_date']).dt.to_period('M')
        monthly = timeline.groupby('year_month').agg({
            'total_invested': ['min', 'max', 'mean'],
            'num_instruments': ['min', 'max']
        }).reset_index()
        
        for _, row in monthly.iterrows():
            month = row['year_month']
            start_inv = row[('total_invested', 'min')]
            end_inv = row[('total_invested', 'max')]
            avg_inv = row[('total_invested', 'mean')]
            min_stocks = row[('num_instruments', 'min')]
            max_stocks = row[('num_instruments', 'max')]
            
            print(f"{month} | Start: ${start_inv:>12,.0f} | End: ${end_inv:>12,.0f} | "
                  f"Added: ${end_inv - start_inv:>12,.0f} | "
                  f"Stocks: {int(min_stocks)}-{int(max_stocks)}")
        
        # Show growth rate
        print("\n📈 GROWTH ANALYSIS:")
        print("-" * 80)
        first_day = timeline.iloc[0]
        last_day = timeline.iloc[-1]
        total_growth = last_day['total_invested'] - first_day['total_invested']
        growth_pct = (total_growth / first_day['total_invested'] * 100) if first_day['total_invested'] > 0 else 0
        days_tracked = (last_day['snapshot_date'] - first_day['snapshot_date']).days
        daily_avg = total_growth / days_tracked if days_tracked > 0 else 0
        
        print(f"Period: {first_day['snapshot_date']} to {last_day['snapshot_date']} ({days_tracked} days)")
        print(f"Starting investment: ${first_day['total_invested']:,.2f}")
        print(f"Ending investment:   ${last_day['total_invested']:,.2f}")
        print(f"Total invested:      ${total_growth:+,.2f} ({growth_pct:+.1f}%)")
        print(f"Daily average:       ${daily_avg:,.2f}/day")
        print(f"Stocks added:        {last_day['num_instruments'] - first_day['num_instruments']}")
    
    analyzer.close()


def example_4_advanced_queries(db_path=None):
    """Advanced: Custom SQL queries for specific questions."""
    print("\n\n" + "="*80)
    print("ADVANCED: NATURAL LANGUAGE QUERIES")
    print("="*80)
    
    db = TimeSeriesDB(db_path or Path("test_portfolio.db"))
    
    # Question 1: What were my top 5 investments on a specific date?
    print("\n❓ Q1: Top 5 investments on May 22, 2026?")
    result = db.query("""
    SELECT instrument, total_quantity, avg_cost_basis, total_invested
    FROM daily_snapshots
    WHERE snapshot_date = '2026-05-22' AND total_quantity > 0
    ORDER BY total_invested DESC
    LIMIT 5
    """)
    
    print("   Answer:")
    for row in result:
        print(f"   - {row['instrument']:6} | ${row['total_invested']:>12,.2f}")
    
    # Question 2: How many new stocks did I buy each week?
    print("\n❓ Q2: How many new instruments added per week?")
    result = db.query("""
    SELECT 
        DATE(snapshot_date, 'weekday 0', '-7 days') as week_start,
        COUNT(DISTINCT instrument) as new_instruments
    FROM daily_snapshots
    WHERE snapshot_date >= '2026-05-01'
    GROUP BY week_start
    ORDER BY week_start
    """)
    
    print("   Answer:")
    for row in result:
        print(f"   Week of {row['week_start']}: {row['new_instruments']} instruments")
    
    # Question 3: On which date was my investment highest?
    print("\n❓ Q3: When was my maximum investment?")
    result = db.query("""
    SELECT snapshot_date, ROUND(SUM(total_invested), 2) as total
    FROM daily_snapshots
    GROUP BY snapshot_date
    ORDER BY total DESC
    LIMIT 1
    """)
    
    if result:
        row = result[0]
        print(f"   Answer: {row['snapshot_date']} with ${row['total']:,.2f}")
    
    db.close()


def main():
    """Run all examples."""
    print("\n" + "🎯 " * 20)
    print("TIME-SERIES PORTFOLIO ANALYSIS EXAMPLES")
    print("🎯 " * 20)
    
    db_path = Path("test_portfolio.db")
    
    example_1_time_window_analysis(db_path)
    example_2_gain_loss_analysis(db_path)
    example_3_investment_timeline(db_path)
    example_4_advanced_queries(db_path)
    
    print("\n\n" + "✅ " * 20)
    print("ANALYSIS COMPLETE")
    print("✅ " * 20 + "\n")


if __name__ == "__main__":
    main()
