"""
Deja la base de datos en estado limpio para practicar la demo las veces
que quieras: borra sesiones/cobros/vehículos de prueba y pone todos los
espacios en 'libre'. No toca las tarifas.

Uso:
    python scripts/reset_demo.py
"""

from db import conectar


def main():
    conexion = conectar()
    cursor = conexion.cursor()

    cursor.execute("DELETE FROM cobros")
    cursor.execute("DELETE FROM sesiones")
    cursor.execute("DELETE FROM vehiculos")
    cursor.execute("UPDATE espacios SET estado = 'libre'")

    conexion.commit()
    cursor.close()
    conexion.close()
    print("Base de datos reiniciada: espacios libres, sin sesiones ni cobros de prueba.")


if __name__ == "__main__":
    main()
