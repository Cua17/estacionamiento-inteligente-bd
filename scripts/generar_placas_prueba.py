"""
Genera imágenes sintéticas de placas (fondo blanco, texto negro, borde negro,
proporciones similares a una placa real) para probar el pipeline de OCR
ANTES de tener la cámara y fotos reales.

Esto NO reemplaza las pruebas con fotos reales (que se harán en cuanto
llegue la cámara / haya placas impresas físicas), pero valida que la
lógica de lectura (preprocesamiento + Tesseract) funciona de punta a punta.

Uso:
    python scripts/generar_placas_prueba.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SALIDA = Path(__file__).resolve().parent.parent / "test_images"
FUENTE = Path(r"C:\Windows\Fonts\arialbd.ttf")

# Formato de placa de Guatemala: 1 letra (categoría, ej. P = particular,
# C = comercial, M = motocicleta) + 3 dígitos + 3 letras.
PLACAS_PRUEBA = ["P456DEF", "C789GHJ", "M234KLM"]

ANCHO, ALTO = 600, 300  # proporción similar a una placa real (2:1)


MARGEN = 40  # espacio mínimo entre el texto y el borde de la placa


def generar_placa(texto: str, ruta_salida: Path):
    img = Image.new("RGB", (ANCHO, ALTO), color="white")
    draw = ImageDraw.Draw(img)

    # Nota: NO se dibuja un marco/borde alrededor del texto. Se probó con
    # borde (como el marco de una placa real) y Tesseract lo confundía con
    # parte del texto (agregaba caracteres fantasma). En el pipeline real,
    # el paso de "aislar la región de la placa" (Fase 4) ya se encarga de
    # recortar solo el texto antes de pasarlo a OCR -- estas imágenes
    # sintéticas simulan justamente esa región ya recortada.

    # El tamaño de letra se ajusta al texto para que SIEMPRE quede dentro del
    # lienzo (con 7 caracteres, un tamaño fijo se puede salir del borde y
    # Tesseract lee mal las letras cortadas -- no es un problema de OCR,
    # es un problema de que la imagen generada estaba mal recortada).
    tamano = 160
    while tamano > 10:
        fuente = ImageFont.truetype(str(FUENTE), size=tamano)
        bbox = draw.textbbox((0, 0), texto, font=fuente)
        ancho_texto = bbox[2] - bbox[0]
        alto_texto = bbox[3] - bbox[1]
        if ancho_texto <= ANCHO - MARGEN and alto_texto <= ALTO - MARGEN:
            break
        tamano -= 5

    x = (ANCHO - ancho_texto) / 2 - bbox[0]
    y = (ALTO - alto_texto) / 2 - bbox[1]

    draw.text((x, y), texto, font=fuente, fill="black")
    img.save(ruta_salida)
    print(f"Generada: {ruta_salida.name} (tamaño de letra: {tamano})")


def main():
    SALIDA.mkdir(exist_ok=True)
    for placa in PLACAS_PRUEBA:
        nombre_archivo = placa.replace(" ", "") + ".png"
        generar_placa(placa, SALIDA / nombre_archivo)


if __name__ == "__main__":
    main()
