"""
Parcel matching engine: FIFO, LIFO, and manual strategies.

The engine creates unsaved ParcelMatch objects for preview,
then confirm_matches() persists them inside an atomic transaction.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from tracker.models import Parcel, ParcelMatch, Transaction
from tracker.services.cgt import calculate_cgt


class MatchingError(Exception):
    """Raised when matching validation fails."""


def _build_match(
    parcel: Parcel,
    sell_transaction: Transaction,
    qty: Decimal,
) -> ParcelMatch:
    """
    Build an unsaved ParcelMatch with computed CGT fields.
    """
    cgt = calculate_cgt(parcel, sell_transaction, qty)
    return ParcelMatch(
        parcel=parcel,
        sell_transaction=sell_transaction,
        matched_quantity=qty,
        cost_base_aud=cgt["cost_base_aud"],
        proceeds_aud=cgt["proceeds_aud"],
        capital_gain_loss=cgt["capital_gain_loss"],
        holding_period_days=cgt["holding_period_days"],
        cgt_discount_eligible=cgt["cgt_discount_eligible"],
        discount_amount=cgt["discount_amount"],
        net_capital_gain=cgt["net_capital_gain"],
    )


def match(
    sell_transaction: Transaction,
    strategy: str = "fifo",
    parcels: list[Parcel] | None = None,
    quantities: list[Decimal] | None = None,
) -> list[ParcelMatch]:
    """
    Create unsaved ParcelMatch objects for a sell transaction.

    Args:
        sell_transaction: The SELL transaction to match against parcels.
        strategy: "fifo", "lifo", or "manual".
        parcels: For manual strategy, the parcels to match against.
        quantities: For manual strategy, the quantity per parcel.

    Returns:
        List of unsaved ParcelMatch objects (call confirm_matches to persist).

    Raises:
        MatchingError: If validation fails.
    """
    if sell_transaction.transaction_type != Transaction.TransactionType.SELL:
        raise MatchingError("Transaction must be a SELL.")

    sell_qty = sell_transaction.quantity

    if strategy == "manual":
        return _match_manual(sell_transaction, sell_qty, parcels, quantities)
    elif strategy in ("fifo", "lifo"):
        return _match_auto(sell_transaction, sell_qty, strategy)
    else:
        raise MatchingError(f"Unknown strategy: {strategy!r}")


def _match_auto(
    sell_transaction: Transaction,
    sell_qty: Decimal,
    strategy: str,
) -> list[ParcelMatch]:
    """FIFO or LIFO automatic matching."""
    order = "acquisition_date" if strategy == "fifo" else "-acquisition_date"

    available_parcels = Parcel.objects.filter(
        security=sell_transaction.security,
        remaining_quantity__gt=0,
    ).order_by(order)

    matches: list[ParcelMatch] = []
    remaining = sell_qty

    for parcel in available_parcels:
        if remaining <= Decimal("0"):
            break

        qty_from_parcel = min(parcel.remaining_quantity, remaining)
        matches.append(_build_match(parcel, sell_transaction, qty_from_parcel))
        remaining -= qty_from_parcel

    if remaining > Decimal("0"):
        raise MatchingError(
            f"Insufficient parcels: need {sell_qty} units, "
            f"only {sell_qty - remaining} available."
        )

    return matches


def _match_manual(
    sell_transaction: Transaction,
    sell_qty: Decimal,
    parcels: list[Parcel] | None,
    quantities: list[Decimal] | None,
) -> list[ParcelMatch]:
    """Manual matching with user-specified parcel/quantity pairs."""
    if not parcels or not quantities:
        raise MatchingError("Manual matching requires parcels and quantities.")

    if len(parcels) != len(quantities):
        raise MatchingError("parcels and quantities must have the same length.")

    matches: list[ParcelMatch] = []
    total_matched = Decimal("0")

    for parcel, qty in zip(parcels, quantities):
        if qty <= Decimal("0"):
            continue

        if qty > parcel.remaining_quantity:
            raise MatchingError(
                f"Cannot match {qty} from parcel {parcel.id}: "
                f"only {parcel.remaining_quantity} remaining."
            )

        if parcel.security_id != sell_transaction.security_id:
            raise MatchingError(f"Parcel {parcel.id} is for a different security.")

        matches.append(_build_match(parcel, sell_transaction, qty))
        total_matched += qty

    if total_matched != sell_qty:
        raise MatchingError(
            f"Total matched quantity ({total_matched}) "
            f"does not equal sell quantity ({sell_qty})."
        )

    return matches


@transaction.atomic
def confirm_matches(matches: list[ParcelMatch]) -> list[ParcelMatch]:
    """
    Persist ParcelMatch records, update parcel remaining quantities.

    All operations run inside a single atomic transaction.

    Args:
        matches: List of unsaved ParcelMatch objects.

    Returns:
        The saved ParcelMatch objects.
    """
    saved: list[ParcelMatch] = []

    for match_obj in matches:
        parcel = match_obj.parcel

        # Re-read parcel to avoid race conditions
        parcel = Parcel.objects.select_for_update().get(pk=parcel.pk)

        if match_obj.matched_quantity > parcel.remaining_quantity:
            raise MatchingError(
                f"Race condition: parcel {parcel.id} remaining_quantity "
                f"({parcel.remaining_quantity}) < matched_quantity "
                f"({match_obj.matched_quantity})."
            )

        # Decrement remaining
        parcel.remaining_quantity -= match_obj.matched_quantity
        if parcel.remaining_quantity == Decimal("0"):
            parcel.is_fully_matched = True
        parcel.save(update_fields=["remaining_quantity", "is_fully_matched"])

        # Save the match
        match_obj.parcel = parcel
        match_obj.save()
        saved.append(match_obj)

    return saved
