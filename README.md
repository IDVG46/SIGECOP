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
├── dev.py     # Desarrollo (DEBUG=True, BD local)
└── prod.py    # Producción (HTTPS, SECRET_KEY obligatoria)
```

`manage.py` apunta a `config.settings.dev` por defecto.  
Para producción, exporta la variable antes de ejecutar:

```bash
export DJANGO_SETTINGS_MODULE=config.settings.prod
```

### Variables de entorno

| Variable | Descripción | Requerida |
|---|---|---|
| `SECRET_KEY` | Clave secreta Django | Sí |
| `DEBUG` | Activa modo debug | Solo dev |
| `ALLOWED_HOSTS` | Hosts permitidos (coma-separados) | Sí |
| `DATABASE_URL` | URL de conexión PostgreSQL | Sí |
| `DNCP_REQUEST_TOKEN` | Token para la API DNCP v3 | Sí |

---

## Rutas Principales

### DNCP Integration

| URL | Descripción |
|---|---|
| `/` | Inicio / dashboard |
| `/tenders/` | Listado de licitaciones importadas |
| `/tenders/<ocid>/` | Detalle de una licitación |
| `/contratos/` | Listado de contratos |
| `/contratos/<id>/` | Detalle de contrato |
| `/contratos/<id>/edit/` | Edición local de contrato |
| `/entidades/` | Entidades contratantes |
| `/api/dncp/` | API interna DNCP |

### Procurement

| URL | Descripción |
|---|---|
| `/orders/` | Órdenes de compra |
| `/orders/add/` | Nueva orden |
| `/budgets/` | Presupuestos por contrato |
| `/budgets/add/` | Nuevo presupuesto |
| `/memos/` | Cumplimientos (memos de recepción) |
| `/memos/add/` | Nuevo memo |
| `/payments/` | Pagos |
| `/payments/add/` | Nuevo pago |
| `/payments/<id>/report/` | Reporte de pago |

### Admin

| URL | Descripción |
|---|---|
| `/admin/` | Panel administrativo Django |

---

## Estructura del Proyecto

```
SIGECOP/
├── apps/
│   ├── dncp_integration/          # Integración API DNCP
│   │   ├── models.py              # CompiledRelease, Contract, Tender, Lot, Award, Party...
│   │   ├── services/
│   │   │   ├── api_client.py      # Cliente HTTP API DNCP v3
│   │   │   └── import_mapper.py   # Mapeo de respuesta JSON a modelos Django
│   │   ├── views/
│   │   ├── templates/
│   │   ├── management/commands/   # import_dncp (CLI)
│   │   └── tests/
│   │
│   └── procurement/               # Gestión transaccional
│       ├── models.py              # PurchaseOrder, ContractBudget, FulfillmentMemo, Payment...
│       ├── services/
│       │   ├── finance_service.py # Reglas de negocio: presupuesto, cumplimiento, pagos
│       │   ├── fulfillment_metrics.py  # Métricas de cumplimiento centralizadas
│       │   ├── balance/           # Servicios de saldo presupuestario
│       │   ├── budget/            # Servicios de presupuesto
│       │   └── payments/          # Servicios de pago
│       ├── views/
│       │   ├── order_views.py     # Vistas de órdenes de compra
│       │   ├── api_views.py       # Endpoints JSON para formularios dinámicos
│       │   └── finance/           # Vistas modulares de presupuesto, memos y pagos
│       │       ├── budget_views.py
│       │       ├── memo_views.py
│       │       └── payment_views.py
│       ├── forms/
│       ├── utils/
│       │   ├── decimal_utils.py   # Parsing y validación decimal centralizado
│       │   └── format_utils.py    # Formateo de montos Gs.
│       ├── templatetags/
│       ├── templates/
│       └── tests/
│
├── config/
│   ├── settings/
│   │   ├── base.py
│   │   ├── dev.py
│   │   └── prod.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
│
├── templates/          # Templates globales (base, home)
├── static/             # JS compartido (numeric-format.js)
├── .env                # Variables de entorno (NO versionar)
├── manage.py
└── requirements.txt
```

---

## Tests

Ejecutar suite de las apps instaladas:

```bash
python manage.py test apps.dncp_integration.tests apps.procurement.tests --keepdb --noinput
```

La suite cubre:
- Parsing y validación decimal localizado
- Reglas de servicio de pagos y consistencia presupuestaria
- Lógica de cumplimientos parciales y métricas de órdenes

---

## Troubleshooting

| Problema | Solución |
|---|---|
| `ModuleNotFoundError: django` | `pip install -r requirements.txt` |
| `No such table: ...` | `python manage.py migrate` |
| Conexión a BD rechazada | Verifica que PostgreSQL esté corriendo y las credenciales en `.env` |
| `SECRET_KEY not configured` | Agrega `SECRET_KEY` al archivo `.env` |
| Puerto 8000 ocupado | `python manage.py runserver 8001` |
| DNCP API timeout | Verifica conexión a internet y la validez de `DNCP_REQUEST_TOKEN` |
| Static files no cargan en prod | `python manage.py collectstatic` |
| Error de test DB existente | Usa `--keepdb --noinput` o elimina la DB de prueba manualmente |

---

## Contacto

- GitHub: [IDVG46](https://github.com/IDVG46)
- Empresa: **IDVG Solutions**

---
