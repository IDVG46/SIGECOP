# SIGECOP - Sistema de Gestión de Contrataciones Públicas

> Plataforma web construida con Django para gestionar procesos de contratación pública: importación desde DNCP, órdenes de compra, presupuestos, cumplimientos y pagos.

![Python](https://img.shields.io/badge/Python-3.12+-blue?style=flat-square)
![Django](https://img.shields.io/badge/Django-6.0-darkgreen?style=flat-square)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-12+-336791?style=flat-square)

---

## Tabla de Contenidos

- [¿Qué es SIGECOP?](#qué-es-sigecop)
- [Módulos](#módulos)
- [Requisitos](#requisitos)
- [Instalación](#instalación)
- [Configuración](#configuración)
- [Rutas Principales](#rutas-principales)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [Tests](#tests)
- [Troubleshooting](#troubleshooting)

---

## ¿Qué es SIGECOP?

**SIGECOP** automatiza el ciclo completo de gestión de contrataciones públicas en una entidad:

1. **Integración DNCP** — importa y sincroniza licitaciones, lotes, adjudicaciones y contratos desde la API v3 del DNCP.
2. **Procurement** — gestiona órdenes de compra/servicio por objeto de gasto, presupuestos por contrato, cumplimientos (memos) y pagos con control de saldo presupuestario.

---

## Módulos

### `apps.dncp_integration`

Consume la API DNCP y mantiene los datos locales sincronizados.

| Funcionalidad | Descripción |
|---|---|
| Importación de OCIDs | Vía formulario web o comando CLI |
| Contratos y lotes | Detalle completo con items, subitems y adjudicaciones |
| Entidades | Listado y selección de entidades contratantes |
| Edición local | Ajuste de datos de contrato (montos, resolución) sin alterar los datos DNCP |
| ImportRun log | Auditoría de cada importación (estado, fecha, usuario) |

### `apps.procurement`

Capa transaccional sobre los contratos importados.

| Funcionalidad | Descripción |
|---|---|
| **Órdenes de compra** | Creación, edición, cancelación. Vinculadas a contrato, lote y proveedor |
| **Presupuestos** (`ContractBudget`) | Asignación de montos por contrato, objeto de gasto y fuente de financiamiento |
| **Cumplimientos** (`FulfillmentMemo`) | Memos de recepción parcial o total de órdenes; flujo borrador → aprobado |
| **Pagos** (`Payment`) | Imputación de pagos con asignaciones multi-orden y multi-presupuesto |
| **Control de saldo** | El saldo presupuestario solo se afecta al imputar pagos (no al aprobar órdenes) |
| **APIs internas** | Endpoints JSON para formularios dinámicos (opciones de contratos, líneas, presupuestos) |

---

## Requisitos

| Requisito | Versión mínima |
|---|---|
| Python | 3.12 |
| PostgreSQL | 12 |
| pip | Última estable |

Dependencias principales (`requirements.txt`):

```
Django==6.0.1
psycopg2-binary==2.9.11
django-environ==0.12.0
requests==2.32.5
```

---

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/IDVG46/sigecop.git
cd sigecop/SIGECOP
```

### 2. Crear entorno virtual

```bash
# Windows
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Crear la base de datos

```bash
createdb sigecop_db
# o con usuario específico:
createdb -U postgres sigecop_db
```

### 5. Configurar variables de entorno

Crea un archivo `.env` en `SIGECOP/` (mismo directorio que `manage.py`):

```env
SECRET_KEY=cambia-esto-por-una-clave-segura
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

DATABASE_URL=postgresql://usuario:contraseña@localhost:5432/sigecop_db

DNCP_REQUEST_TOKEN=tu-token-api-dncp
```

### 6. Aplicar migraciones

```bash
python manage.py migrate
```

### 7. Crear superusuario

```bash
python manage.py createsuperuser
```

### 8. Iniciar el servidor

```bash
python manage.py runserver
```

Accede a **http://localhost:8000**  
Panel de administración: **http://localhost:8000/admin**

---

## Configuración

### Entornos de ejecución

```
config/settings/
├── base.py    # Configuración compartida
# SIGECOP - Sistema de Gestión de Contrataciones Públicas

Plataforma web basada en Django para importar datos de la DNCP y operar el ciclo transaccional de contratación pública sobre esos contratos: órdenes, presupuestos, memorandos de cumplimiento y pagos.

![Python](https://img.shields.io/badge/Python-3.12+-blue?style=flat-square)
![Django](https://img.shields.io/badge/Django-6.0-darkgreen?style=flat-square)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-12+-336791?style=flat-square)

---

## Estado auditado

Auditoría actualizada al 2026-04-21 sobre el workspace real.

- Arquitectura vigente: monolito modular Django + PostgreSQL.
- Dominios productivos: `apps.dncp_integration` y `apps.procurement`.
- Validación ejecutada: `manage.py check` sin errores y `manage.py test apps.procurement.tests --keepdb -v 0` con 50 tests OK.
- La cobertura de templates principales de DNCP y Procurement existe y está enlazada a las vistas activas.
- La deuda principal no es ausencia masiva de templates, sino desalineación documental y flujos incompletos en capacidades ya modeladas.

Hallazgos principales:

1. La documentación operativa apuntaba a `docs/architecture.md`, pero ese archivo no existía en el repositorio versionado.
2. `ContractAmendment` está implementado en modelo, admin, servicios y validaciones, pero todavía no tiene flujo web propio en procurement.
3. El estándar visual actual usa Tom Select, aunque persiste la convención histórica de clases `select2` como marcador de mejora progresiva.
4. El roadmap local seguía marcando fases cerradas, pero aún quedan pendientes funcionales relevantes: adendas/ampliaciones, endurecimiento del reporte de pagos y cierre de deuda de nomenclatura/UI.

---

## Fuentes de verdad

Fuentes oficiales para mantener sincronizado el estado del proyecto:

1. `README.md`: onboarding, mapa funcional y estado general auditado.
2. `docs/architecture.md`: arquitectura vigente, límites de dominio y gaps conocidos.
3. `docs/forms-and-lists-spec.md`: estándar para construir formularios y listados nuevos.
4. `docs/git-conventions.md`: convención de commits y versionado.
5. `.copilot_local/context/contexto.md`: contexto operativo de trabajo diario.
6. `.copilot_local/plans/implementation-plan.md`: roadmap de mejoras priorizado.

---

## Qué hace SIGECOP

SIGECOP automatiza dos capas complementarias:

1. Integración DNCP: importa licitaciones, lotes, adjudicaciones, contratos y entidades desde la API v3.
2. Gestión transaccional: crea órdenes, distribuye presupuesto por contrato, registra cumplimientos por línea y postea pagos con control presupuestario.

Reglas funcionales vigentes:

1. El presupuesto no se consume al aprobar una orden.
2. El saldo presupuestario se afecta al imputar pagos.
3. Los pagos soportan asignaciones multi-orden y multi-presupuesto.
4. Los pagos deben respetar cumplimiento aprobado y presupuesto disponible.
5. Las adendas con impacto financiero condicionan el uso de ciertos códigos financieros, pero hoy ese flujo está disponible sobre todo vía backend/admin.

---

## Módulos

### `apps.dncp_integration`

Mantiene el espejo operativo de la DNCP y permite ajustes locales controlados sobre contratos.

| Funcionalidad | Estado actual |
|---|---|
| Importación de OCID / tender | Implementada por vistas y comando |
| Persistencia de tender, lotes, awards y contratos | Implementada |
| Edición local de contrato | Implementada |
| Entidades contratantes | Implementadas |
| Auditoría de importación | Implementada |

### `apps.procurement`

Gestiona la operación financiera y documental del contrato importado.

| Funcionalidad | Estado actual |
|---|---|
| Órdenes de compra | Implementadas con líneas, ámbito de aplicación y formularios dinámicos |
| Presupuestos por contrato | Implementados con editor batch y vista de detalle |
| Memorandos de cumplimiento | Implementados por línea de orden, con aprobación posterior |
| Pagos | Implementados con asignaciones multi-orden y reporte imprimible |
| Catálogo de ámbito de aplicación | Implementado y usable desde formularios |
| Adendas / ampliaciones (`ContractAmendment`) | Parcial: modelo + reglas + admin, sin flujo UI dedicado |
| Ledger presupuestario (`BudgetLedgerEntry`) | Implementado para trazabilidad |

---

## Rutas principales

### DNCP

| URL | Descripción |
|---|---|
| `/` | Inicio |
| `/tenders/` | Listado de licitaciones/tenders |
| `/tenders/<ocid>/` | Detalle de licitación |
| `/contratos/` | Listado de contratos |
| `/contratos/<id>/` | Detalle de contrato |
| `/contratos/<id>/edit/` | Edición local de contrato |
| `/entidades/` | Entidades contratantes |

### Procurement

| URL | Descripción |
|---|---|
| `/orders/` | Listado de órdenes |
| `/orders/add/` | Alta de orden |
| `/budgets/` | Listado de presupuestos |
| `/budgets/add/` | Entrada al editor batch por contrato |
| `/budgets/contract/<contract_id>/` | Editor batch de presupuestos |
| `/budgets/<id>/detail/` | Detalle de presupuesto |
| `/memos/` | Listado de memorandos |
| `/memos/add/` | Alta de memorando |
| `/payments/` | Listado de pagos |
| `/payments/add/` | Alta de pago |
| `/payments/<id>/report/` | Reporte de pago |

---

## Templates y UI

Cobertura verificada de templates activos:

- DNCP: listados y detalles de tender, DNCP, contratos, entidades y edición/alta local de contrato.
- Procurement órdenes: `list`, `form`, `confirm_delete` y parcial `_table`.
- Procurement presupuestos: `list`, `batch_form`, `detail`, `select_contract` y parcial `_table`.
- Procurement memorandos: `list`, `form` y parcial `_table`.
- Procurement pagos: `list`, `form`, `report` y parcial `_table`.

Templates o flujos todavía faltantes a nivel funcional:

1. Pantallas de alta, edición, listado y detalle para `ContractAmendment`.
2. Navegación de usuario final para administrar ampliaciones de monto/plazo fuera del admin.
3. Posible vista consolidada de trazabilidad presupuestaria basada en ledger.

---

## Arquitectura actual

```text
SIGECOP/
├── apps/
│   ├── dncp_integration/
│   │   ├── forms/
│   │   ├── management/commands/
│   │   ├── services/
│   │   ├── templates/dncp_integration/
│   │   └── views/
│   └── procurement/
│       ├── forms/
│       ├── selectors/
│       ├── services/
│       │   ├── balance/
│       │   ├── budget/
│       │   └── payments/
│       ├── static/procurement/
│       ├── templates/procurement/
│       ├── views/
│       │   └── finance/
│       └── tests/
├── config/settings/
├── docs/
├── static/
└── templates/
```

Principios vigentes:

1. Reglas de negocio en `services`.
2. Lecturas complejas en `selectors`.
3. Templates server-side con mejoras UX via JS progresivo, HTMX y Tom Select.
4. Validación crítica repetida entre formularios, servicios y modelos cuando corresponde.

---

## Instalación rápida

```bash
git clone https://github.com/IDVG46/sigecop.git
cd sigecop/SIGECOP
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Variables mínimas esperadas en `.env`:

```env
SECRET_KEY=clave-segura
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=postgresql://usuario:password@localhost:5432/sigecop_db
DNCP_REQUEST_TOKEN=token-api-dncp
```

---

## Tests y validación

Comandos recomendados:

```bash
python manage.py check
python manage.py test apps.procurement.tests --keepdb -v 0
python manage.py test apps.dncp_integration.tests apps.procurement.tests --keepdb --noinput
```

Cobertura funcional principal:

1. Parsing decimal localizado.
2. Validaciones de pagos y cumplimiento.
3. Reglas presupuestarias y ledger.
4. Métricas de cumplimiento por orden y por línea.
5. Validación de adendas para códigos financieros con impacto monetario.

---

## Backlog prioritario

1. Implementar flujo UI completo para `ContractAmendment`.
2. Unificar nomenclatura `select2`/Tom Select para reducir deuda de mantenimiento.
3. Fortalecer pruebas del reporte de pagos y de agrupaciones por ámbito.
4. Evaluar extracción de reporting cuando la carga de consultas lo justifique.

---

## Troubleshooting

| Problema | Solución |
|---|---|
| `ModuleNotFoundError: django` | Ejecutar `pip install -r requirements.txt` |
| `No such table` | Ejecutar `python manage.py migrate` |
| Error de conexión PostgreSQL | Revisar `DATABASE_URL` y servicio de BD |
| Token DNCP inválido | Revisar `DNCP_REQUEST_TOKEN` |
| Archivos estáticos en producción | Ejecutar `python manage.py collectstatic` |
