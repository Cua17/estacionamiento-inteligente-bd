# Migración del dashboard a Django — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reemplazar `web/app.py` (Flask) por un proyecto Django que sirve
el mismo dashboard, con ORM en vez de SQL directo para las consultas de
lectura, y agrega login + dos roles (Admin y Operador).

**Architecture:** Proyecto Django nuevo en `web_django/`, con dos apps:
`dashboard` (modelos ORM `managed=False` sobre las 5 tablas existentes +
vistas de lectura + panel `/admin/`) y `cuentas` (login, registro, grupos
de rol). El HTML/CSS/JS del dashboard actual se reusa casi sin cambios —
es una sola plantilla que consulta `/api/estado` por JS, no server-side
rendering de los datos. `parqueo.py` y `monitor.py` NO se tocan.

**Tech Stack:** Django (última versión estable), PyMySQL como driver
hacia TiDB (no `mysqlclient`, para evitar compilar en Windows).

## Global Constraints

- Ver el spec completo en
  `docs/superpowers/specs/2026-08-13-migracion-django-login-roles-design.md`
  — este plan lo implementa.
- `scripts/parqueo.py` y `scripts/monitor.py` no se tocan en ningún task.
- Toda cuenta creada por el formulario de registro se asigna al grupo
  "Operador" — nunca "Admin" (ver spec, sección de Registro).
- Estilo visual: reusar `DESIGN.md` (libro de caja, tonos oscuros, sin
  emojis, todo en español) para login/registro — no inventar un estilo
  nuevo.
- El proyecto Django se arma en `web_django/`, en paralelo a `web/`
  (Flask), hasta el Task final de corte — así siempre queda un dashboard
  funcionando mientras se migra.

---

## File Structure

```
web_django/
    manage.py
    panel/                       # paquete de configuración del proyecto
        __init__.py               # shim de PyMySQL
        settings.py
        urls.py
        wsgi.py
    dashboard/                   # modelos + vistas de solo lectura + /admin/
        __init__.py
        apps.py
        models.py
        views.py
        admin.py
        urls.py
        management/
            __init__.py
            commands/
                __init__.py
                crear_grupos.py   # crea los grupos Admin/Operador
        templates/dashboard/index.html
        static/dashboard/dashboard.css   # copiado tal cual de web/static/
        static/dashboard/dashboard.js    # copiado con un guard chico (Task 4)
    cuentas/                      # login, registro, roles
        __init__.py
        apps.py
        views.py
        forms.py
        urls.py
        templates/
            registration/login.html
            cuentas/registro.html
```

---

### Task 1: Scaffolding del proyecto y conexión a TiDB

**Files:**
- Create: `web_django/manage.py`, `web_django/panel/__init__.py`,
  `web_django/panel/settings.py`, `web_django/panel/urls.py`,
  `web_django/panel/wsgi.py`
- Modify: `requirements.txt`

**Interfaces:**
- Produces: proyecto Django corriendo (`python manage.py runserver 5051`)
  conectado a TiDB, sin vistas propias todavía (usa el admin de Django
  para confirmar la conexión).

- [ ] **Step 1: Agregar las dependencias nuevas**

Agregar a `requirements.txt`:

```
Django==5.1.*
PyMySQL==1.1.*
```

(NO agregar `picamera2` acá — ver el plan de cámara, es paquete de
sistema, no de pip.)

Run: `pip install -r requirements.txt`

- [ ] **Step 2: Crear el proyecto**

```bash
cd "C:\Users\jdcua\dev\estacionamiento-inteligente-bd"
django-admin startproject panel web_django
cd web_django
python manage.py startapp dashboard
python manage.py startapp cuentas
```

- [ ] **Step 3: Shim de PyMySQL**

Reemplazar el contenido de `web_django/panel/__init__.py`:

```python
"""
Django asume el driver MySQLdb (mysqlclient), que necesita compilar
extensiones en C. PyMySQL es puro Python y se hace pasar por MySQLdb con
esta llamada — se hace acá porque __init__.py del paquete de settings se
importa antes que cualquier otra cosa de Django.
"""
import pymysql

pymysql.install_as_MySQLdb()
pymysql.version_info = (1, 4, 6, "final", 0)  # Django valida esta tupla al conectar
```

- [ ] **Step 4: Configurar `settings.py`**

En `web_django/panel/settings.py`, reemplazar `BASE_DIR` y agregar debajo:

```python
import os
from pathlib import Path

import certifi
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
RAIZ_PROYECTO = BASE_DIR.parent  # .../estacionamiento-inteligente-bd

# Las credenciales viven en el .env de la raíz del repo, el mismo que usan
# scripts/db.py y web/app.py — no se duplican.
load_dotenv(RAIZ_PROYECTO / ".env")
```

Reemplazar el bloque `DATABASES`:

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST"),
        "PORT": os.getenv("DB_PORT", "4000"),
        # Evita repetir el saludo TLS (~2s) en cada request -- el mismo
        # problema que web/app.py resuelve a mano reusando una conexión.
        "CONN_MAX_AGE": 60,
        "OPTIONS": {"ssl": {"ca": certifi.where()}},
    }
}
```

Agregar las apps nuevas a `INSTALLED_APPS` (dejar las de Django que ya
trae `startproject`):

```python
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "dashboard",
    "cuentas",
]
```

Agregar al final del archivo:

```python
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard:index"
LOGOUT_REDIRECT_URL = "login"

