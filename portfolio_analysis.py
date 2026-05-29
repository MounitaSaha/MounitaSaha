"""
Time-window analysis utilities for portfolio P&L and investment tracking.
"""

import pandas as pd
from datetime import date, timedelta
from pathlib import Path
from time_series_db import TimeSeriesDB


class PortfolioAnalyzer:
    """Perform time-window based portfolio analysis."""
    
    def __init__(self, db_path: Path = Path("portfolio_timeseries.db")):
        self.db = TimeSeriesDB(db_path)
    
    def analyze_period(self, start_date: date, end_date: date = None, 
                      current_prices: dict = None):
        """Analyze portfolio performance for a time period."""
        if end_date is None:
            end_date = date.today()
        
        print(f"\n{'='*70}")
        print(f"PORTFOLIO ANALYSIS: {start_date} to {end_date}")
        print(f"{'='*70}\n")
        
        # Investment timeline
        print("💰 CUMULATIVE INVESTMENT TIMELINE")
        print("-" * 70)
        investment_df = self.db.get_investment_timeline(start_date, end_date)
        if not investment_df.empty:
            print(investment_df.to_string(index=False))
            print(f"\nTotal Invested: ${investment_df['total_invested'].iloc[-1]:,.2f}")
        
        # Position changes
        print("\n\n📊 POSITION ANALYSIS BY INSTRUMENT")
        print("-" * 70)
        positions_df = self.db.get_timeseries(start_date=start_date, end_date=end_date)
        
        if not positions_df.empty:
            # Show first and last positions
            latest = positions_df.sort_values('snapshot_date').drop_duplicates(
                'instrument', keep='last'
            )
            print(latest[['instrument', 'total_quantity', 'avg_cost_basis', 'total_invested']].to_string(index=False))
        
        # Gains/losses if current prices provided
        if current_prices:
            print("\n\n💹 UNREALIZED GAINS/LOSSES (Latest)")
            print("-" * 70)
            gains_df = self.db.get_gains_losses(
                start_date=start_date, 
                end_date=end_date,
                current_prices=current_prices
            )
            
            latest_gains = gains_df.drop_duplicates('instrument', keep='last')
            latest_gains = latest_gains[latest_gains['total_quantity'] > 0]
            
            if not latest_gains.empty:
                display_df = latest_gains[[
                    'instrument', 'total_quantity', 'avg_cost_basis', 
                    'total_invested', 'current_price', 'current_value', 
                    'unrealized_gain', 'unrealized_pct'
                ]].copy()
                display_df.columns = [
                    'Instrument', 'Qty', 'Avg Cost', 'Invested', 
                    'Current $', 'Current Val', 'Gain/Loss $', 'Gain/Loss %'
                ]
                print(display_df.to_string(index=False))
                
                total_invested = latest_gains['total_invested'].sum()
                total_value = latest_gains['current_value'].sum()
                total_gain = total_value - total_invested
                total_pct = (total_gain / total_invested * 100) if total_invested != 0 else 0
                
                print(f"\n{'TOTAL':16} {total_invested:>10,.2f} {total_value:>15,.2f} "
                      f"{total_gain:>15,.2f} {total_pct:>10.2f}%")
    
    def analyze_instrument(self, instrument: str, start_date: date = None):
        """Analyze single instrument over time."""
        print(f"\n{'='*70}")
        print(f"INSTRUMENT ANALYSIS: {instrument}")
        print(f"{'='*70}\n")
        
        df = self.db.get_timeseries(instrument=instrument, start_date=start_date)
        
        if df.empty:
            print(f"No data for {instrument}")
            return
        
        print(f"Date Range: {df['snapshot_date'].min()} to {df['snapshot_date'].max()}")
        print(f"Started: {df.iloc[0]['snapshot_date']} with {df.iloc[0]['total_quantity']} shares @ ${df.iloc[0]['avg_cost_basis']:.2f}")
        print(f"Current: {df.iloc[-1]['snapshot_date']} with {df.iloc[-1]['total_quantity']} shares @ ${df.iloc[-1]['avg_cost_basis']:.2f}")
        print(f"Total Invested: ${df['total_invested'].sum():,.2f}")
    
    def export_analysis(self, output_path: Path, start_date: date = None, 
                       end_date: date = None):
        """Export time-series data to CSV for external analysis."""
        df = self.db.get_timeseries(start_date=start_date, end_date=end_date)
        df.to_csv(output_path, index=False)
        print(f"✅ Exported {len(df)} records to {output_path}")
    
    def get_monthly_summary(self, year: int = None, month: int = None):
        """Get monthly investment summary."""
        if year is None or month is None:
            # Get current month
            today = date.today()
            year, month = today.year, today.month
        
        # Calculate date range
        first_day = date(year, month, 1)
        if month == 12:
            last_day = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = date(year, month + 1, 1) - timedelta(days=1)
        
        return self.db.get_investment_timeline(first_day, last_day)
    
    def close(self):
        self.db.close()


# Example usage functions
def example_setup():
    """Example: Initialize and load data."""
    db = TimeSeriesDB(Path("portfolio_timeseries.db"))
    
    # Load from CSV
    csv_path = Path("bhaskar.csv")
    if csv_path.exists():
        print("Loading transactions from bhaskar.csv...")
        db.load_from_csv(csv_path)
        print("✅ Data loaded and snapshots built")
    
    return db


def example_analysis():
    """Example: Run various analyses."""
    analyzer = PortfolioAnalyzer()
    
    # Analyze last 3 months
    start = date.today() - timedelta(days=90)
    analyzer.analyze_period(start)
    
    # Analyze specific instrument
    analyzer.analyze_instrument("RGTI")
    
    analyzer.close()
