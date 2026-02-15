"""
CGT (Capital Gains Tax) calculation engine.

Australian rules:
- Financial year: Jul 1 - Jun 30
- CGT discount: 50% for individuals holding > 365 days (366+ days)
- Discount applies only to positive gains
- Cost base includes brokerage, converted to AUD via exchange_rate
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db.models import Sum

from tracker.models import Parcel, ParcelMatch, Transaction


def calculate_cgt(
    parcel: Parcel,
    sell_transaction: Transaction,
    matched_quantity: Decimal,
) -> dict:
    """
    Calculate CGT fields for a parcel match.

    Args:
        parcel: The buy-side parcel being matched.
        sell_transaction: The sell transaction consuming the parcel.
        matched_quantity: How many units of the parcel are being sold.

    Returns:
        Dict with: cost_base_aud, proceeds_aud, capital_gain_loss,
        holding_period_days, cgt_discount_eligible, discount_amount,
        net_capital_gain.
    """
    # Cost base = cost_per_unit_aud * matched_quantity
    # (cost_per_unit_aud already includes brokerage + AUD conversion from import)
    cost_base_aud = parcel.cost_per_unit_aud * matched_quantity

    # Proceeds = unit_price * quantity * exchange_rate
    # (sell-side brokerage reduces proceeds)
    sell_rate = sell_transaction.exchange_rate
    proceeds_per_unit = sell_transaction.unit_price * sell_rate
    proceeds_aud = proceeds_per_unit * matched_quantity

    # Capital gain/loss
    capital_gain_loss = proceeds_aud - cost_base_aud

    # Holding period
    holding_period_days = (sell_transaction.trade_date - parcel.acquisition_date).days

    # CGT discount: >365 days AND gain > 0
    cgt_discount_eligible = holding_period_days > 365 and capital_gain_loss > Decimal(
        "0"
    )

    discount_amount = Decimal("0")
    if cgt_discount_eligible:
        discount_amount = capital_gain_loss * Decimal("0.5")

    net_capital_gain = capital_gain_loss - discount_amount

    return {
        "cost_base_aud": cost_base_aud,
        "proceeds_aud": proceeds_aud,
        "capital_gain_loss": capital_gain_loss,
        "holding_period_days": holding_period_days,
        "cgt_discount_eligible": cgt_discount_eligible,
        "discount_amount": discount_amount,
        "net_capital_gain": net_capital_gain,
    }


def get_fy_range(financial_year: int) -> tuple[date, date]:
    """
    Return (start_date, end_date) for an Australian financial year.

    financial_year=2025 means FY2024-25: Jul 1 2024 to Jun 30 2025.
    """
    start = date(financial_year - 1, 7, 1)
    end = date(financial_year, 6, 30)
    return start, end


def fy_summary(financial_year: int) -> dict:
    """
    Aggregate CGT data for a given Australian financial year.

    Args:
        financial_year: The ending year (e.g. 2025 for FY2024-25).

    Returns:
        Dict with total_gains, total_losses, total_discounts,
        net_capital_gain, match_count, and per_security breakdown.
    """
    fy_start, fy_end = get_fy_range(financial_year)

    matches = ParcelMatch.objects.filter(
        sell_transaction__trade_date__gte=fy_start,
        sell_transaction__trade_date__lte=fy_end,
    ).select_related("parcel__security", "sell_transaction")

    total_gains = Decimal("0")
    total_losses = Decimal("0")
    total_discounts = Decimal("0")
    total_net = Decimal("0")
    per_security: dict[str, dict] = {}

    for match in matches:
        ticker = match.parcel.security.ticker

        if match.capital_gain_loss > Decimal("0"):
            total_gains += match.capital_gain_loss
        else:
            total_losses += match.capital_gain_loss

        total_discounts += match.discount_amount
        total_net += match.net_capital_gain

        if ticker not in per_security:
            per_security[ticker] = {
                "ticker": ticker,
                "gains": Decimal("0"),
                "losses": Decimal("0"),
                "discounts": Decimal("0"),
                "net": Decimal("0"),
                "match_count": 0,
            }

        sec = per_security[ticker]
        if match.capital_gain_loss > Decimal("0"):
            sec["gains"] += match.capital_gain_loss
        else:
            sec["losses"] += match.capital_gain_loss
        sec["discounts"] += match.discount_amount
        sec["net"] += match.net_capital_gain
        sec["match_count"] += 1

    return {
        "financial_year": financial_year,
        "fy_label": f"FY{financial_year - 1}-{str(financial_year)[2:]}",
        "start_date": fy_start,
        "end_date": fy_end,
        "total_gains": total_gains,
        "total_losses": total_losses,
        "total_discounts": total_discounts,
        "net_capital_gain": total_net,
        "match_count": matches.count(),
        "per_security": sorted(per_security.values(), key=lambda x: x["ticker"]),
    }
