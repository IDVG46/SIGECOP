# Especificación de Formularios y Listas

Actualizado: 2026-04-21

## 1. Propósito

Este documento define el estándar de construcción para formularios y listas en SIGECOP.

Objetivos:

1. Mantener una experiencia visual y estructural consistente.
2. Reducir variaciones innecesarias entre módulos.
3. Dejar una fuente de verdad para futuras pantallas.
4. Facilitar mantenimiento, revisión y expansión del sistema.

Esta especificación está basada en los patrones reales hoy usados en `apps.procurement` y debe tomarse como referencia por defecto para nuevas pantallas server-side.

## 2. Alcance

Aplica a:

1. Páginas de listado (`list.html` y parciales `_table.html`).
2. Formularios de alta/edición.
3. Formularios con formsets inline o tablas de detalle.
4. Vistas que usan DataTables, HTMX y Tom Select dentro de la UI server-side.

No reemplaza reglas de negocio ni validaciones de dominio. Solo estandariza construcción, composición y convenciones de interfaz.

## 3. Principios de diseño

1. La estructura base debe ser predecible entre módulos.
2. La vista debe ser delgada; la lógica de negocio queda fuera del template.
3. El template principal compone bloques; los fragmentos repetidos se extraen a componentes.
4. Los listados deben poder degradarse a parcial HTMX sin duplicar markup.
5. Los formularios deben soportar validación de servidor y feedback cliente consistente.

## 4. Convenciones de ubicación y nombres

### 4.1 Listas

Toda lista nueva debe usar, como regla general:

1. `templates/<dominio>/<subdominio>/list.html`
2. `templates/<dominio>/<subdominio>/_table.html`

Ejemplos actuales:

1. `procurement/orders/list.html`
2. `procurement/orders/_table.html`
3. `procurement/finance/payments/list.html`
4. `procurement/finance/payments/_table.html`

### 4.2 Formularios

Todo formulario de alta/edición debe usar, como regla general:

1. `templates/<dominio>/<subdominio>/form.html`

Si la pantalla es especializada, puede tener nombres más específicos como:

1. `batch_form.html`
2. `detail.html`
3. `confirm_delete.html`

### 4.3 Componentes reutilizables

Los componentes transversales deben vivir en:

1. `templates/procurement/components/`

Componentes ya estandarizados:

1. `card_header.html`
2. `form_actions.html`
3. `line_index_header.html`
4. `line_index_cell.html`
5. `line_actions_header.html`
6. `line_delete_button.html`
7. `application_scope_modal.html`

## 5. Especificación de listas

### 5.1 Estructura de `list.html`

Toda página de listado debe:

1. Extender `base.html`.
2. Declarar `title`, `page_title`, `page_subtitle` y `breadcrumb`.
3. Tener botón de alta arriba a la derecha si la pantalla permite creación.
4. Encapsular la tabla en `widget-box`.
5. Renderizar el parcial `_table.html` dentro de un wrapper identificable.

Patrón recomendado:

```django
{% extends "base.html" %}

{% block title %}Entidad - SIGECOP{% endblock %}

{% block page_title %}
<i class="ace-icon fa fa-icono"></i>
Entidad
{% endblock %}

{% block page_subtitle %}Lista{% endblock %}

{% block breadcrumb %}
<li><i class="ace-icon fa fa-home home-icon"></i><a href="{% url 'home' %}">Inicio</a></li>
<li class="active">Entidad</li>
{% endblock %}

{% block content %}
<div class="row">
    <div class="col-xs-12">
        <div class="clearfix" style="margin-bottom: 12px;">
            <a href="{% url 'app:entity_create' %}" class="btn btn-success btn-sm pull-right">
                <i class="fa fa-plus"></i> Nueva entidad
            </a>
        </div>

        <div class="widget-box">
            <div class="widget-header widget-header-blue widget-header-flat">
                <h4 class="widget-title lighter">
                    <i class="ace-icon fa fa-icono"></i>
                    Listado de Entidades
                </h4>
            </div>
            <div class="widget-body">
                <div class="widget-main no-padding" id="entity-table-wrapper">
                    {% include "app/entity/_table.html" %}
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

### 5.2 Estructura de `_table.html`

Toda tabla de listado debe:

1. Ser autosuficiente para render completo o parcial HTMX.
2. Usar clase `datatable` cuando la búsqueda/ordenamiento sea del lado cliente.
3. Declarar `data-order-column` y `data-order-dir` si el orden inicial importa.
4. Tener columna final de acciones con ancho acotado.
5. Incluir estado vacío claro dentro de `<tbody>`.

Patrón recomendado:

```django
<table class="table table-striped table-bordered table-hover datatable" data-order-column="0" data-order-dir="desc">
    <thead>
        <tr>
            <th>Columna</th>
            <th class="center">Estado</th>
            <th class="center" style="width: 10%;"></th>
        </tr>
    </thead>
    <tbody>
        {% for item in object_list %}
        <tr>
            <td>{{ item }}</td>
            <td class="center">{{ item.get_status_display }}</td>
            <td class="center">
                <div class="action-buttons">
                    <!-- acciones -->
                </div>
            </td>
        </tr>
        {% empty %}
        <tr>
            <td colspan="3" class="center">
                <div class="empty-state" style="padding: 40px 0;">
                    <i class="ace-icon fa fa-inbox fa-3x grey"></i>
                    <p class="grey" style="margin-top: 15px; font-size: 16px;">Sin registros.</p>
                </div>
            </td>
        </tr>
        {% endfor %}
    </tbody>
