"""
End-to-end tests spanning all phases.

These tests verify the full workflow: import -> match -> report -> forecast.
"""

from datetime import date
from decimal import Decimal

from django.test import TestCase

from tracker.models import (
    Parcel,
    ParcelMatch,
    Security,
    Transaction,
)
from tracker.services.cgt import fy_summary
from tracker.services.forecasting import forecast
from tracker.services.matching import MatchingError, confirm_matches, match


class E2ETestBase(TestCase):
    """Base class with helpers for e2e tests."""

    def _create_security(self, ticker="BHP.AX", exchange="ASX", currency="AUD"):
        return Security.objects.create(
            ticker=ticker,
            exchange=exchange,
            currency=currency,
        )

    def _create_buy(
        self,
        security,
        trade_date,
        quantity,
        unit_price,
        brokerage=Decimal("9.50"),
        exchange_rate=Decimal("1"),
    ):
        txn = Transaction.objects.create(
            security=security,
            trade_date=trade_date,
            transaction_type=Transaction.TransactionType.BUY,
            quantity=quantity,
            unit_price=unit_price,
            brokerage=brokerage,
            total_value=quantity * unit_price,
            exchange_rate=exchange_rate,
        )
        cost_base = (quantity * unit_price + brokerage) * exchange_rate
        parcel = Parcel.objects.create(
            transaction=txn,
            security=security,
            acquisition_date=trade_date,
            original_quantity=quantity,
            remaining_quantity=quantity,
            cost_per_unit_aud=cost_base / quantity,
            total_cost_base_aud=cost_base,
        )
        return txn, parcel

    def _create_sell(
        self,
        security,
        trade_date,
        quantity,
        unit_price,
        brokerage=Decimal("9.50"),
        exchange_rate=Decimal("1"),
    ):
        return Transaction.objects.create(
            security=security,
            trade_date=trade_date,
            transaction_type=Transaction.TransactionType.SELL,
            quantity=quantity,
            unit_price=unit_price,
            brokerage=brokerage,
            total_value=quantity * unit_price,
            exchange_rate=exchange_rate,
        )


class E2EMatchAndVerifyTest(E2ETestBase):
    """1. Create buy -> match sell FIFO -> verify ParcelMatch + CGT + remaining_qty."""

    def test_full_match_flow(self):
        sec = self._create_security()
        _, parcel = self._create_buy(
            sec, date(2024, 1, 10), Decimal("100"), Decimal("40.00")
        )
        sell = self._create_sell(
            sec, date(2025, 6, 15), Decimal("50"), Decimal("55.00")
        )

        # Match
        matches = match(sell, strategy="fifo")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].matched_quantity, Decimal("50"))

        # Confirm
        saved = confirm_matches(matches)
        self.assertEqual(len(saved), 1)

        # Verify parcel state
        parcel.refresh_from_db()
        self.assertEqual(parcel.remaining_quantity, Decimal("50"))
        self.assertFalse(parcel.is_fully_matched)

        # Verify CGT
        pm = saved[0]
        self.assertGreater(pm.proceeds_aud, pm.cost_base_aud)
        self.assertTrue(pm.cgt_discount_eligible)  # >365 days
        self.assertGreater(pm.discount_amount, Decimal("0"))

        # Verify in DB
        self.assertEqual(ParcelMatch.objects.count(), 1)


class E2EPartialMatchingTest(E2ETestBase):
    """2. Buy 100, sell 60 (40 remaining), sell 40 (fully matched)."""

    def test_partial_then_full(self):
        sec = self._create_security()
        _, parcel = self._create_buy(
            sec, date(2024, 1, 10), Decimal("100"), Decimal("40.00")
        )

        # First sell: 60 units
        sell1 = self._create_sell(
            sec, date(2025, 6, 15), Decimal("60"), Decimal("55.00")
        )
        matches1 = match(sell1, strategy="fifo")
        confirm_matches(matches1)

        parcel.refresh_from_db()
        self.assertEqual(parcel.remaining_quantity, Decimal("40"))
        self.assertFalse(parcel.is_fully_matched)

        # Second sell: 40 units (completes the parcel)
        sell2 = self._create_sell(
            sec, date(2025, 7, 1), Decimal("40"), Decimal("50.00")
        )
        matches2 = match(sell2, strategy="fifo")
        confirm_matches(matches2)

        parcel.refresh_from_db()
        self.assertEqual(parcel.remaining_quantity, Decimal("0"))
        self.assertTrue(parcel.is_fully_matched)

        self.assertEqual(ParcelMatch.objects.count(), 2)


