# Convenciones de Commits y Versionado — SIGECOP

Este documento define el estándar de mensajes de commit y la estrategia de versionado del proyecto.  
Se basa en [Conventional Commits 1.0](https://www.conventionalcommits.org/) adaptado al flujo de SIGECOP.

---

## Formato del mensaje de commit

```
<tipo>(<alcance>): <descripción corta>

[cuerpo opcional]

[pie opcional: BREAKING CHANGE o referencias]
```

### Reglas generales

- La **primera línea** no debe superar los 72 caracteres.
- Usar **infinitivo** en la descripción: `agregar`, `corregir`, `eliminar`, `refactorizar`.
- Sin punto final en la primera línea.
- El cuerpo se separa de la primera línea con una línea en blanco.
- Escribir **en español**.

---

## Tipos de commit

| Tipo | Cuándo usarlo | Impacto en versión |
|---|---|---|
| `feat` | Nueva funcionalidad visible para el usuario | MINOR `0.X.0` |
| `fix` | Corrección de un error | PATCH `0.0.X` |
| `refactor` | Reestructuración interna sin cambiar comportamiento | — |
| `perf` | Mejora de rendimiento sin cambiar comportamiento | PATCH |
| `test` | Agregar o corregir tests | — |
| `docs` | Cambios solo de documentación | — |
| `style` | Formato de código (espacios, comas) sin lógica | — |
| `chore` | Tareas de mantenimiento (deps, config, gitignore) | — |
| `ci` | Cambios en pipelines CI/CD | — |
| `revert` | Revertir un commit anterior | PATCH |

> **BREAKING CHANGE**: cualquier tipo puede marcar una ruptura de compatibilidad añadiendo  
> `BREAKING CHANGE: <descripción>` en el pie del commit. Incrementa la versión MAJOR `X.0.0`.

---

## Alcances del proyecto (scopes)

Usar el alcance que mejor describe qué área del código cambia.

| Alcance | Área |
|---|---|
| `dncp` | Integración con la API DNCP (importación, modelos, servicios) |
| `procurement` | Módulo de compras en general |
| `orders` | Órdenes de compra/servicio |
| `budget` | Presupuestos por contrato (`ContractBudget`) |
| `memos` | Cumplimientos / memos de recepción (`FulfillmentMemo`) |
| `payments` | Pagos e imputaciones (`Payment`, `PaymentAllocation`) |
| `api` | Endpoints API internos (opciones para formularios dinámicos) |
| `ui` | Templates HTML, CSS, JS |
| `db` | Migraciones y cambios de modelos |
| `auth` | Autenticación, permisos, acceso |
| `config` | Configuración Django (`settings`, `urls`, `wsgi`) |
| `tests` | Suite de pruebas |
| `docs` | Documentación del proyecto |
| `git` | Configuración del repositorio (`.gitignore`, hooks, templates) |

El alcance es **opcional** para commits transversales (`refactor`, `docs`, `chore`).

---

## Ejemplos

### Funcionalidad nueva
```
feat(payments): agregar vista de reporte de pago con detalle por lote
```

### Corrección de error
```
fix(budget): corregir calculo de saldo disponible al imputar pago parcial
```

### Refactorización
```
refactor(procurement): centralizar parsing decimal en decimal_utils
```

### Test
```
test(payments): agregar casos de prueba para post_payment con saldo insuficiente
```

### Documentación
```
docs: actualizar README con modulo procurement y rutas actuales
```

### Mantenimiento
```
chore(deps): actualizar psycopg2-binary a 2.9.11
```

### Migración de base de datos
```
feat(db): agregar constraint de no negatividad en saldo de ContractBudget
```

### Múltiples líneas con cuerpo
```
feat(memos): implementar flujo borrador -> aprobado en FulfillmentMemo

Agrega servicios create_fulfillment_memo y approve_fulfillment_memo.
El memo solo puede aprobarse si todas sus lineas tienen cantidades validas.
Las lineas parciales validan contra la cantidad disponible de la orden.
```

### Cambio que rompe compatibilidad
```
feat(orders): cambiar campo amount a unit_price en PurchaseOrderLine

BREAKING CHANGE: el campo amount fue reemplazado por unit_price en
PurchaseOrderLine. Los datos existentes requieren migracion manual.
```

---

## Estrategia de versionado

Se usa **Semantic Versioning** (`MAJOR.MINOR.PATCH`):

| Situación | Tipo de cambio | Ejemplo |
|---|---|---|
| Cambio que rompe compatibilidad | `MAJOR` | `1.0.0 → 2.0.0` |
| Nueva funcionalidad sin romper | `MINOR` via `feat` | `1.0.0 → 1.1.0` |
| Corrección de error | `PATCH` via `fix`/`perf`/`revert` | `1.0.0 → 1.0.1` |
| Solo refactor/docs/tests | Sin cambio de versión | — |

### Versión actual

El proyecto se encuentra en fase de desarrollo activo. La versión inicial de producción será **`1.0.0`** al completar los módulos core:
- [x] Integración DNCP con soporte multi-entidad
- [x] Órdenes de compra
- [x] Presupuestos por contrato
- [x] Cumplimientos (memos)
- [x] Pagos con control de saldo presupuestario
- [ ] Reportes consolidados por período

---

## Flujo de trabajo con ramas

```
main              ← producción estable (tags de versión aquí)
  └── develop     ← integración continua
        ├── feat/payments-report
        ├── feat/reporting-module
        └── fix/budget-balance-calculation
```

| Rama | Propósito |
|---|---|
| `main` | Producción. Solo recibe merges desde `develop` o `hotfix/*` |
| `develop` | Integración. Base para nuevas ramas de funcionalidad |
| `feat/<nombre>` | Nueva funcionalidad |
| `fix/<nombre>` | Corrección de error en develop |
| `hotfix/<nombre>` | Corrección urgente en producción (merge a `main` y `develop`) |
| `chore/<nombre>` | Mantenimiento o configuración |

---

## Template de commit

El proyecto incluye el archivo `.gitmessage` como plantilla.  
Para activarlo localmente:

```bash
git config commit.template .gitmessage
```

Al ejecutar `git commit` sin `-m`, se abrirá el editor con la plantilla precargada.

---

## Referencias

- [Conventional Commits 1.0](https://www.conventionalcommits.org/es/v1.0.0/)
- [Semantic Versioning 2.0](https://semver.org/lang/es/)
