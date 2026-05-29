#!/usr/bin/env python3
"""Test the TimeSeriesDB with your portfolio data."""

from pathlib import Path
from time_series_db import TimeSeriesDB

# Initialize database
db_path = Path("test_portfolio.db")
db = TimeSeriesDB(db_path)

# Load data
csv_path = Path("bhaskar.csv")
print(f"Loading from: {csv_path.exists()}")

try:
    db.load_from_csv(csv_path)
    print("✅ Data loaded successfully!")
    
    # Check stats
    transactions = db.query("SELECT COUNT(*) as cnt FROM transactions")[0]
    print(f"\n📊 Total transactions: {transactions['cnt']}")
    
    snapshots = db.query("SELECT COUNT(*) as cnt FROM daily_snapshots")[0]
    print(f"📊 Daily snapshots created: {snapshots['cnt']}")
    
    # Show investment timeline
    print("\n💰 INVESTMENT TIMELINE (Last 5 dates):")
    timeline = db.query("""
    SELECT snapshot_date, ROUND(SUM(total_invested), 2) as total_inv, COUNT(DISTINCT instrument) as num_stocks
    FROM daily_snapshots 
    GROUP BY snapshot_date 
    ORDER BY snapshot_date DESC 
    LIMIT 5
    """)
    for row in timeline:
        print(f"  {row['snapshot_date']} | Total: ${row['total_inv']:,.2f} | Holdings: {row['num_stocks']} stocks")
    
    # Show position breakdown on latest date
    print("\n📊 LATEST POSITIONS (as of most recent date):")
    latest_date_query = db.query("SELECT MAX(snapshot_date) as max_date FROM daily_snapshots")[0]
    latest_date = latest_date_query['max_date']
    latest_positions = db.query(f"""
    SELECT instrument, ROUND(total_quantity, 2) as qty, 
           ROUND(avg_cost_basis, 2) as cost_basis, ROUND(total_invested, 2) as invested
    FROM daily_snapshots 
    WHERE snapshot_date = ? AND total_quantity > 0
    ORDER BY total_invested DESC
    LIMIT 15
    """, [latest_date])
    
    for row in latest_positions:
        print(f"  {row['instrument']:6} | Qty: {row['qty']:8.2f} | Cost: ${row['cost_basis']:7.2f} | Invested: ${row['invested']:12,.2f}")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
