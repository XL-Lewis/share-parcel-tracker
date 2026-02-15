"""Tests for the forecasting service."""

from datetime import date
from decimal import Decimal

from django.test import TestCase

from tracker.models import Parcel, Security, Transaction
from tracker.services.forecasting import ForecastError, forecast


class ForecastTestBase(TestCase):
    """Base class with helpers for forecast tests."""

    def setUp(self):
        self.security = Security.objects.create(
            ticker="BHP.AX",
            exchange=Security.Exchange.ASX,
            currency=Security.Currency.AUD,
        )

    def _make_parcel(
        self,
        buy_date,
        quantity=Decimal("100"),
        unit_price=Decimal("40.00"),
        brokerage=Decimal("9.50"),
    ):
        """Create a buy transaction and associated parcel."""
        txn = Transaction.objects.create(
            security=self.security,
            trade_date=buy_date,
            transaction_type=Transaction.TransactionType.BUY,
            quantity=quantity,
            unit_price=unit_price,
            brokerage=brokerage,
            total_value=quantity * unit_price,
        )
        cost_base = quantity * unit_price + brokerage
        return Parcel.objects.create(
            transaction=txn,
            security=self.security,
            acquisition_date=buy_date,
            original_quantity=quantity,
            remaining_quantity=quantity,
            cost_per_unit_aud=cost_base / quantity,
            total_cost_base_aud=cost_base,
        )


class ForecastBasicTest(ForecastTestBase):
    """Basic forecast functionality tests."""

    def test_forecast_returns_three_strategies(self):
        """Forecast should return fifo, lifo, and optimal results."""
        self._make_parcel(date(2024, 1, 10))
        result = forecast(
            self.security, Decimal("50"), Decimal("55.00"), date(2025, 6, 15)
        )

        self.assertIn("fifo", result)
        self.assertIn("lifo", result)
        self.assertIn("optimal", result)
        self.assertEqual(result["security"], self.security)
        self.assertEqual(result["quantity"], Decimal("50"))

    def test_forecast_no_db_writes(self):
        """Forecast should not create any ParcelMatch records."""
        from tracker.models import ParcelMatch

        parcel = self._make_parcel(date(2024, 1, 10))
        initial_remaining = parcel.remaining_quantity
        initial_match_count = ParcelMatch.objects.count()

        forecast(self.security, Decimal("50"), Decimal("55.00"), date(2025, 6, 15))

        parcel.refresh_from_db()
        self.assertEqual(parcel.remaining_quantity, initial_remaining)
        self.assertEqual(ParcelMatch.objects.count(), initial_match_count)

    def test_forecast_default_sell_date_is_today(self):
        """Forecast with no sell_date should default to today."""
        self._make_parcel(date(2024, 1, 10))
        result = forecast(self.security, Decimal("50"), Decimal("55.00"))
        self.assertEqual(result["sell_date"], date.today())


class ForecastMixedDiscountTest(ForecastTestBase):
    """Test forecast with mixed discount/non-discount parcels."""

    def setUp(self):
        super().setUp()
        # Old parcel (discount-eligible when sold >365 days later)
        self.old_parcel = self._make_parcel(
            date(2023, 1, 10),
            quantity=Decimal("100"),
            unit_price=Decimal("30.00"),
            brokerage=Decimal("10.00"),
        )
        # Recent parcel (no discount)
        self.new_parcel = self._make_parcel(
            date(2025, 1, 10),
            quantity=Decimal("100"),
            unit_price=Decimal("50.00"),
            brokerage=Decimal("10.00"),
        )

    def test_fifo_uses_oldest_first(self):
        """FIFO should consume the older parcel first."""
        result = forecast(
            self.security, Decimal("50"), Decimal("55.00"), date(2025, 6, 15)
        )

        fifo = result["fifo"]
        self.assertEqual(len(fifo["parcels_consumed"]), 1)
        self.assertEqual(
            fifo["parcels_consumed"][0]["acquisition_date"], date(2023, 1, 10)
        )

    def test_lifo_uses_newest_first(self):
        """LIFO should consume the newer parcel first."""
        result = forecast(
            self.security, Decimal("50"), Decimal("55.00"), date(2025, 6, 15)
        )

        lifo = result["lifo"]
        self.assertEqual(len(lifo["parcels_consumed"]), 1)
        self.assertEqual(
            lifo["parcels_consumed"][0]["acquisition_date"], date(2025, 1, 10)
        )

    def test_optimal_uses_highest_cost_first(self):
        """Optimal should consume the highest cost-per-unit parcel first."""
        result = forecast(
            self.security, Decimal("50"), Decimal("55.00"), date(2025, 6, 15)
        )

        optimal = result["optimal"]
        # New parcel has higher cost ($50.10/unit) vs old ($30.10/unit)
        self.assertEqual(len(optimal["parcels_consumed"]), 1)
        self.assertEqual(
            optimal["parcels_consumed"][0]["acquisition_date"], date(2025, 1, 10)
        )

    def test_optimal_minimises_gain(self):
        """Optimal strategy should produce the lowest net capital gain."""
        result = forecast(
            self.security, Decimal("50"), Decimal("55.00"), date(2025, 6, 15)
        )

        # Optimal picks highest cost => smallest gain
        self.assertLessEqual(
            result["optimal"]["total_net_gain"],
            result["fifo"]["total_net_gain"],
        )

    def test_mixed_parcels_discount_eligibility(self):
        """Old parcels should be discount-eligible, new ones not."""
        result = forecast(
            self.security, Decimal("50"), Decimal("55.00"), date(2025, 6, 15)
        )

        # FIFO uses old parcel -> discount eligible (>365 days)
        fifo_consumed = result["fifo"]["parcels_consumed"][0]
        self.assertTrue(fifo_consumed["cgt_discount_eligible"])

        # LIFO uses new parcel -> not discount eligible (<365 days)
        lifo_consumed = result["lifo"]["parcels_consumed"][0]
        self.assertFalse(lifo_consumed["cgt_discount_eligible"])

    def test_multi_parcel_consumption(self):
        """Forecast consuming across multiple parcels."""
        result = forecast(
            self.security, Decimal("150"), Decimal("55.00"), date(2025, 6, 15)
        )

        # FIFO: old (100) + new (50)
        fifo = result["fifo"]
        self.assertEqual(len(fifo["parcels_consumed"]), 2)
        self.assertEqual(fifo["quantity_matched"], Decimal("150"))


