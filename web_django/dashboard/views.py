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
    # Los tramos van en la respuesta para que el navegador pueda estimar el
    # "a cobrar" de una sesión abierta con la MISMA regla que usa parqueo.py
    # al cerrarla. Si la pantalla calculara distinto, prometería un número
    # que después no coincide con el que se guarda en la base.
    tramos = [
        {"desde_minuto": tramo.desde_minuto, "precio_por_hora": float(tramo.precio_por_hora)}
        for tramo in tarifa.tramos.all()
    ]
    return {
        "nombre": tarifa.nombre,
        "precio_por_hora": float(tarifa.precio_por_hora),
        "tramos": tramos,
    }


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