LANGUAGE_CODE = "es"
TIME_ZONE = "America/Guatemala"
USE_TZ = False  # las horas se guardan en hora local, igual que hoy en db.py
```

- [ ] **Step 5: Conectar las URLs del proyecto**

Reemplazar `web_django/panel/urls.py`:

```python
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("cuentas.urls")),
    path("", include("dashboard.urls")),
]
```

- [ ] **Step 6: Probar que levanta y llega a TiDB**

```bash
cd web_django
python manage.py migrate    # crea las tablas auth_* en TiDB
python manage.py createsuperuser   # cuenta tuya, para entrar a /admin/
python manage.py runserver 5051
```

Expected: `migrate` corre sin errores (confirma que llega a TiDB con
PyMySQL), y `http://localhost:5051/admin/` muestra el login de Django
donde entrás con el superusuario que acabás de crear.

- [ ] **Step 7: Commit**

```bash
git add web_django requirements.txt
git commit -m "Scaffolding del proyecto Django, conectado a TiDB con PyMySQL

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: Modelos ORM de las 5 tablas existentes

**Files:**
- Create: `web_django/dashboard/models.py`

**Interfaces:**
- Produces: `Vehiculo`, `Espacio`, `Tarifa`, `Sesion`, `Cobro` — todos
  `managed=False`, mapeados 1:1 a `schema.sql`. Estos nombres y campos
  los usan las Tareas 3 y 6.

- [ ] **Step 1: Escribir los modelos**

```python
"""
Modelos de solo lectura sobre las 5 tablas de negocio (managed=False:
Django nunca las crea ni las altera, ya existen y las escribe
parqueo.py). Reflejan exactamente schema.sql -- si el schema cambia, este
archivo se actualiza a mano.
"""

from django.db import models


class Vehiculo(models.Model):
    placa = models.CharField(max_length=15, primary_key=True)
    primera_deteccion = models.DateTimeField()
    notas = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        managed = False
        db_table = "vehiculos"

    def __str__(self):
        return self.placa


class Espacio(models.Model):
    etiqueta = models.CharField(max_length=10, unique=True)
    estado = models.CharField(max_length=10)  # 'libre' | 'ocupado'
    actualizado_en = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "espacios"
        ordering = ["etiqueta"]

    def __str__(self):
        return self.etiqueta


class Tarifa(models.Model):
    nombre = models.CharField(max_length=50)
    precio_por_hora = models.DecimalField(max_digits=8, decimal_places=2)
    vigente_desde = models.DateTimeField()
    vigente_hasta = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "tarifas"

    def __str__(self):
        return f"{self.nombre} (Q{self.precio_por_hora}/h)"


class Sesion(models.Model):
    placa = models.CharField(max_length=15)
    espacio = models.ForeignKey(
        Espacio, on_delete=models.DO_NOTHING, db_column="espacio_id",
        related_name="sesiones",
    )
    hora_entrada = models.DateTimeField()
    hora_salida = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(max_length=10)  # 'activa' | 'cerrada'

    class Meta:
        managed = False
        db_table = "sesiones"

    def __str__(self):
        return f"{self.placa} en {self.espacio_id}"


class Cobro(models.Model):
    sesion = models.OneToOneField(
        Sesion, on_delete=models.DO_NOTHING, db_column="sesion_id",
        related_name="cobro",
    )
    tarifa = models.ForeignKey(Tarifa, on_delete=models.DO_NOTHING, db_column="tarifa_id")
    minutos_totales = models.IntegerField()
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_cobro = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "cobros"
```

- [ ] **Step 2: Verificar contra la base real**

```bash
cd web_django
python manage.py shell -c "
from dashboard.models import Espacio, Sesion, Tarifa
print(list(Espacio.objects.values('etiqueta', 'estado')))
print(Tarifa.objects.filter(vigente_hasta__isnull=True).first())
"
```

Expected: imprime los espacios reales (`A1`..`A4` con su estado actual) y
la tarifa vigente — confirma que los modelos apuntan bien a las tablas
existentes, sin haber corrido ninguna migración sobre ellas.

- [ ] **Step 3: Commit**

```bash
git add web_django/dashboard/models.py
git commit -m "Agregar modelos ORM managed=False para las 5 tablas de negocio

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: Vistas de lectura (equivalente ORM de reportes.py)

**Files:**
- Create: `web_django/dashboard/views.py`
- Create: `web_django/dashboard/urls.py`

**Interfaces:**
- Consumes: modelos de la Tarea 2.
- Produces: `GET /` (vista `index`, requiere login) y
  `GET /api/estado` (vista `api_estado`, requiere login, devuelve el
  mismo JSON que hoy da Flask, más la clave `"es_admin": bool`).

- [ ] **Step 1: Escribir las consultas ORM**

