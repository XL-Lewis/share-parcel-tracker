"""Tests for CSV import service: parsing, adapters, duplicate detection, confirm."""

from datetime import date
from decimal import Decimal

from django.test import TestCase

from tracker.models import ImportRecord, Parcel, Security, Transaction
from tracker.services.csv_import import (
    SELFWEALTH_MAPPING,
    confirm_import,
    detect_selfwealth,
    find_duplicates,
    get_selfwealth_mapping,
    parse_csv_file,
    preview_import,
)


SELFWEALTH_CSV = """\
Trade Date,Settlement Date,Action,Reference,Code,Name,Units,Average Price,Consideration,Brokerage,Total
2025-03-15,2025-03-17,Buy,REF001,BHP.AX,BHP GROUP LTD,100,45.50,4550.00,9.50,4559.50
2025-03-20,2025-03-22,Sell,REF002,BHP.AX,BHP GROUP LTD,50,48.00,2400.00,9.50,2409.50
2025-04-01,2025-04-03,Buy,REF003,CBA.AX,COMMONWEALTH BANK,10,130.25,1302.50,9.50,1312.00
"""

GENERIC_CSV = """\
Date,Action,Symbol,Shares,Price,Fee,Total,FX Rate,Curr
2025-03-15,B,CBA.AX,200,100.00,9.50,20000.00,1,AUD
2025-03-20,S,CBA.AX,100,110.00,9.50,11000.00,1,AUD
"""

GENERIC_MAPPING = {
    "Date": "trade_date",
    "Action": "transaction_type",
    "Symbol": "ticker",
    "Shares": "quantity",
    "Price": "unit_price",
    "Fee": "brokerage",
    "Total": "total_value",
    "FX Rate": "exchange_rate",
    "Curr": "currency",
}


class SelfWealthDetectionTest(TestCase):
    def test_detect_selfwealth_headers(self):
        headers = [
            "Trade Date",
            "Settlement Date",
            "Action",
            "Reference",
            "Code",
            "Name",
            "Units",
            "Average Price",
            "Consideration",
            "Brokerage",
            "Total",
        ]
        self.assertTrue(detect_selfwealth(headers))

    def test_reject_non_selfwealth_headers(self):
        headers = ["Date", "Type", "Symbol", "Shares"]
        self.assertFalse(detect_selfwealth(headers))

    def test_get_mapping(self):
        mapping = get_selfwealth_mapping()
        self.assertEqual(mapping["Trade Date"], "trade_date")
        self.assertEqual(mapping["Code"], "ticker")


