from django.urls import path

from tracker.views.dashboard import dashboard
from tracker.views.matching import (
    auto_match,
    available_parcels,
    confirm_match,
    manual_match,
    unmatched_sells,
)
from tracker.views.parcels import parcel_detail, parcel_list
from tracker.views.reports import cgt_summary, forecast_results, forecast_view
from tracker.views.transactions import (
    csv_mapping,
    csv_preview,
    csv_upload,
    transaction_detail,
    transaction_list,
)

app_name = "tracker"

urlpatterns = [
    # Dashboard
    path("", dashboard, name="dashboard"),
    # Transactions
    path("transactions/", transaction_list, name="transaction_list"),
    path("transactions/<int:pk>/", transaction_detail, name="transaction_detail"),
    # Parcels
    path("parcels/", parcel_list, name="parcel_list"),
    path("parcels/<int:pk>/", parcel_detail, name="parcel_detail"),
    # Matching
    path("matching/", unmatched_sells, name="unmatched_sells"),
    path(
        "matching/<int:sell_id>/parcels/",
        available_parcels,
        name="available_parcels",
    ),
    path(
        "matching/<int:sell_id>/auto/",
        auto_match,
        name="auto_match",
    ),
    path(
        "matching/<int:sell_id>/manual/",
        manual_match,
        name="manual_match",
    ),
    path(
        "matching/<int:sell_id>/confirm/",
        confirm_match,
        name="confirm_match",
    ),
    # Reports
    path("reports/cgt/", cgt_summary, name="cgt_summary"),
    path("reports/forecast/", forecast_view, name="forecast"),
    path("reports/forecast/results/", forecast_results, name="forecast_results"),
    # CSV Import
    path("import/upload/", csv_upload, name="csv_upload"),
    path("import/mapping/", csv_mapping, name="csv_mapping"),
    path("import/preview/", csv_preview, name="csv_preview"),
]
