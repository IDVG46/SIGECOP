# Arquitectura SIGECOP

Actualizado: 2026-04-21

## 1. Resumen ejecutivo

SIGECOP opera hoy como un monolito modular Django con PostgreSQL y dos dominios activos:

1. `apps.dncp_integration`: ingesta y normalización de datos externos DNCP.
2. `apps.procurement`: operación transaccional y financiera sobre contratos importados.

El estado actual verificado es estable a nivel base:

- `manage.py check` sin errores.
- suite `apps.procurement.tests` con 50 pruebas OK.
- templates principales presentes para todos los listados y formularios activos de DNCP y Procurement.

## 2. Arquitectura actual

### 2.1 Dominios

#### `apps.dncp_integration`

Responsabilidades:

1. Consumir API v3 de la DNCP.
2. Persistir releases compiladas, tenders, awards, contratos, lotes e items.
3. Exponer listados y detalles de datos importados.
4. Permitir edición local de campos operativos del contrato sin perder referencia a DNCP.

No debe hacer:

1. Reglas financieras transaccionales.
2. Cálculo de saldo presupuestario.
3. Orquestación de pagos o memorandos.

#### `apps.procurement`

Responsabilidades:

1. Gestionar órdenes de compra.
2. Gestionar presupuestos por contrato y objeto de gasto.
3. Gestionar memorandos de cumplimiento por línea.
4. Gestionar pagos y sus asignaciones.
5. Registrar trazabilidad presupuestaria mediante ledger.
6. Resolver catálogos auxiliares y opciones de formularios dinámicos.

No debe hacer:

1. Consumir payload raw de la DNCP directamente.
2. Duplicar reglas de parsing o validación de infraestructura ajenas al dominio.

## 3. Capas vigentes

### 3.1 `views`

Coordina request/response, permisos y composición de contexto.

Estado actual:

1. Listados de órdenes, presupuestos, memorandos y pagos usan mixin HTMX para parciales `_table.html`.
2. Las vistas financieras están modularizadas en `views/finance/`.
3. Las APIs internas de opciones residen en `views/api_views.py`.

### 3.2 `forms`

Centralizan entrada de usuario y validación web.

Estado actual:

1. Formularios de órdenes, memorandos y pagos ya incorporan ámbito de aplicación.
2. Presupuestos usan editor batch por contrato.
3. Persisten clases CSS históricas `select2` aunque el runtime actual se apoya en Tom Select.

### 3.3 `services`

Concentran reglas de negocio y operaciones transaccionales.

Estado actual:

1. Reglas de aprobación de presupuesto.
2. Validación de pagos vs cumplimiento aprobado.
3. Validación de adendas con impacto financiero.
4. Métricas de cumplimiento y reporte de pagos.

### 3.4 `selectors`

Encapsulan lecturas ORM reutilizables y optimizadas.

Estado actual:

1. Listados principales ya usan selectors dedicados.
2. Aún no existe un subdominio `reporting` separado.

### 3.5 `models`

Definen entidades, constraints e invariantes de dominio.

Entidades clave vigentes en procurement:

1. `PurchaseOrder` y `PurchaseOrderLine`.
2. `ContractBudget`.
3. `ContractAmendment`.
4. `FulfillmentMemo` y `FulfillmentMemoLine`.
5. `Payment` y `PaymentAllocation`.
6. `BudgetLedgerEntry`.
7. `ApplicationScope`.

## 4. Flujos implementados

### 4.1 Órdenes

Implementado:

1. Alta y edición con líneas.
2. Cancelación y eliminación.
3. Carga de proveedor y líneas dependientes por contrato.
4. Ámbito de aplicación en cabecera y detalle.

### 4.2 Presupuestos

Implementado:

1. Listado.
2. Editor batch por contrato.
3. Detalle con órdenes relacionadas y pagos imputados.
4. Aprobación de presupuesto.

Observación:

- El flujo actual está centrado en `ContractBudget`, no en una pantalla específica de adendas/ampliaciones.

### 4.3 Memorandos de cumplimiento

Implementado:

1. Alta y edición en una única tabla por líneas de orden.
2. Validación contra cantidades pendientes.
3. Aprobación posterior.
4. Ámbito de aplicación en cabecera y/o línea.

### 4.4 Pagos

Implementado:

1. Alta y edición en borrador.
2. Posteo con validación de cumplimiento aprobado.
3. Cancelación.
4. Reporte imprimible por lote, fuente y código financiero.

### 4.5 Adendas / ampliaciones

Implementado parcialmente:

1. Modelo `ContractAmendment`.
2. Validaciones de monto, plazo y código financiero.
3. Uso desde servicios para pagos en presupuestos de ampliación.
4. Registro administrativo en Django admin.

Pendiente:

1. Vistas de usuario final.
2. URLs dedicadas.
3. Formularios propios.
4. Templates de listado, formulario y detalle.

## 5. Templates activos y faltantes

Templates activos verificados:

1. DNCP: `tender_list`, `tender_detail`, `dncp_list`, `dncp_detail`, `contract_list`, `contract_detail`, `contract_edit`, `contract_create`, `organization_list`.
2. Procurement órdenes: `list`, `form`, `confirm_delete`, `_table`.
3. Procurement presupuestos: `list`, `batch_form`, `detail`, `select_contract`, `_table`.
4. Procurement memorandos: `list`, `form`, `_table`.
5. Procurement pagos: `list`, `form`, `report`, `_table`.

Templates faltantes por capacidad funcional no cerrada:

1. CRUD de `ContractAmendment`.
2. Eventual vista de ledger presupuestario para usuario final.

## 6. Convenciones vigentes relevantes

1. Reglas de negocio en `services`, no en `views`.
2. Consultas reutilizables en `selectors`.
3. HTMX para parciales de listado; DataTables como búsqueda de cliente.
4. Tom Select como mejora de selects, aunque el marcador CSS siga siendo `select2`.
5. Normalización numérica respaldada tanto en frontend como backend.

## 7. Riesgos y deuda actual

### Riesgo 1. Capacidad de adendas incompleta

El modelo existe pero el flujo de negocio para usuario final no está completo.

Impacto:

1. Dependencia operativa del admin.
2. Mayor riesgo de errores manuales.
3. Dificultad para auditar ampliaciones dentro del flujo normal.

### Riesgo 2. Deuda de nomenclatura UI

Tom Select convive con clases y nombres `select2`.

Impacto:

1. Mayor costo de mantenimiento.
2. Confusión para nuevos cambios front.

### Riesgo 3. Lógica compleja del reporte de pagos

La composición del reporte creció y requiere más cobertura de regresión.

Impacto:

1. Posibles regresiones visuales o de cálculo.
2. Coste alto de cambio sin tests de snapshot más finos.

## 8. Línea de evolución recomendada

1. Completar flujo UI de `ContractAmendment`.
2. Consolidar nomenclatura y helpers de selects.
3. Añadir más cobertura automática sobre reportes y agrupaciones por ámbito.
4. Evaluar `apps.reporting` cuando aumente la complejidad de consultas operativas.

## 9. Especificación de UI server-side

Para cualquier formulario o listado nuevo, la referencia de construcción debe ser `docs/forms-and-lists-spec.md`.

Ese documento fija:

1. estructura estándar de `list.html` y `_table.html`
2. estructura estándar de `form.html`
3. uso de componentes reutilizables
4. convenciones para formsets/tablas de líneas
5. criterios de CSS, JS y HTMX consistentes con el proyecto actual