"""Tests for Phase 2 views: transactions, parcels, matching, dashboard."""

from datetime import date
from decimal import Decimal

from django.test import TestCase, Client
from django.urls import reverse

from tracker.models import (
    Parcel,
    ParcelMatch,
    Security,
    Transaction,
)
from tracker.services.matching import confirm_matches, match


class ViewTestBase(TestCase):
    """Base class with common setup for view tests."""

    def setUp(self):
        self.client = Client()
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
            brokerage=Decimal("9.50"),
            total_value=Decimal("4000.00"),
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
        self.sell_txn = Transaction.objects.create(
            security=self.security,
            trade_date=date(2025, 6, 15),
            transaction_type=Transaction.TransactionType.SELL,
            quantity=Decimal("50"),
            unit_price=Decimal("55.00"),
            brokerage=Decimal("9.50"),
            total_value=Decimal("2750.00"),
        )


class DashboardViewTest(ViewTestBase):
    def test_dashboard_status_code(self):
        resp = self.client.get(reverse("tracker:dashboard"))
        self.assertEqual(resp.status_code, 200)

    def test_dashboard_context(self):
        resp = self.client.get(reverse("tracker:dashboard"))
        self.assertIn("holdings", resp.context)
        self.assertIn("unmatched_sells", resp.context)
        self.assertIn("total_cost_base", resp.context)
        self.assertIn("total_realised", resp.context)

    def test_dashboard_template(self):
        resp = self.client.get(reverse("tracker:dashboard"))
        self.assertTemplateUsed(resp, "tracker/dashboard.html")


class TransactionListViewTest(ViewTestBase):
    def test_list_status_code(self):
        resp = self.client.get(reverse("tracker:transaction_list"))
        self.assertEqual(resp.status_code, 200)

    def test_list_filter_by_security(self):
        resp = self.client.get(
            reverse("tracker:transaction_list"), {"security": "BHP.AX"}
        )
        self.assertEqual(resp.status_code, 200)
        for txn in resp.context["transactions"]:
            self.assertEqual(txn.security.ticker, "BHP.AX")

    def test_list_filter_by_type(self):
        resp = self.client.get(reverse("tracker:transaction_list"), {"type": "BUY"})
        self.assertEqual(resp.status_code, 200)
        for txn in resp.context["transactions"]:
            self.assertEqual(txn.transaction_type, "BUY")

    def test_list_filter_by_date_range(self):
        resp = self.client.get(
            reverse("tracker:transaction_list"),
            {"date_from": "2025-01-01", "date_to": "2025-12-31"},
        )
        self.assertEqual(resp.status_code, 200)

    def test_list_template(self):
        resp = self.client.get(reverse("tracker:transaction_list"))
        self.assertTemplateUsed(resp, "tracker/transactions/list.html")


class TransactionDetailViewTest(ViewTestBase):
    def test_buy_detail(self):
        resp = self.client.get(
            reverse("tracker:transaction_detail", args=[self.buy_txn.pk])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["txn"], self.buy_txn)
        self.assertEqual(resp.context["parcel"], self.parcel)
        self.assertTemplateUsed(resp, "tracker/transactions/detail.html")

    def test_sell_detail_no_matches(self):
        resp = self.client.get(
            reverse("tracker:transaction_detail", args=[self.sell_txn.pk])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context["matches"]), 0)

    def test_sell_detail_with_matches(self):
        matches = match(self.sell_txn, strategy="fifo")
        confirm_matches(matches)

        resp = self.client.get(
            reverse("tracker:transaction_detail", args=[self.sell_txn.pk])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context["matches"]), 1)

    def test_detail_404(self):
        resp = self.client.get(reverse("tracker:transaction_detail", args=[99999]))
        self.assertEqual(resp.status_code, 404)


