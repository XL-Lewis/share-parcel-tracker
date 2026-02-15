"""Tests for the parcel matching engine."""

from datetime import date
from decimal import Decimal

from django.test import TestCase

from tracker.models import Parcel, ParcelMatch, Security, Transaction
from tracker.services.matching import MatchingError, confirm_matches, match


class MatchingTestBase(TestCase):
    """Base class with helper methods for matching tests."""

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
        )
        cost_base = quantity * unit_price + brokerage
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

    def _make_sell(self, sell_date=None, quantity=Decimal("50")):
        sell_date = sell_date or date(2025, 6, 15)
        return Transaction.objects.create(
            security=self.security,
            trade_date=sell_date,
            transaction_type=Transaction.TransactionType.SELL,
            quantity=quantity,
            unit_price=Decimal("55.00"),
            total_value=quantity * Decimal("55.00"),
        )


class FIFOMatchingTest(MatchingTestBase):
    """Tests for FIFO matching strategy."""

    def test_fifo_ordering(self):
        """FIFO matches oldest parcels first."""
        _, p1 = self._make_buy_and_parcel(buy_date=date(2024, 1, 1))
        _, p2 = self._make_buy_and_parcel(
            buy_date=date(2024, 6, 1), unit_price=Decimal("45.00")
        )
        sell = self._make_sell(quantity=Decimal("50"))

        matches = match(sell, strategy="fifo")

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].parcel_id, p1.pk)
        self.assertEqual(matches[0].matched_quantity, Decimal("50"))

    def test_fifo_spans_multiple_parcels(self):
        """FIFO spans multiple parcels when first isn't enough."""
        _, p1 = self._make_buy_and_parcel(
            buy_date=date(2024, 1, 1), quantity=Decimal("30")
        )
        _, p2 = self._make_buy_and_parcel(
            buy_date=date(2024, 6, 1),
            quantity=Decimal("50"),
            unit_price=Decimal("45.00"),
        )
        sell = self._make_sell(quantity=Decimal("60"))

        matches = match(sell, strategy="fifo")

        self.assertEqual(len(matches), 2)
        self.assertEqual(matches[0].parcel_id, p1.pk)
        self.assertEqual(matches[0].matched_quantity, Decimal("30"))
        self.assertEqual(matches[1].parcel_id, p2.pk)
        self.assertEqual(matches[1].matched_quantity, Decimal("30"))


class LIFOMatchingTest(MatchingTestBase):
    """Tests for LIFO matching strategy."""

    def test_lifo_ordering(self):
        """LIFO matches newest parcels first."""
        _, p1 = self._make_buy_and_parcel(buy_date=date(2024, 1, 1))
        _, p2 = self._make_buy_and_parcel(
            buy_date=date(2024, 6, 1), unit_price=Decimal("45.00")
        )
        sell = self._make_sell(quantity=Decimal("50"))

        matches = match(sell, strategy="lifo")

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].parcel_id, p2.pk)

    def test_lifo_spans_multiple_parcels(self):
        """LIFO spans parcels newest-first."""
        _, p1 = self._make_buy_and_parcel(
            buy_date=date(2024, 1, 1), quantity=Decimal("50")
        )
        _, p2 = self._make_buy_and_parcel(
            buy_date=date(2024, 6, 1),
            quantity=Decimal("30"),
            unit_price=Decimal("45.00"),
        )
        sell = self._make_sell(quantity=Decimal("60"))

        matches = match(sell, strategy="lifo")

        self.assertEqual(len(matches), 2)
        # Newest first
        self.assertEqual(matches[0].parcel_id, p2.pk)
        self.assertEqual(matches[0].matched_quantity, Decimal("30"))
        self.assertEqual(matches[1].parcel_id, p1.pk)
        self.assertEqual(matches[1].matched_quantity, Decimal("30"))


class ManualMatchingTest(MatchingTestBase):
    """Tests for manual matching strategy."""

    def test_manual_matching(self):
        """Manual matching with explicit parcel/quantity pairs."""
        _, p1 = self._make_buy_and_parcel(buy_date=date(2024, 1, 1))
        _, p2 = self._make_buy_and_parcel(
            buy_date=date(2024, 6, 1), unit_price=Decimal("45.00")
        )
        sell = self._make_sell(quantity=Decimal("50"))

        matches = match(
            sell,
            strategy="manual",
            parcels=[p1, p2],
            quantities=[Decimal("20"), Decimal("30")],
        )

        self.assertEqual(len(matches), 2)
        self.assertEqual(matches[0].matched_quantity, Decimal("20"))
        self.assertEqual(matches[1].matched_quantity, Decimal("30"))

    def test_manual_requires_parcels_and_quantities(self):
        """Manual matching raises error without parcels/quantities."""
        sell = self._make_sell()

        with self.assertRaises(MatchingError):
            match(sell, strategy="manual")

    def test_manual_mismatched_lengths(self):
        """Manual matching raises error with mismatched lengths."""
        _, p1 = self._make_buy_and_parcel()
        sell = self._make_sell()

        with self.assertRaises(MatchingError):
            match(
                sell,
                strategy="manual",
                parcels=[p1],
                quantities=[Decimal("25"), Decimal("25")],
            )


