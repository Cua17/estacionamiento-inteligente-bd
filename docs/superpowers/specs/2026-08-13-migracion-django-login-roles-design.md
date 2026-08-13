# Migración del dashboard a Django + login con roles

**Fecha:** 2026-08-13
**Plazo:** entrega final en 1 semana (2026-08-20 aprox.)
**Estado:** diseño aprobado, pendiente plan de implementación

## Motivación

El profesor pidió agregar login y comportamiento distinto según el usuario
que inicia sesión ("Jango" = Django, o Flask). El dashboard actual
(fase 7, ✅ hecho) está en Flask. Se decidió migrar a Django porque:

1. Da login, roles y un panel de administración (`/admin/`) prácticamente
   gratis, sin construir pantallas de gestión a mano.
2. El profesor evalúa uso de Django/ORM específicamente en este curso de
   bases de datos — hay valor de nota en mostrarlo, no solo funcional.

Ver la discusión completa en la conversación del 2026-08-13: se evaluó
Flask+Flask-Login como alternativa de menor riesgo dado el plazo de una
semana, pero el usuario decidió migrar a Django igual, asumiendo el riesgo,
priorizando cumplir con lo pedido.

## Alcance

**Se migra:** el lado que LEE — `web/app.py` + `scripts/reportes.py` — a
un proyecto Django con ORM, más login/registro/roles.

**NO se toca:** `scripts/parqueo.py` ni `scripts/monitor.py` (cámara, OCR,
apertura/cierre de sesiones). Siguen con `mysql-connector-python` y SQL
directo, exactamente como hoy. Ya están probados en vivo (laptop y Pi,
12 de agosto) y no tienen nada que ver con el login — tocarlos solo agrega
riesgo sin necesidad.

## Arquitectura

```
Django (nuevo)                          Sin cambios
─────────────────                       ─────────────────
accounts/  (login, registro, roles)     scripts/monitor.py
dashboard/ (modelos ORM + vistas)       scripts/parqueo.py
  ├─ modelos managed=False de:          scripts/vision.py
  │  vehiculos, espacios, tarifas,      scripts/ocupacion.py
  │  sesiones, cobros                   scripts/camara.py
  └─ admin.py (usa /admin/ de Django    scripts/db.py
     para gestionar espacios/tarifas/
     usuarios)
        │
        ▼
   TiDB Cloud · estacionamiento_db
   (misma base — Django agrega sus
   propias tablas auth_* vía migrate)
```

### Conexión a TiDB desde Django

- Driver: `PyMySQL` (no `mysqlclient` — evita compilador C en Windows).
  Shim estándar: `pymysql.install_as_MySQLdb()`.
- `DATABASES['default']` apunta a la misma TiDB, mismas credenciales de
  `.env`. `django.contrib.auth` migra ahí sus tablas (`auth_user`,
  `auth_group`, `django_session`, etc.) junto a las 5 tablas de negocio.
- `CONN_MAX_AGE` configurado (ej. 60s) para no repetir el handshake TLS de
  ~2s en cada request — el mismo problema que `web/app.py` ya resolvió a
  mano reusando una conexión; acá se resuelve con la config nativa de
  Django.
- Modelos de negocio (`Vehiculo`, `Espacio`, `Tarifa`, `Sesion`, `Cobro`)
  generados con `inspectdb` a partir de `schema.sql`, con
  `class Meta: managed = False` — Django nunca intenta crear/alterar esas
  tablas.

### Roles

- `django.contrib.auth.models.Group`: "Admin" y "Operador". Sin modelo de
  usuario custom — el `User` de Django alcanza.
- **Operador**: dashboard de solo lectura — estado de espacios y bitácora
  de movimientos (equivalente a `reportes.espacios()` +
  `reportes.movimientos()`). Sin recaudación, sin tarifa, sin totales.
- **Admin**: dashboard completo (igual que hoy: espacios, movimientos,
  recaudación, ocupación por hora, tarifa, totales) **+** acceso a
  `/admin/` de Django para gestionar espacios, ver vehículos/sesiones, y
  crear/promover usuarios. `is_staff=True` se otorga al promover a Admin.
- **Cambiar tarifa**: única pieza con lógica propia (cerrar la vigente con
  `vigente_hasta`, abrir la nueva) — se implementa como `save_model`
  personalizado en `TarifaAdmin`, dentro del propio `/admin/`. No es una
  pantalla nueva.

### Registro

- Vista pública `/registro`, mismo estilo visual que el resto (ver
  `DESIGN.md` — libro de caja, tonos oscuros, sin emojis, todo en
  español).
- Toda cuenta nueva se crea como **Operador** por defecto. Nadie se
  autoasigna Admin desde el registro. Un Admin existente promueve desde
  `/admin/`.

## Migración de las consultas de `reportes.py`

Cada función se reescribe a ORM manteniendo el mismo resultado:

| Función actual (SQL directo) | Equivalente ORM |
|---|---|
| `espacios(cursor)` | `Espacio.objects.select_related(...)` con la sesión activa vía `Sesion` filtrado por `estado='activa'` |
| `movimientos(cursor, limite)` | `Sesion.objects.select_related('espacio', 'cobro')`, armado en Python igual que hoy |
| `recaudacion(cursor)` | `Cobro.objects.filter(...).aggregate(Sum, Count)` con `Case/When` para separar día/mes |
| `ocupacion_por_hora(cursor)` | Igual lógica en Python, pero iterando `Sesion.objects.values_list('hora_entrada','hora_salida')` |
| `tarifa(cursor)` | `Tarifa.objects.filter(vigente_hasta__isnull=True).order_by('-vigente_desde').first()` |
| `totales_historicos(cursor)` | `Vehiculo.objects.count()`, `Sesion.objects.count()` |

Se mantiene el mismo esquema de cacheo por capas que hoy tiene `app.py`
(0.25s / 2s / 30s) — no hay razón para perder esa optimización solo por
cambiar de framework.

## Qué NO se hace (para no volar el plazo de 1 semana)

- No se construyen pantallas custom de gestión de usuarios/espacios — se
  usa `/admin/` de Django tal cual.
- No se cambia el diseño visual — login/registro heredan la paleta y
  tipografía ya definidas en `DESIGN.md`.
- No se toca `parqueo.py` ni `monitor.py`.

## Verificación antes de dar por cerrada la migración

1. Cada vista de lectura migrada se compara contra el JSON que hoy
   devuelve `/api/estado` en Flask, campo por campo.
2. Prueba con dos cuentas reales (una Operador, una Admin) confirmando
   qué ve cada una.
3. `monitor.py` sigue escribiendo sin problemas mientras el panel Django
   corre en paralelo — confirma que las dos conexiones a TiDB (la de
   Django/ORM y la de `db.py`) no chocan.
4. Fases 8 (prueba en el parqueo real) y 9 (documentación final) empiezan
   apenas el dashboard esté migrado y probado — son las que quedan
   pendientes y no tienen margen de atraso.

## Documento relacionado

La propuesta académica (`Propuesta_Proyecto_Final.docx`, en
`OneDrive/Universidad/2026 - Ciclo 2/Manejo de Base de Datos/`) ya se
actualizó reflejando este alcance: nuevo objetivo específico de
login/roles, párrafo "Panel web" en Descripción técnica, alcance del
proyecto actualizado, y Django agregado a Herramientas y tecnologías.
