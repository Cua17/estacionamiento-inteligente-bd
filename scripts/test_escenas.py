"""
Mide el acierto del OCR contra las escenas de test_scenes/ -- las que
imitan la demo real (placa sobre la hoja del parqueo, en ángulo), no
recortes limpios de la placa sola.

Uso:
    python scripts/generar_escenas_prueba.py   # una vez, para crearlas
    python scripts/test_escenas.py
"""

import time
from pathlib import Path

import cv2

from vision import formato_valido, leer_placa

CARPETA = Path(__file__).resolve().parent.parent / "test_scenes"


def main():
    escenas = sorted(CARPETA.glob("*.png"))
    if not escenas:
        print(f"No hay escenas en {CARPETA}. Corré primero generar_escenas_prueba.py")
        return

    aciertos = 0
    total_ms = 0.0
    print(f"{'ESCENA':<32} {'ESPERADO':<10} {'LEIDO':<12} {'ms':>7}  RESULTADO")
    print("-" * 80)

    for ruta in escenas:
        esperado = ruta.stem.split("_")[0].upper()
        imagen = cv2.imread(str(ruta))

        inicio = time.monotonic()
        leido = leer_placa(imagen)
        ms = (time.monotonic() - inicio) * 1000
        total_ms += ms

        ok = leido == esperado
        aciertos += ok
        estado = "OK" if ok else ("FALLO" if formato_valido(leido) else "sin lectura")
        print(f"{ruta.stem:<32} {esperado:<10} {leido or '-':<12} {ms:7.0f}  {estado}")

    print("-" * 80)
    print(f"Aciertos: {aciertos}/{len(escenas)}")
    print(f"Tiempo promedio por escena: {total_ms / len(escenas):.0f} ms")


if __name__ == "__main__":
    main()
