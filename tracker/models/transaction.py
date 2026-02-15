from decimal import Decimal

from django.db import models

from .security import Security
from .import_record import ImportRecord


class Transaction(models.Model):
    class TransactionType(models.TextChoices):
        BUY = "BUY", "Buy"
        SELL = "SELL", "Sell"

    security = models.ForeignKey(
        Security, on_delete=models.CASCADE, related_name="transactions"
    )
    import_record = models.ForeignKey(
        ImportRecord,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )
    trade_date = models.DateField()
    transaction_type = models.CharField(max_length=4, choices=TransactionType.choices)
    quantity = models.DecimalField(max_digits=18, decimal_places=8)
    unit_price = models.DecimalField(max_digits=18, decimal_places=6)
    brokerage = models.DecimalField(
        max_digits=18, decimal_places=6, default=Decimal("0")
    )
    total_value = models.DecimalField(max_digits=18, decimal_places=6)
    currency = models.CharField(max_length=3, default="AUD")
    exchange_rate = models.DecimalField(
        max_digits=18, decimal_places=6, default=Decimal("1")
    )
    raw_data = models.JSONField(blank=True, default=dict)

    class Meta:
        ordering = ["-trade_date"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "trade_date",
                    "security",
                    "transaction_type",
                    "quantity",
                    "unit_price",
                ],
                name="unique_transaction",
            )
        ]

    def __str__(self):
        return (
            f"{self.transaction_type} {self.quantity} "
            f"{self.security} @ {self.unit_price} on {self.trade_date}"
        )