class ParseCSVTest(TestCase):
    def test_parse_selfwealth_csv(self):
        mapping = get_selfwealth_mapping()
        headers, rows = parse_csv_file(SELFWEALTH_CSV, mapping)
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(r.is_valid for r in rows))

        # First row: BUY BHP.AX
        r = rows[0]
        self.assertEqual(r.trade_date, date(2025, 3, 15))
        self.assertEqual(r.transaction_type, "BUY")
        self.assertEqual(r.ticker, "BHP.AX")
        self.assertEqual(r.quantity, Decimal("100"))
        self.assertEqual(r.unit_price, Decimal("45.50"))
        self.assertEqual(r.brokerage, Decimal("9.50"))

    def test_parse_sell_transaction(self):
        mapping = get_selfwealth_mapping()
        _, rows = parse_csv_file(SELFWEALTH_CSV, mapping)
        sell = rows[1]
        self.assertEqual(sell.transaction_type, "SELL")
        self.assertEqual(sell.quantity, Decimal("50"))

    def test_parse_third_row(self):
        mapping = get_selfwealth_mapping()
        _, rows = parse_csv_file(SELFWEALTH_CSV, mapping)
        third = rows[2]
        self.assertEqual(third.ticker, "CBA.AX")
        self.assertEqual(third.transaction_type, "BUY")
        self.assertEqual(third.quantity, Decimal("10"))
        self.assertEqual(third.unit_price, Decimal("130.25"))

    def test_parse_generic_csv(self):
        headers, rows = parse_csv_file(GENERIC_CSV, GENERIC_MAPPING)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r.is_valid for r in rows))
        self.assertEqual(rows[0].transaction_type, "BUY")
        self.assertEqual(rows[1].transaction_type, "SELL")

    def test_parse_date_formats(self):
        csv_data = (
            "Trade Date,Action,Code,Units,Average Price\n15/03/2025,Buy,X.AX,10,1.00\n"
        )
        mapping = get_selfwealth_mapping()
        _, rows = parse_csv_file(csv_data, mapping)
        self.assertEqual(rows[0].trade_date, date(2025, 3, 15))

    def test_missing_required_field(self):
        csv_data = (
            "Trade Date,Action,Code,Units,Average Price\n2025-03-15,Buy,,10,1.00\n"
        )
        mapping = get_selfwealth_mapping()
        _, rows = parse_csv_file(csv_data, mapping)
        self.assertFalse(rows[0].is_valid)
        self.assertTrue(any("ticker" in e for e in rows[0].errors))

    def test_invalid_decimal(self):
        csv_data = (
            "Trade Date,Action,Code,Units,Average Price\n2025-03-15,Buy,X.AX,abc,1.00\n"
        )
        mapping = get_selfwealth_mapping()
        _, rows = parse_csv_file(csv_data, mapping)
        self.assertFalse(rows[0].is_valid)

    def test_invalid_date(self):
        csv_data = (
            "Trade Date,Action,Code,Units,Average Price\n99-99-9999,Buy,X.AX,10,1.00\n"
        )
        mapping = get_selfwealth_mapping()
        _, rows = parse_csv_file(csv_data, mapping)
        self.assertFalse(rows[0].is_valid)

    def test_invalid_transaction_type(self):
        csv_data = (
            "Trade Date,Action,Code,Units,Average Price\n2025-03-15,HOLD,X.AX,10,1.00\n"
        )
        mapping = get_selfwealth_mapping()
        _, rows = parse_csv_file(csv_data, mapping)
        self.assertFalse(rows[0].is_valid)

    def test_currency_symbol_stripped(self):
        csv_data = (
            "Trade Date,Action,Code,Units,Average Price\n2025-03-15,Buy,X.AX,10,$1.50\n"
        )
        mapping = get_selfwealth_mapping()
        _, rows = parse_csv_file(csv_data, mapping)
        self.assertTrue(rows[0].is_valid)
        self.assertEqual(rows[0].unit_price, Decimal("1.50"))

    def test_total_value_computed_when_missing(self):
        csv_data = (
            "Trade Date,Action,Code,Units,Average Price\n2025-03-15,Buy,X.AX,10,5.00\n"
        )
        mapping = get_selfwealth_mapping()
        _, rows = parse_csv_file(csv_data, mapping)
        self.assertEqual(rows[0].total_value, Decimal("50.00"))

    def test_raw_data_preserved(self):
        mapping = get_selfwealth_mapping()
        _, rows = parse_csv_file(SELFWEALTH_CSV, mapping)
        self.assertIn("Trade Date", rows[0].raw_data)
        self.assertEqual(rows[0].raw_data["Code"], "BHP.AX")


class DuplicateDetectionTest(TestCase):
    def test_no_duplicates_on_empty_db(self):
        mapping = get_selfwealth_mapping()
        _, rows = parse_csv_file(SELFWEALTH_CSV, mapping)
        dupes = find_duplicates(rows)
        self.assertEqual(len(dupes), 0)

    def test_detects_existing_duplicate(self):
        sec = Security.objects.create(ticker="BHP.AX", exchange="ASX", currency="AUD")
        Transaction.objects.create(
            security=sec,
            trade_date=date(2025, 3, 15),
            transaction_type="BUY",
            quantity=Decimal("100"),
            unit_price=Decimal("45.50"),
            total_value=Decimal("4550.00"),
        )
        mapping = get_selfwealth_mapping()
        _, rows = parse_csv_file(SELFWEALTH_CSV, mapping)
        dupes = find_duplicates(rows)
        self.assertIn(2, dupes)  # Row 2 is the first data row
        self.assertEqual(len(dupes), 1)


class PreviewImportTest(TestCase):
    def test_preview_counts(self):
        preview = preview_import(SELFWEALTH_CSV, get_selfwealth_mapping())
        self.assertEqual(preview.valid_count, 3)
        self.assertEqual(preview.error_count, 0)
        self.assertEqual(preview.duplicate_count, 0)
        self.assertEqual(preview.new_count, 3)

    def test_preview_with_duplicates(self):
        sec = Security.objects.create(ticker="BHP.AX", exchange="ASX", currency="AUD")
        Transaction.objects.create(
            security=sec,
            trade_date=date(2025, 3, 15),
            transaction_type="BUY",
            quantity=Decimal("100"),
            unit_price=Decimal("45.50"),
            total_value=Decimal("4550.00"),
        )
        preview = preview_import(SELFWEALTH_CSV, get_selfwealth_mapping())
        self.assertEqual(preview.duplicate_count, 1)
        self.assertEqual(preview.new_count, 2)


