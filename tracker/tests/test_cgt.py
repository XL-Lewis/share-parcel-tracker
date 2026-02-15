"""Tests for CGT calculation service."""

from datetime import date
from decimal import Decimal

from django.test import TestCase

from tracker.models import Parcel, ParcelMatch, Security, Transaction
from tracker.services.cgt import calculate_cgt, fy_summary, get_fy_range


class CalculateCGTTest(TestCase):
    """Tests for calculate_cgt()."""

    def setUp(self):
        self.security = Security.objects.create(
            ticker="BHP.AX",
            exchange=Security.Exchange.ASX,
            currency=Security.Currency.AUD,
        )

    def _make_buy_and_parcel(
        self,
        buy_date=None,
        quantity=Decimal("100"),
        unit_price=Decimal("40.00"),
        brokerage=Decimal("9.50"),
        exchange_rate=Decimal("1"),
    ):
        buy_date = buy_date or date(2024, 1, 10)
        txn = Transaction.objects.create(
            security=self.security,
            trade_date=buy_date,
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
            security=self.security,
            acquisition_date=buy_date,
            original_quantity=quantity,
            remaining_quantity=quantity,
            cost_per_unit_aud=cost_base / quantity,
            total_cost_base_aud=cost_base,
        )
        return txn, parcel

    def _make_sell(
        self,
        sell_date=None,
        quantity=Decimal("50"),
        unit_price=Decimal("55.00"),
        brokerage=Decimal("9.50"),
        exchange_rate=Decimal("1"),
    ):
        sell_date = sell_date or date(2025, 6, 15)
        return Transaction.objects.create(
            security=self.security,
            trade_date=sell_date,
            transaction_type=Transaction.TransactionType.SELL,
            quantity=quantity,
            unit_price=unit_price,
            brokerage=brokerage,
            total_value=quantity * unit_price,
            exchange_rate=exchange_rate,
        )

    def test_discount_eligible_over_365_days(self):
        """Holding > 365 days with positive gain -> discount eligible."""
        _, parcel = self._make_buy_and_parcel(buy_date=date(2024, 1, 10))
        sell = self._make_sell(
            sell_date=date(2025, 6, 15)
        )  # 522 days (2024 is leap year)

        result = calculate_cgt(parcel, sell, Decimal("50"))

        self.assertTrue(result["cgt_discount_eligible"])
        self.assertEqual(result["holding_period_days"], 522)
        self.assertGreater(result["discount_amount"], Decimal("0"))
        # Net = gain - 50% discount
        expected_gain = result["proceeds_aud"] - result["cost_base_aud"]
        expected_discount = expected_gain * Decimal("0.5")
        self.assertEqual(result["discount_amount"], expected_discount)
        self.assertEqual(
            result["net_capital_gain"],
            expected_gain - expected_discount,
        )

    def test_short_term_no_discount(self):
        """Holding <= 365 days -> no discount."""
        _, parcel = self._make_buy_and_parcel(buy_date=date(2025, 1, 10))
        sell = self._make_sell(sell_date=date(2025, 6, 15))  # 156 days

        result = calculate_cgt(parcel, sell, Decimal("50"))

        self.assertFalse(result["cgt_discount_eligible"])
        self.assertEqual(result["discount_amount"], Decimal("0"))
        self.assertEqual(result["net_capital_gain"], result["capital_gain_loss"])

    def test_exact_365_days_no_discount(self):
        """Exactly 365 days = no discount (need > 365)."""
        _, parcel = self._make_buy_and_parcel(buy_date=date(2024, 1, 10))
        sell = self._make_sell(
            sell_date=date(2025, 1, 10)
        )  # exactly 366 days (2024 leap year)

        # Use a non-leap year scenario for exact 365
        _, parcel2 = self._make_buy_and_parcel(
            buy_date=date(2025, 1, 10),
            unit_price=Decimal("30.00"),
        )
        sell2 = self._make_sell(
            sell_date=date(2026, 1, 10),
            unit_price=Decimal("55.00"),
            quantity=Decimal("100"),
        )

        result = calculate_cgt(parcel2, sell2, Decimal("50"))
        self.assertEqual(result["holding_period_days"], 365)
        self.assertFalse(result["cgt_discount_eligible"])
        self.assertEqual(result["discount_amount"], Decimal("0"))

    def test_366_days_discount_eligible(self):
        """366 days -> discount eligible."""
        _, parcel = self._make_buy_and_parcel(buy_date=date(2025, 1, 10))
        sell = self._make_sell(
            sell_date=date(2026, 1, 11),
            unit_price=Decimal("55.00"),
            quantity=Decimal("100"),
        )

        result = calculate_cgt(parcel, sell, Decimal("50"))
        self.assertEqual(result["holding_period_days"], 366)
        self.assertTrue(result["cgt_discount_eligible"])

    def test_loss_no_discount(self):
        """Losses never get a discount even with long holding."""
        _, parcel = self._make_buy_and_parcel(
            buy_date=date(2024, 1, 10),
            unit_price=Decimal("60.00"),
        )
        sell = self._make_sell(
            sell_date=date(2025, 6, 15),
            unit_price=Decimal("30.00"),
        )

        result = calculate_cgt(parcel, sell, Decimal("50"))

        self.assertLess(result["capital_gain_loss"], Decimal("0"))
        self.assertFalse(result["cgt_discount_eligible"])
        self.assertEqual(result["discount_amount"], Decimal("0"))
        self.assertEqual(result["net_capital_gain"], result["capital_gain_loss"])

    def test_aud_conversion(self):
        """USD transactions use exchange_rate for AUD conversion."""
        usd_sec = Security.objects.create(
            ticker="AAPL",
            exchange=Security.Exchange.NASDAQ,
            currency=Security.Currency.USD,
        )
        buy_txn = Transaction.objects.create(
            security=usd_sec,
            trade_date=date(2024, 1, 10),
            transaction_type=Transaction.TransactionType.BUY,
            quantity=Decimal("10"),
            unit_price=Decimal("150.00"),
            brokerage=Decimal("10.00"),
            total_value=Decimal("1500.00"),
            currency="USD",
            exchange_rate=Decimal("1.50"),  # 1 USD = 1.50 AUD
        )
        # Cost base = (10 * 150 + 10) * 1.50 = 2265 AUD
        cost_base = (Decimal("10") * Decimal("150") + Decimal("10")) * Decimal("1.50")
        parcel = Parcel.objects.create(
            transaction=buy_txn,
            security=usd_sec,
            acquisition_date=date(2024, 1, 10),
            original_quantity=Decimal("10"),
            remaining_quantity=Decimal("10"),
            cost_per_unit_aud=cost_base / Decimal("10"),
            total_cost_base_aud=cost_base,
        )

        sell_txn = Transaction.objects.create(
            security=usd_sec,
            trade_date=date(2025, 6, 15),
            transaction_type=Transaction.TransactionType.SELL,
            quantity=Decimal("5"),
            unit_price=Decimal("200.00"),
            brokerage=Decimal("10.00"),
            total_value=Decimal("1000.00"),
            currency="USD",
            exchange_rate=Decimal("1.60"),  # 1 USD = 1.60 AUD
        )

        result = calculate_cgt(parcel, sell_txn, Decimal("5"))

        # cost_base = cost_per_unit_aud * 5 = (2265/10) * 5 = 1132.50
        expected_cost = parcel.cost_per_unit_aud * Decimal("5")
        self.assertEqual(result["cost_base_aud"], expected_cost)

        # proceeds = 200 * 5 * 1.60 = 1600
        expected_proceeds = Decimal("200") * Decimal("5") * Decimal("1.60")
        self.assertEqual(result["proceeds_aud"], expected_proceeds)

    def test_cost_base_calculation(self):
        """Cost base uses parcel's cost_per_unit_aud * matched_quantity."""
        _, parcel = self._make_buy_and_parcel(
            quantity=Decimal("100"),
            unit_price=Decimal("40.00"),
            brokerage=Decimal("9.50"),
        )
        sell = self._make_sell(quantity=Decimal("50"), unit_price=Decimal("55.00"))

        result = calculate_cgt(parcel, sell, Decimal("50"))

        expected_cost = parcel.cost_per_unit_aud * Decimal("50")
        self.assertEqual(result["cost_base_aud"], expected_cost)


