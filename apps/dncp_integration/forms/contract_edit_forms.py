from decimal import Decimal, InvalidOperation

from django import forms
from django.forms import modelformset_factory
from django.utils import timezone
from apps.dncp_integration.models import (
    Contract,
    Award,
    AwardItem,
    AwardSubItem,
    Party,
)


class ContractEditForm(forms.ModelForm):
    """Formulario para editar datos basicos del contrato"""

    period_start_date = forms.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M",
            attrs={
                "class": "form-control form-control-sm",
                "type": "datetime-local",
            },
        ),
    )
    period_end_date = forms.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M",
            attrs={
                "class": "form-control form-control-sm",
                "type": "datetime-local",
            },
        ),
    )
    value_amount = forms.DecimalField(
        required=False,
        max_digits=18,
        decimal_places=2,
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-sm money-input",
                "inputmode": "decimal",
                "placeholder": "Monto",
            }
        ),
    )

    class Meta:
        model = Contract
        fields = ['status_details', 'period_start_date', 'period_end_date', 'value_amount']
        widgets = {
            'status_details': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': 'Estado del contrato'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.period_start_date:
            start_date = self.instance.period_start_date
            if timezone.is_aware(start_date):
                start_date = timezone.localtime(start_date)
            self.initial["period_start_date"] = start_date.strftime("%Y-%m-%dT%H:%M")
        if self.instance and self.instance.period_end_date:
            end_date = self.instance.period_end_date
            if timezone.is_aware(end_date):
                end_date = timezone.localtime(end_date)
            self.initial["period_end_date"] = end_date.strftime("%Y-%m-%dT%H:%M")

    def clean_value_amount(self):
        raw_value = self.cleaned_data.get("value_amount")
        if raw_value in (None, ""):
            return None
        if isinstance(raw_value, Decimal):
            return raw_value
        if isinstance(raw_value, str):
            normalized = raw_value.replace(".", "").replace(",", ".").strip()
            try:
                return Decimal(normalized)
            except InvalidOperation:
                raise forms.ValidationError("Monto invalido.")
        return raw_value


class AwardEditForm(forms.ModelForm):
    """Formulario para editar datos basicos de la adjudicacion"""

    date = forms.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M",
            attrs={
                "class": "form-control form-control-sm",
                "type": "datetime-local",
            },
        ),
    )
    value_amount = forms.DecimalField(
        required=False,
        max_digits=18,
        decimal_places=2,
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-sm money-input",
                "inputmode": "decimal",
                "placeholder": "Monto",
            }
        ),
    )

    suppliers = forms.ModelMultipleChoiceField(
        queryset=Party.objects.filter(role=Party.ROLE_SUPPLIER),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Proveedores"
    )
    
    class Meta:
        model = Award
        fields = ['status_details', 'date', 'value_amount']
        widgets = {
            'status_details': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': 'Estado de adjudicación'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.date:
            award_date = self.instance.date
            if timezone.is_aware(award_date):
                award_date = timezone.localtime(award_date)
            self.initial["date"] = award_date.strftime("%Y-%m-%dT%H:%M")

    def clean_value_amount(self):
        raw_value = self.cleaned_data.get("value_amount")
        if raw_value in (None, ""):
            return None
        if isinstance(raw_value, Decimal):
            return raw_value
        if isinstance(raw_value, str):
            normalized = raw_value.replace(".", "").replace(",", ".").strip()
            try:
                return Decimal(normalized)
            except InvalidOperation:
                raise forms.ValidationError("Monto invalido.")
        return raw_value


class AwardItemEditForm(forms.ModelForm):
    """Formulario para editar items de adjudicación"""
    
    class Meta:
        model = AwardItem
        fields = ['quantity', 'unit_price_amount']
        widgets = {
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm inline-edit',
                'step': '1',
                'min': '0',
                'data-field': 'quantity',
                'placeholder': 'Cantidad'
            }),
            'unit_price_amount': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm inline-edit',
                'step': '0.01',
                'min': '0',
                'data-field': 'unit_price_amount',
                'placeholder': 'Precio unitario'
            }),
        }


class AwardSubItemEditForm(forms.ModelForm):
    """Formulario para editar subitems de adjudicación"""
    
    class Meta:
        model = AwardSubItem
        fields = ['quantity', 'unit_price_amount']
        widgets = {
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm inline-edit',
                'step': '1',
                'min': '0',
                'data-field': 'quantity',
                'placeholder': 'Cantidad'
            }),
            'unit_price_amount': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm inline-edit',
                'step': '0.01',
                'min': '0',
                'data-field': 'unit_price_amount',
                'placeholder': 'Precio unitario'
            }),
        }


# FormSets para edición bulk de items y subitems
AwardItemFormSet = modelformset_factory(
    AwardItem,
    form=AwardItemEditForm,
    extra=0,
    can_delete=False,
    fields=['quantity', 'unit_price_amount']
)

AwardSubItemFormSet = modelformset_factory(
    AwardSubItem,
    form=AwardSubItemEditForm,
    extra=0,
    can_delete=False,
    fields=['quantity', 'unit_price_amount']
)
