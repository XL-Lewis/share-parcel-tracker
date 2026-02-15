"""CSV import flow + transaction listing views."""

from __future__ import annotations

import csv
import io

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from tracker.forms import ColumnMappingForm, CSVUploadForm
from tracker.models import ImportRecord, Security, Transaction
from tracker.services.csv_import import (
    confirm_import,
    detect_selfwealth,
    get_selfwealth_mapping,
    preview_import,
)


# ---------------------------------------------------------------------------
# Transaction list
# ---------------------------------------------------------------------------


@require_GET
def transaction_list(request):
    """List all transactions with filtering by security, type, date range."""
    transactions = Transaction.objects.select_related("security", "import_record")

    # Filter by security
    security = request.GET.get("security")
    if security:
        transactions = transactions.filter(security__ticker=security)

    # Filter by type
    txn_type = request.GET.get("type")
    if txn_type:
        transactions = transactions.filter(transaction_type=txn_type)

    # Filter by date range
    date_from = request.GET.get("date_from")
    if date_from:
        transactions = transactions.filter(trade_date__gte=date_from)

    date_to = request.GET.get("date_to")
    if date_to:
        transactions = transactions.filter(trade_date__lte=date_to)

    securities = Security.objects.all()

    return render(
        request,
        "tracker/transactions/list.html",
        {
            "transactions": transactions,
            "securities": securities,
            "current_security": security or "",
            "current_type": txn_type or "",
            "current_date_from": date_from or "",
            "current_date_to": date_to or "",
        },
    )


# ---------------------------------------------------------------------------
# Transaction detail
# ---------------------------------------------------------------------------


@require_GET
def transaction_detail(request, pk):
    """Detail view for a single transaction."""
    txn = get_object_or_404(
        Transaction.objects.select_related("security", "import_record"),
        pk=pk,
    )

    # For BUY transactions, get the linked parcel
    parcel = None
    if txn.transaction_type == Transaction.TransactionType.BUY:
        parcel = getattr(txn, "parcel", None)

    # For SELL transactions, get the linked matches
    matches = []
    if txn.transaction_type == Transaction.TransactionType.SELL:
        matches = txn.parcel_matches.select_related("parcel__security").all()

    return render(
        request,
        "tracker/transactions/detail.html",
        {
            "txn": txn,
            "parcel": parcel,
            "matches": matches,
        },
    )


# ---------------------------------------------------------------------------
# CSV import flow
# ---------------------------------------------------------------------------


def csv_upload(request):
    """Step 1: Upload CSV file."""
    if request.method == "POST":
        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = request.FILES["file"]
            file_content = uploaded_file.read().decode("utf-8-sig")
            source_type = form.cleaned_data["source_type"]

            # Store in session for subsequent steps
            request.session["csv_content"] = file_content
            request.session["csv_filename"] = uploaded_file.name
            request.session["csv_source_type"] = source_type

            # Detect headers
            reader = csv.DictReader(io.StringIO(file_content))
            headers = reader.fieldnames or []

            if source_type == ImportRecord.SourceType.SELFWEALTH:
                if detect_selfwealth(headers):
                    # Auto-map and go straight to preview
                    mapping = get_selfwealth_mapping()
                    request.session["csv_mapping"] = mapping
                    return redirect("tracker:csv_preview")
                else:
                    messages.warning(
                        request,
                        "Headers don't match SelfWealth format. "
                        "Please map columns manually.",
                    )
                    request.session["csv_source_type"] = ImportRecord.SourceType.GENERIC
                    return redirect("tracker:csv_mapping")
            else:
                return redirect("tracker:csv_mapping")
    else:
        form = CSVUploadForm()

    return render(request, "tracker/transactions/upload.html", {"form": form})


@require_http_methods(["GET", "POST"])
def csv_mapping(request):
    """Step 2: Map CSV columns to canonical fields (Generic CSVs)."""
    file_content = request.session.get("csv_content")
    if not file_content:
        messages.error(request, "No CSV file in session. Please upload again.")
        return redirect("tracker:csv_upload")

    reader = csv.DictReader(io.StringIO(file_content))
    headers = reader.fieldnames or []
    # Grab first few rows for preview
    sample_rows = []
    for i, row in enumerate(reader):
        sample_rows.append(row)
        if i >= 4:
            break

    if request.method == "POST":
        form = ColumnMappingForm(request.POST, csv_headers=headers)
        if form.is_valid():
            # Build mapping: csv_column -> canonical_field
            mapping = {}
            for header in headers:
                canonical = form.cleaned_data.get(f"col_{header}")
                if canonical:
                    mapping[header] = canonical

            request.session["csv_mapping"] = mapping
            return redirect("tracker:csv_preview")
    else:
        form = ColumnMappingForm(csv_headers=headers)

    return render(
        request,
        "tracker/transactions/mapping.html",
        {
            "form": form,
            "headers": headers,
            "sample_rows": sample_rows,
        },
    )


@require_http_methods(["GET", "POST"])
def csv_preview(request):
    """Step 3: Preview parsed rows + duplicates. Confirm to import."""
    file_content = request.session.get("csv_content")
    mapping = request.session.get("csv_mapping")
    if not file_content or not mapping:
        messages.error(request, "Missing CSV data. Please start over.")
        return redirect("tracker:csv_upload")

    if request.method == "POST":
        # Confirm import
        filename = request.session.get("csv_filename", "unknown.csv")
        source_type = request.session.get(
            "csv_source_type", ImportRecord.SourceType.GENERIC
        )
        import_record = confirm_import(file_content, mapping, filename, source_type)

        # Clear session data
        for key in [
            "csv_content",
            "csv_filename",
            "csv_source_type",
            "csv_mapping",
        ]:
            request.session.pop(key, None)

        messages.success(
            request,
            f"Imported {import_record.row_count} transactions "
            f"from {import_record.filename}.",
        )
        return redirect("tracker:transaction_list")

    # GET: show preview
    preview = preview_import(file_content, mapping)
    return render(
        request,
        "tracker/transactions/preview.html",
        {"preview": preview},
    )