```python
"""
Vistas de solo lectura del dashboard -- equivalente ORM de
scripts/reportes.py. Nunca escriben en la base: quien escribe es
parqueo.py, vía monitor.py.
"""

import threading
import time
from datetime import date, datetime

from django.contrib.auth.decorators import login_required
from django.db.models import Case, Count, DecimalField, OuterRef, Subquery, Sum, When
from django.http import JsonResponse
from django.shortcuts import render

from .models import Cobro, Espacio, Sesion, Tarifa, Vehiculo

HORAS_DEL_DIA = 24


def es_admin(usuario):
    return usuario.groups.filter(name="Admin").exists()


def _hhmm(momento):
    return momento.strftime("%H:%M") if momento else None


def datos_espacios():
    """
    Espacios con su estado y, si está ocupado, quién lo ocupa y desde
    cuándo -- en UNA sola consulta (subquery correlacionada) en vez de dos,
    porque cada viaje a TiDB en Tokio cuesta ~300ms y esto se pide cada
    pocos segundos.
    """
    activa = Sesion.objects.filter(espacio_id=OuterRef("id"), estado="activa")
    qs = Espacio.objects.annotate(
        placa_activa=Subquery(activa.values("placa")[:1]),
        entrada_activa=Subquery(activa.values("hora_entrada")[:1]),
    )
    ahora = datetime.now()
    filas = []
    for espacio in qs:
        minutos = None
        if espacio.entrada_activa:
            minutos = max(0, int((ahora - espacio.entrada_activa).total_seconds() // 60))
        filas.append({
            "etiqueta": espacio.etiqueta,
            "ocupado": espacio.estado == "ocupado",
            "placa": espacio.placa_activa,
            "desde": _hhmm(espacio.entrada_activa),
            "minutos": minutos,
        })
    return filas


def datos_movimientos(limite=12):
    """Bitácora de entradas y salidas, lo más reciente primero."""
    sesiones = (
        Sesion.objects.select_related("espacio", "cobro")
        .order_by("-id")[:limite]
    )
    eventos = []
    for sesion in sesiones:
        eventos.append({
            "tipo": "entrada", "momento": sesion.hora_entrada,
            "hora": _hhmm(sesion.hora_entrada), "placa": sesion.placa,
            "espacio": sesion.espacio.etiqueta, "minutos": None, "monto": None,
        })
        if sesion.hora_salida:
            cobro = getattr(sesion, "cobro", None)
            eventos.append({
                "tipo": "salida", "momento": sesion.hora_salida,
                "hora": _hhmm(sesion.hora_salida), "placa": sesion.placa,
                "espacio": sesion.espacio.etiqueta,
                "minutos": cobro.minutos_totales if cobro else None,
                "monto": float(cobro.monto) if cobro else None,
            })
    eventos.sort(key=lambda e: e["momento"], reverse=True)
    for evento in eventos:
        del evento["momento"]
    return eventos[:limite]


def datos_recaudacion():
    """Totales cobrados hoy y en el mes en curso."""
    hoy = date.today()
    agregado = Cobro.objects.aggregate(
        total_dia=Sum(Case(
            When(sesion__hora_salida__date=hoy, then="monto"),
            output_field=DecimalField(),
        )),
        sesiones_dia=Count(Case(When(sesion__hora_salida__date=hoy, then=1))),
        total_mes=Sum(Case(
            When(sesion__hora_salida__year=hoy.year, sesion__hora_salida__month=hoy.month, then="monto"),
            output_field=DecimalField(),
        )),
        sesiones_mes=Count(Case(When(
            sesion__hora_salida__year=hoy.year, sesion__hora_salida__month=hoy.month, then=1,
        ))),
    )
    return {
        "dia": float(agregado["total_dia"] or 0),
        "sesiones_dia": agregado["sesiones_dia"] or 0,
        "mes": float(agregado["total_mes"] or 0),
        "sesiones_mes": agregado["sesiones_mes"] or 0,
    }


def datos_ocupacion_por_hora():
    """Sesiones activas en cada hora del día, sobre todo el histórico."""
    ahora = datetime.now()
    conteo = [0] * HORAS_DEL_DIA
    for hora_entrada, hora_salida in Sesion.objects.values_list("hora_entrada", "hora_salida"):
        fin = hora_salida or ahora
        if fin < hora_entrada:
            continue
        primera = hora_entrada.hour
        ultima = fin.hour if fin.date() == hora_entrada.date() else HORAS_DEL_DIA - 1
        for hora in range(primera, ultima + 1):
            conteo[hora] += 1
    return conteo


def datos_tarifa():
    tarifa = Tarifa.objects.filter(vigente_hasta__isnull=True).order_by("-vigente_desde").first()
    if tarifa is None:
        return None
    return {"nombre": tarifa.nombre, "precio_por_hora": float(tarifa.precio_por_hora)}


def datos_totales():
    return {
        "vehiculos": Vehiculo.objects.count(),
        "sesiones": Sesion.objects.count(),
    }


# ── Cacheo por capas: igual criterio que web/app.py, portado tal cual ──
CACHE_SEGUNDOS = 0.25
CACHE_MEDIOS_SEGUNDOS = 2
CACHE_LENTOS_SEGUNDOS = 30

_candado = threading.Lock()
_cache = {"datos": None, "momento": 0.0}
_cache_medios = {"datos": None, "momento": 0.0}
_cache_lentos = {"datos": None, "momento": 0.0}


def _estado_completo(admin):
    ahora = time.monotonic()
    if _cache_medios["datos"] is None or ahora - _cache_medios["momento"] >= CACHE_MEDIOS_SEGUNDOS:
        _cache_medios["datos"] = {
            "movimientos": datos_movimientos(),
            "recaudacion": datos_recaudacion(),
        }
        _cache_medios["momento"] = time.monotonic()
    if _cache_lentos["datos"] is None or ahora - _cache_lentos["momento"] >= CACHE_LENTOS_SEGUNDOS:
        _cache_lentos["datos"] = {
            "ocupacion_por_hora": datos_ocupacion_por_hora(),
            "tarifa": datos_tarifa(),
            "totales": datos_totales(),
        }
        _cache_lentos["momento"] = time.monotonic()

    lista_espacios = datos_espacios()
    resultado = {
        "espacios": lista_espacios,
        "libres": sum(1 for e in lista_espacios if not e["ocupado"]),
        "total": len(lista_espacios),
        "actualizado": datetime.now().strftime("%H:%M:%S"),
        "movimientos": _cache_medios["datos"]["movimientos"],
        "tarifa": _cache_lentos["datos"]["tarifa"],
        "totales": _cache_lentos["datos"]["totales"],
    }
    # Recaudación y ocupación por hora son reportes agregados: el
    # Operador ve el estado en vivo del parqueo, no las sumas de dinero
    # ni el histórico -- ver spec de diseño, sección "Roles".
    if admin:
        resultado["recaudacion"] = _cache_medios["datos"]["recaudacion"]
        resultado["ocupacion_por_hora"] = _cache_lentos["datos"]["ocupacion_por_hora"]
    return resultado


@login_required
def index(request):
    return render(request, "dashboard/index.html", {"es_admin": es_admin(request.user)})


@login_required
def api_estado(request):
    ahora = time.monotonic()
    if _cache["datos"] is not None and ahora - _cache["momento"] < CACHE_SEGUNDOS:
        return JsonResponse(_cache["datos"])

    with _candado:
        ahora = time.monotonic()
        if _cache["datos"] is not None and ahora - _cache["momento"] < CACHE_SEGUNDOS:
            return JsonResponse(_cache["datos"])
        try:
            datos = _estado_completo(es_admin(request.user))
        except Exception as error:
            return JsonResponse({"error": f"No se pudo leer de la base: {error}"}, status=503)
        _cache["datos"] = datos
        _cache["momento"] = time.monotonic()
        return JsonResponse(datos)
```

