# 📋 SIGECOP - Sistema de Gestión de Contrataciones Públicas

> Plataforma web para gestionar procesos de licitación pública con integración a la API del DNCP

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square)
![Django](https://img.shields.io/badge/Django-6.0+-darkgreen?style=flat-square)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-12+-336791?style=flat-square)

---

## 📑 Tabla de Contenidos

- [¿Qué es SIGECOP?](#-qué-es-sigecop)
- [Características](#-características)
- [Requisitos](#-requisitos)
- [Instalación](#-instalación)
- [Configuración](#-configuración)
- [Funcionalidades](#-funcionalidades)
- [Estructura del Proyecto](#-estructura-del-proyecto)
- [Uso](#-uso)
- [Troubleshooting](#-troubleshooting)

---

## 🎯 ¿Qué es SIGECOP?

**SIGECOP** es un sistema web construido con Django que automatiza la importación, procesamiento y gestión de procesos de licitación pública desde la API del DNCP (Dirección Nacional de Contrataciones Públicas).

Te permite:
- 📥 Importar licitaciones automáticamente desde DNCP
- 📊 Centralizar toda la información de contrataciones
- 🔍 Auditar cambios (quién modificó qué y cuándo)
- ⚡ Gestionar lotes, items, adjudicaciones y contratos
- 🔐 Controlar acceso con autenticación

---

## ✨ Características Principales

### ✅ Importación de Licitaciones
- Sincronización automática con API DNCP
- Soporte para múltiples OCIDs en una sola operación
- Manejo robusto de errores y reintentos
- Registro de cada importación (fecha, usuario, estado)

### ✅ Gestión Completa de Datos
- **Procesos (Tenders)**: Título, estado, monto, método de contratación
- **Lotes**: Organizados por procesos
- **Items y Subitems**: Detalle técnico de lo que se contrata
- **Adjudicaciones (Awards)**: Proveedores seleccionados
- **Contratos**: Información de ejecución

### ✅ Auditoría y Trazabilidad
- Registro automático de created_at, updated_at, modified_by
- Panel administrativo para auditar cambios
- Historial completo de importaciones

### ✅ Panel Administrativo
- Interfaz Django admin optimizada
- Búsqueda y filtrado avanzado
- Acciones batch para procesamiento masivo
- Gestión de usuarios y permisos

### ✅ Multi-entorno
- Configuración separada para desarrollo y producción
- Variables de entorno para secretos
- Soporte PostgreSQL escalable

---

## 📋 Requisitos

| Requisito | Versión |
|-----------|---------|
| Python | 3.10+ |
| PostgreSQL | 12+ |
| pip | Latest |

### Dependencias Python
```
Django==6.0.1
psycopg2-binary==2.9.11
django-environ==0.12.0
requests==2.32.5
```

---

## 🚀 Instalación

### 1. Clonar repositorio
```bash
git clone https://github.com/tu-usuario/sigecop.git
cd sigecop
```

### 2. Crear entorno virtual
```bash
# Windows
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux/Mac
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Configurar base de datos
```bash
# Crear BD (asegúrate PostgreSQL está corriendo)
createdb sigecop_db

# O con usuario específico
createdb -U postgres sigecop_db
```

### 5. Configurar variables de entorno
Crea `.env` en la raíz del proyecto:
```env
SECRET_KEY=tu-clave-secreta-aqui
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

DATABASE_URL=postgresql://usuario:contraseña@localhost:5432/sigecop_db

DNCP_REQUEST_TOKEN=tu-token-dncp-aqui
```

### 6. Ejecutar migraciones
```bash
python manage.py migrate
```

### 7. Crear superusuario
```bash
python manage.py createsuperuser
# Ingresa: usuario, email, contraseña
```

### 8. Iniciar servidor
```bash
python manage.py runserver
```

Accede a **http://localhost:8000** 🎉

Admin: **http://localhost:8000/admin**

---

## ⚙️ Configuración

### Entornos

```
config/settings/
├── base.py              # Configuración compartida
├── dev.py               # Desarrollo
└── prod.py              # Producción
```

Edita `manage.py` para cambiar de entorno:
```python
# Desarrollo:
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')

# Producción:
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.prod')
```

### Variables de Entorno

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `SECRET_KEY` | Clave secreta Django | `django-insecure-...` |
| `DEBUG` | Modo debug | `True` (dev) / `False` (prod) |
| `ALLOWED_HOSTS` | Hosts permitidos | `localhost,127.0.0.1` |
| `DATABASE_URL` | URL BD PostgreSQL | `postgresql://user:pass@localhost/db` |
| `DNCP_REQUEST_TOKEN` | Token API DNCP | `tu-token-aqui` |

---

## 💡 Funcionalidades

### Módulo de Importación

#### Importar vía Web
1. Accede a `/dncp/` → "Importar Licitaciones"
2. Ingresa OCIDs (uno por línea o separados por comas)
3. Haz clic en "Importar"
4. Monitorea el progreso en tiempo real

```
Ejemplo OCID: ocid-open-2024-001234
```

#### Importar vía CLI
```bash
python manage.py import_dncp \
  --ocid "ocid-xxx-123" \
  --ocid "ocid-xxx-456"
```

### Módulo de Procesos

#### Listar Licitaciones
- Accede a `/dncp/list`
- Filtra por estado, entidad, rango de fechas
- Exporta datos en tabla
- Busca por OCID o título

#### Ver Detalles
- Accede a `/dncp/detail/<OCID>`
- Información completa del proceso
- Lotes, items, adjudicaciones asociadas
- Historial de cambios

### Módulo Admin

#### Administradores pueden:
- Ver todas las importaciones realizadas
- Editar licitaciones, lotes, items
- Gestionar usuarios y permisos
- Auditar cambios (quién modificó qué)
- Ver estado de sincronización DNCP

**URL**: `/admin`

---

## 📁 Estructura del Proyecto

```
sigecop/
├── apps/
│   └── dncp_integration/              ← App principal
│       ├── models.py                 (Tender, Lot, Item, Award, Contract)
│       ├── views/
│       │   ├── api_views.py          (Importación, listado)
│       │   ├── tender_views.py       (Detalle licitación)
│       │   └── contract_views.py     (Detalle contrato)
│       ├── services/
│       │   ├── api_client.py         (Cliente API DNCP)
│       │   ├── data_processor.py     (Procesar datos)
│       │   └── import_mapper.py      (Mapear a modelos)
│       ├── management/commands/
│       │   └── import_dncp.py        (Comando CLI)
│       ├── migrations/               (Cambios BD)
│       ├── templates/                (HTML)
│       ├── tests/
│       └── admin.py                  (Admin customizado)
│
├── config/                            ← Configuración Django
│   ├── settings/
│   │   ├── base.py                  (Común)
│   │   ├── dev.py                   (Desarrollo)
│   │   └── prod.py                  (Producción)
│   ├── urls.py                      (Rutas)
│   ├── wsgi.py
│   └── asgi.py
│
├── templates/                         ← Templates globales
│   ├── base.html
│   └── home.html
│
├── static/                            ← CSS, JS, imágenes
├── .env                               ← Variables (NO commitar)
├── .env.example                       ← Plantilla variables
├── manage.py
├── requirements.txt
└── README.md
```

---

## 📖 Uso

### Dashboard/Home
```
URL: http://localhost:8000/
- Descripción del sistema
- Accesos rápidos a funcionalidades
```

### Importar Licitaciones
```
URL: http://localhost:8000/dncp/import/
- Formulario para ingresar OCIDs
- Monitoreo de importación en progreso
- Historial de importaciones anteriores
```

### Listar Licitaciones Importadas
```
URL: http://localhost:8000/dncp/list/
- Tabla con todas las licitaciones
- Filtros por estado, entidad, fecha
- Links a detalles de cada licitación
```

### Ver Detalle de Licitación
```
URL: http://localhost:8000/dncp/detail/<OCID>/
- Información completa del proceso
- Lotes y sus items
- Adjudicaciones (proveedores ganadores)
- Presupuestos y montos
```

### Acceso Administrativo
```
URL: http://localhost:8000/admin/
- Requiere login como superusuario
- Gestión completa de datos
- Auditoría de cambios
- Gestión de usuarios
```

---

## Modelos de Datos

### Tender (Licitación)
```python
- id: Identificador único
- title: Título del proceso
- status: Estado (Abierto, Cerrado, Fallido, etc)
- procuring_entity: Entidad que contrata
- value_amount: Monto total
- date_published: Fecha de publicación
```

### Lot (Lote)
```python
- id: Identificador único
- tender: Relación a Tender
- title: Nombre del lote
- value_amount: Monto del lote
```

### Item (Item del Lote)
```python
- id: Identificador único
- lot: Relación a Lot
- description: Descripción de lo que se contrata
- quantity: Cantidad
- unit_price_amount: Precio unitario
```

### Award (Adjudicación)
```python
- id: Identificador único
- tender: Relación a Tender
- suppliers: Proveedores ganadores (relación M2M a Party)
- value_amount: Monto adjudicado
- date: Fecha de adjudicación
```

### Contract (Contrato)
```python
- id: Identificador único
- award: Relación a Award
- status: Estado del contrato
- period_start_date: Fecha inicio
- period_end_date: Fecha fin
- value_amount: Monto contratado
```

---

## 🐛 Troubleshooting

| Problema | Solución |
|----------|----------|
| `ModuleNotFoundError: django` | `pip install -r requirements.txt` |
| `No such table: ...` | `python manage.py migrate` |
| Conexión a BD rechazada | Verifica PostgreSQL está corriendo y credenciales en `.env` |
| `SECRET_KEY not configured` | Agrega `SECRET_KEY` a `.env` |
| Puerto 8000 ocupado | `python manage.py runserver 8001` |
| DNCP API timeout | Aumenta `DNCP_API_TIMEOUT` en `.env` o revisa conexión internet |
| Static files no cargan | `python manage.py collectstatic` |

---

## 📞 Contacto

- GitHub: [IDVG46](https://github.com/IDVG46)
- Empresa: **IDVG Solutions**

---
