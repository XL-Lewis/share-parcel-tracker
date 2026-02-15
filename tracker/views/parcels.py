"""Parcel list and detail views."""

from __future__ import annotations

from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from tracker.models import Parcel, Security


@require_GET
def parcel_list(request):
    """List all parcels with filtering by security and matched status."""
    parcels = Parcel.objects.select_related("security", "transaction").prefetch_related(
        "matches"
    )

    # Filter by security
    security = request.GET.get("security")
    if security:
        parcels = parcels.filter(security__ticker=security)

    # Filter by matched/unmatched
    status = request.GET.get("status")
    if status == "matched":
        parcels = parcels.filter(is_fully_matched=True)
    elif status == "unmatched":
        parcels = parcels.filter(is_fully_matched=False)

    securities = Security.objects.all()

    return render(
        request,
        "tracker/parcels/list.html",
        {
            "parcels": parcels,
            "securities": securities,
            "current_security": security or "",
            "current_status": status or "",
        },
    )


@require_GET
def parcel_detail(request, pk):
    """Detail view for a single parcel: acquisition info, matches."""
    parcel = get_object_or_404(
        Parcel.objects.select_related("security", "transaction"),
        pk=pk,
    )
    matches = parcel.matches.select_related("sell_transaction").all()

    return render(
        request,
        "tracker/parcels/detail.html",
        {
            "parcel": parcel,
            "matches": matches,
        },
    )
