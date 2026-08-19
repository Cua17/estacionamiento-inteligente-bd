"""
Acceso a la cámara, aislado del resto del código.

Existe para que el mismo programa corra sin cambios en la laptop (webcam
por DirectShow en Windows) y en la Raspberry Pi (V4L2 en Linux). Todo lo
demás del proyecto solo pide "un cuadro" y no le importa de dónde salió.
"""

import platform

import cv2


class _CamaraPi:
    """
    Envoltorio de picamera2 con la misma interfaz que cv2.VideoCapture
    (read() -> (bool, cuadro BGR), release()), para que monitor.py no
    tenga que saber qué cámara está usando.

    picamera2 se importa acá adentro (no al inicio del archivo) porque
    solo existe como paquete del sistema en Linux/Raspberry Pi — si este
    archivo se importa en Windows, ese import nunca se ejecuta.
    """

    def __init__(self, ancho=640, alto=480):
        from picamera2 import Picamera2
        self._picam2 = Picamera2()
        config = self._picam2.create_video_configuration(
            main={"size": (ancho, alto), "format": "BGR888"}
        )
        self._picam2.configure(config)
        self._picam2.start()
        # Igual que con la webcam: los primeros cuadros vienen con la
        # exposición todavía ajustándose.
        for _ in range(5):
            self._picam2.capture_array()

    def read(self):
        return True, self._picam2.capture_array()

    def release(self):
        self._picam2.stop()
        self._picam2.close()

    def isOpened(self):
        return True


def hay_camara_pi():
    """
    True si hay una cámara CSI detectada por libcamera (típico en la Pi).

    Se usa para elegir automáticamente el camino de captura correcto sin
    que haga falta pasar un flag a mano.
    """
    if platform.system() != "Linux":
        return False
    try:
        from picamera2 import Picamera2
        return len(Picamera2.global_camera_info()) > 0
    except Exception:
        return False


def abrir_camara(indice=0, ancho=640, alto=480, usar_pi_camera=False):
    """
    Abre la cámara y devuelve un objeto con .read()/.release()/.isOpened()
    ya configurado.

    usar_pi_camera=True usa la cámara CSI de la Raspberry Pi (picamera2)
    en vez de una webcam genérica. En Windows se fuerza el backend
    DirectShow: con el backend por defecto, OpenCV puede tardar varios
    segundos en abrir la webcam o devolver cuadros negros al principio.
    """
    if usar_pi_camera:
        return _CamaraPi(ancho, alto)

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
