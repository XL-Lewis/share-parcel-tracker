from decimal import Decimal

from django.db import models

from .security import Security
from .transaction import Transaction


class Parcel(models.Model):
    transaction = models.OneToOneField(
        Transaction, on_delete=models.CASCADE, related_name="parcel"
    )
    security = models.ForeignKey(
        Security, on_delete=models.CASCADE, related_name="parcels"
    )
    acquisition_date = models.DateField()
    original_quantity = models.DecimalField(max_digits=18, decimal_places=8)
    remaining_quantity = models.DecimalField(max_digits=18, decimal_places=8)
    cost_per_unit_aud = models.DecimalField(max_digits=18, decimal_places=6)
    total_cost_base_aud = models.DecimalField(max_digits=18, decimal_places=6)
    is_fully_matched = models.BooleanField(default=False)

    class Meta:
        ordering = ["acquisition_date"]

    def __str__(self):
        return (
            f"{self.security} parcel {self.acquisition_date} "
            f"({self.remaining_quantity}/{self.original_quantity})"
        )


class ParcelMatch(models.Model):
    parcel = models.ForeignKey(Parcel, on_delete=models.CASCADE, related_name="matches")
    sell_transaction = models.ForeignKey(
        Transaction, on_delete=models.CASCADE, related_name="parcel_matches"
    )
    matched_quantity = models.DecimalField(max_digits=18, decimal_places=8)
    cost_base_aud = models.DecimalField(max_digits=18, decimal_places=6)
    proceeds_aud = models.DecimalField(max_digits=18, decimal_places=6)
    capital_gain_loss = models.DecimalField(max_digits=18, decimal_places=6)
    holding_period_days = models.IntegerField()
    cgt_discount_eligible = models.BooleanField(default=False)
    discount_amount = models.DecimalField(
        max_digits=18, decimal_places=6, default=Decimal("0")
    )
    net_capital_gain = models.DecimalField(max_digits=18, decimal_places=6)

    class Meta:
        ordering = ["parcel__acquisition_date"]

    def __str__(self):
        return (
            f"Match: {self.matched_quantity} of {self.parcel.security} "
            f"-> gain/loss {self.net_capital_gain}"
        )