class E2EMultiSecurityTest(E2ETestBase):
    """3. Multiple securities: independent matching, no cross-contamination."""

    def test_multi_security_isolation(self):
        sec1 = self._create_security("BHP.AX")
        sec2 = self._create_security("CBA.AX")

        _, parcel1 = self._create_buy(
            sec1, date(2024, 1, 10), Decimal("100"), Decimal("40.00")
        )
        _, parcel2 = self._create_buy(
            sec2, date(2024, 2, 15), Decimal("50"), Decimal("80.00")
        )

        sell1 = self._create_sell(
            sec1, date(2025, 6, 15), Decimal("50"), Decimal("55.00")
        )
        sell2 = self._create_sell(
            sec2, date(2025, 6, 15), Decimal("30"), Decimal("90.00")
        )

        # Match sec1
        matches1 = match(sell1, strategy="fifo")
        confirm_matches(matches1)

        # Match sec2
        matches2 = match(sell2, strategy="fifo")
        confirm_matches(matches2)

        # Verify isolation
        parcel1.refresh_from_db()
        parcel2.refresh_from_db()

        self.assertEqual(parcel1.remaining_quantity, Decimal("50"))
        self.assertEqual(parcel2.remaining_quantity, Decimal("20"))

        # Each sell matched to its own security's parcel
        pm1 = ParcelMatch.objects.get(sell_transaction=sell1)
        pm2 = ParcelMatch.objects.get(sell_transaction=sell2)
        self.assertEqual(pm1.parcel.security, sec1)
        self.assertEqual(pm2.parcel.security, sec2)


class E2EInternationalSharesTest(E2ETestBase):
    """4. USD transactions with exchange_rate, verify AUD cost base/proceeds."""

    def test_usd_transactions(self):
        sec = self._create_security("AAPL", "NASDAQ", "USD")
        buy_txn, parcel = self._create_buy(
            sec,
            date(2024, 1, 10),
            Decimal("10"),
            Decimal("150.00"),
            brokerage=Decimal("10.00"),
            exchange_rate=Decimal("1.50"),
        )
        sell = self._create_sell(
            sec,
            date(2025, 6, 15),
            Decimal("5"),
            Decimal("200.00"),
            brokerage=Decimal("10.00"),
            exchange_rate=Decimal("1.60"),
        )

        matches = match(sell, strategy="fifo")
        confirm_matches(matches)

        pm = ParcelMatch.objects.first()

        # Cost base = cost_per_unit_aud * 5
        # cost_per_unit_aud = (10*150 + 10)*1.50 / 10 = 2265/10 = 226.5
        expected_cost = parcel.cost_per_unit_aud * Decimal("5")
        self.assertEqual(pm.cost_base_aud, expected_cost)

        # Proceeds = 200 * 5 * 1.60 = 1600
        expected_proceeds = Decimal("200") * Decimal("5") * Decimal("1.60")
        self.assertEqual(pm.proceeds_aud, expected_proceeds)


class E2EFYReportTest(E2ETestBase):
    """5. FY report accuracy: matches spanning FYs, verify aggregation."""

    def test_fy_report_boundaries(self):
        sec = self._create_security()

        # Match in FY2025 (sell on Aug 15 2024)
        _, p1 = self._create_buy(
            sec, date(2023, 1, 10), Decimal("100"), Decimal("40.00")
        )
        sell1 = self._create_sell(
            sec, date(2024, 8, 15), Decimal("50"), Decimal("55.00")
        )
        m1 = match(sell1, strategy="fifo")
        confirm_matches(m1)

        # Match in FY2026 (sell on Jul 1 2025)
        sell2 = self._create_sell(
            sec, date(2025, 7, 1), Decimal("30"), Decimal("60.00")
        )
        m2 = match(sell2, strategy="fifo")
        confirm_matches(m2)

        # FY2025 summary
        summary_2025 = fy_summary(2025)
        self.assertEqual(summary_2025["match_count"], 1)

        # FY2026 summary
        summary_2026 = fy_summary(2026)
        self.assertEqual(summary_2026["match_count"], 1)

        # Totals don't leak across FYs
        self.assertGreater(summary_2025["total_gains"], Decimal("0"))
        self.assertGreater(summary_2026["total_gains"], Decimal("0"))


class E2EForecastConsistencyTest(E2ETestBase):
    """6. Forecast then execute same match, verify forecast == actual."""

    def test_forecast_matches_actual(self):
        sec = self._create_security()
        _, parcel = self._create_buy(
            sec, date(2024, 1, 10), Decimal("100"), Decimal("40.00")
        )

        # Forecast
        fc = forecast(sec, Decimal("50"), Decimal("55.00"), date(2025, 6, 15))
        fifo_forecast = fc["fifo"]

        # Execute actual match
        sell = self._create_sell(
            sec, date(2025, 6, 15), Decimal("50"), Decimal("55.00")
        )
        matches = match(sell, strategy="fifo")
        confirm_matches(matches)

        pm = ParcelMatch.objects.first()

        # Forecast should match actual
        self.assertEqual(fifo_forecast["total_cost_base"], pm.cost_base_aud)
        self.assertEqual(fifo_forecast["total_proceeds"], pm.proceeds_aud)
        self.assertEqual(fifo_forecast["total_gain_loss"], pm.capital_gain_loss)
        self.assertEqual(fifo_forecast["total_discount"], pm.discount_amount)
        self.assertEqual(fifo_forecast["total_net_gain"], pm.net_capital_gain)


