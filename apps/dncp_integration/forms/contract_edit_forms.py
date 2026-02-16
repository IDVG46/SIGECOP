from django import forms
from django.forms import modelformset_factory, inlineformset_factory
from apps.dncp_integration.models import (
    Contract,
    Award,
    AwardItem,
    AwardSubItem,
    Party,
)


class ContractEditForm(forms.ModelForm):
    """Formulario para editar datos básicos del contrato"""
    
    class Meta:
        model = Contract
        fields = ['status_details', 'period_start_date', 'period_end_date', 'value_amount']
        widgets = {
            'status_details': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': 'Estado del contrato'
            }),
            'period_start_date': forms.DateTimeInput(attrs={
                'class': 'form-control form-control-sm',
                'type': 'datetime-local',
            }),
            'period_end_date': forms.DateTimeInput(attrs={
                'class': 'form-control form-control-sm',
                'type': 'datetime-local',
            }),
            'value_amount': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Monto'
            }),
        }


class AwardEditForm(forms.ModelForm):
    """Formulario para editar datos básicos de la adjudicación"""
    
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
            'date': forms.DateTimeInput(attrs={
                'class': 'form-control form-control-sm',
                'type': 'datetime-local',
            }),
            'value_amount': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Monto'
            }),
        }


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