</table>
```

### 5.3 Convenciones de vista para listas

Toda vista de listado nueva debe usar, si aplica render parcial por HTMX:

1. `HtmxTemplateMixin`
2. `template_name = ".../list.html"`
3. `partial_template_name = ".../_table.html"`
4. `context_object_name` explícito

Patrón recomendado:

```python
class EntityListView(HtmxTemplateMixin, LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "app.view_entity"
    model = Entity
    template_name = "app/entity/list.html"
    partial_template_name = "app/entity/_table.html"
    context_object_name = "entities"
```

## 6. Especificación de formularios

### 6.1 Estructura general

Todo formulario nuevo debe:

1. Extender `base.html`.
2. Cargar `static` si usa CSS/JS propios.
3. Incluir `procurement_form_base.css` cuando siga el patrón estándar de procurement.
4. Envolver el contenido en `<form class="proc-form">`.
5. Incluir CSRF.
6. Tener `form-intro` si hay ayuda contextual útil.
7. Tener un contenedor explícito de feedback global.
8. Separar visualmente cabecera y detalle por `widget-box`.
9. Cerrar con `form_actions.html`.

Patrón mínimo:

```django
{% extends "base.html" %}
{% load static %}

{% block extra_css %}
<link rel="stylesheet" href="{% static 'procurement/css/procurement_form_base.css' %}" />
<link rel="stylesheet" href="{% static 'procurement/css/entity_form.css' %}" />
{% endblock %}

{% block content %}
<form method="post" id="entity-form" class="proc-form" novalidate>
    {% csrf_token %}

    <div class="alert form-intro">
        <strong><i class="fa fa-info-circle"></i> Consejo:</strong>
        texto corto de ayuda.
    </div>

    <div id="form-feedback" class="alert alert-danger form-feedback" style="display: none;"></div>

    <div class="widget-box">
        {% include "procurement/components/card_header.html" with title="Datos principales" %}
        <div class="widget-body">
            <div class="widget-main">
                <!-- filas de campos -->
            </div>
        </div>
    </div>

    {% include "procurement/components/form_actions.html" with save_button_id="save-entity-button" cancel_url=cancel_url %}
</form>
{% endblock %}
```

### 6.2 Distribución de campos

Convenciones:

1. Usar grilla Bootstrap con `.row` y `.col-sm-*`.
2. Agrupar campos por afinidad funcional, no solo por cantidad.
3. Cuando un campo es obligatorio y se renderiza manualmente, incluir `span.required-marker`.
4. Mantener espaciado vertical consistente usando `proc-row-top` o `style="margin-top: 10px;"` solo cuando todavía no exista clase dedicada.
5. Si el widget del formulario ya trae label correcto y no requiere asterisco visual, puede usarse `{{ form.campo.label_tag }}`.

### 6.3 Validaciones visibles

Todo formulario nuevo debe soportar ambos niveles:

1. Errores de servidor: `form.non_field_errors`, `field.errors`, `formset.non_form_errors`.
2. Feedback cliente: bloque `form-feedback` y clases `js-client-invalid` cuando haya JS asociado.

Reglas:

1. Los errores globales van al inicio del `widget-main` correspondiente o al feedback general.
2. Los errores de campo deben renderizarse junto al control.
3. Los formularios complejos con JS deben incluir `form_errors.js`.
4. El orden de validación cliente debe seguir el mismo orden visual del formulario, de arriba hacia abajo y de izquierda a derecha.
5. Si un campo es obligatorio en la práctica del flujo, debe quedar marcado igual en los tres niveles: etiqueta visual, `Form.required` y validación JS.
6. Los errores de servidor deben decorarse con `decorateFieldsWithErrors()` para no dejar `errorlist` crudo cuando el formulario ya usa patrón JS.
7. El feedback flotante debe resumir el problema y luego llevar el foco al primer campo o fila inválida.

### 6.4 Foco inicial y foco de error

Reglas:

1. En formularios de alta, el foco inicial debe caer en el primer campo operativo del flujo, no necesariamente en el primer input del DOM.
2. Si el primer campo operativo es un `select` mejorado con Tom Select, el foco debe ir al control visual de Tom Select.
3. El foco inicial no debe abrir el dropdown automáticamente salvo que la pantalla lo requiera de forma explícita.
4. Cuando una validación falle sobre un `select` mejorado, el foco debe volver al control visual de Tom Select y no al `select` oculto.
5. No usar `autofocus` HTML en campos de texto si el foco real será controlado por JS.

### 6.5 Contrato mínimo para formularios con JS

Si el formulario tiene validación cliente o selects mejorados, debe cumplir este contrato:

1. Tener `id` estable en el `<form>`.
2. Tener contenedor `form-feedback` con `id` propio.
3. Ejecutar `SIGECOPUI.enhanceSelects(form)` al iniciar.
4. Ejecutar `SIGECOPFormErrors.disableNativeRequiredOnEnhancedSelects(form)` cuando use Tom Select.
5. Ejecutar `SIGECOPFormErrors.decorateFieldsWithErrors(form)` para hidratar errores de servidor.
6. Limpiar errores de campo al `input` o `change`.
7. Normalizar importes o cantidades antes del submit cuando corresponda.

## 7. Formularios con tablas de líneas o formsets

### 7.1 Estructura obligatoria

Cuando un formulario tenga líneas repetibles:

1. Incluir `management_form`.
2. Encapsular la tabla en `proc-lines-wrap`.
3. Usar `proc-lines-table` como tabla base.
4. Usar componentes de índice y acciones.
5. Incluir `<template>` para nuevas filas si habrá agregado dinámico.

Patrón base:

```django
<div class="widget-box" style="margin-top: 12px;">
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
                <table class="table table-bordered table-striped proc-lines-table">
                    <thead>...</thead>
                    <tbody>...</tbody>
                </table>
            </div>
        </div>
    </div>
</div>
```

### 7.2 Columnas comunes

Si el patrón es de líneas editables, priorizar este orden:

1. Índice.
2. Campos relacionales principales.
3. Cantidades o importes.
4. Campos auxiliares.
5. Total calculado si aplica.
6. Acciones.

### 7.3 Acciones de fila

Toda fila eliminable debe usar el componente `line_delete_button.html` cuando el patrón coincida. No crear botones ad hoc si el comportamiento es el mismo.

Reglas adicionales:

1. Las filas inline reutilizables deben llevar la clase `line-row` además de sus clases específicas del módulo.
2. El estado eliminado/restaurable debe apoyarse en `line_delete.js` o replicar exactamente su contrato visual.
3. El botón debe alternar entre `Eliminar detalle` y `Restaurar detalle`.
4. El estado restaurable debe verse en verde; no debe quedar rojo cuando la fila ya está marcada para borrar.

### 7.4 Validación inline de tablas editables

Toda tabla editable nueva debe seguir el mismo patrón de órdenes, memorandos y presupuestos batch:

1. Validar por fila, no solo por celda aislada.
2. Ignorar filas nuevas completamente vacías si el flujo permite agregarlas dinámicamente.
3. Tratar como inválida toda fila parcialmente cargada que no complete sus requeridos.
4. Marcar la fila completa con estado visual de error además del campo puntual.
5. Marcar el bloque completo (`widget-box`) con `js-client-invalid-block` cuando exista al menos una fila inválida.
6. Si no hay ninguna fila activa y el flujo exige detalle, mostrar feedback global y llevar scroll al bloque.
7. Al corregir un campo, limpiar tanto el error del campo como el estado de error de la fila.
8. Si una fila se marca para borrar, limpiar su estado inválido.
9. El primer error del submit debe llevar scroll a la primera fila inválida y foco al primer control inválido de esa fila.

## 8. CSS y comportamiento estándar

### 8.1 Base visual

Si el formulario sigue el estándar procurement, debe cargar:

1. `procurement/css/procurement_form_base.css`
2. CSS específico del módulo solo para layout o comportamiento particular

`procurement_form_base.css` ya define:

1. `proc-form`
2. `form-intro`
3. `form-feedback`
4. `required-marker`
5. `friendly-header`
6. `proc-lines-wrap`
7. `proc-lines-table`
8. estilos de foco
9. estilos de error de cliente

### 8.2 Selects

Regla vigente del proyecto:

1. El runtime estándar es Tom Select.
2. Puede mantenerse la clase `select2` por compatibilidad interna mientras no se cierre la deuda técnica existente.
3. No introducir un tercer patrón de selects.
4. El control visible de Tom Select es la referencia real para foco, validación y styling; no diseñar comportamientos nuevos contra el `select` oculto.
5. Los estilos de error deben contemplar también el estado `focus` o `input-active` del wrapper de Tom Select.

### 8.3 DataTables

Si la lista usa búsqueda y ordenamiento del lado cliente:

1. Usar clase `datatable`.
2. Declarar orden inicial con `data-order-column` y `data-order-dir`.
3. No duplicar filtros server-side si la pantalla ya está estandarizada sobre DataTables.

## 9. JS estándar por tipo de pantalla

### 9.1 Formularios simples

Incluir solo el JS específico si realmente agrega comportamiento.

### 9.2 Formularios complejos

Si hay validación cliente, filas dinámicas o selects dependientes, usar:

1. `form_errors.js`
2. `line_delete.js` si hay eliminación/restauración de filas
3. JS específico de pantalla, por ejemplo:
   - `order_form.js`
   - `memo_form.js`
   - `payment_form.js`
   - `batch_budget_form.js`

El JS específico de pantalla debe exponer como mínimo estos comportamientos cuando apliquen:

1. `showFormFeedback()` o equivalente.
2. `validateRequiredFields()` o separación equivalente entre cabecera y detalle.
3. `focusField()` con soporte para Tom Select.
4. `clearFieldError()` al modificar campos.
5. `decorateFieldsWithErrors()` al cargar respuestas del servidor con errores.

### 9.3 Atributos `data-*`

Los endpoints y banderas para JS deben vivir en el `<form>` o en el contenedor principal de la pantalla, no dispersos en múltiples nodos sin necesidad.

## 10. Checklist para nuevas pantallas

### 10.1 Nueva lista

1. Crear `list.html`.
2. Crear `_table.html`.
3. Usar `HtmxTemplateMixin` si habrá parcial HTMX.
4. Añadir botón de alta si corresponde.
5. Añadir estado vacío.
6. Añadir columna de acciones consistente.

### 10.2 Nuevo formulario

1. Extender `base.html`.
2. Cargar `procurement_form_base.css` si aplica.
3. Usar `<form class="proc-form">`.
4. Incluir `form-intro` si hay ayuda útil.
5. Incluir `form-feedback`.
6. Agrupar por `widget-box`.
7. Renderizar errores globales y por campo.
8. Cerrar con `form_actions.html`.
9. Si hay formset, usar `proc-lines-wrap` y `proc-lines-table`.
10. Si hay JS, usar nombres y data attributes consistentes.
11. Si usa Tom Select, definir foco inicial y foco de error sobre el control visual.
12. Alinear el orden de validación JS con el orden visual del formulario.
13. No dejar requeridos solo en JS o solo en backend; sincronizar label, `required` y validación cliente.

### 10.3 Checklist de revisión antes de merge

Antes de cerrar una pantalla nueva, validar explícitamente:

1. Los errores de servidor se ven con el mismo estilo que los errores cliente.
2. El primer error enfoca el control correcto.
3. Los `select` con Tom Select mantienen estilo rojo en error incluso cuando tienen foco.
4. El foco inicial del alta cae en el primer control operativo correcto y no abre dropdown por accidente.
5. Las filas inline nuevas vacías no quedan marcadas como error por defecto.
6. Las filas inline parciales sí quedan marcadas como error completo.
7. El botón de eliminar/restaurar usa `line_delete_button.html` o un patrón 100% idéntico.
8. El estado restaurar se muestra en verde.

## 11. Qué no hacer

1. No crear listas completas sin `_table.html` si el módulo ya usa patrón HTMX/tabla parcial.
2. No mezclar estilos inline extensos cuando el patrón ya existe en CSS base o de módulo.
3. No duplicar botones de guardar/cancelar fuera de `form_actions.html` salvo caso excepcional muy justificado.
4. No introducir un nuevo estilo de tabla editable paralelo a `proc-lines-table` sin necesidad real.
5. No inventar convenciones nuevas de naming si ya existe equivalente en procurement.
6. No dejar decisiones de foco inicial o validación inline “a criterio”; deben salir de esta especificación.
7. No crear variantes locales del botón de eliminar fila cuando el componente compartido ya cubre el caso.

## 12. Estado de adopción actual

Pantallas que ya siguen en gran parte este estándar:

1. Órdenes.
2. Pagos.
3. Memorandos.
4. Presupuestos batch y detalle.
5. Adendas.

## 13. Referencias canónicas

Cuando haya dudas sobre implementación, tomar como referencia primero estas pantallas reales:

1. Órdenes: formulario complejo con cabecera, líneas, validación cliente y modal auxiliar.
2. Memorandos: formulario con tabla inline, validación por fila y feedback global.
3. Pagos: formulario financiero con validación de bloque complejo.
4. Presupuestos batch: editor inline de formset con borrado/restauración y validación por fila.
5. Adendas: formulario simple con Tom Select, foco controlado por JS y validación cliente alineada al orden visual.

## 14. Artefactos de trabajo recomendados

Para nuevos desarrollos, usar además:

1. `docs/form-scaffold.md` como base copiable de `form.html`, JS de formulario y bloque inline.
2. `.github/PULL_REQUEST_TEMPLATE.md` como checklist mínima de revisión antes de merge.

Este documento debe usarse como base para futuras implementaciones antes de introducir nuevos formularios o listas.