class ForecastEdgeCasesTest(ForecastTestBase):
    """Edge case tests for forecasting."""

    def test_no_parcels_raises_error(self):
        """Forecast with no parcels should raise ForecastError."""
        with self.assertRaises(ForecastError) as ctx:
            forecast(self.security, Decimal("50"), Decimal("55.00"))
        self.assertIn("No available parcels", str(ctx.exception))

    def test_insufficient_quantity_raises_error(self):
        """Forecast requesting more than available should raise."""
        self._make_parcel(date(2024, 1, 10), quantity=Decimal("50"))

        with self.assertRaises(ForecastError) as ctx:
            forecast(self.security, Decimal("100"), Decimal("55.00"))
        self.assertIn("Insufficient parcels", str(ctx.exception))

    def test_zero_quantity_raises_error(self):
        """Quantity must be positive."""
        self._make_parcel(date(2024, 1, 10))
        with self.assertRaises(ForecastError):
            forecast(self.security, Decimal("0"), Decimal("55.00"))

    def test_negative_quantity_raises_error(self):
        """Quantity must be positive."""
        self._make_parcel(date(2024, 1, 10))
        with self.assertRaises(ForecastError):
            forecast(self.security, Decimal("-10"), Decimal("55.00"))

    def test_zero_price_raises_error(self):
        """Sell price must be positive."""
        self._make_parcel(date(2024, 1, 10))
        with self.assertRaises(ForecastError):
            forecast(self.security, Decimal("50"), Decimal("0"))

    def test_fully_matched_parcels_excluded(self):
        """Fully matched parcels (remaining_quantity=0) should not be used."""
        parcel = self._make_parcel(date(2024, 1, 10))
        parcel.remaining_quantity = Decimal("0")
        parcel.is_fully_matched = True
        parcel.save()

        with self.assertRaises(ForecastError):
            forecast(self.security, Decimal("50"), Decimal("55.00"))

    def test_exact_quantity_match(self):
        """Selling exactly the available quantity should work."""
        self._make_parcel(date(2024, 1, 10), quantity=Decimal("50"))

        result = forecast(
            self.security, Decimal("50"), Decimal("55.00"), date(2025, 6, 15)
        )
        self.assertEqual(result["fifo"]["quantity_matched"], Decimal("50"))
        self.assertEqual(result["fifo"]["quantity_shortfall"], Decimal("0"))


class ForecastCGTCalculationTest(ForecastTestBase):
    """Verify CGT calculations within forecast."""

    def test_proceeds_calculation(self):
        """Proceeds = sell_price * quantity."""
        self._make_parcel(date(2024, 1, 10), quantity=Decimal("100"))

        result = forecast(
            self.security, Decimal("50"), Decimal("55.00"), date(2025, 6, 15)
        )

        expected_proceeds = Decimal("55.00") * Decimal("50")
        self.assertEqual(result["fifo"]["total_proceeds"], expected_proceeds)

    def test_cost_base_calculation(self):
        """Cost base = cost_per_unit_aud * matched_quantity."""
        parcel = self._make_parcel(
            date(2024, 1, 10),
            quantity=Decimal("100"),
            unit_price=Decimal("40.00"),
            brokerage=Decimal("10.00"),
        )

        result = forecast(
            self.security, Decimal("50"), Decimal("55.00"), date(2025, 6, 15)
        )

        expected_cost = parcel.cost_per_unit_aud * Decimal("50")
        self.assertEqual(result["fifo"]["total_cost_base"], expected_cost)

    def test_gain_loss_calculation(self):
        """Gain = proceeds - cost_base."""
        self._make_parcel(date(2024, 1, 10))

        result = forecast(
            self.security, Decimal("50"), Decimal("55.00"), date(2025, 6, 15)
        )

        fifo = result["fifo"]
        expected_gain = fifo["total_proceeds"] - fifo["total_cost_base"]
        self.assertEqual(fifo["total_gain_loss"], expected_gain)