class ParcelListViewTest(ViewTestBase):
    def test_list_status_code(self):
        resp = self.client.get(reverse("tracker:parcel_list"))
        self.assertEqual(resp.status_code, 200)

    def test_list_filter_by_security(self):
        resp = self.client.get(reverse("tracker:parcel_list"), {"security": "BHP.AX"})
        self.assertEqual(resp.status_code, 200)
        for p in resp.context["parcels"]:
            self.assertEqual(p.security.ticker, "BHP.AX")

    def test_list_filter_matched(self):
        resp = self.client.get(reverse("tracker:parcel_list"), {"status": "matched"})
        self.assertEqual(resp.status_code, 200)

    def test_list_filter_unmatched(self):
        resp = self.client.get(reverse("tracker:parcel_list"), {"status": "unmatched"})
        self.assertEqual(resp.status_code, 200)

    def test_list_template(self):
        resp = self.client.get(reverse("tracker:parcel_list"))
        self.assertTemplateUsed(resp, "tracker/parcels/list.html")


class ParcelDetailViewTest(ViewTestBase):
    def test_detail_status_code(self):
        resp = self.client.get(reverse("tracker:parcel_detail", args=[self.parcel.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["parcel"], self.parcel)
        self.assertTemplateUsed(resp, "tracker/parcels/detail.html")

    def test_detail_404(self):
        resp = self.client.get(reverse("tracker:parcel_detail", args=[99999]))
        self.assertEqual(resp.status_code, 404)


class UnmatchedSellsViewTest(ViewTestBase):
    def test_status_code(self):
        resp = self.client.get(reverse("tracker:unmatched_sells"))
        self.assertEqual(resp.status_code, 200)

    def test_unmatched_shows_sell(self):
        resp = self.client.get(reverse("tracker:unmatched_sells"))
        unmatched = resp.context["unmatched_sells"]
        self.assertEqual(len(unmatched), 1)
        self.assertEqual(unmatched[0]["transaction"].pk, self.sell_txn.pk)

    def test_matched_sell_not_listed(self):
        matches = match(self.sell_txn, strategy="fifo")
        confirm_matches(matches)

        resp = self.client.get(reverse("tracker:unmatched_sells"))
        self.assertEqual(len(resp.context["unmatched_sells"]), 0)

    def test_template(self):
        resp = self.client.get(reverse("tracker:unmatched_sells"))
        self.assertTemplateUsed(resp, "tracker/matching/match_sell.html")


class AvailableParcelsViewTest(ViewTestBase):
    def test_returns_parcels_partial(self):
        resp = self.client.get(
            reverse("tracker:available_parcels", args=[self.sell_txn.pk])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "tracker/matching/partials/parcel_list.html")
        self.assertIn(self.parcel, resp.context["parcels"])


class AutoMatchViewTest(ViewTestBase):
    def test_fifo_match_preview(self):
        resp = self.client.post(
            reverse("tracker:auto_match", args=[self.sell_txn.pk]),
            {"strategy": "fifo"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "tracker/matching/partials/match_preview.html")
        self.assertIn("matches", resp.context)
        self.assertGreater(len(resp.context["matches"]), 0)

    def test_lifo_match_preview(self):
        resp = self.client.post(
            reverse("tracker:auto_match", args=[self.sell_txn.pk]),
            {"strategy": "lifo"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("matches", resp.context)

    def test_insufficient_parcels_error(self):
        # Remove remaining qty
        self.parcel.remaining_quantity = Decimal("0")
        self.parcel.is_fully_matched = True
        self.parcel.save()

        resp = self.client.post(
            reverse("tracker:auto_match", args=[self.sell_txn.pk]),
            {"strategy": "fifo"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("error", resp.context)


class ConfirmMatchViewTest(ViewTestBase):
    def test_confirm_flow(self):
        # First, auto match to set up session
        self.client.post(
            reverse("tracker:auto_match", args=[self.sell_txn.pk]),
            {"strategy": "fifo"},
        )

        # Then confirm
        resp = self.client.post(
            reverse("tracker:confirm_match", args=[self.sell_txn.pk]),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "tracker/matching/partials/match_confirmed.html")

        # Verify DB state
        self.assertEqual(ParcelMatch.objects.count(), 1)
        self.parcel.refresh_from_db()
        self.assertEqual(self.parcel.remaining_quantity, Decimal("50"))

    def test_confirm_without_pending_shows_error(self):
        resp = self.client.post(
            reverse("tracker:confirm_match", args=[self.sell_txn.pk]),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("error", resp.context)