- [ ] **Step 2: Conectar las URLs de la app**

Crear `web_django/dashboard/urls.py`:

```python
from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.index, name="index"),
    path("api/estado", views.api_estado, name="api_estado"),
]
```

- [ ] **Step 3: Probar la API a mano (sin plantilla todavía)**

```bash
python manage.py runserver 5051
```

Con sesión iniciada en el navegador (entrar primero por `/admin/` con el
superusuario), abrir `http://localhost:5051/api/estado`.

Expected: JSON con `espacios`, `movimientos`, `tarifa`, `totales`,
`recaudacion` y `ocupacion_por_hora` (el superusuario cae en el grupo
Admin recién en la Tarea 7 — hasta entonces, para probar, alcanza con
que `es_admin()` devuelva `False` y falten esas dos claves, es
comportamiento esperado en este punto del plan).

- [ ] **Step 4: Commit**

```bash
git add web_django/dashboard/views.py web_django/dashboard/urls.py
git commit -m "Agregar vistas ORM del dashboard, equivalentes a reportes.py

Mismo cacheo por capas que web/app.py. La API omite recaudacion y
ocupacion_por_hora para quien no esta en el grupo Admin.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 4: Plantillas — reusar el dashboard existente

**Files:**
- Create: `web_django/dashboard/templates/dashboard/index.html` (copia
  adaptada de `web/templates/dashboard.html`)
- Copy: `web/static/dashboard.css` → `web_django/dashboard/static/dashboard/dashboard.css` (sin cambios)
- Modify (copia): `web/static/dashboard.js` → `web_django/dashboard/static/dashboard/dashboard.js` (2 líneas)
- Modify: `web_django/panel/settings.py` (config de `STATICFILES_DIRS`/`TEMPLATES` si hace falta)

**Interfaces:**
- Consumes: `es_admin` del contexto de la vista `index` (Tarea 3).

**Por qué esto es chico:** el dashboard actual arma toda su tabla por JS
consultando `/api/estado` — el HTML no tiene lógica de servidor más allá
de los dos `url_for` de estáticos. No hace falta portar lógica de
renderizado, solo la carga de CSS/JS y ocultar dos secciones según el
rol.

- [ ] **Step 1: Copiar CSS sin cambios**

```bash
mkdir -p web_django/dashboard/static/dashboard
cp web/static/dashboard.css web_django/dashboard/static/dashboard/dashboard.css
```

- [ ] **Step 2: Copiar el HTML y adaptar los dos `url_for`, más el rol**

Copiar `web/templates/dashboard.html` a
`web_django/dashboard/templates/dashboard/index.html` y aplicar estos
cambios puntuales (todo el resto del archivo, comentario de diseño
incluido, queda igual):

En el `<head>`, agregar `{% load static %}` como primera línea del
archivo, y cambiar:
```
<link rel="stylesheet" href="{{ url_for('static', filename='dashboard.css') }}">
```
por:
```
<link rel="stylesheet" href="{% static 'dashboard/dashboard.css' %}">
```

Antes de `</body>`, cambiar:
```
<script src="{{ url_for('static', filename='dashboard.js') }}"></script>
```
por:
```
<script src="{% static 'dashboard/dashboard.js' %}"></script>
```

Agregar, dentro de `<header class="cabecera">`, justo después de
`<p class="folio">`, envolver la parte de la tarifa (Admin-only, ver
Tarea 3):

Cambiar:
```html
      <p class="folio">
        Folio <span id="folio-fecha">—</span>
        <span class="folio__sep">·</span>
        Tarifa <span id="folio-tarifa" class="cifra">—</span> por hora
      </p>
