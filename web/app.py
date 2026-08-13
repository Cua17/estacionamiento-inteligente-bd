"""
Dashboard del parqueo: muestra en tiempo real qué espacios hay libres, quién
está adentro, la bitácora de movimientos y lo recaudado.

Solo lee de la base de datos; nunca la modifica. Quien escribe es el monitor
(scripts/monitor.py), así que este servidor puede reiniciarse o cerrarse sin
afectar el registro del parqueo.

Uso:
    python web/app.py
Luego abrir http://localhost:5050 en el navegador.
"""

import sys
import threading
import time
from pathlib import Path

from flask import Flask, jsonify, render_template

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from db import conectar  # noqa: E402
from reportes import estado_completo, partes_lentas, partes_medias  # noqa: E402

app = Flask(__name__)

PUERTO = 5050

# El servidor de TiDB está en Tokio: abrir una conexión nueva cuesta cerca de
# dos segundos solo en el saludo TLS. Como la página consulta cada pocos
# segundos, reconectar cada vez hacía que las consultas se amontonaran y el
# tablero quedara varios segundos atrasado. Se mantiene UNA conexión viva y se
# reusa; si se cae, se abre otra sola.
_conexion = None
_candado = threading.Lock()

# Además se guarda la última lectura por un instante: si llegan varias
# peticiones casi juntas, la segunda reusa el resultado en vez de castigar a
# la base con la misma consulta repetida.
CACHE_SEGUNDOS = 0.25
_cache = {"datos": None, "momento": 0.0}

# Cada consulta es un viaje de ida y vuelta a Tokio (~300 ms), así que se
# agrupan por qué tan seguido cambian de verdad:
#   - ocupación de espacios: en cada refresco (es LO que hay que ver al instante)
#   - bitácora y recaudación: solo cambian cuando entra o sale un vehículo
#   - perfil por hora, tarifa y totales: prácticamente estáticos
CACHE_MEDIOS_SEGUNDOS = 2
_cache_medios = {"datos": None, "momento": 0.0}

CACHE_LENTOS_SEGUNDOS = 30
_cache_lentos = {"datos": None, "momento": 0.0}


def _obtener_conexion():
    """
    Devuelve la conexión viva, reconectando si hace falta.

    OJO con `autocommit`: TiDB (como MySQL) usa aislamiento REPEATABLE READ,
    así que una conexión reutilizada se queda mirando la MISMA foto de la
    base que vio al abrir su transacción, y nunca se entera de lo que escribe
    el monitor. Con autocommit cada consulta es su propia transacción y
    siempre lee el estado actual. Sin esto, el tablero se queda congelado en
    datos viejos por minutos.
    """
    global _conexion
    if _conexion is not None:
        # No se hace ping: comprobar la conexión cuesta otro viaje a Tokio en
        # cada refresco. Se usa directo y, si falla, el que llama la descarta
        # y en el siguiente intento se abre una nueva.
        return _conexion

    _conexion = conectar()
    _conexion.autocommit = True
    return _conexion


@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/api/estado")
def api_estado():
    """
    Estado completo del parqueo en JSON. La página lo consulta cada pocos
    segundos.

    Si la base no responde se devuelve 503 con el motivo, en vez de dejar
    que Flask muestre una traza: el navegador necesita distinguir "no pude
    leer" de "leí y no hay nada", para avisar en pantalla que los números
    que se están viendo ya no son de ahora.
    """
    ahora = time.monotonic()
    if _cache["datos"] is not None and ahora - _cache["momento"] < CACHE_SEGUNDOS:
        return jsonify(_cache["datos"])

    with _candado:
        # Otra petición pudo refrescar el cache mientras se esperaba el turno.
        ahora = time.monotonic()
        if _cache["datos"] is not None and ahora - _cache["momento"] < CACHE_SEGUNDOS:
            return jsonify(_cache["datos"])

        try:
            conexion = _obtener_conexion()
            ahora = time.monotonic()
            if (_cache_medios["datos"] is None
                    or ahora - _cache_medios["momento"] >= CACHE_MEDIOS_SEGUNDOS):
                _cache_medios["datos"] = partes_medias(conexion)
                _cache_medios["momento"] = time.monotonic()
            if (_cache_lentos["datos"] is None
                    or ahora - _cache_lentos["momento"] >= CACHE_LENTOS_SEGUNDOS):
                _cache_lentos["datos"] = partes_lentas(conexion)
                _cache_lentos["momento"] = time.monotonic()
            datos = estado_completo(conexion,
                                    medios=_cache_medios["datos"],
                                    lentos=_cache_lentos["datos"])
        except Exception as error:
            global _conexion
            _conexion = None      # se fuerza reconexión en el próximo intento
            return jsonify({"error": f"No se pudo leer de la base: {error}"}), 503

        _cache["datos"] = datos
        _cache["momento"] = time.monotonic()
        return jsonify(datos)


if __name__ == "__main__":
    print(f"Dashboard en http://localhost:{PUERTO}")
    app.run(debug=False, port=PUERTO, threaded=True)
