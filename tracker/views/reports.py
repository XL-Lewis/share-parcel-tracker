"""Reports views: CGT summary and forecasting."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_http_methods

from tracker.models import ParcelMatch, Security
from tracker.services.cgt import fy_summary
from tracker.services.forecasting import ForecastError, forecast


@require_GET
def cgt_summary(request):
    """
    CGT summary report with FY selector.

    Displays per-FY summary (gains, losses, discounts, net) with
    per-security breakdown for the selected financial year.
    """
    # Build list of FYs that have matches
    available_fys = _get_available_fys()

    selected_fy = request.GET.get("fy")
    summary = None

    if selected_fy:
        try:
            selected_fy = int(selected_fy)
            summary = fy_summary(selected_fy)
        except ValueError, TypeError:
            selected_fy = None

    return render(
        request,
        "tracker/reports/cgt_summary.html",
        {
            "available_fys": available_fys,
            "selected_fy": selected_fy,
            "summary": summary,
        },
    )


@require_GET
def forecast_view(request):
    """
    Forecast form: select security, quantity, and price.

    The form submits via HTMX to load comparison results as a partial.
    """
    securities = (
        Security.objects.filter(
            parcels__remaining_quantity__gt=0,
        )
        .distinct()
        .order_by("ticker")
    )

    return render(
        request,
        "tracker/reports/forecast.html",
        {
            "securities": securities,
        },
    )


@require_http_methods(["GET", "POST"])
def forecast_results(request):
    """
    HTMX endpoint: compute forecast and return results partial.

    Accepts GET (from HTMX hx-get with query params) or POST.
    """
    # Support both GET params and POST data
    data = request.GET if request.method == "GET" else request.POST
    errors = []

    security_id = data.get("security")
    quantity_str = data.get("quantity", "")
    sell_price_str = data.get("sell_price", "")
    sell_date_str = data.get("sell_date", "")

    # Validate inputs
    security = None
    quantity = None
    sell_price = None
    sell_date = None

    if not security_id:
        errors.append("Please select a security.")
    else:
        try:
            security = Security.objects.get(pk=security_id)
        except Security.DoesNotExist, ValueError:
            errors.append("Invalid security selected.")

    try:
        quantity = Decimal(quantity_str)
        if quantity <= 0:
            errors.append("Quantity must be positive.")
    except InvalidOperation, ValueError:
        errors.append("Please enter a valid quantity.")

    try:
        sell_price = Decimal(sell_price_str)
        if sell_price <= 0:
            errors.append("Sell price must be positive.")
    except InvalidOperation, ValueError:
        errors.append("Please enter a valid sell price.")

    if sell_date_str:
        try:
            sell_date = date.fromisoformat(sell_date_str)
        except ValueError:
            errors.append("Invalid date format. Use YYYY-MM-DD.")
    else:
        sell_date = date.today()

    if errors:
        return render(
            request,
            "tracker/reports/partials/forecast_results.html",
            {"errors": errors},
        )

    # Run forecast
    try:
        result = forecast(
            security=security,
            quantity=quantity,
            sell_price=sell_price,
            sell_date=sell_date,
        )
    except ForecastError as e:
        return render(
            request,
            "tracker/reports/partials/forecast_results.html",
            {"errors": [str(e)]},
        )

    return render(
        request,
        "tracker/reports/partials/forecast_results.html",
        {"result": result},
    )


def _get_available_fys() -> list[dict]:
    """
    Return a list of financial years that have ParcelMatch records.

    Each entry: {"fy": int, "label": str} e.g. {"fy": 2025, "label": "FY2024-25"}.
    """
    # Get distinct sell dates that have matches
    sell_dates = (
        ParcelMatch.objects.values_list("sell_transaction__trade_date", flat=True)
        .distinct()
        .order_by("sell_transaction__trade_date")
    )

    fys = set()
    for d in sell_dates:
        # Australian FY: Jul 1 - Jun 30
        # A sell on Jul 1 2024 is in FY2025 (ending Jun 30 2025)
        if d.month >= 7:
            fys.add(d.year + 1)
        else:
            fys.add(d.year)

    return [
        {"fy": fy, "label": f"FY{fy - 1}-{str(fy)[2:]}"}
        for fy in sorted(fys, reverse=True)
    ]
