"""
Simulación de punta a punta: un vehículo "entra" al parqueo (usando una
foto de placa de prueba, ya que todavía no hay cámara conectada), se le
lee la placa por OCR, ocupa un espacio real en la base de datos en la
nube, permanece un rato, "sale", y se calcula el cobro automáticamente.

De la placa hacia adelante, todo lo que hace este script es real: conecta
a TiDB Cloud de verdad, escribe filas de verdad, calcula el cobro con la
tarifa real guardada en la base. Lo único simulado es el origen de la
imagen (una foto de prueba en vez de la cámara del Raspberry Pi).

Por defecto, el tiempo estacionado es el tiempo REAL que pasa entre que
arranca el script y presionás ENTER para cerrar la sesión -- si esperás
2 minutos, cobra 2 minutos, sin trucos. Si para la demo no querés esperar
mucho rato para que el cobro se vea significativo, se puede forzar una
entrada retroactiva con --minutos (ej. --minutos 45 simula que el carro
entró hace 45 minutos, sin que tengas que esperar 45 minutos de verdad).

Uso:
    python scripts/simulacion_demo.py
    python scripts/simulacion_demo.py --placa test_images/C789GHJ.png --espacio A2
    python scripts/simulacion_demo.py --minutos 45
"""

import argparse
import math
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

import cv2
import pytesseract

from db import conectar

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
CONFIG_TESSERACT = "--psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

CARPETA_IMAGENES = Path(__file__).resolve().parent.parent / "test_images"


def leer_placa(ruta_imagen: Path) -> str:
    img = cv2.imread(str(ruta_imagen))
    gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, binaria = cv2.threshold(gris, 150, 255, cv2.THRESH_BINARY)
    texto = pytesseract.image_to_string(binaria, config=CONFIG_TESSERACT)
    return re.sub(r"[^A-Z0-9]", "", texto.upper())


def paso(mensaje):
    print(f"\n>> {mensaje}")
    time.sleep(0.6)  # pausa breve solo para que la demo se pueda leer en vivo


def main():
    parser = argparse.ArgumentParser(description="Simulación completa: entrada, ocupación y cobro")
    parser.add_argument("--placa", default=None, help="Ruta a la imagen de la placa (default: foto real de referencia)")
    parser.add_argument("--espacio", default="A1", help="Etiqueta del espacio a ocupar (default: A1)")
    parser.add_argument(
        "--minutos", type=int, default=None,
        help="Simula que el carro entró hace N minutos, en vez de usar el tiempo real de espera",
    )
    args = parser.parse_args()

    ruta_imagen = Path(args.placa) if args.placa else CARPETA_IMAGENES / "Placa_vehicular_de_Guatemala.png"
    etiqueta_espacio = args.espacio

    print("=" * 60)
    print(" SIMULACIÓN — Estacionamiento Inteligente")
    print("=" * 60)

    paso(f"Cámara captura un vehículo ingresando (foto de prueba: {ruta_imagen.name})")
    placa = leer_placa(ruta_imagen)
    print(f"   Placa leída por OCR: {placa}")

    conexion = conectar()
    cursor = conexion.cursor()

    paso(f"Registrando vehículo '{placa}' en la base de datos (si es la primera vez que se ve)")
    cursor.execute("INSERT IGNORE INTO vehiculos (placa) VALUES (%s)", (placa,))

    paso(f"Verificando el espacio '{etiqueta_espacio}'")
    cursor.execute("SELECT id, estado FROM espacios WHERE etiqueta = %s", (etiqueta_espacio,))
    fila = cursor.fetchone()
    if fila is None:
        raise SystemExit(f"No existe el espacio '{etiqueta_espacio}'. Espacios disponibles: A1-A4.")
    espacio_id, estado_actual = fila
    if estado_actual == "ocupado":
        raise SystemExit(f"El espacio '{etiqueta_espacio}' ya está ocupado. Elegí otro con --espacio.")
    print(f"   Espacio libre. Se lo asigna a la placa {placa}.")

    if args.minutos is not None:
        hora_entrada = datetime.now() - timedelta(minutes=args.minutos)
        paso(f"Abriendo sesión de estacionamiento (entrada forzada hace {args.minutos} min con --minutos)")
    else:
        hora_entrada = datetime.now()
        paso("Abriendo sesión de estacionamiento (entrada AHORA -- el cobro va a usar el tiempo real que esperes)")
    cursor.execute(
        "INSERT INTO sesiones (placa, espacio_id, hora_entrada, estado) VALUES (%s, %s, %s, 'activa')",
        (placa, espacio_id, hora_entrada),
    )
    sesion_id = cursor.lastrowid
    cursor.execute("UPDATE espacios SET estado = 'ocupado' WHERE id = %s", (espacio_id,))
    conexion.commit()
    print(f"   Sesión #{sesion_id} abierta. Espacio '{etiqueta_espacio}' ahora está OCUPADO.")
    print(f"   -> Revisá el dashboard web o el SQL Editor de TiDB: el espacio '{etiqueta_espacio}' ya cambió de estado.")

    input("\nPresioná ENTER para simular que el vehículo se retira y cerrar la sesión...")

    hora_salida = datetime.now()
    # Igual que un parqueo real: se cobra el minuto en el que ya entraste,
    # aunque sea parcial (ceil, no round) -- y siempre al menos 1 minuto.
    minutos_totales = max(1, math.ceil((hora_salida - hora_entrada).total_seconds() / 60))

    paso("Vehículo se retira. Cerrando sesión y calculando el cobro")
    cursor.execute("SELECT id, precio_por_hora FROM tarifas WHERE vigente_hasta IS NULL ORDER BY vigente_desde DESC LIMIT 1")
    tarifa_id, precio_por_hora = cursor.fetchone()
    monto = round(float(precio_por_hora) * minutos_totales / 60, 2)

    cursor.execute(
        "UPDATE sesiones SET hora_salida = %s, estado = 'cerrada' WHERE id = %s",
        (hora_salida, sesion_id),
    )
    cursor.execute("UPDATE espacios SET estado = 'libre' WHERE id = %s", (espacio_id,))
    cursor.execute(
        "INSERT INTO cobros (sesion_id, tarifa_id, minutos_totales, monto) VALUES (%s, %s, %s, %s)",
        (sesion_id, tarifa_id, minutos_totales, monto),
    )
    conexion.commit()

    print(f"\n   Tiempo estacionado: {minutos_totales} minutos")
    print(f"   Tarifa aplicada: Q{precio_por_hora}/hora")
    print(f"   COBRO GENERADO: Q{monto}")
    print(f"   Espacio '{etiqueta_espacio}' ahora está LIBRE de nuevo.")

    cursor.close()
    conexion.close()

    print("\n" + "=" * 60)
    print(" Simulación completa. Todo lo anterior quedó guardado en TiDB Cloud.")
    print("=" * 60)


if __name__ == "__main__":
    main()
