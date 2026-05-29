import csv
from pathlib import Path

from utils import parse_numeric_value


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
