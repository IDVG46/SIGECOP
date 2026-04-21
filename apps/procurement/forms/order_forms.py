from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory

from apps.dncp_integration.models import AwardItem, AwardSubItem, Lot, Party
from apps.procurement.forms.mixins import LocalizedDecimalMixin
from apps.procurement.models import ApplicationScope, ExpenseObject, PurchaseOrder, PurchaseOrderLine


def _award_item_label(instance):
    order_value = instance.orden_licitado if instance.orden_licitado is not None else "-"
    description = instance.item.description if instance.item else "Sin descripción"
    return f"{order_value} - {description}"


def _award_subitem_label(instance):
    order_value = instance.orden_licitado if instance.orden_licitado is not None else "-"
    description = instance.subitem.description if instance.subitem else "Sin descripción"
    return f"{order_value} - {description}"


class PurchaseOrderForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        contract = kwargs.pop("contract", None)
        super().__init__(*args, **kwargs)

        self.fields["supplier"].queryset = Party.objects.filter(role=Party.ROLE_SUPPLIER)
        self.fields["issue_date"].input_formats = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]
        self.fields["expense_object"].queryset = ExpenseObject.objects.filter(is_active=True).order_by("code")
        self.fields["expense_object"].required = True
        self.fields["application_scope"].queryset = ApplicationScope.objects.filter(is_active=True).order_by("name")
        self.fields["application_scope"].required = False

        if self.instance and self.instance.pk and self.instance.expense_object_id and not self.instance.expense_object.is_active:
            self.fields["expense_object"].queryset = ExpenseObject.objects.filter(pk=self.instance.expense_object_id)

        contract_obj = contract
        if contract_obj is None and self.instance and self.instance.pk:
            contract_obj = self.instance.contract

        if contract_obj is not None:
            self.fields["contract"].initial = contract_obj.pk
            self.fields["supplier"].queryset = contract_obj.award.suppliers.filter(role=Party.ROLE_SUPPLIER)

    class Meta:
        model = PurchaseOrder
        fields = [
            "order_number",
            "contract",
            "supplier",
            "issue_date",
            "expense_object",
            "application_scope",
            "application_detail",
            "delivery_term",
            "delivery_place",
            "status",
            "notes",
        ]
        widgets = {
            "issue_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"}),
            "order_number": forms.TextInput(attrs={"class": "form-control", "autofocus": True}),
            "contract": forms.Select(attrs={"class": "form-control select2"}),
            "supplier": forms.Select(attrs={"class": "form-control select2"}),
            "expense_object": forms.Select(attrs={"class": "form-control select2"}),
            "application_scope": forms.Select(attrs={"class": "form-control select2"}),
            "application_detail": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ej: Camioneta Toyota Hilux placa ABC123",
                }
            ),
            "delivery_term": forms.TextInput(attrs={"class": "form-control"}),
            "delivery_place": forms.TextInput(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-control select2"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }


class PurchaseOrderLineForm(LocalizedDecimalMixin, forms.ModelForm):
    def __init__(self, *args, **kwargs):
        contract = kwargs.pop("contract", None)
        super().__init__(*args, **kwargs)

        self.fields["lot"].queryset = Lot.objects.none()
        self.fields["award_item"].queryset = AwardItem.objects.none()
        self.fields["award_subitem"].queryset = AwardSubItem.objects.none()
        self.fields["application_scope"].queryset = ApplicationScope.objects.filter(is_active=True).order_by("name")
        self.fields["application_scope"].required = False

        contract_obj = contract
        if contract_obj is None and self.instance and self.instance.pk:
            contract_obj = self.instance.purchase_order.contract

        if contract_obj is not None:
            self.fields["lot"].queryset = Lot.objects.filter(tender=contract_obj.award.tender).order_by("id")
            self.fields["award_item"].queryset = AwardItem.objects.filter(award=contract_obj.award).select_related("item")
            self.fields["award_subitem"].queryset = AwardSubItem.objects.filter(award=contract_obj.award).select_related("subitem")

        self.fields["award_item"].label_from_instance = _award_item_label
        self.fields["award_subitem"].label_from_instance = _award_subitem_label

    class Meta:
        model = PurchaseOrderLine
        fields = ["lot", "award_item", "award_subitem", "quantity", "unit_price", "application_scope", "application_detail"]
        widgets = {
            "lot": forms.Select(attrs={
                "class": "form-control select2",
                "placeholder": "Buscar lote...",
                "data-placeholder": "Buscar lote...",
            }),
            "award_item": forms.Select(attrs={
                "class": "form-control select2",
                "placeholder": "Buscar item...",
                "data-placeholder": "Buscar item...",
            }),
            "award_subitem": forms.Select(attrs={
                "class": "form-control select2",
                "placeholder": "Buscar subitem...",
                "data-placeholder": "Buscar subitem...",
            }),
            "quantity": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "inputmode": "decimal",
                    "autocomplete": "off",
                    "placeholder": "0",
                }
            ),
            "unit_price": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "inputmode": "decimal",
                    "autocomplete": "off",
                    "placeholder": "0",
                }
            ),
            "application_scope": forms.Select(attrs={"class": "form-control select2"}),
            "application_detail": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Detalle específico (opcional)",
                }
            ),
        }

    def clean_quantity(self):
        value = self._clean_localized_decimal_field("quantity")
        if value is None:
            return value
        if value != value.to_integral_value():
            raise ValidationError("La cantidad debe ser un numero entero.")
        return value

    def clean_unit_price(self):
        return self._clean_localized_decimal_field("unit_price")


class BasePurchaseOrderLineFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()

        if any(self.errors):
            return

        has_detail_line = False
        header_scope = getattr(self.instance, "application_scope", None)
        if header_scope is None and self.is_bound:
            header_scope_id = self.data.get("application_scope")
            if header_scope_id:
                try:
                    header_scope = ApplicationScope.objects.filter(pk=header_scope_id).first()
                except (TypeError, ValueError):
                    header_scope = None
        for form in self.forms:
            cleaned = getattr(form, "cleaned_data", None) or {}
            if not cleaned or cleaned.get("DELETE"):
                continue

            has_values = any(
                cleaned.get(field) not in (None, "")
                for field in ("lot", "award_item", "award_subitem", "quantity", "unit_price")
            )
            if has_values:
                has_detail_line = True
                line_scope = cleaned.get("application_scope")
                if not line_scope and not header_scope:
                    form.add_error(
                        "application_scope",
                        "Defina un ámbito en la línea o en la cabecera de la orden.",
                    )
                continue

        if not has_detail_line:
            raise ValidationError("Debe agregar al menos una línea de detalle para guardar la orden.")

PurchaseOrderLineFormSet = inlineformset_factory(
    PurchaseOrder,
    PurchaseOrderLine,
    form=PurchaseOrderLineForm,
    formset=BasePurchaseOrderLineFormSet,
    extra=1,
    can_delete=True,
)

PurchaseOrderLineEditFormSet = inlineformset_factory(
    PurchaseOrder,
    PurchaseOrderLine,
    form=PurchaseOrderLineForm,
    formset=BasePurchaseOrderLineFormSet,
    extra=0,
    can_delete=True,
)
