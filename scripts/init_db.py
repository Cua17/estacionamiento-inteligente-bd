"""
Crea la base de datos `estacionamiento_db` en el cluster de TiDB Cloud
(si no existe) y le aplica schema.sql.

Uso:
    python scripts/init_db.py
"""

import os
from pathlib import Path

import certifi
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema.sql"


def config_servidor():
    """Config de conexión SIN especificar base de datos (para poder crearla)."""
    return {
        "host": os.getenv("DB_HOST"),
        "port": int(os.getenv("DB_PORT", "4000")),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "ssl_ca": certifi.where(),
        "ssl_verify_identity": True,
    }


def main():
    nombre_db = os.getenv("DB_NAME", "estacionamiento_db")

    conexion = mysql.connector.connect(**config_servidor())
    cursor = conexion.cursor()

    print(f"Creando base de datos '{nombre_db}' si no existe...")
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {nombre_db}")
    cursor.execute(f"USE {nombre_db}")

    print(f"Aplicando {SCHEMA_PATH.name}...")
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    # mysql-connector no soporta multi-statement directo en execute();
    # usamos su iterador de comandos múltiples.
    for _ in cursor.execute(sql, multi=True):
        pass

    conexion.commit()
    cursor.close()
    conexion.close()
    print("Listo. Base de datos y tablas creadas correctamente.")


if __name__ == "__main__":
    main()
