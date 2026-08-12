"""
Define dónde está cada espacio de parqueo dentro del cuadro de la cámara.

Abre la cámara, te deja dibujar un rectángulo por cada espacio arrastrando
el mouse, y guarda esas regiones en config_espacios.json. El detector
(ocupacion.py) después lee ese archivo para saber qué mirar.

Hay que volver a correr esto cada vez que se mueva la cámara: las regiones
son coordenadas fijas del cuadro, así que si la cámara cambia de ángulo,
dejan de coincidir con los espacios reales.

Uso:
    python scripts/configurar_espacios.py
    python scripts/configurar_espacios.py --camara 1     # otra cámara
    python scripts/configurar_espacios.py --rejilla 4    # sin mouse: 4 columnas iguales

Controles (modo mouse):
    arrastrar  : dibujar un espacio
    z          : deshacer el último
    r          : empezar de cero
    g          : guardar y salir
    ESC        : salir sin guardar
"""

import argparse
import sys

import cv2

from camara import abrir_camara
from ocupacion import ARCHIVO_CONFIG, UMBRAL_OCUPADO_POR_DEFECTO, evaluar_espacios, guardar_config

VERDE = (74, 222, 128)
ROJO = (113, 113, 248)
BLANCO = (255, 255, 255)
NEGRO = (0, 0, 0)


class Dibujante:
    """Maneja el arrastre del mouse para ir creando rectángulos."""

    def __init__(self):
        self.regiones = []
        self.origen = None
        self.actual = None

    def callback(self, evento, x, y, _flags, _param):
        if evento == cv2.EVENT_LBUTTONDOWN:
            self.origen = (x, y)
            self.actual = (x, y)
        elif evento == cv2.EVENT_MOUSEMOVE and self.origen is not None:
            self.actual = (x, y)
        elif evento == cv2.EVENT_LBUTTONUP and self.origen is not None:
            x0, y0 = self.origen
            ancho, alto = abs(x - x0), abs(y - y0)
            if ancho > 15 and alto > 15:  # ignora clicks accidentales
                self.regiones.append([min(x0, x), min(y0, y), ancho, alto])
            self.origen = None
            self.actual = None

    def rectangulo_en_progreso(self):
        if self.origen is None or self.actual is None:
            return None
        x0, y0 = self.origen
        x1, y1 = self.actual
        return (min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))


def etiqueta_para(indice):
    """0 -> A1, 1 -> A2, ... (mismas etiquetas que la tabla `espacios`)."""
    return f"A{indice + 1}"


def texto_con_fondo(imagen, texto, posicion, color=BLANCO):
    """Dibuja texto con un fondo oscuro para que se lea sobre cualquier imagen."""
    x, y = posicion
    (ancho, alto), _ = cv2.getTextSize(texto, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    cv2.rectangle(imagen, (x - 3, y - alto - 5), (x + ancho + 3, y + 4), NEGRO, -1)
    cv2.putText(imagen, texto, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)


def rejilla_automatica(ancho_cuadro, alto_cuadro, columnas):
    """Genera N espacios iguales en fila, sin necesidad de dibujar con el mouse."""
    margen = 20
    ancho_util = ancho_cuadro - margen * 2
    ancho_espacio = ancho_util // columnas
    alto_espacio = int(alto_cuadro * 0.6)
    y = (alto_cuadro - alto_espacio) // 2
    return [
        [margen + i * ancho_espacio + 4, y, ancho_espacio - 8, alto_espacio]
        for i in range(columnas)
    ]


def a_config(regiones):
    return [
        {"etiqueta": etiqueta_para(i), "region": region, "umbral": UMBRAL_OCUPADO_POR_DEFECTO}
        for i, region in enumerate(regiones)
    ]


def main():
    parser = argparse.ArgumentParser(description="Define las regiones de los espacios de parqueo")
    parser.add_argument("--camara", type=int, default=0, help="Índice de la cámara (default: 0)")
    parser.add_argument("--rejilla", type=int, default=None,
                        help="Crea N espacios iguales automáticamente, sin dibujar con el mouse")
    args = parser.parse_args()

    camara = abrir_camara(args.camara)
    ok, cuadro = camara.read()
    if not ok:
        camara.release()
        sys.exit("No se pudo leer de la cámara.")

    alto, ancho = cuadro.shape[:2]

    if args.rejilla:
        regiones = rejilla_automatica(ancho, alto, args.rejilla)
        guardar_config(a_config(regiones))
        camara.release()
        print(f"Guardados {len(regiones)} espacios en rejilla automática -> {ARCHIVO_CONFIG.name}")
        print("Ajustá la posición de la cámara para que los espacios reales queden dentro de los recuadros.")
        return

    dibujante = Dibujante()
    ventana = "Configurar espacios  |  arrastrar=nuevo  z=deshacer  r=reiniciar  g=guardar  ESC=salir"
    cv2.namedWindow(ventana)
    cv2.setMouseCallback(ventana, dibujante.callback)

    print(__doc__)

    while True:
        ok, cuadro = camara.read()
        if not ok:
            break

        vista = cuadro.copy()

        # Muestra en vivo cómo se vería la detección con lo dibujado hasta ahora,
        # para poder calibrar el encuadre sin salir de la herramienta.
        if dibujante.regiones:
            for resultado, region in zip(
                evaluar_espacios(cuadro, a_config(dibujante.regiones)), dibujante.regiones
            ):
                x, y, w, h = region
                color = ROJO if resultado["ocupado"] else VERDE
                cv2.rectangle(vista, (x, y), (x + w, y + h), color, 2)
                texto_con_fondo(
                    vista,
                    f"{resultado['etiqueta']} {resultado['densidad']:.2f}",
                    (x + 4, y + 18), color,
                )

        en_progreso = dibujante.rectangulo_en_progreso()
        if en_progreso:
            x, y, w, h = en_progreso
            cv2.rectangle(vista, (x, y), (x + w, y + h), BLANCO, 1)

        texto_con_fondo(vista, f"Espacios definidos: {len(dibujante.regiones)}", (10, alto - 12))
        cv2.imshow(ventana, vista)

        tecla = cv2.waitKey(1) & 0xFF
        if tecla == 27:  # ESC
            print("Salida sin guardar.")
            break
        if tecla == ord("z") and dibujante.regiones:
            dibujante.regiones.pop()
        elif tecla == ord("r"):
            dibujante.regiones.clear()
        elif tecla == ord("g"):
            if not dibujante.regiones:
                print("No hay espacios definidos todavía.")
                continue
            guardar_config(a_config(dibujante.regiones))
            print(f"Guardados {len(dibujante.regiones)} espacios en {ARCHIVO_CONFIG.name}")
            break

    camara.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