```
por:
```html
      <p class="folio">
        Folio <span id="folio-fecha">—</span>
        {% if es_admin %}
        <span class="folio__sep">·</span>
        Tarifa <span id="folio-tarifa" class="cifra">—</span> por hora
        {% endif %}
      </p>
```

Envolver la sección de "Ocupación por hora del día" completa (el
`<section class="seccion seccion--campo" ...>...</section>`) en
`{% if es_admin %}...{% endif %}`.

Envolver solo la `<table class="sumas">...</table>` dentro del `<footer>`
(NO el `<p class="sello">`, que muestra el estado de conexión y tiene que
verse para los dos roles) en `{% if es_admin %}...{% endif %}`.

Agregar, justo antes de `</div>` que cierra `<div class="hoja">`, un
enlace de cierre de sesión (no estaba en el diseño original porque no
había login):

```html
  <form action="{% url 'logout' %}" method="post" class="cierre-sesion">
    {% csrf_token %}
    <button type="submit">Cerrar sesión</button>
  </form>
```

- [ ] **Step 3: Copiar el JS y agregar el guard de dos líneas**

```bash
cp web/static/dashboard.js web_django/dashboard/static/dashboard/dashboard.js
```

En `web_django/dashboard/static/dashboard/dashboard.js`, dentro de
`actualizar()`, cambiar:

```js
    pintarCampoHoras(datos.ocupacion_por_hora);
    pintarBitacora(datos);
    pintarPie(datos);
```

por:

```js
    if (datos.ocupacion_por_hora) pintarCampoHoras(datos.ocupacion_por_hora);
    pintarBitacora(datos);
    if (datos.recaudacion) pintarPie(datos);
```

(Sin este guard, un usuario Operador -- para quien la API no manda esas
dos claves -- rompería el `fetch` con un `TypeError` al intentar leer
`datos.recaudacion.dia` de un valor `undefined`.)

- [ ] **Step 4: Confirmar `STATICFILES_DIRS`**

En `web_django/panel/settings.py`, Django ya encuentra
`dashboard/static/dashboard/` automáticamente porque `dashboard` está en
`INSTALLED_APPS` (convención de app estática) — no hace falta agregar
nada más, pero confirmar que existe esta línea (la trae `startproject`
por defecto):

```python
STATIC_URL = "static/"
```

- [ ] **Step 5: Probar en el navegador**

```bash
python manage.py runserver 5051
```

Entrar con el superusuario (por ahora sin grupo, ve la versión
"Operador": sin tarifa en la cabecera, sin ocupación por hora, sin
sumas) en `http://localhost:5051/`.

Expected: el dashboard se ve visualmente igual al de Flask, sin errores
en la consola del navegador, con las tres secciones Admin-only ocultas.

- [ ] **Step 6: Commit**

```bash
git add web_django/dashboard/templates web_django/dashboard/static
git commit -m "Reusar el HTML/CSS/JS del dashboard en Django, con secciones por rol

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 5: Login

**Files:**
- Modify: `web_django/panel/urls.py`
- Create: `web_django/dashboard/templates/registration/login.html`
- Modify: `web_django/panel/settings.py` (agregar carpeta de templates
  compartida si hace falta)

**Interfaces:**
- Produces: `GET/POST /login` (nombre de URL `login`, ya referenciado por
  `LOGIN_URL` en la Tarea 1) y `POST /logout` (nombre `logout`, ya
  referenciado desde el template de la Tarea 4).

- [ ] **Step 1: Agregar las rutas built-in de Django**

En `web_django/panel/urls.py`, agregar el import y la ruta:

```python
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("cuentas.urls")),
    path("", include("dashboard.urls")),
]
```

- [ ] **Step 2: Template de login con el estilo del proyecto**

```html
{% load static %}<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Iniciar sesión — Registro de Estacionamiento</title>
<link rel="stylesheet" href="{% static 'dashboard/dashboard.css' %}">
<link rel="stylesheet" href="{% static 'cuentas/cuentas.css' %}">
</head>
<body>
<div class="hoja hoja--angosta">
  <header class="cabecera">
    <div class="cabecera__titulo">
      <h1>Registro de Estacionamiento</h1>
      <p class="folio">Iniciar sesión</p>
    </div>
  </header>

  {% if form.errors %}
  <div class="aviso" role="alert">
    <span class="aviso__texto">Usuario o contraseña incorrectos.</span>
  </div>
  {% endif %}

  <form method="post" class="formulario-cuenta">
    {% csrf_token %}
    <label for="id_username">Usuario</label>
    {{ form.username }}
    <label for="id_password">Contraseña</label>
    {{ form.password }}
    <button type="submit">Entrar</button>
  </form>

  <p class="folio"><a href="{% url 'registro' %}">Crear una cuenta nueva</a></p>
