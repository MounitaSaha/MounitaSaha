# Time-Series Analysis Quick Reference

## One-Liner Examples

### Load Data
```python
from time_series_db import TimeSeriesDB; from pathlib import Path
db = TimeSeriesDB(Path("portfolio.db")); db.load_from_csv(Path("bhaskar.csv"))
```

### Get Investment Timeline
```python
df = db.get_investment_timeline(start_date=date(2026,5,1))  # Daily total invested
df.to_csv('timeline.csv')  # Export
```

### Time Window Analysis
```python
from portfolio_analysis import PortfolioAnalyzer
analyzer = PortfolioAnalyzer(Path("portfolio.db"))
analyzer.analyze_period(start_date=date(2026,5,1))  # Full report
```

### Gain/Loss with Prices
```python
prices = {'NVDA': 915.50, 'TSLA': 875.00}
gains = db.get_gains_losses(current_prices=prices)
print(gains[['instrument', 'unrealized_gain', 'unrealized_pct']])
```

### Single Instrument
```python
analyzer.analyze_instrument("NVDA")  # Full analysis for one stock
```

---

## Common Queries

### Top 5 Investments on Specific Date
```python
db.query("""
SELECT instrument, total_invested
FROM daily_snapshots 
WHERE snapshot_date = '2026-05-22'
ORDER BY total_invested DESC LIMIT 5
""")
```

### Total Portfolio Value Over Time
```python
db.query("""
SELECT snapshot_date, SUM(total_invested) as total
FROM daily_snapshots
GROUP BY snapshot_date
ORDER BY snapshot_date
""")
```

### Instruments Bought Most Recent
```python
db.query("""
SELECT DISTINCT instrument 
FROM daily_snapshots
WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM daily_snapshots)
ORDER BY total_invested DESC
""")
```

### Investment Growth Rate
```python
df = db.get_investment_timeline()
start = df.iloc[0]['total_invested']
end = df.iloc[-1]['total_invested']
growth = (end - start) / start * 100
print(f"Growth: {growth:.1f}%")
```

---

## API Reference

### TimeSeriesDB

#### Methods
- `load_from_csv(csv_path)` - Load transactions
- `get_timeseries(instrument, start_date, end_date)` - Get time-series DataFrame
- `get_gains_losses(start_date, end_date, current_prices)` - P&L analysis
- `get_investment_timeline(start_date, end_date)` - Daily totals
- `query(sql, params)` - Custom SQL queries
- `close()` - Close connection

#### Example
```python
db = TimeSeriesDB(Path("portfolio.db"))
db.load_from_csv(Path("bhaskar.csv"))
timeline = db.get_investment_timeline()
db.close()
```

### PortfolioAnalyzer

#### Methods
- `analyze_period(start_date, end_date, current_prices)` - Full period analysis
- `analyze_instrument(instrument, start_date)` - Single instrument
- `export_analysis(output_path, start_date, end_date)` - Export to CSV
- `get_monthly_summary(year, month)` - Monthly data
- `close()` - Close connection

#### Example
```python
analyzer = PortfolioAnalyzer(Path("portfolio.db"))
analyzer.analyze_period(date(2026,5,1))
analyzer.export_analysis(Path("export.csv"))
analyzer.close()
```

---

## Data Columns

### daily_snapshots
```
snapshot_date         - DATE: YYYY-MM-DD
instrument            - TEXT: Stock symbol
total_quantity        - REAL: Cumulative shares owned
avg_cost_basis        - REAL: Average cost per share
total_invested        - REAL: Total $ invested
```

### transactions
```
activity_date         - DATE: Transaction date
instrument            - TEXT: Stock symbol
quantity              - REAL: Shares transacted
price                 - REAL: $ per share
trans_type            - TEXT: 'buy' or 'sell'
amount                - REAL: Quantity × Price
description           - TEXT: Transaction notes
```

---

## Filters & Parameters

### Time Ranges
```python
from datetime import date, timedelta

today = date.today()
last_30_days = date.today() - timedelta(days=30)
last_month_start = date(2026, 4, 1)
specific_range = (date(2026, 5, 15), date(2026, 5, 22))
```

### Database Paths
```python
Path("portfolio.db")              # Current directory
Path("path/to/portfolio.db")      # Relative path
Path.home() / "portfolio.db"      # Home directory
```

---

## Integration Code Snippet

```python
# Add to finalys.py
from time_series_db import TimeSeriesDB
from pathlib import Path
from datetime import date, timedelta

def get_timeseries_data():
    db = TimeSeriesDB(Path("portfolio.db"))
    
    # 3-month timeline
    start = date.today() - timedelta(days=90)
    timeline = db.get_investment_timeline(start_date=start)
    
    # Get current positions
    positions = db.get_timeseries()
    
    db.close()
    return timeline, positions

# Use in your dashboard
timeline, positions = get_timeseries_data()
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "No such table" | Run `db.load_from_csv()` first |
| Empty results | Check date range is correct (2026-04-24 to 2026-05-22) |
| Slow queries | Add index: `db.conn.execute("CREATE INDEX idx_symbol ON daily_snapshots(instrument)")` |
| DB locked | Another process using it; close other connections |
| Memory error | Check query returns too many rows; add LIMIT |

---

## Performance Tips

1. **Always filter by date** when possible
   ```python
   # ✅ FAST
   db.query("SELECT * FROM daily_snapshots WHERE snapshot_date = '2026-05-22'")
   
   # ❌ SLOW
   db.query("SELECT * FROM daily_snapshots")  # Loads all 23,525 rows
   ```

2. **Use get_timeseries()** instead of raw queries for standard analysis
3. **Export to CSV** once, then use pandas for complex analysis
4. **Cache current_prices** instead of fetching repeatedly

---

## Files Provided

- `time_series_db.py` - Core database layer
- `portfolio_analysis.py` - Analysis utilities
- `example_analysis.py` - Working examples
- `TIME_SERIES_GUIDE.md` - Full documentation
- `QUICK_REFERENCE.md` - This file
- `test_portfolio.db` - Pre-loaded test data

---

**Need Help?** Check TIME_SERIES_GUIDE.md for detailed documentation.
