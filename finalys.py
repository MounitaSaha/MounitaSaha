import argparse
import logging
import webbrowser
from decimal import Decimal
from pathlib import Path

from data_loader import load_small_holdings
from extract_bhaskar_small import (
    aggregate_instruments,
    aggregate_instruments_from_files,
    append_transaction,
    write_aggregates,
)
from portfolio import build_stock_dataframe
from report import build_dashboard
from server import start_local_server

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = BASE_DIR / 'dashboard.html'
RAW_HOLDINGS_FILE = BASE_DIR / 'bhaskar.csv'
SMALL_HOLDINGS_FILE = BASE_DIR / 'bhaskar_small.csv'


def configure_logging():
    logging.getLogger('yfinance').setLevel(logging.ERROR)
    logging.getLogger('urllib3').setLevel(logging.ERROR)


def prepare_holdings(raw_paths: list[Path], small_path: Path):
    existing_raw = [path for path in raw_paths if path.exists()]
    if small_path.exists():
        if existing_raw:
            latest_raw_mtime = max(path.stat().st_mtime for path in existing_raw)
            if latest_raw_mtime <= small_path.stat().st_mtime:
                return
        else:
            return

    if not existing_raw:
        if small_path.exists():
            return
        raise FileNotFoundError(
            f"Required holding file not found. Create {small_path.name} from one of the raw CSV files or provide {small_path.name}."
        )

    print(f'Generating holdings file from {", ".join(path.name for path in existing_raw)}...')
    if len(existing_raw) == 1:
        aggregates = aggregate_instruments(str(existing_raw[0]))
    else:
        aggregates = aggregate_instruments_from_files([str(path) for path in existing_raw])

    written = write_aggregates(str(small_path), aggregates)
    print(f'Wrote {written} instruments to {small_path.name}')


def run_dashboard(input_files: list[str], small_file: str, output_file: str, no_serve: bool):
    raw_paths = [Path(file) for file in input_files]
    small_path = Path(small_file)
    output_path = Path(output_file)

    prepare_holdings(raw_paths, small_path)
    share_allocation, transaction_values, symbols = load_small_holdings(small_path)
    df, sector_totals, overall_total = build_stock_dataframe(symbols, share_allocation, transaction_values)
    build_dashboard(df, sector_totals, overall_total, output_path)

    if no_serve:
        print(f'Dashboard generated at {output_path}')
        return

    server, port = start_local_server(BASE_DIR)
    url = f'http://127.0.0.1:{port}/{output_path.name}'
    print(f'Serving dashboard at {url}')
    webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
        print('Local server stopped.')


def run_update(file: str, stock: str, quantity: Decimal, action: str, price: Decimal, activity_date: str | None):
    append_transaction(file, stock, quantity, action, price, activity_date)
    print(f'Appended {action} transaction for {stock} to {file}')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Stock portfolio dashboard CLI')
    subparsers = parser.add_subparsers(dest='command', required=True)

    dashboard_parser = subparsers.add_parser('dashboard', help='Build and show the portfolio dashboard')
    dashboard_parser.add_argument(
        '--input', '-i',
        nargs='+',
        default=[str(RAW_HOLDINGS_FILE)],
        help='One or more raw transaction CSV files to source portfolio data from',
    )
    dashboard_parser.add_argument(
        '--small', '-s',
        default=str(SMALL_HOLDINGS_FILE),
        help='Path to the aggregated small holdings CSV file',
    )
    dashboard_parser.add_argument(
        '--output', '-o',
        default=str(OUTPUT_FILE),
        help='Path for the generated dashboard HTML file',
    )
    dashboard_parser.add_argument(
        '--no-serve',
        action='store_true',
        help='Generate the dashboard without starting the local browser/server',
    )

    update_parser = subparsers.add_parser('update', help='Add a buy/sell transaction to a transaction CSV')
    update_parser.add_argument(
        '--file', '-f',
        default=str(RAW_HOLDINGS_FILE),
        help='CSV file to update with the new transaction',
    )
    update_parser.add_argument('--stock', '-t', required=True, help='Stock symbol or instrument name')
    update_parser.add_argument('--quantity', '-q', type=Decimal, required=True, help='Number of shares')
    update_parser.add_argument('--action', '-a', choices=['buy', 'sell'], required=True, help='Transaction type')
    update_parser.add_argument('--price', '-p', type=Decimal, required=True, help='Price per share')
    update_parser.add_argument('--date', '-d', help='Transaction date (MM/DD/YYYY). Defaults to today')

    return parser.parse_args()


def main():
    configure_logging()
    args = parse_args()

    if args.command == 'dashboard':
        run_dashboard(args.input, args.small, args.output, args.no_serve)
    elif args.command == 'update':
        run_update(args.file, args.stock, args.quantity, args.action, args.price, args.date)


if __name__ == '__main__':
    main()
