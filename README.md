# 📋 SIGECOP - Sistema de Gestión de Contrataciones Públicas

> Un sistema moderno y escalable para gestionar procesos de licitación pública con integración a la API del DNCP.

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square)
![Django](https://img.shields.io/badge/Django-6.0+-darkgreen?style=flat-square)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-12+-336791?style=flat-square)

## 🎯 ¿Qué es SIGECOP?

SIGECOP es una plataforma web construida con Django que automatiza la importación, procesamiento y gestión de datos de licitaciones públicas desde la API del DNCP. Te permite centralizar toda la información de contrataciones en un único lugar, fácil de consultar y administrar.

## ✨ Características

- ✅ Integración automática con API DNCP
- ✅ Importación masiva de procesos de licitación
- ✅ Gestión de lotes, items y adjudicaciones
- ✅ Panel administrativo intuitivo
- ✅ Configuración multi-entorno (dev/prod)
- ✅ Base de datos PostgreSQL escalable

## 🚀 Inicio Rápido

### Requisitos previos

- Python 3.10 o superior
- PostgreSQL 12 o superior
- pip y virtualenv

### 1️⃣ Clona el repositorio

```bash
git clone https://github.com/IDVG46/sigecop.git
cd sigecop
```

### 2️⃣ Prepara tu entorno virtual

```bash
# Crear entorno virtual
python -m venv .venv

# Activar (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# O en Linux/Mac
source .venv/bin/activate
```

### 3️⃣ Instala las dependencias

```bash
pip install -r requirements.txt
```

### 4️⃣ Configura las variables de entorno

Crea un archivo `.env` en la raíz:

```env
# Seguridad
SECRET_KEY=tu_clave_super_secreta_aqui_cambia_en_produccion

# Entorno
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Base de datos (PostgreSQL recomendado)
DATABASE_URL=postgresql://usuario:contraseña@localhost:5432/sigecop_db
```

### 5️⃣ Configura la base de datos

```bash
# Crea la base de datos
createdb sigecop_db

# Ejecuta las migraciones
python manage.py migrate
```

### 6️⃣ ¡Listo! Inicia el servidor

```bash
python manage.py runserver
```

Visita: **http://localhost:8000** 🎉

## 📁 Estructura del Proyecto

```
sigecop/
├── 📂 apps/
│   └── 📂 dncp_integration/        ← La app principal
│       ├── services/               (Lógica de negocio)
│       ├── utils/                  (Funciones auxiliares)
│       ├── tests/                  (Tests)
│       ├── templates/              (HTML)
│       └── migrations/
├── 📂 config/                      ← Configuración del proyecto
│   ├── settings/
│   │   ├── base.py                (Común a todos los entornos)
│   │   ├── dev.py                 (Desarrollo)
│   │   ├── prod.py                (Producción)
│   │   └── db.py                  (Base de datos)
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── 📂 templates/                   (Templates globales)
├── 📂 static/                      (CSS, JS, imágenes)
├── .env                            (Variables de entorno 🔒)
├── .gitignore
├── manage.py
└── README.md                       ← Tú estás aquí
```

## ⚙️ Configuración Avanzada

### Cambiar entre entornos

En `manage.py`, cambia la variable:

```python
# Para desarrollo:
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')

# Para producción:
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.prod')
```

### Variables de entorno (.env)

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `SECRET_KEY` | Clave secreta (cambiar en producción) | `django-insecure-...` |
| `DEBUG` | Modo debug | `True` (dev) / `False` (prod) |
| `ALLOWED_HOSTS` | Hosts permitidos | `localhost,127.0.0.1` |
| `DATABASE_URL` | Conexión PostgreSQL | `postgresql://user:pass@localhost/db` |

## 📝 Convención de Commits

Usamos **Conventional Commits** para mantener el historial limpio:

```bash
# Nueva funcionalidad
git commit -m "feat: agregar vista de licitaciones"

# Corrección
git commit -m "fix: validar campos del formulario"

# Refactor
git commit -m "refactor: optimizar query de licitaciones"

# Tareas
git commit -m "chore: actualizar dependencies"

# Documentación
git commit -m "docs: agregar guía de setup"

# Tests
git commit -m "test: agregar tests para api client"
```

## 🧪 Desarrollo y Testing

### Ejecutar tests

```bash
# Todos los tests
python manage.py test

# Solo app específica
python manage.py test apps.dncp_integration

# Con cobertura
coverage run --source='.' manage.py test
coverage report
```

### Migraciones

```bash
# Crear nuevas migraciones
python manage.py makemigrations

# Aplicar migraciones
python manage.py migrate

# Ver estado
python manage.py showmigrations
```

### Acceder a admin

1. Crea un superusuario:
   ```bash
   python manage.py createsuperuser
   ```

2. Abre: **http://localhost:8000/admin**

## 🐛 Troubleshooting

| Problema | Solución |
|----------|----------|
| ImportError: `django_environ` | `pip install django-environ psycopg2-binary` |
| Error en PostgreSQL | Verifica que está corriendo y las credenciales |
| Migraciones perdidas | `python manage.py migrate --run-syncdb` |
| Puerto 8000 ocupado | `python manage.py runserver 8001` |

## 👨‍💻 Desarrollado por

- **[IDVG Solutions](https://github.com/IDVG46)**
- GitHub: [@IDVG46](https://github.com/IDVG46)

## 📄 Licencia

...

---

¿Preguntas? Abre un [issue](https://github.com/IDVG46/sigecop/issues) o contacta al equipo. ¡Gracias por usar SIGECOP! 🚀
