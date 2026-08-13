"""
Motor del parqueo: toda la lógica de negocio en un solo lugar.

Este módulo NO sabe nada de cámaras ni de OCR -- solo de vehículos,
espacios, sesiones y cobros. Lo usan por igual:
  - simulacion_demo.py  (demo manual, sin cámara)
  - monitor.py          (pipeline real con cámara)

Tenerlo separado es lo que permite que el mismo cálculo de cobro corra
igual en la laptop y en la Raspberry Pi, sin duplicar código.
"""

import math
from datetime import datetime

from db import conectar


class EspacioNoExiste(Exception):
    pass


class EspacioOcupado(Exception):
    pass


# ─────────────────────────────────────────────────────────────────────
# Consultas de estado
# ─────────────────────────────────────────────────────────────────────

def listar_espacios(cursor):
    """Devuelve todos los espacios con su estado y la placa que lo ocupa (si hay)."""
    cursor.execute("""
        SELECT e.id, e.etiqueta, e.estado, s.placa
        FROM espacios e
        LEFT JOIN sesiones s ON s.espacio_id = e.id AND s.estado = 'activa'
        ORDER BY e.etiqueta
    """)
    return cursor.fetchall()


def buscar_espacio(cursor, etiqueta):
    """Devuelve (id, estado) del espacio, o lanza EspacioNoExiste."""
    cursor.execute("SELECT id, estado FROM espacios WHERE etiqueta = %s", (etiqueta,))
    fila = cursor.fetchone()
    if fila is None:
        raise EspacioNoExiste(f"No existe el espacio '{etiqueta}'.")
    return fila


def primer_espacio_libre(cursor):
    """Devuelve (id, etiqueta) del primer espacio libre, o None si está lleno."""
    cursor.execute("SELECT id, etiqueta FROM espacios WHERE estado = 'libre' ORDER BY etiqueta LIMIT 1")
    return cursor.fetchone()


def sesion_activa_de_placa(cursor, placa):
    """Si esta placa ya está adentro, devuelve (sesion_id, espacio_id). Si no, None."""
    cursor.execute(
        "SELECT id, espacio_id FROM sesiones WHERE placa = %s AND estado = 'activa' LIMIT 1",
        (placa,),
    )
    return cursor.fetchone()


def sesion_activa_de_espacio(cursor, espacio_id):
    """Si el espacio tiene una sesión abierta, devuelve (sesion_id, placa, hora_entrada)."""
    cursor.execute(
        "SELECT id, placa, hora_entrada FROM sesiones WHERE espacio_id = %s AND estado = 'activa' LIMIT 1",
        (espacio_id,),
    )
    return cursor.fetchone()


def actualizar_placa_de_sesion(conexion, etiqueta_espacio, placa):
    """
    Cambia la placa de la sesión abierta de un espacio.

    Existe porque el monitor abre la sesión apenas detecta el vehículo (para
    que el tablero reaccione al instante) y sigue intentando leer la placa
    unos segundos más. Cuando por fin la lee, corrige el registro.
    """
    cursor = conexion.cursor()
    try:
        espacio_id, _ = buscar_espacio(cursor, etiqueta_espacio)
        sesion = sesion_activa_de_espacio(cursor, espacio_id)
        if sesion is None:
            return False
        sesion_id, placa_actual, _ = sesion
        if placa_actual == placa:
            return False
        registrar_vehiculo(cursor, placa)
        cursor.execute("UPDATE sesiones SET placa = %s WHERE id = %s", (placa, sesion_id))
        conexion.commit()
        return True
    finally:
        cursor.close()


def estado_actual_de_espacios(conexion):
    """
    Devuelve {etiqueta: True/False} según lo que dice la base de datos.

    Lo usa el monitor al arrancar para partir del estado real y no del
    primer cuadro que vea la cámara.
    """
    cursor = conexion.cursor()
    cursor.execute("SELECT etiqueta, estado FROM espacios")
    estado = {etiqueta: (valor == "ocupado") for etiqueta, valor in cursor.fetchall()}
    cursor.close()
    return estado


def tarifa_vigente(cursor):
    """Devuelve (id, precio_por_hora) de la tarifa vigente ahora."""
    cursor.execute("""
        SELECT id, precio_por_hora FROM tarifas
        WHERE vigente_hasta IS NULL
        ORDER BY vigente_desde DESC LIMIT 1
    """)
    fila = cursor.fetchone()
    if fila is None:
        raise RuntimeError("No hay ninguna tarifa vigente en la base de datos.")
    return fila


# ─────────────────────────────────────────────────────────────────────
# Operaciones
# ─────────────────────────────────────────────────────────────────────

def registrar_vehiculo(cursor, placa):
    """Registra la placa si es la primera vez que se ve. Idempotente."""
    cursor.execute("INSERT IGNORE INTO vehiculos (placa) VALUES (%s)", (placa,))


