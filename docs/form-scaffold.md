# Scaffold Base para Formularios Nuevos

Actualizado: 2026-04-21

Este archivo sirve como punto de partida para construir formularios nuevos alineados con SIGECOP.

Usar siempre junto con:

1. `docs/forms-and-lists-spec.md`
2. las pantallas canónicas reales del módulo (`orders`, `memos`, `payments`, `budgets`, `amendments`)

No copiar este scaffold de forma ciega. Ajustar solo lo mínimo que el caso requiera.

## 1. Formulario simple: `form.html`

```django
{% extends "base.html" %}
{% load static %}

{% block title %}Entidad - SIGECOP{% endblock %}

{% block page_title %}
<i class="ace-icon fa fa-file-text-o"></i>
Entidad
{% endblock %}

{% block page_subtitle %}{% if object and object.pk %}Editar{% else %}Agregar{% endif %}{% endblock %}

{% block breadcrumb %}
<li><i class="ace-icon fa fa-home home-icon"></i><a href="{% url 'home' %}">Inicio</a></li>
<li><a href="{% url 'app:entity_list' %}">Entidades</a></li>
<li class="active">Formulario</li>
{% endblock %}

{% block extra_css %}
<link rel="stylesheet" href="{% static 'procurement/css/procurement_form_base.css' %}" />
<link rel="stylesheet" href="{% static 'procurement/css/entity_form.css' %}" />
{% endblock %}

{% block content %}
<form method="post" id="entity-form" class="proc-form" novalidate data-is-create="{% if object and object.pk %}0{% else %}1{% endif %}">
    {% csrf_token %}

    <div class="alert form-intro">
        <strong><i class="fa fa-info-circle"></i> Consejo:</strong>
        explique en una línea el flujo correcto de uso.
    </div>

    <div id="entity-form-feedback" class="alert alert-danger form-feedback" style="display: none;"></div>

    <div class="widget-box">
        {% include "procurement/components/card_header.html" with title="Datos principales" %}
        <div class="widget-body">
            <div class="widget-main">
                {% if form.non_field_errors %}
                <div class="alert alert-danger">{{ form.non_field_errors }}</div>
                {% endif %}

                <div class="row">
                    <div class="col-sm-4">
                        <label for="{{ form.field_a.id_for_label }}">{{ form.field_a.label }}<span class="required-marker">*</span></label>
                        {{ form.field_a }}{{ form.field_a.errors }}
                    </div>
                    <div class="col-sm-4">
                        <label for="{{ form.field_b.id_for_label }}">{{ form.field_b.label }}<span class="required-marker">*</span></label>
                        {{ form.field_b }}{{ form.field_b.errors }}
                    </div>
                    <div class="col-sm-4">
                        <label for="{{ form.field_c.id_for_label }}">{{ form.field_c.label }}</label>
                        {{ form.field_c }}{{ form.field_c.errors }}
                    </div>
                </div>

                <div class="row proc-row-top">
                    <div class="col-sm-12">
                        <label for="{{ form.notes.id_for_label }}">{{ form.notes.label }}</label>
                        {{ form.notes }}{{ form.notes.errors }}
                    </div>
                </div>
            </div>
        </div>
    </div>

    {% url 'app:entity_list' as entity_cancel_url %}
    {% include "procurement/components/form_actions.html" with save_button_id="save-entity-button" cancel_url=entity_cancel_url %}
</form>
{% endblock %}

{% block extra_js %}
<script src="{% static 'procurement/js/form_errors.js' %}"></script>
<script src="{% static 'procurement/js/entity_form.js' %}"></script>
{% endblock %}
```

## 2. JS base para formulario simple: `entity_form.js`

