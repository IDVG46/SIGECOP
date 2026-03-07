from decimal import Decimal


def is_quantity_based_lot(lot):
    open_contract_type = (getattr(lot, "open_contract_type", "") or "").strip().lower()
    return "cantidad" in open_contract_type


def has_positive_quantity_limit(raw_quantity):
    if raw_quantity is None:
        return False
    return Decimal(str(raw_quantity)) > Decimal("0")


def should_enforce_quantity_limit_for_lot_and_quantity(lot, raw_quantity):
    """
    Regla unificada para control por cantidad:
    1) Si no hay cantidad maxima > 0, no restringe por cantidad.
    2) Si cantidad maxima > 1, siempre restringe por cantidad.
    3) Si cantidad maxima == 1, restringe por cantidad solo en lotes abiertos por cantidad.
    """
    if not has_positive_quantity_limit(raw_quantity):
        return False

    max_qty = Decimal(str(raw_quantity))
    if max_qty > Decimal("1"):
        return True

    return is_quantity_based_lot(lot)
