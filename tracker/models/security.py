from django.db import models


class Security(models.Model):
    class Exchange(models.TextChoices):
        ASX = "ASX", "ASX"
        NYSE = "NYSE", "NYSE"
        NASDAQ = "NASDAQ", "NASDAQ"

    class Currency(models.TextChoices):
        AUD = "AUD", "AUD"
        USD = "USD", "USD"

    class AssetType(models.TextChoices):
        SHARE = "SHARE", "Share"
        ETF = "ETF", "ETF"

    ticker = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200, blank=True)
    exchange = models.CharField(max_length=10, choices=Exchange.choices)
    currency = models.CharField(max_length=3, choices=Currency.choices)
    asset_type = models.CharField(
        max_length=10, choices=AssetType.choices, default=AssetType.SHARE
    )

    class Meta:
        verbose_name_plural = "securities"
        ordering = ["ticker"]

    def __str__(self):
        return self.ticker
