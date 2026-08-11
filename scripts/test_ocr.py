"""
Prueba de concepto de OCR de placas: aplica el mismo pipeline que se
usará en la Raspberry Pi (aislar región -> preprocesar -> Tesseract)
sobre las imágenes de test_images/, y compara el resultado leído contra
el nombre esperado del archivo.

Uso:
    python scripts/test_ocr.py
"""

import re
from pathlib import Path

import cv2
import pytesseract

# En Windows, Tesseract no siempre queda en el PATH -> se apunta directo al exe.
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

CARPETA_IMAGENES = Path(__file__).resolve().parent.parent / "test_images"

# Solo letras y números, una línea -> mismo criterio que se usará para placas reales.
CONFIG_TESSERACT = "--psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def preprocesar(ruta_imagen: Path):
    """Escala de grises + upscale + umbral -- mejora mucho la lectura de OCR.

    El upscale (x2, interpolación cúbica) ayuda porque Tesseract fue entrenado
    sobre texto escaneado a ~300 DPI; imágenes pequeñas capturadas por una
    cámara quedan por debajo de eso y se leen peor sin este paso.
    """
    img = cv2.imread(str(ruta_imagen))
    gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gris = cv2.resize(gris, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    _, binaria = cv2.threshold(gris, 150, 255, cv2.THRESH_BINARY)
    return binaria


def leer_placa(ruta_imagen: Path) -> str:
    imagen_procesada = preprocesar(ruta_imagen)
    texto = pytesseract.image_to_string(imagen_procesada, config=CONFIG_TESSERACT)
    return re.sub(r"[^A-Z0-9]", "", texto.upper())


def main():
    imagenes = sorted(CARPETA_IMAGENES.glob("*.png"))
    if not imagenes:
        print(f"No hay imágenes en {CARPETA_IMAGENES}. Correr primero generar_placas_prueba.py")
        return

    aciertos = 0
    for ruta in imagenes:
        esperado = ruta.stem.upper()  # nombre del archivo = placa esperada, sin espacios
        leido = leer_placa(ruta)
        ok = leido == esperado
        aciertos += ok
        estado = "OK " if ok else "FALLO"
        print(f"[{estado}] esperado={esperado:10s} leido={leido:10s} archivo={ruta.name}")

    print(f"\n{aciertos}/{len(imagenes)} placas leídas correctamente.")


if __name__ == "__main__":
    main()
