"""
Página web simple que muestra la disponibilidad de espacios en tiempo real,
leyendo directo de la base de datos. Se auto-refresca sola cada 3 segundos.

Uso:
    python web/app.py
Luego abrir http://localhost:5050 en el navegador.
"""

import sys
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template_string

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from db import conectar  # noqa: E402

app = Flask(__name__)

PLANTILLA = """
<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="3">
<title>Estacionamiento Inteligente — Disponibilidad</title>
<style>
  body { font-family: system-ui, sans-serif; background: #0f172a; color: #e2e8f0; padding: 2rem; }
  h1 { font-size: 1.5rem; margin-bottom: 0.25rem; }
  .subtitulo { color: #94a3b8; margin-bottom: 2rem; }
  .resumen { font-size: 1.1rem; margin-bottom: 1.5rem; }
  .resumen b { color: #4ade80; }
  .grid { display: flex; gap: 1rem; flex-wrap: wrap; }
  .espacio {
    width: 140px; height: 140px; border-radius: 12px;
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    font-size: 1.1rem; font-weight: bold; gap: 0.5rem;
  }
  .libre { background: #14532d; border: 3px solid #4ade80; color: #bbf7d0; }
  .ocupado { background: #7f1d1d; border: 3px solid #f87171; color: #fecaca; }
  .placa { font-size: 0.85rem; font-weight: normal; opacity: 0.85; }
  table { margin-top: 2.5rem; border-collapse: collapse; width: 100%; max-width: 700px; }
  th, td { text-align: left; padding: 0.5rem 1rem; border-bottom: 1px solid #334155; }
  th { color: #94a3b8; font-weight: normal; font-size: 0.85rem; }
  h2 { font-size: 1rem; color: #cbd5e1; margin-top: 2.5rem; margin-bottom: 0; }
  .vacio { color: #64748b; font-size: 0.9rem; margin-top: 0.5rem; }
</style>
</head>
<body>
  <h1>Estacionamiento Inteligente</h1>
  <div class="subtitulo">Disponibilidad en tiempo real — se actualiza sola cada 3s</div>
  <div class="resumen"><b>{{ libres }}</b> de {{ total }} espacios disponibles</div>

  <div class="grid">
    {% for e in espacios %}
    <div class="espacio {{ e.estado }}">
      <div>{{ e.etiqueta }}</div>
      <div>{{ 'LIBRE' if e.estado == 'libre' else 'OCUPADO' }}</div>
      {% if e.placa %}<div class="placa">{{ e.placa }}</div>{% endif %}
    </div>
    {% endfor %}
  </div>

  <h2>Vehículos adentro ahora mismo</h2>
  {% if activas %}
  <table>
    <tr><th>Placa</th><th>Espacio</th><th>Entró a las</th><th>Minutos hasta ahora</th></tr>
    {% for a in activas %}
    <tr><td>{{ a.placa }}</td><td>{{ a.etiqueta }}</td><td>{{ a.hora_entrada }}</td><td>{{ a.minutos_transcurridos }} min</td></tr>
    {% endfor %}
  </table>
  {% else %}
  <div class="vacio">No hay vehículos estacionados ahora mismo.</div>
  {% endif %}

  <h2>Últimos cobros (sesiones ya cerradas)</h2>
  {% if cobros %}
  <table>
    <tr><th>Hora</th><th>Placa</th><th>Minutos</th><th>Monto</th></tr>
    {% for c in cobros %}
    <tr><td>{{ c.fecha }}</td><td>{{ c.placa }}</td><td>{{ c.minutos }} min</td><td>Q{{ c.monto }}</td></tr>
    {% endfor %}
  </table>
  {% else %}
  <div class="vacio">Todavía no se cerró ninguna sesión.</div>
  {% endif %}
</body>
</html>
"""


@app.route("/")
def index():
    conexion = conectar()
    cursor = conexion.cursor(dictionary=True)

    cursor.execute("""
        SELECT e.etiqueta, e.estado, s.placa
        FROM espacios e
        LEFT JOIN sesiones s ON s.espacio_id = e.id AND s.estado = 'activa'
        ORDER BY e.etiqueta
    """)
    espacios = cursor.fetchall()

    # El tiempo transcurrido se calcula en Python (contra datetime.now()),
    # NO con NOW() del servidor: hora_entrada se guarda con la hora local de
    # quien corre el script, y el servidor de TiDB puede estar en otra zona
    # horaria (UTC) -- comparar ahí daba minutos negativos o inflados.
    cursor.execute("""
        SELECT s.placa, e.etiqueta, s.hora_entrada
        FROM sesiones s
        JOIN espacios e ON e.id = s.espacio_id
        WHERE s.estado = 'activa'
        ORDER BY s.hora_entrada
    """)
    activas = cursor.fetchall()
    ahora = datetime.now()
    for a in activas:
        a["minutos_transcurridos"] = max(0, round((ahora - a["hora_entrada"]).total_seconds() / 60))
        a["hora_entrada"] = a["hora_entrada"].strftime("%H:%M:%S")

    # hora_salida sí se guarda con la hora local de Python (igual que
    # hora_entrada), así que se muestra esa en vez de fecha_cobro -- que es
    # un TIMESTAMP puesto por el propio servidor de TiDB y puede estar en
    # otro huso horario (ver el mismo comentario más arriba, en "activas").
    cursor.execute("""
        SELECT s.placa, s.hora_salida, c.minutos_totales AS minutos, c.monto
        FROM cobros c
        JOIN sesiones s ON s.id = c.sesion_id
        ORDER BY c.fecha_cobro DESC
        LIMIT 5
    """)
    cobros = cursor.fetchall()
    for c in cobros:
        c["fecha"] = c["hora_salida"].strftime("%H:%M:%S")

    cursor.close()
    conexion.close()

    libres = sum(1 for e in espacios if e["estado"] == "libre")
    return render_template_string(
        PLANTILLA, espacios=espacios, activas=activas, cobros=cobros,
        libres=libres, total=len(espacios)
    )


if __name__ == "__main__":
    app.run(debug=False, port=5050)