```javascript
(function () {
    const form = document.getElementById('entity-form');
    if (!form) return;

    form.setAttribute('novalidate', 'novalidate');

    const feedbackBox = document.getElementById('entity-form-feedback');
    const formErrors = window.SIGECOPFormErrors || {};
    const firstSelect = document.getElementById('id_field_a');
    const requiredText = document.getElementById('id_field_b');

    if (window.SIGECOPUI && window.SIGECOPUI.enhanceSelects) {
        window.SIGECOPUI.enhanceSelects(form);
    }

    if (formErrors.disableNativeRequiredOnEnhancedSelects) {
        formErrors.disableNativeRequiredOnEnhancedSelects(form);
    }

    if (formErrors.decorateFieldsWithErrors) {
        formErrors.decorateFieldsWithErrors(form);
    }

    function showFormFeedback(message, level) {
        if (formErrors.showFloatingFeedback) {
            formErrors.showFloatingFeedback(feedbackBox, message, level);
            return;
        }

        if (!feedbackBox) return;
        if (!message) {
            feedbackBox.style.display = 'none';
            feedbackBox.textContent = '';
            feedbackBox.className = 'alert alert-danger form-feedback';
            return;
        }

        feedbackBox.style.display = '';
        feedbackBox.textContent = message;
        feedbackBox.className = `alert alert-${level || 'danger'} form-feedback`;
    }

    function focusField(field) {
        if (!field) return;
        if (field.tomselect) {
            const previousOpenOnFocus = field.tomselect.settings.openOnFocus;
            field.tomselect.settings.openOnFocus = false;
            if (field.tomselect.control_input) {
                field.tomselect.control_input.focus();
            } else if (field.tomselect.control) {
                field.tomselect.control.focus();
            }
            window.setTimeout(function () {
                field.tomselect.close();
                field.tomselect.settings.openOnFocus = previousOpenOnFocus;
            }, 0);
            return;
        }
        field.focus();
    }

    function clearField(field) {
        if (!field || !formErrors.clearFieldError) return;
        formErrors.clearFieldError(field);
    }

    function validateRequiredFields() {
        const requiredFields = [
            { field: firstSelect, message: 'Debe seleccionar el campo principal.' },
            { field: requiredText, message: 'Debe completar el segundo campo.' },
        ];

        requiredFields.forEach(function (entry) {
            clearField(entry.field);
        });

        for (const entry of requiredFields) {
            if (!entry.field) continue;
            const value = String(entry.field.value || '').trim();
            if (value !== '') continue;

            if (formErrors.markFieldInvalid) {
                formErrors.markFieldInvalid(entry.field, entry.message);
            }
            return entry.field;
        }

        return null;
    }

    [firstSelect, requiredText].forEach(function (field) {
        if (!field) return;
        field.addEventListener('input', function () {
            clearField(field);
            showFormFeedback('', 'danger');
        });
        field.addEventListener('change', function () {
            clearField(field);
            showFormFeedback('', 'danger');
        });
        if (field.tomselect && typeof field.tomselect.on === 'function') {
            field.tomselect.off('change');
            field.tomselect.on('change', function () {
                clearField(field);
                showFormFeedback('', 'danger');
            });
        }
    });

    form.addEventListener('submit', function (event) {
        const invalidField = validateRequiredFields();
        if (invalidField) {
            event.preventDefault();
            showFormFeedback('Revise los campos obligatorios antes de guardar.', 'danger');
            focusField(invalidField);
            return false;
        }
    });

    if (form.dataset.isCreate === '1') {
        window.setTimeout(function () {
            focusField(firstSelect || requiredText);
        }, 0);
    }
})();
```

## 3. Scaffold para bloque inline de líneas

Usar este patrón cuando la pantalla tenga tabla editable o formset inline:

```django
<div class="widget-box" id="entity-lines-widget" style="margin-top: 12px;">
    {% include "procurement/components/card_header.html" with title="Detalles" add_button_id="add-line-button" add_button_label="Agregar" %}
    <div class="widget-body">
        <div class="widget-main no-padding">
            {{ line_formset.management_form }}
            {% if line_formset.non_form_errors %}
            <div class="alert alert-danger" style="margin: 10px;">
                {{ line_formset.non_form_errors }}
            </div>
            {% endif %}
            <div class="proc-lines-wrap">
                <table class="table table-striped table-bordered table-hover proc-lines-table" id="entity-lines-table">
                    <thead>
                        <tr>
                            {% include "procurement/components/line_index_header.html" %}
                            <th>Campo A</th>
                            <th>Campo B</th>
                            {% include "procurement/components/line_actions_header.html" %}
                        </tr>
                    </thead>
                    <tbody id="entity-lines-body">
                        {% for line_form in line_formset %}
                        <tr class="entity-line-row line-row">
                            {% for hidden in line_form.hidden_fields %}{{ hidden }}{% endfor %}
                            {% include "procurement/components/line_index_cell.html" with value=forloop.counter %}
                            <td>{{ line_form.field_a }}{{ line_form.field_a.errors }}</td>
                            <td>{{ line_form.field_b }}{{ line_form.field_b.errors }}</td>
                            <td class="proc-col-actions">
                                {{ line_form.DELETE }}
                                {% include "procurement/components/line_delete_button.html" with show_label=False title="Eliminar detalle" %}
                            </td>
                        </tr>
                        {% if line_form.non_field_errors %}
                        <tr>
                            <td colspan="4" class="text-danger">{{ line_form.non_field_errors }}</td>
                        </tr>
                        {% endif %}
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</div>
```

## 4. Reglas de uso del scaffold

1. Cambiar nombres, textos, iconos y URLs antes del primer commit.
2. No dejar `autofocus` HTML si el foco inicial lo controlará JS.
3. No reemplazar `line_delete_button.html` por botones ad hoc.
4. Si la pantalla usa Tom Select, el primer foco debe ir al control visual sin abrir dropdown.
5. Si hay tabla inline, copiar también el patrón de validación por fila y bloque descrito en `docs/forms-and-lists-spec.md`.
6. Antes de abrir PR, revisar la checklist del PR template del repo.