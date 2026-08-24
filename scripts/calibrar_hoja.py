"""
Calibra los espacios DETECTANDO la hoja del kit impreso, en vez de inventar
una rejilla fija.

Por qué existe: `configurar_espacios.py --rejilla 4` no mira la imagen. Calcula
cuatro cajas con pura aritmética sobre el tamaño del cuadro (640x480), así que
da SIEMPRE las mismas coordenadas sin importar dónde esté la hoja. Su propio
mensaje final lo dice ("ajustá la posición de la cámara para que los espacios
queden dentro de los recuadros"): obliga a mover el hardware hasta calzar con
una rejilla inamovible.

Eso falló en la práctica. Medido en la Pi: con la hoja apoyada en la mesa, la
región configurada de A3 quedó en x 324-466 mientras el vehículo estaba en
x≈300-360; como además solo se mide el 44% central de cada región, la franja
medida de A3 era x 363-427 y el vehículo caía ENTERO fuera de ella. El sistema
no "fallaba al detectar": estaba mirando un pedazo de papel vacío.

Acá se hace al revés: se detecta la hoja (región clara sobre fondo oscuro) y se
la divide en columnas iguales, que es lo que el kit tiene dibujado. Así las
regiones siguen a la hoja donde esté, y mover la cámara solo obliga a
recalibrar, no a acertarle a una cuadrícula fija.

    python scripts/calibrar_hoja.py            # 4 espacios (default)
    python scripts/calibrar_hoja.py --espacios 6

IMPORTANTE: correr con el parqueo VACÍO y sin manos ni objetos en el cuadro.
El recorte vertical se apoya en que la única tinta oscura sobre la hoja sean
las líneas dibujadas; una mano dentro del cuadro lo arruina.
"""

import argparse
import sys

import cv2
import numpy as np

from camara import abrir_camara, hay_camara_pi
from ocupacion import ARCHIVO_CONFIG, UMBRAL_OCUPADO_POR_DEFECTO, guardar_config

SEGUNDOS_DE_CALENTAMIENTO = 3.0

# Recortes al alto de la cuadrícula para quedarse con la zona útil del
# espacio. Abajo se recorta más porque ahí van los rótulos "A1".."A4", que
# están dentro del recuadro dibujado pero no son lugar de estacionamiento.
MARGEN_LATERAL = 0.0
MARGEN_SUPERIOR = 0.02
MARGEN_INFERIOR = 0.18


