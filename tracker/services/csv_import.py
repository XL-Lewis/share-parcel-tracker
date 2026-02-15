"""
CSV import pipeline: Upload -> Detect/Map Columns -> Preview -> Confirm.

Supports SelfWealth format (auto-mapped) and generic CSV (user-defined mapping).
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction

from tracker.models import ImportRecord, Parcel, Security, Transaction


# ---------------------------------------------------------------------------
# Column adapters
# ---------------------------------------------------------------------------

# Canonical field names expected after mapping
CANONICAL_FIELDS = [
    "trade_date",
    "transaction_type",
    "ticker",
    "quantity",
    "unit_price",
    "brokerage",
    "total_value",
    "exchange_rate",
    "currency",
    "exchange",
    "asset_type",
]

REQUIRED_FIELDS = [
    "trade_date",
    "transaction_type",
    "ticker",
    "quantity",
    "unit_price",
]


# SelfWealth column name -> canonical field
SELFWEALTH_MAPPING: dict[str, str] = {
    "Trade Date": "trade_date",
    "Action": "transaction_type",
    "Code": "ticker",
    "Units": "quantity",
    "Average Price": "unit_price",
    "Brokerage": "brokerage",
    "Total": "total_value",
}


def get_selfwealth_mapping() -> dict[str, str]:
    """Return the fixed SelfWealth column mapping."""
    return dict(SELFWEALTH_MAPPING)


def detect_selfwealth(headers: list[str]) -> bool:
    """Check whether CSV headers look like SelfWealth export."""
    required = {"Trade Date", "Action", "Code", "Units", "Average Price"}
    return required.issubset(set(headers))


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_date(value: str) -> date:
    """Parse a date string, trying common formats."""
    for fmt in (
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y",
        "%d/%m/%Y %H:%M:%S",
        "%d-%m-%Y",
        "%m/%d/%Y",
    ):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {value!r}")


def _parse_decimal(value: str) -> Decimal:
    """Parse a string to Decimal, stripping currency symbols and commas."""
    cleaned = value.strip().replace("$", "").replace(",", "")
    if not cleaned:
        return Decimal("0")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        raise ValueError(f"Cannot parse decimal: {value!r}")


def _normalise_transaction_type(value: str) -> str:
    """Normalise transaction type to BUY or SELL."""
    upper = value.strip().upper()
    if upper in ("BUY", "B"):
        return "BUY"
    if upper in ("SELL", "S"):
        return "SELL"
    if upper in ("IN", "OUT"):
        raise ValueError(
            f"Corporate action '{value}' (e.g. transfer/conversion) "
            f"-- not a trade, skipped"
        )
    raise ValueError(f"Unknown transaction type: {value!r}")


# ---------------------------------------------------------------------------
# Row parsing
# ---------------------------------------------------------------------------


@dataclass
class ParsedRow:
    """A single parsed CSV row in canonical form."""

    trade_date: date
    transaction_type: str
    ticker: str
    quantity: Decimal
    unit_price: Decimal
    brokerage: Decimal = Decimal("0")
    total_value: Decimal = Decimal("0")
    exchange_rate: Decimal = Decimal("1")
    currency: str = "AUD"
    exchange: str = "ASX"
    asset_type: str = "SHARE"
    raw_data: dict[str, Any] = field(default_factory=dict)
    row_number: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0


def parse_csv_file(
    file_content: str,
    column_mapping: dict[str, str],
) -> tuple[list[str], list[ParsedRow]]:
    """
    Parse CSV content using the given column mapping.

    Args:
        file_content: Raw CSV text.
        column_mapping: Maps CSV column name -> canonical field name.

    Returns:
        (headers, parsed_rows) where headers are original CSV headers.
    """
    reader = csv.DictReader(io.StringIO(file_content))
    headers = reader.fieldnames or []

    # Invert mapping: canonical -> csv column
    reverse_map = {v: k for k, v in column_mapping.items()}

    rows: list[ParsedRow] = []
    for i, raw_row in enumerate(reader, start=2):  # row 1 is header
        row = ParsedRow(
            trade_date=date.today(),
            transaction_type="BUY",
            ticker="",
            quantity=Decimal("0"),
            unit_price=Decimal("0"),
            raw_data=dict(raw_row),
            row_number=i,
        )

        # trade_date
        col = reverse_map.get("trade_date", "")
        if col and col in raw_row and raw_row[col]:
            try:
                row.trade_date = _parse_date(raw_row[col])
            except ValueError as e:
                row.errors.append(f"trade_date: {e}")
        elif "trade_date" in REQUIRED_FIELDS:
            row.errors.append("trade_date: missing")

        # transaction_type
        col = reverse_map.get("transaction_type", "")
        if col and col in raw_row and raw_row[col]:
            try:
                row.transaction_type = _normalise_transaction_type(raw_row[col])
            except ValueError as e:
                row.errors.append(f"transaction_type: {e}")
        elif "transaction_type" in REQUIRED_FIELDS:
            row.errors.append("transaction_type: missing")

        # ticker
        col = reverse_map.get("ticker", "")
        if col and col in raw_row and raw_row[col]:
            row.ticker = raw_row[col].strip().upper()
        elif "ticker" in REQUIRED_FIELDS:
            row.errors.append("ticker: missing")

        # Decimal fields
        for field_name, default in [
            ("quantity", Decimal("0")),
            ("unit_price", Decimal("0")),
            ("brokerage", Decimal("0")),
            ("total_value", Decimal("0")),
            ("exchange_rate", Decimal("1")),
        ]:
            col = reverse_map.get(field_name, "")
            if col and col in raw_row and raw_row[col]:
                try:
                    val = _parse_decimal(raw_row[col])
                    # quantity and total_value should be positive
                    if field_name in ("quantity", "total_value"):
                        val = abs(val)
                    setattr(row, field_name, val)
                except ValueError as e:
                    row.errors.append(f"{field_name}: {e}")
            elif field_name in REQUIRED_FIELDS:
                row.errors.append(f"{field_name}: missing")
            else:
                setattr(row, field_name, default)

        # Optional string fields
        col = reverse_map.get("currency", "")
        if col and col in raw_row and raw_row[col]:
            row.currency = raw_row[col].strip().upper()

        col = reverse_map.get("exchange", "")
        if col and col in raw_row and raw_row[col]:
            row.exchange = raw_row[col].strip().upper()

        col = reverse_map.get("asset_type", "")
        if col and col in raw_row and raw_row[col]:
            row.asset_type = raw_row[col].strip().upper()

        # Compute total_value if not provided
        if row.total_value == Decimal("0") and row.is_valid:
            row.total_value = row.quantity * row.unit_price

        rows.append(row)

    return headers, rows


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------


def find_duplicates(rows: list[ParsedRow]) -> set[int]:
    """
    Return set of row_numbers that would be duplicates of existing transactions.
    """
    duplicate_rows: set[int] = set()
    for row in rows:
        if not row.is_valid:
            continue
        exists = Transaction.objects.filter(
            trade_date=row.trade_date,
            security__ticker=row.ticker,
            transaction_type=row.transaction_type,
            quantity=row.quantity,
            unit_price=row.unit_price,
        ).exists()
        if exists:
            duplicate_rows.add(row.row_number)
    return duplicate_rows


# ---------------------------------------------------------------------------
# Preview result
# ---------------------------------------------------------------------------


@dataclass
class ImportPreview:
    """Result of preview_import -- everything the UI needs to show."""

    rows: list[ParsedRow]
    duplicate_row_numbers: set[int]
    valid_count: int = 0
    error_count: int = 0
    duplicate_count: int = 0
    new_count: int = 0

    def __post_init__(self):
        self.valid_count = sum(1 for r in self.rows if r.is_valid)
        self.error_count = sum(1 for r in self.rows if not r.is_valid)
        self.duplicate_count = len(self.duplicate_row_numbers)
        self.new_count = self.valid_count - self.duplicate_count


def preview_import(
    file_content: str,
    column_mapping: dict[str, str],
) -> ImportPreview:
    """
    Parse CSV and check for duplicates. Returns an ImportPreview for the UI.
    """
    _headers, rows = parse_csv_file(file_content, column_mapping)
    duplicates = find_duplicates(rows)
    return ImportPreview(rows=rows, duplicate_row_numbers=duplicates)


# ---------------------------------------------------------------------------
# Confirm import
# ---------------------------------------------------------------------------


def _get_or_create_security(row: ParsedRow) -> Security:
    """Get or create a Security from a parsed row."""
    security, _created = Security.objects.get_or_create(
        ticker=row.ticker,
        defaults={
            "exchange": row.exchange,
            "currency": row.currency,
            "asset_type": row.asset_type,
        },
    )
    return security


def _create_parcel_from_buy(txn: Transaction) -> Parcel:
    """Auto-create a Parcel from a BUY transaction."""
    cost_base = (txn.quantity * txn.unit_price + txn.brokerage) * txn.exchange_rate
    cost_per_unit = cost_base / txn.quantity if txn.quantity else Decimal("0")

    return Parcel.objects.create(
        transaction=txn,
        security=txn.security,
        acquisition_date=txn.trade_date,
        original_quantity=txn.quantity,
        remaining_quantity=txn.quantity,
        cost_per_unit_aud=cost_per_unit,
        total_cost_base_aud=cost_base,
    )


@transaction.atomic
def confirm_import(
    file_content: str,
    column_mapping: dict[str, str],
    filename: str,
    source_type: str,
) -> ImportRecord:
    """
    Parse CSV, skip duplicates, create Transactions + Parcels (for BUYs).

    Returns the ImportRecord with row_count set to number of rows created.
    """
    _headers, rows = parse_csv_file(file_content, column_mapping)
    duplicates = find_duplicates(rows)

    import_record = ImportRecord.objects.create(
        filename=filename,
        source_type=source_type,
        column_mapping=column_mapping,
        row_count=0,
    )

    created_count = 0
    for row in rows:
        if not row.is_valid:
            continue
        if row.row_number in duplicates:
            continue

        security = _get_or_create_security(row)

        txn = Transaction.objects.create(
            security=security,
            import_record=import_record,
            trade_date=row.trade_date,
            transaction_type=row.transaction_type,
            quantity=row.quantity,
            unit_price=row.unit_price,
            brokerage=row.brokerage,
            total_value=row.total_value,
            currency=row.currency,
            exchange_rate=row.exchange_rate,
            raw_data=row.raw_data,
        )

        if txn.transaction_type == Transaction.TransactionType.BUY:
            _create_parcel_from_buy(txn)

        created_count += 1

    import_record.row_count = created_count
    import_record.save(update_fields=["row_count"])

    return import_record
