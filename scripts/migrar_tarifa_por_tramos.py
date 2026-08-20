"""
Crea la tabla tarifa_tramos y le carga el escalonado a la tarifa vigente.

Para una base que ya existe y tiene datos: schema.sql trae la tabla y los
tramos para una instalación nueva, pero la base de TiDB ya está creada, así
que este script hace el cambio sin tocar nada de lo que ya hay (vehículos,
sesiones y cobros quedan intactos).

Es idempotente: correrlo dos veces no duplica nada.

Uso:
    python scripts/migrar_tarifa_por_tramos.py
"""

from db import conectar

# 15 minutos de gracia y después el precio por hora va subiendo, como un
# parqueo real. Estos números son un punto de partida razonable, NO tarifas
# oficiales de ningún parqueo -- se cambian desde /admin/ sin tocar código.
TRAMOS = [
    (0, 0.00),     # primeros 15 minutos: gratis
    (15, 5.00),    # de 15 minutos a 1 hora
    (60, 7.00),    # segunda hora
    (120, 10.00),  # de la tercera hora en adelante
]

CREAR_TABLA = """
CREATE TABLE IF NOT EXISTS tarifa_tramos (
    id                  INT           NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tarifa_id           INT           NOT NULL,
    desde_minuto        INT           NOT NULL,
    precio_por_hora     DECIMAL(8,2)  NOT NULL,
    FOREIGN KEY (tarifa_id) REFERENCES tarifas(id),
    UNIQUE KEY uq_tarifa_desde (tarifa_id, desde_minuto)
)
"""


def main():
    conexion = conectar()
    cursor = conexion.cursor()
    try:
        cursor.execute(CREAR_TABLA)
        print("Tabla tarifa_tramos lista.")

        cursor.execute("""
            SELECT id, nombre FROM tarifas
            WHERE vigente_hasta IS NULL
            ORDER BY vigente_desde DESC LIMIT 1
        """)
        fila = cursor.fetchone()
        if fila is None:
            raise SystemExit("No hay ninguna tarifa vigente. Corré primero init_db.py.")
        tarifa_id, nombre = fila
        print(f"Tarifa vigente: #{tarifa_id} '{nombre}'")

        for desde, precio in TRAMOS:
            cursor.execute("""
                INSERT INTO tarifa_tramos (tarifa_id, desde_minuto, precio_por_hora)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE precio_por_hora = VALUES(precio_por_hora)
            """, (tarifa_id, desde, precio))

        conexion.commit()

        cursor.execute("""
            SELECT desde_minuto, precio_por_hora FROM tarifa_tramos
            WHERE tarifa_id = %s ORDER BY desde_minuto
        """, (tarifa_id,))
        print("\nTramos cargados:")
        tramos = cursor.fetchall()
        for indice, (desde, precio) in enumerate(tramos):
            hasta = tramos[indice + 1][0] if indice + 1 < len(tramos) else None
            rango = f"{desde}-{hasta} min" if hasta else f"{desde}+ min"
            etiqueta = "gratis" if float(precio) == 0 else f"Q{precio}/hora"
            print(f"  {rango:<16} {etiqueta}")
    finally:
        cursor.close()
        conexion.close()


if __name__ == "__main__":
    main()