class FYRangeTest(TestCase):
    """Tests for get_fy_range()."""

    def test_fy_2025(self):
        start, end = get_fy_range(2025)
        self.assertEqual(start, date(2024, 7, 1))
        self.assertEqual(end, date(2025, 6, 30))

    def test_fy_2024(self):
        start, end = get_fy_range(2024)
        self.assertEqual(start, date(2023, 7, 1))
        self.assertEqual(end, date(2024, 6, 30))


class FYSummaryTest(TestCase):
    """Tests for fy_summary()."""

    _match_counter = 0

    def setUp(self):
        self.security = Security.objects.create(
            ticker="CBA.AX",
            exchange=Security.Exchange.ASX,
            currency=Security.Currency.AUD,
        )

    def _create_match(self, sell_date, gain, discount_eligible=False):
        """Helper to create a match with specific sell date and gain."""
        FYSummaryTest._match_counter += 1
        n = FYSummaryTest._match_counter

        buy_txn = Transaction.objects.create(
            security=self.security,
            trade_date=date(2023, 1, n % 28 + 1),
            transaction_type=Transaction.TransactionType.BUY,
            quantity=Decimal(str(100 + n)),
            unit_price=Decimal("40.00"),
            total_value=Decimal(str((100 + n) * 40)),
        )
        sell_txn = Transaction.objects.create(
            security=self.security,
            trade_date=sell_date,
            transaction_type=Transaction.TransactionType.SELL,
            quantity=Decimal(str(50 + n)),
            unit_price=Decimal("55.00"),
            total_value=Decimal(str((50 + n) * 55)),
        )
        parcel = Parcel.objects.create(
            transaction=buy_txn,
            security=self.security,
            acquisition_date=date(2023, 1, 1),
            original_quantity=Decimal("100"),
            remaining_quantity=Decimal("50"),
            cost_per_unit_aud=Decimal("40.00"),
            total_cost_base_aud=Decimal("4000.00"),
        )
        discount = (
            gain * Decimal("0.5") if discount_eligible and gain > 0 else Decimal("0")
        )
        net = gain - discount
        return ParcelMatch.objects.create(
            parcel=parcel,
            sell_transaction=sell_txn,
            matched_quantity=Decimal("50"),
            cost_base_aud=Decimal("2000"),
            proceeds_aud=Decimal("2000") + gain,
            capital_gain_loss=gain,
            holding_period_days=400 if discount_eligible else 100,
            cgt_discount_eligible=discount_eligible,
            discount_amount=discount,
            net_capital_gain=net,
        )

    def test_fy_aggregation(self):
        """Matches in FY are aggregated correctly."""
        # FY2025 = Jul 1 2024 to Jun 30 2025
        self._create_match(date(2024, 8, 15), Decimal("500"))
        self._create_match(date(2025, 3, 10), Decimal("300"), discount_eligible=True)

        result = fy_summary(2025)

        self.assertEqual(result["financial_year"], 2025)
        self.assertEqual(result["match_count"], 2)
        self.assertEqual(result["total_gains"], Decimal("800"))
        self.assertEqual(result["total_losses"], Decimal("0"))

    def test_fy_boundary_jun_30(self):
        """Sell on Jun 30 falls in the FY ending that date."""
        self._create_match(date(2025, 6, 30), Decimal("100"))

        result = fy_summary(2025)
        self.assertEqual(result["match_count"], 1)

    def test_fy_boundary_jul_1(self):
        """Sell on Jul 1 falls in the *next* FY."""
        self._create_match(date(2025, 7, 1), Decimal("100"))

        # Should NOT be in FY2025
        result_2025 = fy_summary(2025)
        self.assertEqual(result_2025["match_count"], 0)

        # Should be in FY2026
        result_2026 = fy_summary(2026)
        self.assertEqual(result_2026["match_count"], 1)

    def test_empty_fy(self):
        """FY with no matches returns zeroes."""
        result = fy_summary(2025)

        self.assertEqual(result["match_count"], 0)
        self.assertEqual(result["total_gains"], Decimal("0"))
        self.assertEqual(result["total_losses"], Decimal("0"))
        self.assertEqual(result["total_discounts"], Decimal("0"))
        self.assertEqual(result["net_capital_gain"], Decimal("0"))

    def test_losses_tracked_separately(self):
        """Losses and gains tracked separately."""
        self._create_match(date(2024, 8, 15), Decimal("500"))
        self._create_match(date(2024, 12, 1), Decimal("-200"))

        result = fy_summary(2025)

        self.assertEqual(result["total_gains"], Decimal("500"))
        self.assertEqual(result["total_losses"], Decimal("-200"))

    def test_per_security_breakdown(self):
        """Per-security breakdown groups correctly."""
        sec2 = Security.objects.create(
            ticker="WES.AX",
            exchange=Security.Exchange.ASX,
            currency=Security.Currency.AUD,
        )
        self._create_match(date(2024, 8, 15), Decimal("500"))

        # Create a match for the second security
        buy2 = Transaction.objects.create(
            security=sec2,
            trade_date=date(2023, 6, 1),
            transaction_type=Transaction.TransactionType.BUY,
            quantity=Decimal("50"),
            unit_price=Decimal("50.00"),
            total_value=Decimal("2500.00"),
        )
        sell2 = Transaction.objects.create(
            security=sec2,
            trade_date=date(2024, 9, 1),
            transaction_type=Transaction.TransactionType.SELL,
            quantity=Decimal("50"),
            unit_price=Decimal("60.00"),
            total_value=Decimal("3000.00"),
        )
        parcel2 = Parcel.objects.create(
            transaction=buy2,
            security=sec2,
            acquisition_date=date(2023, 6, 1),
            original_quantity=Decimal("50"),
            remaining_quantity=Decimal("0"),
            cost_per_unit_aud=Decimal("50.00"),
            total_cost_base_aud=Decimal("2500.00"),
        )
        ParcelMatch.objects.create(
            parcel=parcel2,
            sell_transaction=sell2,
            matched_quantity=Decimal("50"),
            cost_base_aud=Decimal("2500"),
            proceeds_aud=Decimal("3000"),
            capital_gain_loss=Decimal("500"),
            holding_period_days=458,
            cgt_discount_eligible=True,
            discount_amount=Decimal("250"),
            net_capital_gain=Decimal("250"),
        )

        result = fy_summary(2025)

        self.assertEqual(len(result["per_security"]), 2)
        tickers = [s["ticker"] for s in result["per_security"]]
        self.assertIn("CBA.AX", tickers)
        self.assertIn("WES.AX", tickers)
