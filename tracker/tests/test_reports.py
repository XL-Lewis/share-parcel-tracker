"""Tests for report views: CGT summary and forecast."""

from datetime import date
from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse

from tracker.models import Parcel, ParcelMatch, Security, Transaction


class ReportTestBase(TestCase):
    """Base class with helpers for report view tests."""

    def setUp(self):
        self.client = Client()
        self.security = Security.objects.create(
            ticker="CBA.AX",
            exchange=Security.Exchange.ASX,
            currency=Security.Currency.AUD,
        )

    _counter = 0

    def _create_matched_sell(
        self,
        sell_date,
        gain,
        discount_eligible=False,
        security=None,
    ):
        """Create a complete buy->parcel->sell->match chain."""
        ReportTestBase._counter += 1
        n = ReportTestBase._counter
        sec = security or self.security

        buy_txn = Transaction.objects.create(
            security=sec,
            trade_date=date(2023, 1, max(1, n % 28)),
            transaction_type=Transaction.TransactionType.BUY,
            quantity=Decimal(str(100 + n)),
            unit_price=Decimal("40.00"),
            total_value=Decimal(str((100 + n) * 40)),
        )
        sell_txn = Transaction.objects.create(
            security=sec,
            trade_date=sell_date,
            transaction_type=Transaction.TransactionType.SELL,
            quantity=Decimal(str(50 + n)),
            unit_price=Decimal("55.00"),
            total_value=Decimal(str((50 + n) * 55)),
        )
        parcel = Parcel.objects.create(
            transaction=buy_txn,
            security=sec,
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


class CGTSummaryViewTest(ReportTestBase):
    """Tests for the CGT summary report view."""

    def test_summary_status_code(self):
        resp = self.client.get(reverse("tracker:cgt_summary"))
        self.assertEqual(resp.status_code, 200)

    def test_summary_template(self):
        resp = self.client.get(reverse("tracker:cgt_summary"))
        self.assertTemplateUsed(resp, "tracker/reports/cgt_summary.html")

    def test_summary_empty_fys(self):
        """No matches -> no available FYs."""
        resp = self.client.get(reverse("tracker:cgt_summary"))
        self.assertEqual(len(resp.context["available_fys"]), 0)
        self.assertIsNone(resp.context["summary"])

    def test_summary_with_fy_data(self):
        """FY with matches shows in available_fys."""
        # FY2025 = Jul 1 2024 to Jun 30 2025
        self._create_matched_sell(date(2024, 8, 15), Decimal("500"))

        resp = self.client.get(reverse("tracker:cgt_summary"))
        fys = resp.context["available_fys"]
        self.assertTrue(any(fy["fy"] == 2025 for fy in fys))

    def test_summary_selected_fy(self):
        """Selecting an FY returns summary data."""
        self._create_matched_sell(date(2024, 8, 15), Decimal("500"))

        resp = self.client.get(reverse("tracker:cgt_summary"), {"fy": "2025"})
        summary = resp.context["summary"]
        self.assertIsNotNone(summary)
        self.assertEqual(summary["financial_year"], 2025)
        self.assertEqual(summary["total_gains"], Decimal("500"))

    def test_summary_fy_boundary_jun_30(self):
        """Sell on Jun 30 is in the FY ending that date."""
        self._create_matched_sell(date(2025, 6, 30), Decimal("100"))

        resp = self.client.get(reverse("tracker:cgt_summary"), {"fy": "2025"})
        summary = resp.context["summary"]
        self.assertEqual(summary["match_count"], 1)

    def test_summary_fy_boundary_jul_1(self):
        """Sell on Jul 1 is in the next FY."""
        self._create_matched_sell(date(2025, 7, 1), Decimal("100"))

        # Not in FY2025
        resp = self.client.get(reverse("tracker:cgt_summary"), {"fy": "2025"})
        summary = resp.context["summary"]
        self.assertEqual(summary["match_count"], 0)

        # In FY2026
        resp = self.client.get(reverse("tracker:cgt_summary"), {"fy": "2026"})
        summary = resp.context["summary"]
        self.assertEqual(summary["match_count"], 1)

    def test_summary_multi_fy(self):
        """Matches across multiple FYs show correct available_fys."""
        self._create_matched_sell(date(2024, 8, 15), Decimal("500"))  # FY2025
        self._create_matched_sell(date(2025, 8, 15), Decimal("300"))  # FY2026

        resp = self.client.get(reverse("tracker:cgt_summary"))
        fys = [fy["fy"] for fy in resp.context["available_fys"]]
        self.assertIn(2025, fys)
        self.assertIn(2026, fys)

    def test_summary_empty_fy_selected(self):
        """Selecting an FY with no matches shows zero summary."""
        self._create_matched_sell(date(2024, 8, 15), Decimal("500"))  # FY2025

        resp = self.client.get(reverse("tracker:cgt_summary"), {"fy": "2020"})
        summary = resp.context["summary"]
        self.assertEqual(summary["match_count"], 0)
        self.assertEqual(summary["total_gains"], Decimal("0"))

    def test_summary_per_security_breakdown(self):
        """Per-security breakdown appears in the summary."""
        sec2 = Security.objects.create(
            ticker="WES.AX",
            exchange=Security.Exchange.ASX,
            currency=Security.Currency.AUD,
        )
        self._create_matched_sell(date(2024, 8, 15), Decimal("500"))
        self._create_matched_sell(date(2024, 9, 1), Decimal("300"), security=sec2)

        resp = self.client.get(reverse("tracker:cgt_summary"), {"fy": "2025"})
        summary = resp.context["summary"]
        tickers = [s["ticker"] for s in summary["per_security"]]
        self.assertIn("CBA.AX", tickers)
        self.assertIn("WES.AX", tickers)

    def test_summary_invalid_fy_param(self):
        """Invalid FY param is handled gracefully."""
        resp = self.client.get(reverse("tracker:cgt_summary"), {"fy": "abc"})
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.context["summary"])