def detectar_hoja(cuadro):
    """
    Caja (x, y, ancho, alto) de la CUADRÍCULA DIBUJADA dentro del cuadro.

    Se busca la tinta, no el papel. Detectar "la hoja" como región clara
    falla cuando la pared de atrás tiene un brillo parecido al del papel:
    medido en este cuarto, pared 95-107 y papel 120-125 de brillo promedio,
    demasiado cerca para separarlos por nivel, y Otsu terminaba devolviendo
    hoja + pared como un solo bloque (y las regiones quedaban arriba, sobre
    la pared, con las celdas apretadas abajo).

    El umbral ADAPTATIVO resuelve eso de raíz porque no mira el nivel
    absoluto sino el contraste LOCAL: la pared es lisa y no genera marca por
    más gris que sea, mientras que las líneas dibujadas son oscuras respecto
    de sus vecinos inmediatos y sí la generan. Da igual entonces si la hoja
    se confunde con la pared -- lo que interesa es el rectángulo que forman
    las líneas negras.

    Las cuatro celdas quedan unidas en un solo contorno (sus líneas se
    tocan), así que el contorno de tinta más grande ES la cuadrícula
    completa. Verificado sobre la escena real: da x117-458 y256-463, y los
    rótulos A1..A4 aparecen aparte, centrados cada 85 px = 341/4, que
    confirma la geometría por un camino independiente.
    """
    gris = cv2.cvtColor(cuadro, cv2.COLOR_BGR2GRAY)

    # Los tamaños de filtro se escalan con la resolución. Están afinados
    # sobre cuadros de 640 px de ancho, y a 1296 px un kernel del mismo
    # tamaño en píxeles es la mitad de grande en términos de la escena: la
    # cuadrícula deja de cerrarse en una sola pieza y la detección devuelve
    # una franja suelta en vez del recuadro completo (pasó de verdad al
    # subir la resolución).
    escala = max(1.0, cuadro.shape[1] / 640.0)

    def impar(valor):
        entero = max(3, int(round(valor)))
        return entero if entero % 2 == 1 else entero + 1

    suave = cv2.GaussianBlur(gris, (impar(5 * escala), impar(5 * escala)), 0)

    tinta = cv2.adaptiveThreshold(
        suave, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV,
        impar(25 * escala), 12
    )
    # Cierra los cortes del trazo para que la cuadrícula quede de una pieza.
    lado = impar(7 * escala)
    cerrada = cv2.morphologyEx(
        tinta, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (lado, lado))
    )

    contornos, _ = cv2.findContours(cerrada, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    if not contornos:
        return None

    # Por área de la CAJA, no del trazo: la cuadrícula es un marco hueco, así
    # que su área de contorno es chica aunque abarque toda la escena.
    mejor = max(contornos, key=lambda c: np.prod(cv2.boundingRect(c)[2:]))
    return cv2.boundingRect(mejor)


def celdas_de_hoja(caja, columnas):
    """Divide la hoja en `columnas` espacios iguales."""
    x, y, ancho, alto = caja
    dx = int(ancho * MARGEN_LATERAL)
    util_x0 = x + dx
    util_ancho = ancho - 2 * dx
    ancho_celda = util_ancho // columnas

    y_celda = y + int(alto * MARGEN_SUPERIOR)
    alto_celda = alto - int(alto * MARGEN_SUPERIOR) - int(alto * MARGEN_INFERIOR)

    return [
        [util_x0 + i * ancho_celda + 4, y_celda, ancho_celda - 8, alto_celda]
        for i in range(columnas)
    ]


def etiqueta_para(indice):
    return f"A{indice + 1}"


def main():
    parser = argparse.ArgumentParser(
        description="Calibra los espacios detectando la hoja del kit impreso"
    )
    parser.add_argument("--espacios", type=int, default=4,
                        help="Cuántos espacios tiene la hoja (default: 4)")
    parser.add_argument("--camara", type=int, default=0)
    parser.add_argument("--camara-pi", action="store_true",
                        help="Forzar la cámara CSI de la Raspberry Pi")
    parser.add_argument("--ancho", type=int, default=1296,
                        help="Ancho de captura (default: 1296)")
    parser.add_argument("--alto", type=int, default=972,
                        help="Alto de captura (default: 972)")
    args = parser.parse_args()

    camara = abrir_camara(args.camara, ancho=args.ancho, alto=args.alto,
                          usar_pi_camera=args.camara_pi or hay_camara_pi())
    try:
        # Mismo calentamiento que monitor.py: los primeros cuadros salen con
        # la exposición sin converger y la hoja puede no separarse del fondo.
        import time
        fin = time.monotonic() + SEGUNDOS_DE_CALENTAMIENTO
        while time.monotonic() < fin:
            camara.read()
        ok, cuadro = camara.read()
    finally:
        camara.release()

    if not ok or cuadro is None:
        sys.exit("No se pudo leer de la cámara.")

    caja = detectar_hoja(cuadro)
    if caja is None:
        sys.exit("No se encontró la hoja. ¿Hay suficiente luz y la hoja se ve completa?")

    x, y, ancho, alto = caja
    alto_img, ancho_img = cuadro.shape[:2]
    print(f"Hoja detectada: x {x}-{x + ancho}, y {y}-{y + alto} "
          f"({ancho}x{alto} de {ancho_img}x{alto_img})")

    if ancho < ancho_img * 0.3 or alto < alto_img * 0.3:
        print("AVISO: la hoja ocupa poco del cuadro. Acercá la cámara para que "
              "las placas salgan con más píxeles y el OCR las lea mejor.")

    celdas = celdas_de_hoja(caja, args.espacios)
    config = [
        {"etiqueta": etiqueta_para(i), "region": celda, "umbral": UMBRAL_OCUPADO_POR_DEFECTO}
        for i, celda in enumerate(celdas)
    ]
    guardar_config(config)

    for entrada in config:
        rx, ry, rw, rh = entrada["region"]
        print(f"   {entrada['etiqueta']}: x {rx}-{rx + rw}  y {ry}-{ry + rh}")
    print(f"\nGuardado en {ARCHIVO_CONFIG.name}. "
          f"Revisá con: python ver_regiones.py")


if __name__ == "__main__":
    main()