class PartialMatchingTest(MatchingTestBase):
    """Tests for partial matching scenarios."""

    def test_partial_then_full(self):
        """Buy 100, sell 60 (40 remaining), then sell 40 (fully matched)."""
        _, parcel = self._make_buy_and_parcel(quantity=Decimal("100"))
        sell1 = self._make_sell(quantity=Decimal("60"), sell_date=date(2025, 3, 1))

        matches1 = match(sell1, strategy="fifo")
        self.assertEqual(len(matches1), 1)
        self.assertEqual(matches1[0].matched_quantity, Decimal("60"))

        # Confirm first match
        saved1 = confirm_matches(matches1)
        parcel.refresh_from_db()
        self.assertEqual(parcel.remaining_quantity, Decimal("40"))
        self.assertFalse(parcel.is_fully_matched)

        # Sell remaining 40
        sell2 = self._make_sell(quantity=Decimal("40"), sell_date=date(2025, 6, 1))
        matches2 = match(sell2, strategy="fifo")
        saved2 = confirm_matches(matches2)

        parcel.refresh_from_db()
        self.assertEqual(parcel.remaining_quantity, Decimal("0"))
        self.assertTrue(parcel.is_fully_matched)


class MatchValidationTest(MatchingTestBase):
    """Tests for matching validation."""

    def test_over_match_rejection(self):
        """Cannot match more than available."""
        _, parcel = self._make_buy_and_parcel(quantity=Decimal("50"))
        sell = self._make_sell(quantity=Decimal("100"))

        with self.assertRaises(MatchingError) as ctx:
            match(sell, strategy="fifo")

        self.assertIn("Insufficient", str(ctx.exception))

    def test_manual_over_parcel_qty(self):
        """Cannot match more than parcel's remaining quantity."""
        _, parcel = self._make_buy_and_parcel(quantity=Decimal("30"))
        sell = self._make_sell(quantity=Decimal("50"))

        with self.assertRaises(MatchingError):
            match(
                sell,
                strategy="manual",
                parcels=[parcel],
                quantities=[Decimal("50")],
            )

    def test_manual_total_mismatch(self):
        """Total matched qty must equal sell qty."""
        _, parcel = self._make_buy_and_parcel(quantity=Decimal("100"))
        sell = self._make_sell(quantity=Decimal("50"))

        with self.assertRaises(MatchingError) as ctx:
            match(
                sell,
                strategy="manual",
                parcels=[parcel],
                quantities=[Decimal("30")],
            )

        self.assertIn("does not equal", str(ctx.exception))

    def test_sell_transaction_required(self):
        """Only SELL transactions can be matched."""
        buy_txn, _ = self._make_buy_and_parcel()

        with self.assertRaises(MatchingError):
            match(buy_txn, strategy="fifo")

    def test_cross_security_rejection(self):
        """Cannot match parcels from different securities."""
        other_sec = Security.objects.create(
            ticker="CBA.AX",
            exchange=Security.Exchange.ASX,
            currency=Security.Currency.AUD,
        )
        buy_txn = Transaction.objects.create(
            security=other_sec,
            trade_date=date(2024, 1, 1),
            transaction_type=Transaction.TransactionType.BUY,
            quantity=Decimal("50"),
            unit_price=Decimal("100.00"),
            total_value=Decimal("5000.00"),
        )
        other_parcel = Parcel.objects.create(
            transaction=buy_txn,
            security=other_sec,
            acquisition_date=date(2024, 1, 1),
            original_quantity=Decimal("50"),
            remaining_quantity=Decimal("50"),
            cost_per_unit_aud=Decimal("100.00"),
            total_cost_base_aud=Decimal("5000.00"),
        )

        sell = self._make_sell(quantity=Decimal("50"))

        with self.assertRaises(MatchingError) as ctx:
            match(
                sell,
                strategy="manual",
                parcels=[other_parcel],
                quantities=[Decimal("50")],
            )
        self.assertIn("different security", str(ctx.exception))


class ConfirmMatchesTest(MatchingTestBase):
    """Tests for confirm_matches()."""

    def test_remaining_quantity_updated(self):
        """confirm_matches decrements remaining_quantity."""
        _, parcel = self._make_buy_and_parcel(quantity=Decimal("100"))
        sell = self._make_sell(quantity=Decimal("60"))

        matches = match(sell, strategy="fifo")
        saved = confirm_matches(matches)

        parcel.refresh_from_db()
        self.assertEqual(parcel.remaining_quantity, Decimal("40"))

    def test_is_fully_matched_flag(self):
        """is_fully_matched set when remaining_quantity reaches zero."""
        _, parcel = self._make_buy_and_parcel(quantity=Decimal("50"))
        sell = self._make_sell(quantity=Decimal("50"))

        matches = match(sell, strategy="fifo")
        confirm_matches(matches)

        parcel.refresh_from_db()
        self.assertTrue(parcel.is_fully_matched)
        self.assertEqual(parcel.remaining_quantity, Decimal("0"))

    def test_matches_persisted(self):
        """confirm_matches saves ParcelMatch records to DB."""
        _, parcel = self._make_buy_and_parcel(quantity=Decimal("100"))
        sell = self._make_sell(quantity=Decimal("50"))

        matches = match(sell, strategy="fifo")
        self.assertFalse(any(m.pk for m in matches))  # Unsaved

        saved = confirm_matches(matches)
        self.assertTrue(all(m.pk for m in saved))  # Now saved
        self.assertEqual(ParcelMatch.objects.count(), 1)

    def test_remaining_quantity_never_negative(self):
        """Cannot confirm if remaining_quantity would go negative."""
        _, parcel = self._make_buy_and_parcel(quantity=Decimal("50"))

        # First match: takes 50, fully matched
        sell1 = self._make_sell(quantity=Decimal("50"), sell_date=date(2025, 3, 1))
        matches1 = match(sell1, strategy="fifo")
        confirm_matches(matches1)

        # Second attempt: no parcels available
        sell2 = self._make_sell(quantity=Decimal("10"), sell_date=date(2025, 6, 1))
        with self.assertRaises(MatchingError):
            match(sell2, strategy="fifo")
