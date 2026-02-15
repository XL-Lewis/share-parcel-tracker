"""Dashboard view -- portfolio overview with polished stats."""

from decimal import Decimal

from django.db.models import F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import render
from django.views.decorators.http import require_GET

from tracker.models import ImportRecord, Parcel, ParcelMatch, Transaction


@require_GET
def dashboard(request):
    """Portfolio overview: holdings, cost base, gains, recent activity."""
    # -- Effective holdings: parcel remaining minus unmatched sell quantities --
    holdings = _compute_holdings()

    # Top holdings by cost base (top 5)
    top_holdings = sorted(
        [h for h in holdings if h["effective_remaining"] > 0],
        key=lambda h: h["total_cost_base"],
        reverse=True,
    )[:5]

    # Holdings count (securities with effective remaining > 0)
    holdings_count = sum(
        1 for h in holdings if h["effective_remaining"] > 0
    )

    # -- Unmatched sell transactions --
    unmatched_sells_qs = (
        Transaction.objects.filter(
            transaction_type=Transaction.TransactionType.SELL,
        )
        .annotate(
            total_matched=Coalesce(
                Sum("parcel_matches__matched_quantity"), Value(Decimal("0"))
            ),
        )
        .filter(
            Q(total_matched__lt=F("quantity")),
        )
    )
    unmatched_sells_count = unmatched_sells_qs.count()

    # -- Summary stats --
    total_transactions = Transaction.objects.count()
    total_parcels = Parcel.objects.count()

    # Total cost base of current holdings
    total_cost_base = Parcel.objects.filter(remaining_quantity__gt=0).aggregate(
        total=Sum("total_cost_base_aud")
    )["total"] or Decimal("0")

    # Realised gains summary (all time)
    realised = ParcelMatch.objects.aggregate(
        total_net_gain=Sum("net_capital_gain"),
        total_gross_gain=Sum("capital_gain_loss"),
        total_discounts=Sum("discount_amount"),
    )
    total_realised = realised["total_net_gain"] or Decimal("0")
    total_gross = realised["total_gross_gain"] or Decimal("0")
    total_discounts = realised["total_discounts"] or Decimal("0")

    # -- Recent activity --
    recent_imports = ImportRecord.objects.order_by("-imported_at")[:5]
    recent_matches = ParcelMatch.objects.select_related(
        "parcel__security", "sell_transaction"
    ).order_by("-id")[:5]

    return render(
        request,
        "tracker/dashboard.html",
        {
            "holdings": [h for h in holdings if h["effective_remaining"] > 0],
            "top_holdings": top_holdings,
            "unmatched_sells": unmatched_sells_count,
            "total_transactions": total_transactions,
            "total_parcels": total_parcels,
            "holdings_count": holdings_count,
            "total_cost_base": total_cost_base,
            "total_realised": total_realised,
            "total_gross": total_gross,
            "total_discounts": total_discounts,
            "recent_imports": recent_imports,
            "recent_matches": recent_matches,
        },
    )


def _compute_holdings() -> list[dict]:
    """
    Compute effective holdings per security.

    Effective remaining = parcel remaining_quantity - unmatched sell quantity.
    This gives a real-world view: if a sell has been imported but not yet
    matched, the units are still shown as "pending sale" rather than held.
    """
    # Parcel remaining per security
    parcel_qs = (
        Parcel.objects.filter(remaining_quantity__gt=0)
        .values("security__ticker")
        .annotate(
            parcel_remaining=Sum("remaining_quantity"),
            total_cost_base=Sum("total_cost_base_aud"),
        )
    )
    by_ticker: dict[str, dict] = {}
    for row in parcel_qs:
        ticker = row["security__ticker"]
        by_ticker[ticker] = {
            "security__ticker": ticker,
            "parcel_remaining": row["parcel_remaining"],
            "total_cost_base": row["total_cost_base"],
            "pending_sell_qty": Decimal("0"),
        }

    # Unmatched sell quantity per security
    # For each sell: unmatched portion = quantity - coalesce(sum(matched), 0)
    # Computed in Python since Django ORM can't Sum over an annotated aggregate
    unmatched_sells = (
        Transaction.objects.filter(
            transaction_type=Transaction.TransactionType.SELL,
        )
        .annotate(
            total_matched=Coalesce(
                Sum("parcel_matches__matched_quantity"), Value(Decimal("0"))
            ),
        )
        .filter(total_matched__lt=F("quantity"))
        .select_related("security")
    )
    for sell in unmatched_sells:
        ticker = sell.security.ticker
        if ticker in by_ticker:
            pending = sell.quantity - sell.total_matched
            by_ticker[ticker]["pending_sell_qty"] += pending

    # Build final list with effective remaining
    result = []
    for ticker in sorted(by_ticker):
        data = by_ticker[ticker]
        effective = data["parcel_remaining"] - data["pending_sell_qty"]
        result.append(
            {
                "security__ticker": ticker,
                "parcel_remaining": data["parcel_remaining"],
                "pending_sell_qty": data["pending_sell_qty"],
                "effective_remaining": max(effective, Decimal("0")),
                "total_cost_base": data["total_cost_base"],
            }
        )
    return result
