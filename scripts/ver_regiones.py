"""
Captura un cuadro y lo guarda con las regiones de config_espacios.json
dibujadas encima.

Sirve para responder de un vistazo la pregunta "¿qué está midiendo
realmente cada espacio?", que no se puede contestar mirando una foto
pelada ni leyendo el JSON de coordenadas. Un espacio cuya región se pasa
del área que le toca -- y agarra el borde de la hoja, la mesa o la pared --
va a dar diferencias de color enormes ante cualquier movimiento mínimo,
porque el contraste papel/mesa entra y sale de la región.

Igual que monitor.py, descarta unos segundos de cuadros antes de capturar
para que la cámara termine de ajustar exposición y balance de blancos.
"""

import time

import cv2

from camara import abrir_camara, hay_camara_pi
from ocupacion import cargar_config

SALIDA = "/home/cua/vista_espacios.jpg"
SALIDA_LIMPIA = "/home/cua/vista_limpia.jpg"
SEGUNDOS_DE_CALENTAMIENTO = 3.0

COLORES = [(0, 0, 255), (0, 200, 0), (255, 0, 0), (0, 200, 200)]


def main():
    espacios = [e for e in cargar_config() if e["etiqueta"].upper() != "PLACA"]
    # MISMA resolución que calibrar_hoja.py y monitor.py (1296x972, no el
    # 640x480 de antes). Las regiones del config están en coordenadas de
    # ESE tamaño; dibujarlas sobre un cuadro más chico las corre de lugar
    # -- pasó de verdad: con 640x480 acá las cajas aparecían desplazadas
    # respecto de los recuadros impresos, aunque la calibración estaba
    # bien. No es cosmético: si esta herramienta no ve lo mismo que
    # monitor.py, cualquier verificación que hagas con ella no sirve.
    camara = abrir_camara(0, ancho=1296, alto=972, usar_pi_camera=hay_camara_pi())
    try:
        fin = time.monotonic() + SEGUNDOS_DE_CALENTAMIENTO
        while time.monotonic() < fin:
            camara.read()
        ok, cuadro = camara.read()
        if not ok or cuadro is None:
            raise SystemExit("No se pudo leer un cuadro de la cámara.")
    finally:
        camara.release()

    cv2.imwrite(SALIDA_LIMPIA, cuadro)
    print(f"foto sin marcar : {SALIDA_LIMPIA}")

    marcado = cuadro.copy()
    for indice, espacio in enumerate(espacios):
        x, y, ancho, alto = espacio["region"]
        color = COLORES[indice % len(COLORES)]
        cv2.rectangle(marcado, (x, y), (x + ancho, y + alto), color, 2)
        cv2.putText(marcado, espacio["etiqueta"], (x + 4, y + 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        print(f"{espacio['etiqueta']}: x {x}-{x + ancho}, y {y}-{y + alto}")

    cv2.imwrite(SALIDA, marcado)
    print(f"foto con regiones: {SALIDA}")


if __name__ == "__main__":
    main()
