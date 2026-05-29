import pandas as pd


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


def format_currency(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 'N/A'
    return f'${value:,.2f}'


def format_number(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 'N/A'
    return f'{value:,.0f}'
