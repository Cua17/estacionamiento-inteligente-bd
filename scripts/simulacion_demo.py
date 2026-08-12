"""
Simulación de punta a punta SIN cámara: un vehículo "entra" al parqueo
usando una imagen de placa ya guardada, se le lee la placa por OCR, ocupa
un espacio real en la base de datos, y al salir se calcula el cobro.

Toda la lógica de negocio vive en parqueo.py -- este script solo la maneja
paso a paso para poder narrarla en vivo. El pipeline con cámara real
(monitor.py) usa exactamente las mismas funciones.

Por defecto el tiempo estacionado es el tiempo REAL entre que arranca el
script y presionás ENTER. Para no esperar en una demo, --minutos fuerza
una entrada retroactiva.

Uso:
    python scripts/simulacion_demo.py
    python scripts/simulacion_demo.py --placa test_images/C789GHJ.png --espacio A2
    python scripts/simulacion_demo.py --minutos 45
"""

import argparse
import time
from datetime import datetime, timedelta
from pathlib import Path

import parqueo
from vision import leer_placa_de_archivo

CARPETA_IMAGENES = Path(__file__).resolve().parent.parent / "test_images"


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
    print(" SIMULACION - Estacionamiento Inteligente")
    print("=" * 60)

    paso(f"Camara captura un vehiculo ingresando (imagen: {ruta_imagen.name})")
    placa = leer_placa_de_archivo(ruta_imagen)
    print(f"   Placa leida por OCR: {placa}")

    conexion = parqueo.conectar_parqueo()

    if args.minutos is not None:
        hora_entrada = datetime.now() - timedelta(minutes=args.minutos)
        paso(f"Abriendo sesion (entrada forzada hace {args.minutos} min con --minutos)")
    else:
        hora_entrada = None
        paso("Abriendo sesion (entrada AHORA -- el cobro usara el tiempo real que esperes)")

    try:
        sesion_id = parqueo.abrir_sesion(conexion, placa, etiqueta_espacio, hora_entrada)
    except (parqueo.EspacioNoExiste, parqueo.EspacioOcupado) as error:
        raise SystemExit(f"{error} Proba con otro espacio usando --espacio.")

    print(f"   Sesion #{sesion_id} abierta. Espacio '{etiqueta_espacio}' ahora esta OCUPADO.")
    print("   -> Mira el dashboard: el espacio ya cambio de estado y aparece en 'adentro ahora mismo'.")

    input("\nPresiona ENTER para simular que el vehiculo se retira y cerrar la sesion...")

    paso("Vehiculo se retira. Cerrando sesion y calculando el cobro")
    minutos, monto, precio = parqueo.cerrar_sesion(conexion, sesion_id)

    print(f"\n   Tiempo estacionado: {minutos} minutos")
    print(f"   Tarifa aplicada: Q{precio}/hora")
    print(f"   COBRO GENERADO: Q{monto}")
    print(f"   Espacio '{etiqueta_espacio}' ahora esta LIBRE de nuevo.")

    conexion.close()

    print("\n" + "=" * 60)
    print(" Simulacion completa. Todo quedo guardado en TiDB Cloud.")
    print("=" * 60)


if __name__ == "__main__":
    main()
