"""Tests for tracker models: creation, constraints, __str__, relationships."""

from datetime import date
from decimal import Decimal

from django.db import IntegrityError
from django.test import TestCase

from tracker.models import (
    ImportRecord,
    Parcel,
    ParcelMatch,
    Security,
    Transaction,
)


class SecurityModelTest(TestCase):
    def test_create_security(self):
        sec = Security.objects.create(
            ticker="BHP.AX",
            name="BHP Group",
            exchange=Security.Exchange.ASX,
            currency=Security.Currency.AUD,
            asset_type=Security.AssetType.SHARE,
        )
        self.assertEqual(str(sec), "BHP.AX")
        self.assertEqual(sec.exchange, "ASX")

    def test_ticker_unique(self):
        Security.objects.create(
            ticker="BHP.AX",
            exchange=Security.Exchange.ASX,
            currency=Security.Currency.AUD,
        )
        with self.assertRaises(IntegrityError):
            Security.objects.create(
                ticker="BHP.AX",
                exchange=Security.Exchange.ASX,
                currency=Security.Currency.AUD,
            )

    def test_default_asset_type(self):
        sec = Security.objects.create(
            ticker="CBA.AX",
            exchange=Security.Exchange.ASX,
            currency=Security.Currency.AUD,
        )
        self.assertEqual(sec.asset_type, Security.AssetType.SHARE)

    def test_ordering(self):
        Security.objects.create(ticker="ZZZ.AX", exchange="ASX", currency="AUD")
        Security.objects.create(ticker="AAA.AX", exchange="ASX", currency="AUD")
        tickers = list(Security.objects.values_list("ticker", flat=True))
        self.assertEqual(tickers, ["AAA.AX", "ZZZ.AX"])


class ImportRecordModelTest(TestCase):
    def test_create_import_record(self):
        rec = ImportRecord.objects.create(
            filename="trades.csv",
            source_type=ImportRecord.SourceType.SELFWEALTH,
            row_count=10,
        )
        self.assertIn("trades.csv", str(rec))
        self.assertIsNotNone(rec.imported_at)

    def test_default_column_mapping(self):
        rec = ImportRecord.objects.create(
            filename="test.csv",
            source_type=ImportRecord.SourceType.GENERIC,
        )
        self.assertEqual(rec.column_mapping, {})


class TransactionModelTest(TestCase):
    def setUp(self):
        self.security = Security.objects.create(
            ticker="BHP.AX",
            exchange=Security.Exchange.ASX,
            currency=Security.Currency.AUD,
        )

    def _make_txn(self, **kwargs):
        defaults = {
            "security": self.security,
            "trade_date": date(2025, 3, 15),
            "transaction_type": Transaction.TransactionType.BUY,
            "quantity": Decimal("100"),
            "unit_price": Decimal("45.50"),
            "brokerage": Decimal("9.50"),
            "total_value": Decimal("4550.00"),
        }
        defaults.update(kwargs)
        return Transaction.objects.create(**defaults)

    def test_create_transaction(self):
        txn = self._make_txn()
        self.assertIn("BUY", str(txn))
        self.assertIn("BHP.AX", str(txn))

    def test_default_exchange_rate(self):
        txn = self._make_txn()
        self.assertEqual(txn.exchange_rate, Decimal("1"))

    def test_default_currency(self):
        txn = self._make_txn()
        self.assertEqual(txn.currency, "AUD")

    def test_duplicate_constraint(self):
        self._make_txn()
        with self.assertRaises(IntegrityError):
            self._make_txn()

    def test_different_date_not_duplicate(self):
        self._make_txn()
        txn2 = self._make_txn(trade_date=date(2025, 3, 16))
        self.assertIsNotNone(txn2.pk)

    def test_different_type_not_duplicate(self):
        self._make_txn()
        txn2 = self._make_txn(transaction_type=Transaction.TransactionType.SELL)
        self.assertIsNotNone(txn2.pk)

    def test_raw_data_default(self):
        txn = self._make_txn()
        self.assertEqual(txn.raw_data, {})

    def test_ordering_by_trade_date_desc(self):
        self._make_txn(trade_date=date(2025, 1, 1))
        self._make_txn(trade_date=date(2025, 6, 1))
        dates = list(Transaction.objects.values_list("trade_date", flat=True))
        self.assertEqual(dates, [date(2025, 6, 1), date(2025, 1, 1)])


