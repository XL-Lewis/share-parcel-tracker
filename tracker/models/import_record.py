from django.db import models


class ImportRecord(models.Model):
    class SourceType(models.TextChoices):
        SELFWEALTH = "SELFWEALTH", "SelfWealth"
        GENERIC = "GENERIC", "Generic CSV"

    filename = models.CharField(max_length=255)
    imported_at = models.DateTimeField(auto_now_add=True)
    source_type = models.CharField(max_length=20, choices=SourceType.choices)
    row_count = models.PositiveIntegerField(default=0)
    column_mapping = models.JSONField(blank=True, default=dict)

    class Meta:
        ordering = ["-imported_at"]

    def __str__(self):
        return f"{self.filename} ({self.imported_at:%Y-%m-%d %H:%M})"
