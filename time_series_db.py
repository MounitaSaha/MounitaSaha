"""
Time-series database module for portfolio analysis.
Stores transactions and generates snapshots for time-window analysis.
"""

import sqlite3
from datetime import datetime, date
from pathlib import Path
from decimal import Decimal
import pandas as pd


class TimeSeriesDB:
    """SQLite database for time-series portfolio analysis."""
    
    def __init__(self, db_path: Path = Path("portfolio_timeseries.db")):
        self.db_path = db_path
        self.conn = None
        self.init_db()
    
    def init_db(self):
        """Initialize database schema."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        
        # Transactions table - immutable audit trail
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY,
            activity_date DATE NOT NULL,
            instrument TEXT NOT NULL,
            quantity REAL NOT NULL,
            price REAL NOT NULL,
            trans_type TEXT NOT NULL CHECK (trans_type IN ('buy', 'sell')),
            amount REAL NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Indexes for fast queries
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_activity_date ON transactions(activity_date)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_instrument ON transactions(instrument)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_date_instrument ON transactions(activity_date, instrument)"
        )
        
        # Daily snapshots - denormalized for fast time-series analysis
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_snapshots (
            snapshot_date DATE NOT NULL,
            instrument TEXT NOT NULL,
            total_quantity REAL NOT NULL,
            avg_cost_basis REAL NOT NULL,
            total_invested REAL NOT NULL,
            PRIMARY KEY (snapshot_date, instrument)
        )
        """)
        
        self.conn.commit()
    
    def load_from_csv(self, csv_path: Path):
        """Load transactions from bhaskar.csv format."""
        import csv
        
        with open(csv_path, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if not row:
                    continue
                try:
                    activity_date_str = (row.get('Activity Date') or '').strip()
                    instrument = (row.get('Instrument') or '').strip()
                    trans_code = (row.get('Trans Code') or '').strip().lower()
                    quantity_str = (row.get('Quantity') or '').strip()
                    price_str = (row.get('Price') or '').strip()
                    amount_str = (row.get('Amount') or '').strip()
                    description = (row.get('Description') or '').strip()
                    
                    # Skip non-trading transactions
                    if trans_code not in ('buy', 'sell') or not instrument:
                        continue
                    
                    # Parse values
                    activity_date = datetime.strptime(activity_date_str, '%m/%d/%Y').date()
                    quantity = float(quantity_str.replace(',', '')) if quantity_str else 0.0
                    # Handle prices with format like "$26.22" or "(2,000.00)"
                    price_cleaned = price_str.lstrip('$').replace('(', '-').replace(')', '').replace(',', '')
                    price = float(price_cleaned) if price_cleaned else 0.0
                    # Handle amounts with format like "($2,000.00)"
                    amount_cleaned = amount_str.lstrip('$(').replace(')', '').replace(',', '')
                    amount = float(amount_cleaned) if amount_cleaned else quantity * price
                    
                    if quantity > 0 and price > 0:
                        self.add_transaction(
                            activity_date=activity_date,
                            instrument=instrument,
                            quantity=quantity,
                            price=price,
                            trans_type=trans_code,
                            description=description
                        )
                except (ValueError, KeyError, AttributeError) as e:
                    pass  # Skip rows that can't be parsed
        
        self.conn.commit()
        self.build_snapshots()
    
    def add_transaction(self, activity_date: date, instrument: str, quantity: float, 
                       price: float, trans_type: str, description: str = ""):
        """Add a single transaction."""
        amount = quantity * price
        self.conn.execute("""
        INSERT INTO transactions 
        (activity_date, instrument, quantity, price, trans_type, amount, description)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (activity_date, instrument, quantity, price, trans_type, amount, description))
        self.conn.commit()
    
    def build_snapshots(self):
        """Build daily snapshots from transactions."""
        # Clear existing snapshots
        self.conn.execute("DELETE FROM daily_snapshots")
        
        # Get all unique dates
        dates = self.conn.execute(
            "SELECT DISTINCT DATE(activity_date) as date FROM transactions ORDER BY date"
        ).fetchall()
        
        for date_row in dates:
            snapshot_date = date_row['date']
            
            # Get all instruments with activity on or before this date
            instruments = self.conn.execute("""
            SELECT DISTINCT instrument FROM transactions 
            WHERE activity_date <= ? 
            ORDER BY instrument
            """, (snapshot_date,)).fetchall()
            
            for instr_row in instruments:
                instrument = instr_row['instrument']
                
                # Calculate cumulative position and cost basis
                result = self.conn.execute("""
                SELECT 
                    SUM(CASE WHEN trans_type = 'buy' THEN quantity ELSE -quantity END) as total_qty,
                    SUM(CASE WHEN trans_type = 'buy' THEN quantity * price ELSE -quantity * price END) as total_invested
                FROM transactions
                WHERE activity_date <= ? AND instrument = ?
                """, (snapshot_date, instrument)).fetchone()
                
                total_qty = result['total_qty'] or 0.0
                total_invested = result['total_invested'] or 0.0
                
                if total_qty != 0:
                    avg_cost = total_invested / total_qty
                else:
                    avg_cost = 0.0
                
                self.conn.execute("""
                INSERT OR REPLACE INTO daily_snapshots 
                (snapshot_date, instrument, total_quantity, avg_cost_basis, total_invested)
                VALUES (?, ?, ?, ?, ?)
                """, (snapshot_date, instrument, total_qty, avg_cost, total_invested))
        
        self.conn.commit()
    
    def get_timeseries(self, instrument: str = None, start_date: date = None, 
                       end_date: date = None) -> pd.DataFrame:
        """
        Get time-series data for analysis.
        
        Args:
            instrument: Filter by instrument (None = all)
            start_date: Start date (None = earliest)
            end_date: End date (None = latest)
        
        Returns:
            DataFrame with columns: snapshot_date, instrument, quantity, cost_basis, invested_amount
        """
        query = "SELECT * FROM daily_snapshots WHERE 1=1"
        params = []
        
        if instrument:
            query += " AND instrument = ?"
            params.append(instrument)
        
        if start_date:
            query += " AND snapshot_date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND snapshot_date <= ?"
            params.append(end_date)
        
        query += " ORDER BY snapshot_date, instrument"
        
        return pd.read_sql_query(
            query, self.conn, params=params,
            parse_dates=['snapshot_date']
        )
    
    def get_gains_losses(self, start_date: date = None, end_date: date = None, 
                        current_prices: dict = None) -> pd.DataFrame:
        """
        Calculate gains/losses over time window.
        
        Args:
            start_date: Start date for analysis window
            end_date: End date for analysis window
            current_prices: Dict of {instrument: current_price}
        
        Returns:
            DataFrame with P&L analysis
        """
        df = self.get_timeseries(start_date=start_date, end_date=end_date)
        
        if df.empty:
            return df
        
        if current_prices:
            df['current_price'] = df['instrument'].map(current_prices)
            df['current_value'] = df['total_quantity'] * df['current_price']
            df['unrealized_gain'] = df['current_value'] - df['total_invested']
            df['unrealized_pct'] = (df['unrealized_gain'] / df['total_invested'] * 100).round(2)
        
        return df
    
    def get_investment_timeline(self, start_date: date = None, 
                               end_date: date = None) -> pd.DataFrame:
        """
        Get cumulative investment timeline.
        
        Returns:
            DataFrame with daily total invested amount across all instruments
        """
        query = """
        SELECT 
            snapshot_date,
            SUM(total_invested) as total_invested,
            COUNT(DISTINCT instrument) as num_instruments
        FROM daily_snapshots
        WHERE 1=1
        """
        params = []
        
        if start_date:
            query += " AND snapshot_date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND snapshot_date <= ?"
            params.append(end_date)
        
        query += " GROUP BY snapshot_date ORDER BY snapshot_date"
        
        return pd.read_sql_query(
            query, self.conn, params=params,
            parse_dates=['snapshot_date']
        )
    
    def query(self, sql: str, params: list = None) -> list:
        """Execute custom SQL query."""
        cursor = self.conn.execute(sql, params or [])
        return cursor.fetchall()
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