class ForecastViewTest(ReportTestBase):
    """Tests for the forecast form view."""

    def setUp(self):
        super().setUp()
        # Create a parcel so the security shows in the dropdown
        buy = Transaction.objects.create(
            security=self.security,
            trade_date=date(2024, 1, 10),
            transaction_type=Transaction.TransactionType.BUY,
            quantity=Decimal("100"),
            unit_price=Decimal("40.00"),
            total_value=Decimal("4000.00"),
        )
        self.parcel = Parcel.objects.create(
            transaction=buy,
            security=self.security,
            acquisition_date=date(2024, 1, 10),
            original_quantity=Decimal("100"),
            remaining_quantity=Decimal("100"),
            cost_per_unit_aud=Decimal("40.00"),
            total_cost_base_aud=Decimal("4000.00"),
        )

    def test_forecast_page_status_code(self):
        resp = self.client.get(reverse("tracker:forecast"))
        self.assertEqual(resp.status_code, 200)

    def test_forecast_page_template(self):
        resp = self.client.get(reverse("tracker:forecast"))
        self.assertTemplateUsed(resp, "tracker/reports/forecast.html")

    def test_forecast_page_lists_securities(self):
        resp = self.client.get(reverse("tracker:forecast"))
        self.assertIn(self.security, resp.context["securities"])


class ForecastResultsViewTest(ReportTestBase):
    """Tests for the HTMX forecast results endpoint."""

    def setUp(self):
        super().setUp()
        buy = Transaction.objects.create(
            security=self.security,
            trade_date=date(2024, 1, 10),
            transaction_type=Transaction.TransactionType.BUY,
            quantity=Decimal("100"),
            unit_price=Decimal("40.00"),
            total_value=Decimal("4000.00"),
        )
        self.parcel = Parcel.objects.create(
            transaction=buy,
            security=self.security,
            acquisition_date=date(2024, 1, 10),
            original_quantity=Decimal("100"),
            remaining_quantity=Decimal("100"),
            cost_per_unit_aud=Decimal("40.00"),
            total_cost_base_aud=Decimal("4000.00"),
        )

    def test_forecast_results_success(self):
        resp = self.client.get(
            reverse("tracker:forecast_results"),
            {
                "security": self.security.pk,
                "quantity": "50",
                "sell_price": "55.00",
                "sell_date": "2025-06-15",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "tracker/reports/partials/forecast_results.html")
        self.assertIn("result", resp.context)
        result = resp.context["result"]
        self.assertIn("fifo", result)
        self.assertIn("lifo", result)
        self.assertIn("optimal", result)

    def test_forecast_results_missing_security(self):
        resp = self.client.get(
            reverse("tracker:forecast_results"),
            {"quantity": "50", "sell_price": "55.00"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("errors", resp.context)

    def test_forecast_results_invalid_quantity(self):
        resp = self.client.get(
            reverse("tracker:forecast_results"),
            {
                "security": self.security.pk,
                "quantity": "abc",
                "sell_price": "55.00",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("errors", resp.context)

    def test_forecast_results_invalid_price(self):
        resp = self.client.get(
            reverse("tracker:forecast_results"),
            {
                "security": self.security.pk,
                "quantity": "50",
                "sell_price": "-10",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("errors", resp.context)

    def test_forecast_results_invalid_date(self):
        resp = self.client.get(
            reverse("tracker:forecast_results"),
            {
                "security": self.security.pk,
                "quantity": "50",
                "sell_price": "55.00",
                "sell_date": "not-a-date",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("errors", resp.context)

    def test_forecast_results_no_date_defaults_to_today(self):
        resp = self.client.get(
            reverse("tracker:forecast_results"),
            {
                "security": self.security.pk,
                "quantity": "50",
                "sell_price": "55.00",
            },
        )
        self.assertEqual(resp.status_code, 200)
        result = resp.context["result"]
        self.assertEqual(result["sell_date"], date.today())

    def test_forecast_results_post(self):
        """POST method also works for forecast results."""
        resp = self.client.post(
            reverse("tracker:forecast_results"),
            {
                "security": self.security.pk,
                "quantity": "50",
                "sell_price": "55.00",
                "sell_date": "2025-06-15",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("result", resp.context)

    def test_forecast_results_insufficient_parcels(self):
        resp = self.client.get(
            reverse("tracker:forecast_results"),
            {
                "security": self.security.pk,
                "quantity": "500",
                "sell_price": "55.00",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("errors", resp.context)
