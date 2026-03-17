"""
Mixins reutilizables para formularios del módulo procurement.

LocalizedDecimalMixin centraliza el método _clean_localized_decimal_field
que estaba duplicado en:
  - forms/order_forms.py      (PurchaseOrderLineForm)
  - forms/finance_forms.py    (ContractBudgetForm, PaymentForm, PaymentAllocationForm)
"""
from apps.procurement.forms.number_utils import normalize_localized_decimal_input


class LocalizedDecimalMixin:
    """Mixin para ModelForm: parsea campos decimales localizados (separadores , / .)."""

    def _clean_localized_decimal_field(self, field_name):
        """Normaliza un campo DecimalField que puede venir con formato localizado.

        Flujo:
        1. Si Django ya lo convirtió (cleaned_data tiene un valor), devuelve tal cual.
        2. Si el raw value está vacío, devuelve None para que el campo aplique
           sus propias validaciones (required, etc.).
        3. Normaliza el string y lo parsea con el to_python del campo declarado.
        """
        value = self.cleaned_data.get(field_name)
        if value is not None:
            return value

        raw_value = self.data.get(self.add_prefix(field_name))
        if raw_value in (None, ""):
            return value

        normalized = normalize_localized_decimal_input(raw_value)
        return self.fields[field_name].to_python(normalized)
