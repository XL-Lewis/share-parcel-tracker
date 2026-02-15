"""Matching UI views -- HTMX-powered parcel matching workflow."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from tracker.models import Parcel, Transaction
from tracker.services.matching import MatchingError, confirm_matches, match


@require_GET
def unmatched_sells(request):
    """List sell transactions that have no matches (or partial matches)."""
    sells = (
        Transaction.objects.filter(
            transaction_type=Transaction.TransactionType.SELL,
        )
        .select_related("security")
        .order_by("-trade_date")
    )

    # Filter to only unmatched/partially matched sells
    unmatched = []
    for sell in sells:
        matched_qty = sum(m.matched_quantity for m in sell.parcel_matches.all())
        if matched_qty < sell.quantity:
            unmatched.append(
                {
                    "transaction": sell,
                    "matched_qty": matched_qty,
                    "remaining_qty": sell.quantity - matched_qty,
                }
            )

    return render(
        request,
        "tracker/matching/match_sell.html",
        {"unmatched_sells": unmatched},
    )


@require_GET
def available_parcels(request, sell_id):
    """HTMX partial: available parcels for a sell transaction's security."""
    sell = get_object_or_404(Transaction, pk=sell_id)
    parcels = (
        Parcel.objects.filter(
            security=sell.security,
            remaining_quantity__gt=0,
        )
        .select_related("security")
        .order_by("acquisition_date")
    )

    return render(
        request,
        "tracker/matching/partials/parcel_list.html",
        {
            "parcels": parcels,
            "sell": sell,
        },
    )


@require_http_methods(["POST"])
def auto_match(request, sell_id):
    """HTMX POST: run auto matching (FIFO or LIFO) and return preview."""
    sell = get_object_or_404(Transaction, pk=sell_id)
    strategy = request.POST.get("strategy", "fifo")

    try:
        matches = match(sell, strategy=strategy)
    except MatchingError as e:
        return render(
            request,
            "tracker/matching/partials/match_preview.html",
            {"error": str(e), "sell": sell},
        )

    # Store matches in session for confirm step
    request.session[f"pending_matches_{sell_id}"] = [
        {
            "parcel_id": m.parcel_id,
            "matched_quantity": str(m.matched_quantity),
        }
        for m in matches
    ]

    return render(
        request,
        "tracker/matching/partials/match_preview.html",
        {
            "matches": matches,
            "sell": sell,
            "strategy": strategy,
        },
    )


@require_http_methods(["POST"])
def manual_match(request, sell_id):
    """HTMX POST: manual matching with user-specified quantities."""
    sell = get_object_or_404(Transaction, pk=sell_id)

    # Parse parcel quantities from form
    parcel_ids = request.POST.getlist("parcel_id")
    quantity_values = request.POST.getlist("quantity")

    parcels_list = []
    quantities_list = []

    for pid, qty_str in zip(parcel_ids, quantity_values):
        qty_str = qty_str.strip()
        if not qty_str or qty_str == "0":
            continue
        try:
            qty = Decimal(qty_str)
        except InvalidOperation:
            return render(
                request,
                "tracker/matching/partials/match_preview.html",
                {"error": f"Invalid quantity: {qty_str!r}", "sell": sell},
            )

        try:
            parcel = Parcel.objects.get(pk=int(pid))
        except Parcel.DoesNotExist, ValueError:
            return render(
                request,
                "tracker/matching/partials/match_preview.html",
                {"error": f"Invalid parcel ID: {pid}", "sell": sell},
            )

        parcels_list.append(parcel)
        quantities_list.append(qty)

    try:
        matches = match(
            sell,
            strategy="manual",
            parcels=parcels_list,
            quantities=quantities_list,
        )
    except MatchingError as e:
        return render(
            request,
            "tracker/matching/partials/match_preview.html",
            {"error": str(e), "sell": sell},
        )

    # Store matches in session for confirm step
    request.session[f"pending_matches_{sell_id}"] = [
        {
            "parcel_id": m.parcel_id,
            "matched_quantity": str(m.matched_quantity),
        }
        for m in matches
    ]

    return render(
        request,
        "tracker/matching/partials/match_preview.html",
        {
            "matches": matches,
            "sell": sell,
            "strategy": "manual",
        },
    )


@require_http_methods(["POST"])
def confirm_match(request, sell_id):
    """HTMX POST: persist the previewed matches."""
    sell = get_object_or_404(Transaction, pk=sell_id)
    pending = request.session.pop(f"pending_matches_{sell_id}", None)

    if not pending:
        return render(
            request,
            "tracker/matching/partials/match_confirmed.html",
            {"error": "No pending matches found. Please try again.", "sell": sell},
        )

    # Rebuild match objects from session data
    parcels_list = []
    quantities_list = []
    for item in pending:
        try:
            parcel = Parcel.objects.get(pk=item["parcel_id"])
            qty = Decimal(item["matched_quantity"])
        except Parcel.DoesNotExist, InvalidOperation, KeyError:
            return render(
                request,
                "tracker/matching/partials/match_confirmed.html",
                {"error": "Invalid match data. Please try again.", "sell": sell},
            )
        parcels_list.append(parcel)
        quantities_list.append(qty)

    try:
        matches = match(
            sell,
            strategy="manual",
            parcels=parcels_list,
            quantities=quantities_list,
        )
        saved = confirm_matches(matches)
    except MatchingError as e:
        return render(
            request,
            "tracker/matching/partials/match_confirmed.html",
            {"error": str(e), "sell": sell},
        )

    return render(
        request,
        "tracker/matching/partials/match_confirmed.html",
        {
            "matches": saved,
            "sell": sell,
        },
    )
