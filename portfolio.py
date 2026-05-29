import pandas as pd

from finance_data import get_sector, get_price_info


def build_stock_dataframe(symbols, share_allocation, transaction_values):
    rows = []
    for symbol in symbols:
        shares = round(float(share_allocation.get(symbol, 0.0)), 2)
        invested_value = round(float(transaction_values.get(symbol, 0.0)), 2)
        current_price, previous_close = get_price_info(symbol)
        current_value = round(shares * current_price, 2) if current_price is not None else 0.0
        rows.append({
            'Stock': symbol,
            'Sector': get_sector(symbol),
            'Shares': shares,
            'Price': current_price,
            'Previous Close': previous_close,
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