</div>
</body>
</html>
```

- [ ] **Step 3: Hoja de estilo mínima para las pantallas de cuenta**

Crear `web_django/cuentas/static/cuentas/cuentas.css`:

```css
/* Extiende dashboard.css con lo mínimo para login/registro: reusa las
   variables de color y tipografía ya definidas ahí (ver DESIGN.md), no
   redefine nada propio. */
.hoja--angosta {
  max-width: 420px;
  margin: 10vh auto 0;
}

.formulario-cuenta {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-top: 1.5rem;
}

.formulario-cuenta label {
  font-size: 0.85rem;
  color: var(--color-texto-secundario, #999);
}

.formulario-cuenta input {
  background: var(--color-fondo-alterno, #1a1a1a);
  border: 1px solid var(--color-filete, #333);
  color: inherit;
  padding: 0.5rem 0.75rem;
  font: inherit;
}

.formulario-cuenta button {
  margin-top: 0.5rem;
  padding: 0.6rem;
  background: var(--color-acento, #b91c1c);
  color: #fff;
  border: none;
  font: inherit;
  cursor: pointer;
}

.cierre-sesion {
  margin-top: 1rem;
  text-align: right;
}

.cierre-sesion button {
  background: none;
  border: 1px solid var(--color-filete, #333);
  color: inherit;
  padding: 0.35rem 0.75rem;
  font: inherit;
  cursor: pointer;
}
```

(Los nombres exactos de variables CSS -- `--color-texto-secundario`,
`--color-fondo-alterno`, `--color-filete`, `--color-acento` -- hay que
confirmarlos contra `web/static/dashboard.css`/`DESIGN.md` al implementar
y ajustar si se llaman distinto; la intención es reusar la paleta ya
definida, no inventar colores nuevos.)

- [ ] **Step 4: Probar el login**

```bash
python manage.py runserver 5051
```

Ir a `http://localhost:5051/login`, entrar con el superusuario.

Expected: redirige a `/` (el dashboard) tras loguear. Entrar a
`http://localhost:5051/` sin sesión iniciada (navegador en incógnito)
redirige a `/login?next=/`.

- [ ] **Step 5: Commit**

```bash
git add web_django/panel/urls.py web_django/dashboard/templates/registration web_django/cuentas/static
git commit -m "Agregar pantalla de login con el estilo del proyecto

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 6: Registro (cuentas nuevas → grupo Operador)

**Files:**
- Create: `web_django/cuentas/forms.py`
- Create: `web_django/cuentas/views.py`
- Create: `web_django/cuentas/urls.py`
- Create: `web_django/cuentas/templates/cuentas/registro.html`

**Interfaces:**
- Consumes: `django.contrib.auth.models.Group` (grupo "Operador", creado
  en la Tarea 7 — si no existe todavía al probar este Task, crearlo a
  mano una vez con `Group.objects.get_or_create(name="Operador")` desde
  el shell, la Tarea 7 lo automatiza).
- Produces: `GET/POST /registro` (nombre de URL `registro`, ya
  referenciado desde el template de login).

- [ ] **Step 1: Formulario**

```python
"""Registro público de cuentas -- toda cuenta nueva entra como Operador."""

from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class FormularioRegistro(UserCreationForm):
    class Meta:
        model = User
        fields = ["username"]
```

- [ ] **Step 2: Vista**

```python
from django.contrib.auth import login
from django.contrib.auth.models import Group
from django.shortcuts import redirect, render

from .forms import FormularioRegistro


def registro(request):
    if request.method == "POST":
        formulario = FormularioRegistro(request.POST)
        if formulario.is_valid():
            usuario = formulario.save()
            # Toda cuenta nueva entra como Operador. Nadie se autoasigna
            # Admin desde acá -- un Admin existente promueve desde /admin/.
            grupo_operador, _ = Group.objects.get_or_create(name="Operador")
            usuario.groups.add(grupo_operador)
            login(request, usuario)
            return redirect("dashboard:index")
    else:
        formulario = FormularioRegistro()
    return render(request, "cuentas/registro.html", {"form": formulario})
```

- [ ] **Step 3: URLs**

```python
from django.urls import path

from . import views

urlpatterns = [
    path("registro", views.registro, name="registro"),
]
```

- [ ] **Step 4: Template**

```html
{% load static %}<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Crear cuenta — Registro de Estacionamiento</title>
<link rel="stylesheet" href="{% static 'dashboard/dashboard.css' %}">
<link rel="stylesheet" href="{% static 'cuentas/cuentas.css' %}">
</head>
<body>
<div class="hoja hoja--angosta">
  <header class="cabecera">
    <div class="cabecera__titulo">
      <h1>Registro de Estacionamiento</h1>
      <p class="folio">Crear cuenta nueva (rol: operador)</p>
    </div>
  </header>

  {% if form.errors %}
  <div class="aviso" role="alert">
    <span class="aviso__texto">Revisá los datos: {{ form.errors }}</span>
  </div>
  {% endif %}

  <form method="post" class="formulario-cuenta">
    {% csrf_token %}
    <label for="id_username">Usuario</label>
    {{ form.username }}
    <label for="id_password1">Contraseña</label>
    {{ form.password1 }}
    <label for="id_password2">Repetir contraseña</label>
    {{ form.password2 }}
    <button type="submit">Crear cuenta</button>
  </form>

  <p class="folio"><a href="{% url 'login' %}">Ya tengo cuenta</a></p>
</div>
</body>
</html>
```

- [ ] **Step 5: Probar**

Ir a `http://localhost:5051/registro`, crear una cuenta de prueba.

Expected: entra directo al dashboard tras registrarse, y ve la versión
Operador (sin tarifa, sin ocupación por hora, sin sumas — confirma que
`es_admin()` da `False` para esta cuenta nueva).

- [ ] **Step 6: Commit**

```bash
git add web_django/cuentas
git commit -m "Agregar registro publico, con toda cuenta nueva como Operador

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 7: Grupos de rol y panel `/admin/` personalizado

**Files:**
- Create: `web_django/dashboard/management/commands/crear_grupos.py`
- Create: `web_django/dashboard/admin.py`

**Interfaces:**
- Produces: comando `python manage.py crear_grupos` (idempotente) y
  registro de `Espacio`, `Vehiculo`, `Sesion` (solo lectura) y `Tarifa`
  (con la lógica de "cerrar la vieja, abrir la nueva") en `/admin/`.

- [ ] **Step 1: Comando para crear los grupos**

```python
"""
Crea los grupos Admin y Operador si no existen. Idempotente: correrlo de
nuevo no duplica nada.

Uso:
    python manage.py crear_grupos
"""

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Crea los grupos de rol Admin y Operador"

    def handle(self, *args, **options):
        for nombre in ("Admin", "Operador"):
            _, creado = Group.objects.get_or_create(name=nombre)
            estado = "creado" if creado else "ya existía"
            self.stdout.write(f"Grupo '{nombre}': {estado}")
```

- [ ] **Step 2: Correrlo y promover tu propia cuenta a Admin**

```bash
python manage.py crear_grupos
python manage.py shell -c "
from django.contrib.auth.models import Group, User
u = User.objects.get(username='TU_USUARIO_SUPERUSER')
u.groups.add(Group.objects.get(name='Admin'))
u.is_staff = True
# is_superuser, no solo is_staff+grupo: un grupo de Django NO trae permisos
# solo, hay que asignarle explicitamente Permission por modelo o hacer
# superuser al usuario. Se usa is_superuser porque es lo que necesita el
# rol Admin de todas formas (gestionar espacios, tarifas Y usuarios desde
# /admin/), y las restricciones de SesionAdmin/CobroAdmin (Tarea 3) son
# overrides de código que devuelven False para TODOS, superuser incluido
# -- no dependen del sistema de permisos, así que is_superuser no las
# saltea. (Encontrado probando en vivo: promover solo con is_staff+grupo
# entra a /admin/ pero muestra "no cuenta con permiso para ver ni editar
# nada" -- el grupo por sí solo no alcanza.)
u.is_superuser = True
u.save()
"
```

- [ ] **Step 3: Registrar los modelos en `/admin/`, con la regla de negocio de tarifas**

```python
"""
Panel /admin/ de Django: lo usa el rol Admin para gestionar espacios,
tarifas y usuarios -- sin construir pantallas propias para eso.
"""

from django.contrib import admin

from .models import Cobro, Espacio, Sesion, Tarifa, Vehiculo


@admin.register(Espacio)
class EspacioAdmin(admin.ModelAdmin):
    list_display = ["etiqueta", "estado", "actualizado_en"]
    # El estado lo escribe monitor.py en tiempo real -- acá solo se
    # gestiona la etiqueta/alta de espacios, no se fuerza el estado a mano.
    readonly_fields = ["estado", "actualizado_en"]


@admin.register(Vehiculo)
class VehiculoAdmin(admin.ModelAdmin):
    list_display = ["placa", "primera_deteccion", "notas"]
    readonly_fields = ["placa", "primera_deteccion"]


@admin.register(Sesion)
class SesionAdmin(admin.ModelAdmin):
    list_display = ["placa", "espacio", "hora_entrada", "hora_salida", "estado"]
    list_filter = ["estado"]
    # Solo lectura: abrir/cerrar sesiones es responsabilidad exclusiva de
    # parqueo.py (ver principio de diseño en CONTEXTO.md) -- el panel no
    # debe poder tocar esto a mano y desincronizarlo de la cámara.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Cobro)
class CobroAdmin(admin.ModelAdmin):
    list_display = ["sesion", "tarifa", "minutos_totales", "monto", "fecha_cobro"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Tarifa)
class TarifaAdmin(admin.ModelAdmin):
    list_display = ["nombre", "precio_por_hora", "vigente_desde", "vigente_hasta"]

    def save_model(self, request, obj, form, change):
        """
        La tarifa nunca se borra, se cierra (ver CONTEXTO.md): al crear
        una fila nueva sin vigente_hasta, se le pone vigente_hasta=ahora a
        la que estaba vigente antes, para que un cobro viejo se siga
        pudiendo explicar con la tarifa que regía ese día.
        """
        from django.utils import timezone

        if not change:  # solo al CREAR una tarifa nueva, no al editar una existente
            Tarifa.objects.filter(vigente_hasta__isnull=True).update(
                vigente_hasta=timezone.now()
            )
        super().save_model(request, obj, form, change)
```

- [ ] **Step 4: Probar el ciclo completo de roles**

1. Entrar como el usuario Admin (promovido en el Step 2) → confirmar que
   el dashboard muestra tarifa, ocupación por hora y sumas, y que
   `/admin/` deja crear una tarifa nueva y cierra la anterior sola.
2. Entrar como la cuenta de prueba creada en la Tarea 6 (Operador) →
   confirmar que NO ve esas tres secciones y que `/admin/` le pide
   permiso (no tiene `is_staff`).

Expected: los dos roles se comportan como en el spec de diseño.

- [ ] **Step 5: Commit**

```bash
git add web_django/dashboard/management web_django/dashboard/admin.py
git commit -m "Agregar grupos de rol y panel /admin/ con regla de negocio de tarifas

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 8: Verificación final contra Flask, y decisión de corte

**Files:** ninguno nuevo — solo verificación manual.

- [ ] **Step 1: Comparar el JSON de las dos versiones, lado a lado**

Con Flask corriendo en :5050 (`python web/app.py`) y Django en :5051
(`python web_django/manage.py runserver 5051`), ambos contra la misma
base:

```bash
curl -s http://localhost:5050/api/estado | python -m json.tool > /tmp/flask.json
curl -s -H "Cookie: sessionid=..." http://localhost:5051/api/estado | python -m json.tool > /tmp/django.json
diff /tmp/flask.json /tmp/django.json
```

(Necesita la cookie de sesión de un usuario Admin logueado en Django
para que ambas respuestas incluyan las mismas claves — copiarla de las
herramientas de desarrollador del navegador tras loguearte en :5051.)

Expected: sin diferencias más allá de `actualizado` (la marca de hora
difiere porque son consultas en momentos distintos) — todos los números
de espacios, movimientos, recaudación y tarifa coinciden.

- [ ] **Step 2: Confirmar que `monitor.py` sigue escribiendo sin problemas**

Con Django corriendo, en otra terminal:

```bash
python scripts/monitor.py --simular
```

Ocupar y liberar un espacio a mano. Expected: el dashboard Django refleja
el cambio en un par de segundos, igual que hoy hace con Flask — confirma
que las dos conexiones a TiDB (la del ORM de Django y la de
`scripts/db.py`) no chocan entre sí.

- [ ] **Step 3: Decisión de corte (con el usuario, no automático)**

Este paso NO se hace solo — implica borrar código que hoy funciona.
Avisar al usuario y esperar confirmación antes de:

```bash
git rm -r web
mv web_django web
# Ajustar cualquier referencia a "web_django" que haya quedado (README.md, CONTEXTO.md)
git add -A
git commit -m "Reemplazar el dashboard Flask por el panel Django, ya verificado

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Self-review

- **Cobertura del spec**: login ✅ (Task 5), registro con rol por defecto
  ✅ (Task 6), roles Admin/Operador ✅ (Task 3+7), panel `/admin/` para
  gestión de espacios/tarifas/usuarios ✅ (Task 7), ORM sobre las 5
  tablas existentes sin migrarlas ✅ (Task 2), mismo cacheo por capas ✅
  (Task 3), `parqueo.py`/`monitor.py` intocados ✅ (ningún task los
  menciona).
- **Ajuste sobre el spec original**: el spec de diseño decía "Operador:
  ...sin tarifa..." de forma general; este plan lo precisa como "sin ver
  el precio en la cabecera ni en `/admin/`", pero SÍ usa la tarifa para
  calcular la columna "A cobrar" de cada espacio ocupado en la tabla que
  el Operador sí ve (es parte de "el estado en vivo del parqueo", no un
  reporte financiero agregado). Se documenta acá para que quede claro
  que es una decisión tomada al implementar, no una omisión.
- **Placeholders**: ninguno — el único texto literal a completar es
  `TU_USUARIO_SUPERUSER` en el Step 2 de la Tarea 7, que por definición
  depende de qué usuario haya creado cada quien al ejecutar la Tarea 1.
- **Consistencia de tipos**: `es_admin(usuario)` se define una vez en
  `dashboard/views.py` (Task 3) y se reusa en `dashboard/admin.py`
  conceptualmente (ahí se resuelve por `is_staff` + grupo, no llamando a
  la misma función, porque el admin de Django ya trae su propio control
  de acceso por `is_staff`/permisos — son dos mecanismos de Django que
  coexisten a propósito, no una duplicación accidental).

## Qué NO se hace acá

- No se construyen pantallas propias para gestionar espacios, tarifas o
  usuarios — se usa `/admin/` de Django tal cual, con la única
  personalización necesaria (`TarifaAdmin.save_model`).
- No se cambia nada de `parqueo.py`, `monitor.py`, `vision.py`,
  `ocupacion.py` ni `camara.py`.
- No se borra `web/` (Flask) hasta que la Tarea 8 esté verificada y el
  usuario confirme el corte.