class ConfirmImportTest(TestCase):
    def test_confirm_creates_transactions(self):
        record = confirm_import(
            SELFWEALTH_CSV,
            get_selfwealth_mapping(),
            "trades.csv",
            ImportRecord.SourceType.SELFWEALTH,
        )
        self.assertEqual(record.row_count, 3)
        self.assertEqual(Transaction.objects.count(), 3)

    def test_confirm_creates_parcels_for_buys(self):
        confirm_import(
            SELFWEALTH_CSV,
            get_selfwealth_mapping(),
            "trades.csv",
            ImportRecord.SourceType.SELFWEALTH,
        )
        # 2 BUY transactions -> 2 parcels
        self.assertEqual(Parcel.objects.count(), 2)

    def test_no_parcel_for_sell(self):
        confirm_import(
            SELFWEALTH_CSV,
            get_selfwealth_mapping(),
            "trades.csv",
            ImportRecord.SourceType.SELFWEALTH,
        )
        sell_txn = Transaction.objects.get(transaction_type="SELL")
        self.assertFalse(hasattr(sell_txn, "parcel") and sell_txn.parcel is not None)

    def test_parcel_cost_base_includes_brokerage(self):
        confirm_import(
            SELFWEALTH_CSV,
            get_selfwealth_mapping(),
            "trades.csv",
            ImportRecord.SourceType.SELFWEALTH,
        )
        parcel = Parcel.objects.get(security__ticker="BHP.AX")
        # cost = (100 * 45.50 + 9.50) * 1 = 4559.50
        self.assertEqual(parcel.total_cost_base_aud, Decimal("4559.50"))

    def test_parcel_cba_cost_base(self):
        confirm_import(
            SELFWEALTH_CSV,
            get_selfwealth_mapping(),
            "trades.csv",
            ImportRecord.SourceType.SELFWEALTH,
        )
        parcel = Parcel.objects.get(security__ticker="CBA.AX")
        # cost = (10 * 130.25 + 9.50) * 1 = 1312.00
        expected = Decimal("10") * Decimal("130.25") + Decimal("9.50")
        self.assertEqual(parcel.total_cost_base_aud, expected)

    def test_parcel_remaining_equals_original(self):
        confirm_import(
            SELFWEALTH_CSV,
            get_selfwealth_mapping(),
            "trades.csv",
            ImportRecord.SourceType.SELFWEALTH,
        )
        for parcel in Parcel.objects.all():
            self.assertEqual(parcel.remaining_quantity, parcel.original_quantity)
            self.assertFalse(parcel.is_fully_matched)

    def test_security_get_or_create(self):
        confirm_import(
            SELFWEALTH_CSV,
            get_selfwealth_mapping(),
            "trades.csv",
            ImportRecord.SourceType.SELFWEALTH,
        )
        # BHP.AX and CBA.AX -- 2 securities
        self.assertEqual(Security.objects.count(), 2)

    def test_import_record_saved(self):
        record = confirm_import(
            SELFWEALTH_CSV,
            get_selfwealth_mapping(),
            "trades.csv",
            ImportRecord.SourceType.SELFWEALTH,
        )
        self.assertEqual(record.filename, "trades.csv")
        self.assertEqual(record.source_type, "SELFWEALTH")
        self.assertIsNotNone(record.pk)

    def test_duplicate_import_skipped(self):
        confirm_import(
            SELFWEALTH_CSV,
            get_selfwealth_mapping(),
            "trades1.csv",
            ImportRecord.SourceType.SELFWEALTH,
        )
        record2 = confirm_import(
            SELFWEALTH_CSV,
            get_selfwealth_mapping(),
            "trades2.csv",
            ImportRecord.SourceType.SELFWEALTH,
        )
        # Second import creates 0 new transactions
        self.assertEqual(record2.row_count, 0)
        self.assertEqual(Transaction.objects.count(), 3)

    def test_generic_csv_import(self):
        record = confirm_import(
            GENERIC_CSV,
            GENERIC_MAPPING,
            "generic.csv",
            ImportRecord.SourceType.GENERIC,
        )
        self.assertEqual(record.row_count, 2)
        self.assertEqual(Transaction.objects.count(), 2)
        # 1 BUY -> 1 parcel
        self.assertEqual(Parcel.objects.count(), 1)

    def test_raw_data_stored_on_transaction(self):
        confirm_import(
            SELFWEALTH_CSV,
            get_selfwealth_mapping(),
            "trades.csv",
            ImportRecord.SourceType.SELFWEALTH,
        )
        txn = Transaction.objects.filter(transaction_type="BUY").first()
        self.assertIn("Code", txn.raw_data)


class CSVImportViewSmokeTest(TestCase):
    """Basic smoke tests for import flow views."""

    def test_upload_page_loads(self):
        response = self.client.get("/import/upload/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Import CSV")

    def test_dashboard_loads(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard")

    def test_transaction_list_loads(self):
        response = self.client.get("/transactions/")
        self.assertEqual(response.status_code, 200)

    def test_mapping_redirect_without_session(self):
        response = self.client.get("/import/mapping/")
        self.assertRedirects(response, "/import/upload/")

    def test_preview_redirect_without_session(self):
        response = self.client.get("/import/preview/")
        self.assertRedirects(response, "/import/upload/")
