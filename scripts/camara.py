"""
Acceso a la cámara, aislado del resto del código.

Existe para que el mismo programa corra sin cambios en la laptop (webcam
por DirectShow en Windows) y en la Raspberry Pi (V4L2 en Linux). Todo lo
demás del proyecto solo pide "un cuadro" y no le importa de dónde salió.
"""

import platform

import cv2


def abrir_camara(indice=0, ancho=640, alto=480):
    """
    Abre la cámara y devuelve el objeto VideoCapture ya configurado.

    En Windows se fuerza el backend DirectShow: con el backend por defecto,
    OpenCV puede tardar varios segundos en abrir la webcam o devolver
    cuadros negros al principio.
    """
    backend = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_ANY
    camara = cv2.VideoCapture(indice, backend)
    camara.set(cv2.CAP_PROP_FRAME_WIDTH, ancho)
    camara.set(cv2.CAP_PROP_FRAME_HEIGHT, alto)

    if not camara.isOpened():
        raise RuntimeError(
            f"No se pudo abrir la cámara {indice}. "
            "Verificá que no esté siendo usada por otro programa "
            "(Zoom, Teams, Meet) y que Windows le dé permiso de cámara."
        )

    # Los primeros cuadros de una webcam suelen venir oscuros o vacíos
    # mientras el sensor ajusta exposición: se descartan.
    for _ in range(5):
        camara.read()

    return camara


def leer_cuadro(camara):
    """Lee un cuadro. Lanza RuntimeError si la cámara dejó de responder."""
    ok, cuadro = camara.read()
    if not ok:
        raise RuntimeError("La cámara dejó de entregar imagen.")
    return cuadro