class ParcelModelTest(TestCase):
    def setUp(self):
        self.security = Security.objects.create(
            ticker="CBA.AX",
            exchange=Security.Exchange.ASX,
            currency=Security.Currency.AUD,
        )
        self.buy_txn = Transaction.objects.create(
            security=self.security,
            trade_date=date(2024, 6, 15),
            transaction_type=Transaction.TransactionType.BUY,
            quantity=Decimal("200"),
            unit_price=Decimal("100.00"),
            total_value=Decimal("20000.00"),
            brokerage=Decimal("9.50"),
        )

    def _make_parcel(self, **kwargs):
        defaults = {
            "transaction": self.buy_txn,
            "security": self.security,
            "acquisition_date": date(2024, 6, 15),
            "original_quantity": Decimal("200"),
            "remaining_quantity": Decimal("200"),
            "cost_per_unit_aud": Decimal("100.0475"),
            "total_cost_base_aud": Decimal("20009.50"),
        }
        defaults.update(kwargs)
        return Parcel.objects.create(**defaults)

    def test_create_parcel(self):
        parcel = self._make_parcel()
        self.assertIn("CBA.AX", str(parcel))
        self.assertIn("200", str(parcel))
        self.assertFalse(parcel.is_fully_matched)

    def test_parcel_ordering(self):
        # Need a second buy transaction for a second parcel
        buy2 = Transaction.objects.create(
            security=self.security,
            trade_date=date(2024, 1, 1),
            transaction_type=Transaction.TransactionType.BUY,
            quantity=Decimal("50"),
            unit_price=Decimal("95.00"),
            total_value=Decimal("4750.00"),
        )
        p1 = self._make_parcel()
        p2 = Parcel.objects.create(
            transaction=buy2,
            security=self.security,
            acquisition_date=date(2024, 1, 1),
            original_quantity=Decimal("50"),
            remaining_quantity=Decimal("50"),
            cost_per_unit_aud=Decimal("95.00"),
            total_cost_base_aud=Decimal("4750.00"),
        )
        parcels = list(Parcel.objects.all())
        # Ordered by acquisition_date ASC
        self.assertEqual(parcels[0], p2)
        self.assertEqual(parcels[1], p1)


class ParcelMatchModelTest(TestCase):
    def setUp(self):
        self.security = Security.objects.create(
            ticker="BHP.AX",
            exchange=Security.Exchange.ASX,
            currency=Security.Currency.AUD,
        )
        self.buy_txn = Transaction.objects.create(
            security=self.security,
            trade_date=date(2024, 1, 10),
            transaction_type=Transaction.TransactionType.BUY,
            quantity=Decimal("100"),
            unit_price=Decimal("40.00"),
            total_value=Decimal("4000.00"),
            brokerage=Decimal("9.50"),
        )
        self.sell_txn = Transaction.objects.create(
            security=self.security,
            trade_date=date(2025, 6, 15),
            transaction_type=Transaction.TransactionType.SELL,
            quantity=Decimal("50"),
            unit_price=Decimal("55.00"),
            total_value=Decimal("2750.00"),
            brokerage=Decimal("9.50"),
        )
        self.parcel = Parcel.objects.create(
            transaction=self.buy_txn,
            security=self.security,
            acquisition_date=date(2024, 1, 10),
            original_quantity=Decimal("100"),
            remaining_quantity=Decimal("100"),
            cost_per_unit_aud=Decimal("40.095"),
            total_cost_base_aud=Decimal("4009.50"),
        )

    def test_create_match(self):
        match = ParcelMatch.objects.create(
            parcel=self.parcel,
            sell_transaction=self.sell_txn,
            matched_quantity=Decimal("50"),
            cost_base_aud=Decimal("2004.75"),
            proceeds_aud=Decimal("2740.50"),
            capital_gain_loss=Decimal("735.75"),
            holding_period_days=521,
            cgt_discount_eligible=True,
            discount_amount=Decimal("367.875"),
            net_capital_gain=Decimal("367.875"),
        )
        self.assertIn("BHP.AX", str(match))
        self.assertTrue(match.cgt_discount_eligible)

    def test_match_relationships(self):
        match = ParcelMatch.objects.create(
            parcel=self.parcel,
            sell_transaction=self.sell_txn,
            matched_quantity=Decimal("50"),
            cost_base_aud=Decimal("2004.75"),
            proceeds_aud=Decimal("2740.50"),
            capital_gain_loss=Decimal("735.75"),
            holding_period_days=521,
            cgt_discount_eligible=True,
            discount_amount=Decimal("367.875"),
            net_capital_gain=Decimal("367.875"),
        )
        # Parcel -> matches
        self.assertEqual(self.parcel.matches.count(), 1)
        # Sell transaction -> parcel_matches
        self.assertEqual(self.sell_txn.parcel_matches.count(), 1)
