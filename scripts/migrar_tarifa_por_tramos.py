"""
Instala el cobro por rangos con monto fijo en una base que ya existe.

Hace dos cosas:

1. Deja la tabla tarifa_tramos con las columnas del modelo actual
   (monto_fijo + precio_por_hora_adicional). Si venía de la versión que
   solo tenía precio_por_hora, la convierte sin perder las filas.

2. CIERRA la tarifa vigente y crea una nueva con los tramos de abajo, en
   vez de sobrescribir la que estaba. Es el mismo principio que el resto
   del proyecto: una tarifa no se borra ni se edita, se cierra con
   vigente_hasta, para que un cobro viejo se pueda seguir explicando con
   la tarifa que regía ese día.

Es idempotente: si la tarifa vigente ya tiene exactamente estos tramos, no
crea otra.

Uso:
    python scripts/migrar_tarifa_por_tramos.py
"""

from db import conectar

NOMBRE_TARIFA = "Tarifa escalonada"

# (desde_minuto, monto_fijo, precio_por_hora_adicional)
#   menos de 15 min  gratis
#   15 a 60 min      Q15 fijo
#   1 a 5 horas      Q35 fijo
#   más de 5 horas   Q35 + Q10 por cada hora empezada de más
TRAMOS = [
    (0, 0.00, 0.00),
    (15, 15.00, 0.00),
    (60, 35.00, 0.00),
    (300, 35.00, 10.00),
]

# Precio de referencia que queda en la fila de `tarifas`. El cobro real sale
# de los tramos; esta columna existe desde antes y se conserva.
PRECIO_REFERENCIA = 15.00

CREAR_TABLA = """
CREATE TABLE IF NOT EXISTS tarifa_tramos (
    id                          INT           NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tarifa_id                   INT           NOT NULL,
    desde_minuto                INT           NOT NULL,
    monto_fijo                  DECIMAL(8,2)  NOT NULL DEFAULT 0.00,
    precio_por_hora_adicional   DECIMAL(8,2)  NOT NULL DEFAULT 0.00,
    FOREIGN KEY (tarifa_id) REFERENCES tarifas(id),
    UNIQUE KEY uq_tarifa_desde (tarifa_id, desde_minuto)
)
"""


def _columnas(cursor, tabla):
    cursor.execute(f"SHOW COLUMNS FROM {tabla}")
    return {fila[0] for fila in cursor.fetchall()}


def poner_al_dia_la_tabla(cursor):
    """Lleva tarifa_tramos al modelo actual, venga de donde venga."""
    cursor.execute(CREAR_TABLA)
    columnas = _columnas(cursor, "tarifa_tramos")

    # Versión anterior: la columna se llamaba precio_por_hora y significaba
    # "precio prorrateado dentro del tramo". Ahora el tramo abierto usa
    # precio_por_hora_adicional; se renombra para no perder las filas.
    if "precio_por_hora" in columnas and "precio_por_hora_adicional" not in columnas:
        cursor.execute(
            "ALTER TABLE tarifa_tramos "
            "CHANGE precio_por_hora precio_por_hora_adicional DECIMAL(8,2) NOT NULL DEFAULT 0.00"
        )
        print("  columna precio_por_hora -> precio_por_hora_adicional")
        columnas = _columnas(cursor, "tarifa_tramos")

    if "monto_fijo" not in columnas:
        cursor.execute(
            "ALTER TABLE tarifa_tramos "
            "ADD COLUMN monto_fijo DECIMAL(8,2) NOT NULL DEFAULT 0.00 AFTER desde_minuto"
        )
        print("  columna monto_fijo agregada")


def tramos_actuales(cursor, tarifa_id):
    cursor.execute("""
        SELECT desde_minuto, monto_fijo, precio_por_hora_adicional
        FROM tarifa_tramos WHERE tarifa_id = %s ORDER BY desde_minuto
    """, (tarifa_id,))
    return [(int(d), float(f), float(a)) for d, f, a in cursor.fetchall()]


def main():
    conexion = conectar()
    cursor = conexion.cursor()
    try:
        print("Poniendo al día la tabla tarifa_tramos...")
        poner_al_dia_la_tabla(cursor)

        cursor.execute("""
            SELECT id, nombre FROM tarifas
            WHERE vigente_hasta IS NULL
            ORDER BY vigente_desde DESC LIMIT 1
        """)
        vigente = cursor.fetchone()

        if vigente and tramos_actuales(cursor, vigente[0]) == TRAMOS:
            print(f"\nLa tarifa vigente #{vigente[0]} '{vigente[1]}' ya tiene estos tramos.")
            print("No hay nada que cambiar.")
            return

        if vigente:
            cursor.execute(
                "UPDATE tarifas SET vigente_hasta = NOW() WHERE id = %s", (vigente[0],))
            print(f"\nTarifa #{vigente[0]} '{vigente[1]}' cerrada (queda en el historial).")

        cursor.execute(
            "INSERT INTO tarifas (nombre, precio_por_hora) VALUES (%s, %s)",
            (NOMBRE_TARIFA, PRECIO_REFERENCIA),
        )
        tarifa_id = cursor.lastrowid
        print(f"Tarifa nueva #{tarifa_id} '{NOMBRE_TARIFA}' creada y vigente.")

        for desde, fijo, adicional in TRAMOS:
            cursor.execute("""
                INSERT INTO tarifa_tramos
                    (tarifa_id, desde_minuto, monto_fijo, precio_por_hora_adicional)
                VALUES (%s, %s, %s, %s)
            """, (tarifa_id, desde, fijo, adicional))

        conexion.commit()

        print("\nTramos cargados:")
        tramos = tramos_actuales(cursor, tarifa_id)
        for indice, (desde, fijo, adicional) in enumerate(tramos):
            hasta = tramos[indice + 1][0] if indice + 1 < len(tramos) else None
            rango = f"{desde}-{hasta} min" if hasta else f"más de {desde} min"
            if fijo == 0 and adicional == 0:
                precio = "gratis"
            elif adicional:
                precio = f"Q{fijo:.2f} + Q{adicional:.2f} por hora empezada de más"
            else:
                precio = f"Q{fijo:.2f}"
            print(f"  {rango:<18} {precio}")
    finally:
        cursor.close()
        conexion.close()


if __name__ == "__main__":
    main()
