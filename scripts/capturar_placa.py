"""
Lee placas en vivo con la cámara.

Es la versión "real" de la prueba de OCR: en vez de leer un archivo del
disco, sostenés la placa (impresa o en la pantalla del celular) frente a
la cámara y el programa la lee. Sirve para dos cosas:

  1. Demostrar el OCR funcionando en vivo, sin trampa.
  2. Calibrar antes de una demo: ver a qué distancia y con qué luz la
     cámara lee bien, para saber dónde pararte el día de la presentación.

Dentro del recuadro guía se recorta la imagen antes de pasarla a OCR:
acotar la búsqueda a esa zona da lecturas mucho más confiables que
mandarle la foto completa a Tesseract.

Uso:
    python scripts/capturar_placa.py
    python scripts/capturar_placa.py --continuo   # lee todo el tiempo, sin apretar nada

Controles:
    ESPACIO : leer la placa del cuadro actual
    g       : guardar el recorte actual en test_images/ (para usarlo después)
    q / ESC : salir
"""

import argparse
from datetime import datetime
from pathlib import Path

import cv2

from camara import abrir_camara
from vision import formato_valido, leer_placa

CARPETA_IMAGENES = Path(__file__).resolve().parent.parent / "test_images"

VERDE = (74, 222, 128)
AMARILLO = (80, 200, 255)
BLANCO = (255, 255, 255)
NEGRO = (0, 0, 0)


def recuadro_guia(ancho, alto):
    """Zona central donde hay que poner la placa. Proporción 2:1, como una placa real."""
    ancho_guia = int(ancho * 0.6)
    alto_guia = int(ancho_guia * 0.5)
    x = (ancho - ancho_guia) // 2
    y = (alto - alto_guia) // 2
    return x, y, ancho_guia, alto_guia


def dibujar(cuadro, guia, ultima_lectura, valida, modo_continuo):
    vista = cuadro.copy()
    x, y, ancho, alto = guia
    color = VERDE if valida else AMARILLO

    cv2.rectangle(vista, (x, y), (x + ancho, y + alto), color, 2)

    if ultima_lectura:
        etiqueta = ultima_lectura if valida else f"{ultima_lectura} (formato invalido)"
    else:
        etiqueta = "Coloca la placa dentro del recuadro"

    (ancho_texto, alto_texto), _ = cv2.getTextSize(etiqueta, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
    px, py = x, y - 12
    cv2.rectangle(vista, (px - 4, py - alto_texto - 8), (px + ancho_texto + 8, py + 6), NEGRO, -1)
    cv2.putText(vista, etiqueta, (px + 2, py), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)

    ayuda = "continuo" if modo_continuo else "ESPACIO=leer  g=guardar  q=salir"
    cv2.putText(vista, ayuda, (10, vista.shape[0] - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, BLANCO, 1, cv2.LINE_AA)
    return vista


def main():
    parser = argparse.ArgumentParser(description="Lee placas en vivo con la cámara")
    parser.add_argument("--camara", type=int, default=0, help="Índice de la cámara (default: 0)")
    parser.add_argument("--continuo", action="store_true",
                        help="Lee continuamente en vez de esperar que aprietes ESPACIO")
    args = parser.parse_args()

    camara = abrir_camara(args.camara)
    ok, cuadro = camara.read()
    if not ok:
        camara.release()
        raise SystemExit("No se pudo leer de la cámara.")

    alto, ancho = cuadro.shape[:2]
    guia = recuadro_guia(ancho, alto)
    x, y, ancho_guia, alto_guia = guia

    ultima_lectura, valida = "", False
    cuadros = 0
    ventana = "Lector de placas  |  ESPACIO=leer  g=guardar  q=salir"

    print(__doc__)

    try:
        while True:
            ok, cuadro = camara.read()
            if not ok:
                break
            cuadros += 1
            recorte = cuadro[y:y + alto_guia, x:x + ancho_guia]

            # En modo continuo no se lee cada cuadro: el OCR es lento
            # (~100 ms) y leer 30 veces por segundo trabaría el video.
            if args.continuo and cuadros % 10 == 0:
                ultima_lectura = leer_placa(recorte)
                valida = formato_valido(ultima_lectura)
                if valida:
                    print(f"[{datetime.now():%H:%M:%S}] {ultima_lectura}")

            cv2.imshow(ventana, dibujar(cuadro, guia, ultima_lectura, valida, args.continuo))

            tecla = cv2.waitKey(1) & 0xFF
            if tecla in (ord("q"), 27):
                break
            if tecla == ord(" "):
                ultima_lectura = leer_placa(recorte)
                valida = formato_valido(ultima_lectura)
                estado = "válida" if valida else "NO calza con el formato guatemalteco"
                print(f"[{datetime.now():%H:%M:%S}] Lectura: {ultima_lectura or '(vacío)'} — {estado}")
            elif tecla == ord("g"):
                CARPETA_IMAGENES.mkdir(exist_ok=True)
                nombre = f"captura_{datetime.now():%Y%m%d_%H%M%S}.png"
                cv2.imwrite(str(CARPETA_IMAGENES / nombre), recorte)
                print(f"Recorte guardado en test_images/{nombre}")
    finally:
        camara.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
