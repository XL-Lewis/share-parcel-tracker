"""
Forecasting service: simulate CGT outcomes for hypothetical sells.

Preview-only -- no database writes. Compares FIFO, LIFO, and optimal
(highest cost base first to minimise gain) strategies side-by-side.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from tracker.models import Parcel, Security
from tracker.services.cgt import calculate_cgt


class ForecastError(Exception):
    """Raised when forecast inputs are invalid."""


def _simulate_strategy(
    parcels,
    security: Security,
    quantity: Decimal,
    sell_price: Decimal,
    sell_date: date,
) -> dict:
    """
    Simulate matching against ordered parcels and compute CGT breakdown.

    Uses a lightweight fake Transaction object to avoid DB writes.

    Returns:
        Dict with parcels_consumed (list of per-parcel breakdowns),
        total_cost_base, total_proceeds, total_gain_loss,
        total_discount, total_net_gain.
    """

    class _FakeSellTransaction:
        """Lightweight stand-in for a Transaction -- enough for calculate_cgt."""

        def __init__(self, security, trade_date, unit_price, exchange_rate):
            self.security = security
            self.security_id = security.pk
            self.trade_date = trade_date
            self.unit_price = unit_price
            self.exchange_rate = exchange_rate
            self.transaction_type = "SELL"

    fake_sell = _FakeSellTransaction(
        security=security,
        trade_date=sell_date,
        unit_price=sell_price,
        exchange_rate=Decimal("1"),  # forecast assumes AUD price
    )

    parcels_consumed = []
    remaining = quantity
    total_cost_base = Decimal("0")
    total_proceeds = Decimal("0")
    total_gain_loss = Decimal("0")
    total_discount = Decimal("0")
    total_net_gain = Decimal("0")

    for parcel in parcels:
        if remaining <= Decimal("0"):
            break

        qty = min(parcel.remaining_quantity, remaining)
        cgt = calculate_cgt(parcel, fake_sell, qty)

        parcels_consumed.append(
            {
                "parcel_id": parcel.id,
                "acquisition_date": parcel.acquisition_date,
                "matched_quantity": qty,
                "cost_per_unit_aud": parcel.cost_per_unit_aud,
                **cgt,
            }
        )

        total_cost_base += cgt["cost_base_aud"]
        total_proceeds += cgt["proceeds_aud"]
        total_gain_loss += cgt["capital_gain_loss"]
        total_discount += cgt["discount_amount"]
        total_net_gain += cgt["net_capital_gain"]
        remaining -= qty

    return {
        "parcels_consumed": parcels_consumed,
        "total_cost_base": total_cost_base,
        "total_proceeds": total_proceeds,
        "total_gain_loss": total_gain_loss,
        "total_discount": total_discount,
        "total_net_gain": total_net_gain,
        "quantity_matched": quantity - remaining,
        "quantity_shortfall": remaining,
    }


def forecast(
    security: Security,
    quantity: Decimal,
    sell_price: Decimal,
    sell_date: date | None = None,
) -> dict:
    """
    Forecast CGT outcomes for a hypothetical sell using three strategies.

    Args:
        security: The security to sell.
        quantity: Number of units to sell.
        sell_price: Price per unit (in AUD).
        sell_date: Date of hypothetical sell (defaults to today).

    Returns:
        Dict with keys: security, quantity, sell_price, sell_date,
        fifo, lifo, optimal -- each a strategy result dict.

    Raises:
        ForecastError: If no available parcels or invalid inputs.
    """
    if sell_date is None:
        sell_date = date.today()

    if quantity <= Decimal("0"):
        raise ForecastError("Quantity must be positive.")

    if sell_price <= Decimal("0"):
        raise ForecastError("Sell price must be positive.")

    base_qs = Parcel.objects.filter(
        security=security,
        remaining_quantity__gt=0,
    )

    if not base_qs.exists():
        raise ForecastError(f"No available parcels for {security.ticker}.")

    total_available = sum(p.remaining_quantity for p in base_qs)
    if total_available < quantity:
        raise ForecastError(
            f"Insufficient parcels: need {quantity} units, "
            f"only {total_available} available for {security.ticker}."
        )

    # FIFO: oldest first
    fifo_parcels = list(base_qs.order_by("acquisition_date"))
    fifo_result = _simulate_strategy(
        fifo_parcels, security, quantity, sell_price, sell_date
    )

    # LIFO: newest first
    lifo_parcels = list(base_qs.order_by("-acquisition_date"))
    lifo_result = _simulate_strategy(
        lifo_parcels, security, quantity, sell_price, sell_date
    )

    # Optimal: highest cost per unit first (minimise gain)
    optimal_parcels = list(base_qs.order_by("-cost_per_unit_aud"))
    optimal_result = _simulate_strategy(
        optimal_parcels, security, quantity, sell_price, sell_date
    )

    return {
        "security": security,
        "quantity": quantity,
        "sell_price": sell_price,
        "sell_date": sell_date,
        "fifo": fifo_result,
        "lifo": lifo_result,
        "optimal": optimal_result,
    }
