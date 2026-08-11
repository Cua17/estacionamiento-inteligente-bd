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

# Formato de placa de Costa Rica para vehículos particulares: 3 letras + 3 números
PLACAS_PRUEBA = ["BGZ 123", "CPL 482", "SJO 907", "HKM 356"]

ANCHO, ALTO = 600, 300  # proporción similar a una placa real (2:1)


def generar_placa(texto: str, ruta_salida: Path):
    img = Image.new("RGB", (ANCHO, ALTO), color="white")
    draw = ImageDraw.Draw(img)

    # Borde negro grueso, como el marco de una placa real
    draw.rectangle([10, 10, ANCHO - 10, ALTO - 10], outline="black", width=8)

    fuente = ImageFont.truetype(str(FUENTE), size=140)
    bbox = draw.textbbox((0, 0), texto, font=fuente)
    ancho_texto = bbox[2] - bbox[0]
    alto_texto = bbox[3] - bbox[1]
    x = (ANCHO - ancho_texto) / 2 - bbox[0]
    y = (ALTO - alto_texto) / 2 - bbox[1]

    draw.text((x, y), texto, font=fuente, fill="black")
    img.save(ruta_salida)
    print(f"Generada: {ruta_salida.name}")


def main():
    SALIDA.mkdir(exist_ok=True)
    for placa in PLACAS_PRUEBA:
        nombre_archivo = placa.replace(" ", "") + ".png"
        generar_placa(placa, SALIDA / nombre_archivo)


if __name__ == "__main__":
    main()
