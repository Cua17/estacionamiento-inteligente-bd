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
from pathlib import Path

from flask import Flask, jsonify, render_template

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from db import conectar  # noqa: E402
from reportes import estado_completo  # noqa: E402

app = Flask(__name__)

PUERTO = 5050


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
    try:
        conexion = conectar()
    except Exception as error:
        return jsonify({"error": f"No se pudo conectar: {error}"}), 503

    try:
        return jsonify(estado_completo(conexion))
    except Exception as error:
        return jsonify({"error": f"Error al consultar: {error}"}), 503
    finally:
        conexion.close()


if __name__ == "__main__":
    print(f"Dashboard en http://localhost:{PUERTO}")
    app.run(debug=False, port=PUERTO)
