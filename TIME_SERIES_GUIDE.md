# Time-Series Portfolio Analysis Guide

## Architecture Overview

Your portfolio analysis system now has three layers:

### 1. **Time Series Database** (`time_series_db.py`)
- **Stores**: 3,572 transactions + 23,525 daily snapshots
- **Design**: SQLite for efficiency and natural language queries
- **Immutable**: All historical data preserved for audit trail

### 2. **Analysis Module** (`portfolio_analysis.py`)
- High-level analysis functions
- Period-based analysis
- Instrument-specific analysis
- Export capabilities

### 3. **Natural Language Capability**
SQLite allows you to write SQL queries for any analysis. Examples:

```python
# What was my portfolio value on a specific date?
db.query("""
SELECT snapshot_date, SUM(total_invested) as total, COUNT(*) as count
FROM daily_snapshots 
WHERE snapshot_date = '2026-05-15'
""")

# How much have I invested in each sector by date?
db.query("""
SELECT snapshot_date, instrument, total_invested
FROM daily_snapshots
WHERE snapshot_date BETWEEN '2026-05-01' AND '2026-05-22'
ORDER BY snapshot_date, total_invested DESC
""")

# Identify largest gains (need current prices)
db.query("""
SELECT instrument, 
       MAX(total_quantity) as qty,
       MIN(avg_cost_basis) as avg_cost,
       SUM(total_invested) as invested
FROM daily_snapshots
WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM daily_snapshots)
GROUP BY instrument
ORDER BY invested DESC
""")
```

---

## Use Cases & Solutions

### **Use Case 1: Time Window Based Analysis**

```python
from portfolio_analysis import PortfolioAnalyzer
from datetime import date, timedelta

analyzer = PortfolioAnalyzer()

# Analyze last 30 days
start_date = date.today() - timedelta(days=30)
analyzer.analyze_period(start_date)

# Export to CSV for external analysis
analyzer.export_analysis(
    Path("export_30days.csv"),
    start_date=start_date
)
```

**What you get:**
- Daily investment totals over time
- Position changes by instrument  
- Number of holdings growing/shrinking
- Exact investment amount on each date

---

### **Use Case 2: Loss/Gain Analysis Over Time**

```python
# With current stock prices
current_prices = {
    'NVDA': 915.50,
    'TSLA': 875.00,
    'GOOGL': 185.25,
    # ... add all current prices
}

gains_df = analyzer.db.get_gains_losses(
    start_date=date(2026, 5, 1),
    current_prices=current_prices
)

# Shows: invested amount → current value → unrealized P&L
print(gains_df[[
    'instrument', 'total_invested', 'current_value', 
    'unrealized_gain', 'unrealized_pct'
]])
```

**Key metrics provided:**
- `unrealized_gain`: Dollar gain/loss
- `unrealized_pct`: Percentage gain/loss
- `total_invested`: Cost basis
- `current_value`: Current market value

---

### **Use Case 3: Investment Amount on Time Scale**

```python
# Get cumulative investment over time
investment_timeline = analyzer.db.get_investment_timeline(
    start_date=date(2026, 4, 1),
    end_date=date(2026, 5, 22)
)

# Output: snapshot_date, total_invested, num_instruments
# Shows how your portfolio grew day by day
```

**Example output:**
```
  2026-04-24 | Total: $450,000.00 | Holdings: 45 stocks
  2026-04-25 | Total: $465,000.00 | Holdings: 46 stocks
  2026-04-26 | Total: $490,000.00 | Holdings: 48 stocks
  ...
  2026-05-22 | Total: $1,071,001.20 | Holdings: 82 stocks
```

This shows exactly how much you invested each day.

---

## Database vs In-Memory Dict Comparison

| Feature | In-Memory Dict | SQLite |
|---------|---|---|
| **Speed for 3,500+ transactions** | Slow (O(n) loops) | Fast (indexed queries) |
| **Time-range queries** | Manual iteration | `WHERE date BETWEEN X AND Y` |
| **Date grouping** | Manual aggregation | `GROUP BY snapshot_date` |
| **Persistence** | Lost on restart | Saved to file |
| **Natural language queries** | Not feasible | Direct SQL |
| **Export to CSV** | Manual conversion | Built-in |
| **Memory usage** | All in RAM (~10MB) | Disk-based (~5MB database) |
| **Schema enforcement** | None | Strict types |

**Recommendation**: SQLite is strictly better for your use case.

---

## Quick Start

### 1. Initialize Database

```python
from pathlib import Path
from time_series_db import TimeSeriesDB

db = TimeSeriesDB(Path("portfolio.db"))
db.load_from_csv(Path("bhaskar.csv"))
print("✅ Database ready with daily snapshots")
```

### 2. Run Analysis

```python
from portfolio_analysis import PortfolioAnalyzer
from datetime import date, timedelta

analyzer = PortfolioAnalyzer()

# 3-month analysis
start = date.today() - timedelta(days=90)
analyzer.analyze_period(start)

# Single instrument analysis
analyzer.analyze_instrument("NVDA")
```

### 3. Custom SQL Queries

```python
# Get top 5 investments on any date
db.query("""
SELECT instrument, total_invested, total_quantity
FROM daily_snapshots
WHERE snapshot_date = '2026-05-22' 
  AND total_invested > 0
ORDER BY total_invested DESC
LIMIT 5
""")
```

---

## Integration with Existing finalys.py

Add to your `finalys.py`:

```python
from time_series_db import TimeSeriesDB
from portfolio_analysis import PortfolioAnalyzer
from datetime import date, timedelta

def add_timeseries_analysis():
    """Enhanced finalys with time-series capability."""
    
    # Initialize
    analyzer = PortfolioAnalyzer()
    
    # Include in your dashboard
    investment_timeline = analyzer.db.get_investment_timeline()
    
    # Export for visualization
    analyzer.export_analysis(Path('timeseries_export.csv'))
    
    # Add to your HTML report
    # ... chart investment growth over time
    
    analyzer.close()
```

---

## Next Steps

1. **Add live price fetching** (already in your `finance_data.py`)
2. **Integrate into dashboard.html** for time-series charts
3. **Add LLM layer** for natural language queries:
   ```python
   # "Show my portfolio value on May 15th"
   # → SQL: SELECT SUM(total_invested) FROM daily_snapshots WHERE snapshot_date = '2026-05-15'
   ```

---

## Files Created

- **`time_series_db.py`**: Core database module (268 lines)
- **`portfolio_analysis.py`**: Analysis utilities (193 lines)  
- **`test_db.py`**: Example usage and verification
