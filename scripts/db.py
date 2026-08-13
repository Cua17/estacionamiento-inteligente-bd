"""Helper de conexión a la base de datos, compartido por los demás scripts."""

import os

import certifi
import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def conectar():
    """
    Abre una conexión a TiDB Cloud.

    Va con autocommit por dos razones, y las dos importan:

    1. Velocidad. El servidor está en Tokio y cada ida y vuelta cuesta unos
       350 ms. Con autocommit, el COMMIT viaja pegado a la sentencia en vez
       de ser un viaje aparte.
    2. Datos frescos. TiDB usa aislamiento REPEATABLE READ: una conexión que
       se reutiliza sin cerrar su transacción sigue viendo la MISMA foto de
       la base con la que abrió, y nunca se entera de lo que escribió el
       monitor. Con autocommit cada consulta ve el estado actual.
    """
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "4000")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        ssl_ca=certifi.where(),
        ssl_verify_identity=True,
        autocommit=True,
    )
