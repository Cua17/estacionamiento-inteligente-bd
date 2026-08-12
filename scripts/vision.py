"""
Lectura de placas: preprocesamiento de imagen + OCR + corrección por formato.

Funciona igual con una imagen guardada en disco o con un cuadro capturado
en vivo por la cámara, así que el mismo código sirve para la demo sin
cámara, para la webcam de la laptop y para la cámara de la Raspberry Pi.
"""

import platform
import re

import cv2
import pytesseract

# En Windows Tesseract no queda en el PATH; en Linux/Raspberry Pi sí.
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

CONFIG_TESSERACT = "--psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

# Formato de placa particular de Guatemala: 1 letra + 3 dígitos + 3 letras.
LARGO_PLACA = 7
POSICIONES_LETRA = (0, 4, 5, 6)
POSICIONES_DIGITO = (1, 2, 3)

# Confusiones clásicas de OCR: caracteres que se ven casi iguales.
# Se usan para corregir según lo que DEBERÍA ir en cada posición.
DIGITO_A_LETRA = {"0": "O", "1": "I", "5": "S", "8": "B", "4": "A", "2": "Z", "6": "G"}
LETRA_A_DIGITO = {v: k for k, v in DIGITO_A_LETRA.items()}


def preprocesar(imagen):
    """Escala de grises + umbral binario. Recibe un cuadro BGR de OpenCV."""
    gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    _, binaria = cv2.threshold(gris, 150, 255, cv2.THRESH_BINARY)
    return binaria


def corregir_por_formato(texto):
    """
    Corrige confusiones de OCR usando el formato conocido de la placa.

    Si el OCR devuelve 'PAS6DEF', sabemos que las posiciones 1-3 tienen que
    ser dígitos, así que 'A'->'4' y 'S'->'5', dando 'P456DEF'. Esto es lo
    que en NOTAS_OCR.md estaba anotado como mitigación pendiente.

    Si el texto no tiene el largo esperado, se devuelve tal cual (mejor
    devolver algo imperfecto que inventar una placa).
    """
    if len(texto) != LARGO_PLACA:
        return texto

    caracteres = list(texto)
    for i in POSICIONES_LETRA:
        if caracteres[i].isdigit():
            caracteres[i] = DIGITO_A_LETRA.get(caracteres[i], caracteres[i])
    for i in POSICIONES_DIGITO:
        if caracteres[i].isalpha():
            caracteres[i] = LETRA_A_DIGITO.get(caracteres[i], caracteres[i])
    return "".join(caracteres)


def leer_placa(imagen, corregir=True):
    """Lee la placa de un cuadro BGR de OpenCV. Devuelve el texto normalizado."""
    texto = pytesseract.image_to_string(preprocesar(imagen), config=CONFIG_TESSERACT)
    limpio = re.sub(r"[^A-Z0-9]", "", texto.upper())
    return corregir_por_formato(limpio) if corregir else limpio


def leer_placa_de_archivo(ruta, corregir=True):
    """Lee la placa de una imagen guardada en disco."""
    imagen = cv2.imread(str(ruta))
    if imagen is None:
        raise FileNotFoundError(f"No se pudo abrir la imagen: {ruta}")
    return leer_placa(imagen, corregir=corregir)


def formato_valido(placa):
    """True si la placa calza con el formato guatemalteco (1 letra + 3 dígitos + 3 letras)."""
    return bool(re.fullmatch(r"[A-Z]\d{3}[A-Z]{3}", placa))