def abrir_sesion(conexion, placa, etiqueta_espacio, hora_entrada=None):
    """
    Un vehículo ocupa un espacio. Devuelve el id de la sesión creada.

    hora_entrada permite forzar una entrada retroactiva (útil para demos);
    si se omite, se usa el momento actual.
    """
    cursor = conexion.cursor()
    espacio_id, estado = buscar_espacio(cursor, etiqueta_espacio)
    if estado == "ocupado":
        cursor.close()
        raise EspacioOcupado(f"El espacio '{etiqueta_espacio}' ya está ocupado.")

    registrar_vehiculo(cursor, placa)
    cursor.execute(
        "INSERT INTO sesiones (placa, espacio_id, hora_entrada, estado) VALUES (%s, %s, %s, 'activa')",
        (placa, espacio_id, hora_entrada or datetime.now()),
    )
    sesion_id = cursor.lastrowid
    cursor.execute("UPDATE espacios SET estado = 'ocupado' WHERE id = %s", (espacio_id,))
    conexion.commit()
    cursor.close()
    return sesion_id


def calcular_monto(precio_por_hora, minutos):
    """
    Cobro = tarifa por hora prorrateada a los minutos usados.

    Se usa ceil (no round) y mínimo 1 minuto, igual que un parqueo real:
    el minuto empezado se cobra completo.
    """
    minutos_cobrables = max(1, math.ceil(minutos))
    return round(float(precio_por_hora) * minutos_cobrables / 60, 2), minutos_cobrables


def cerrar_sesion(conexion, sesion_id, hora_salida=None):
    """
    El vehículo se retira: cierra la sesión, libera el espacio y genera el
    cobro según la tarifa vigente. Devuelve (minutos, monto, precio_por_hora).
    """
    cursor = conexion.cursor()
    cursor.execute(
        "SELECT espacio_id, hora_entrada, estado FROM sesiones WHERE id = %s",
        (sesion_id,),
    )
    fila = cursor.fetchone()
    if fila is None:
        cursor.close()
        raise ValueError(f"No existe la sesión #{sesion_id}.")

    espacio_id, hora_entrada, estado = fila
    if estado == "cerrada":
        cursor.close()
        raise ValueError(f"La sesión #{sesion_id} ya estaba cerrada.")

    hora_salida = hora_salida or datetime.now()
    # El tiempo se calcula en Python, no con NOW() del servidor: hora_entrada
    # se guardó con la hora local de esta máquina, y el servidor de TiDB puede
    # estar en otro huso horario (comparar allá daba minutos inflados).
    minutos_crudos = (hora_salida - hora_entrada).total_seconds() / 60
    tarifa_id, precio_por_hora = tarifa_vigente(cursor)
    monto, minutos = calcular_monto(precio_por_hora, minutos_crudos)

    cursor.execute(
        "UPDATE sesiones SET hora_salida = %s, estado = 'cerrada' WHERE id = %s",
        (hora_salida, sesion_id),
    )
    cursor.execute("UPDATE espacios SET estado = 'libre' WHERE id = %s", (espacio_id,))
    cursor.execute(
        "INSERT INTO cobros (sesion_id, tarifa_id, minutos_totales, monto) VALUES (%s, %s, %s, %s)",
        (sesion_id, tarifa_id, minutos, monto),
    )
    conexion.commit()
    cursor.close()
    return minutos, monto, precio_por_hora


def sincronizar_espacio(conexion, etiqueta_espacio, ocupado_ahora, placa=None):
    """
    Reconcilia lo que ve la cámara con lo que dice la base de datos.

    Esta es la función que usa el pipeline real: la cámara reporta si el
    espacio se ve ocupado o libre, y acá se decide si eso significa abrir
    una sesión nueva, cerrar la existente, o no hacer nada.

    Devuelve una descripción de lo que pasó (o None si no hubo cambio).
    """
    cursor = conexion.cursor()
    espacio_id, estado_db = buscar_espacio(cursor, etiqueta_espacio)
    sesion = sesion_activa_de_espacio(cursor, espacio_id)
    cursor.close()

    if ocupado_ahora and estado_db == "libre":
        # Llegó un carro a un espacio que estaba libre.
        sesion_id = abrir_sesion(conexion, placa or "DESCONOCIDA", etiqueta_espacio)
        return f"entrada: {placa or 'DESCONOCIDA'} ocupó {etiqueta_espacio} (sesión #{sesion_id})"

    if not ocupado_ahora and estado_db == "ocupado" and sesion is not None:
        # Se fue el carro que estaba en ese espacio.
        sesion_id, placa_sesion, _ = sesion
        minutos, monto, _ = cerrar_sesion(conexion, sesion_id)
        return f"salida: {placa_sesion} liberó {etiqueta_espacio} — {minutos} min, Q{monto}"

    return None


def conectar_parqueo():
    """Atajo para que los scripts no tengan que importar db por separado."""
    return conectar()