class E2EDuplicateImportTest(E2ETestBase):
    """7. Duplicate import rejection: same transaction twice, no duplicates."""

    def test_duplicate_rejection(self):
        sec = self._create_security()

        # First transaction
        txn1 = Transaction.objects.create(
            security=sec,
            trade_date=date(2024, 1, 10),
            transaction_type=Transaction.TransactionType.BUY,
            quantity=Decimal("100"),
            unit_price=Decimal("40.00"),
            total_value=Decimal("4000.00"),
        )

        # Attempt duplicate (same trade_date, security, type, quantity, unit_price)
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            Transaction.objects.create(
                security=sec,
                trade_date=date(2024, 1, 10),
                transaction_type=Transaction.TransactionType.BUY,
                quantity=Decimal("100"),
                unit_price=Decimal("40.00"),
                total_value=Decimal("4000.00"),
            )


class E2EEdgeCasesTest(E2ETestBase):
    """8. Edge cases: zero brokerage, single-unit, same-day, 365-day boundary."""

    def test_zero_brokerage(self):
        """Zero brokerage should work without errors."""
        sec = self._create_security()
        _, parcel = self._create_buy(
            sec,
            date(2024, 1, 10),
            Decimal("100"),
            Decimal("40.00"),
            brokerage=Decimal("0"),
        )
        sell = self._create_sell(
            sec,
            date(2025, 6, 15),
            Decimal("50"),
            Decimal("55.00"),
            brokerage=Decimal("0"),
        )
        matches = match(sell, strategy="fifo")
        saved = confirm_matches(matches)
        self.assertEqual(len(saved), 1)

    def test_single_unit_parcel(self):
        """Single-unit parcel can be matched."""
        sec = self._create_security()
        _, parcel = self._create_buy(
            sec, date(2024, 1, 10), Decimal("1"), Decimal("100.00")
        )
        sell = self._create_sell(
            sec, date(2025, 6, 15), Decimal("1"), Decimal("150.00")
        )
        matches = match(sell, strategy="fifo")
        saved = confirm_matches(matches)

        parcel.refresh_from_db()
        self.assertEqual(parcel.remaining_quantity, Decimal("0"))
        self.assertTrue(parcel.is_fully_matched)

    def test_same_day_buy_sell(self):
        """Buy and sell on the same day (0 holding days, no discount)."""
        sec = self._create_security()
        _, parcel = self._create_buy(
            sec, date(2025, 3, 15), Decimal("100"), Decimal("40.00")
        )
        sell = self._create_sell(
            sec, date(2025, 3, 15), Decimal("50"), Decimal("55.00")
        )

        matches = match(sell, strategy="fifo")
        saved = confirm_matches(matches)

        pm = saved[0]
        self.assertEqual(pm.holding_period_days, 0)
        self.assertFalse(pm.cgt_discount_eligible)
        self.assertEqual(pm.discount_amount, Decimal("0"))

    def test_exact_365_days_no_discount(self):
        """Exactly 365 days = no discount (need > 365)."""
        sec = self._create_security()
        _, parcel = self._create_buy(
            sec, date(2025, 1, 10), Decimal("100"), Decimal("40.00")
        )
        # 365 days later (2025 is not leap year)
        sell = self._create_sell(
            sec, date(2026, 1, 10), Decimal("50"), Decimal("55.00")
        )

        matches = match(sell, strategy="fifo")
        saved = confirm_matches(matches)

        pm = saved[0]
        self.assertEqual(pm.holding_period_days, 365)
        self.assertFalse(pm.cgt_discount_eligible)

    def test_366_days_gets_discount(self):
        """366 days = discount eligible."""
        sec = self._create_security()
        _, parcel = self._create_buy(
            sec, date(2025, 1, 10), Decimal("100"), Decimal("40.00")
        )
        sell = self._create_sell(
            sec, date(2026, 1, 11), Decimal("50"), Decimal("55.00")
        )

        matches = match(sell, strategy="fifo")
        saved = confirm_matches(matches)

        pm = saved[0]
        self.assertEqual(pm.holding_period_days, 366)
        self.assertTrue(pm.cgt_discount_eligible)
        self.assertGreater(pm.discount_amount, Decimal("0"))

    def test_over_match_rejected(self):
        """Cannot match more than available."""
        sec = self._create_security()
        _, parcel = self._create_buy(
            sec, date(2024, 1, 10), Decimal("50"), Decimal("40.00")
        )
        sell = self._create_sell(
            sec, date(2025, 6, 15), Decimal("100"), Decimal("55.00")
        )

        with self.assertRaises(MatchingError):
            match(sell, strategy="fifo")
