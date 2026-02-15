from django import forms

from tracker.models import ImportRecord
from tracker.services.csv_import import CANONICAL_FIELDS


class CSVUploadForm(forms.Form):
    """Step 1: Upload CSV file and select source type."""

    file = forms.FileField(
        label="CSV File",
        help_text="Upload a CSV file containing your trade history.",
    )
    source_type = forms.ChoiceField(
        choices=ImportRecord.SourceType.choices,
        label="Source Type",
        help_text="Select SelfWealth for auto-mapping, or Generic to map columns manually.",
    )


MAPPING_CHOICES = [("", "-- skip --")] + [
    (f, f.replace("_", " ").title()) for f in CANONICAL_FIELDS
]


class ColumnMappingForm(forms.Form):
    """
    Step 2 (Generic only): Map CSV columns to canonical fields.

    Dynamically built from CSV headers.
    """

    def __init__(self, *args, csv_headers: list[str] | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        if csv_headers:
            for header in csv_headers:
                self.fields[f"col_{header}"] = forms.ChoiceField(
                    choices=MAPPING_CHOICES,
                    required=False,
                    label=header,
                )
