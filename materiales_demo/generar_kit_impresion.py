# -*- coding: utf-8 -*-
"""
Kit para imprimir a escala de juguete: hoja 1 con los 4 parqueos, hoja 2
con varias placas CHICAS (proporcionadas a un carrito, no a un carro real)
para recortar y pegarle a cada uno.
"""

from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

RUTA_SALIDA = r"C:\Users\jdcua\AppData\Local\Temp\claude\C--Users-jdcua-OneDrive-Universidad-2026---Ciclo-2-Manejo-de-Base-de-Datos\39c20d57-3627-4756-8523-6b68d13ad0bd\scratchpad\kit_impresion.pdf"

ANCHO, ALTO = landscape(A4)  # 841.89 x 595.27 pt
NEGRO = (0.08, 0.08, 0.08)
BLANCO = (1, 1, 1)
MM = 72 / 25.4  # puntos por milímetro


def hoja_parqueos(c):
    """Los 4 espacios, lo más anchos posible en la hoja, fondo blanco."""
    c.setFillColorRGB(*BLANCO)
    c.rect(0, 0, ANCHO, ALTO, fill=1, stroke=0)

    margen_x = 15 * MM
    margen_y = 20 * MM
    gap = 6 * MM
    etiquetas = ["A1", "A2", "A3", "A4"]

    ancho_util = ANCHO - 2 * margen_x
    ancho_cajon = (ancho_util - (len(etiquetas) - 1) * gap) / len(etiquetas)
    alto_cajon = ALTO - 2 * margen_y
    y0 = margen_y

    c.setStrokeColorRGB(*NEGRO)
    c.setLineWidth(6)
    c.setLineJoin(1)

    for i, etiqueta in enumerate(etiquetas):
        x0 = margen_x + i * (ancho_cajon + gap)
        c.line(x0, y0, x0, y0 + alto_cajon)
        c.line(x0 + ancho_cajon, y0, x0 + ancho_cajon, y0 + alto_cajon)
        c.line(x0, y0, x0 + ancho_cajon, y0)

        c.setFillColorRGB(*NEGRO)
        c.setFont("Helvetica-Bold", 34)
        c.drawCentredString(x0 + ancho_cajon / 2, y0 + 24, etiqueta)

    print(f"Ancho de cada espacio dibujado: {ancho_cajon / MM:.1f} mm "
          f"({ancho_cajon / MM / 10:.1f} cm)")
    c.showPage()
    return ancho_cajon / MM  # en mm, para dimensionar las placas en proporción


def placa_en(c, x0, y0, texto, ancho_mm, alto_mm):
    ancho_pt, alto_pt = ancho_mm * MM, alto_mm * MM

    c.setFillColorRGB(*BLANCO)
    c.setStrokeColorRGB(*NEGRO)
    c.setLineWidth(2.5)
    c.rect(x0, y0, ancho_pt, alto_pt, fill=1, stroke=1)

    borde = 2.5 * MM
    c.setLineWidth(0.75)
    c.rect(x0 + borde, y0 + borde, ancho_pt - 2 * borde, alto_pt - 2 * borde,
           fill=0, stroke=1)

    ancho_texto_max = ancho_pt - 2 * borde - 4 * MM
    tamano_letra = alto_pt * 0.5
    c.setFillColorRGB(*NEGRO)
    while tamano_letra > 4 and c.stringWidth(texto, "Helvetica-Bold", tamano_letra) > ancho_texto_max:
        tamano_letra -= 0.5
    c.setFont("Helvetica-Bold", tamano_letra)
    c.drawCentredString(x0 + ancho_pt / 2, y0 + alto_pt * 0.30, texto)


def hoja_placas(c, textos, ancho_mm, alto_mm):
    """Varias placas chicas en grilla, para recortar. ancho_mm/alto_mm ya
    vienen calculados en proporción a los espacios de la hoja 1."""
    c.setFillColorRGB(*BLANCO)
    c.rect(0, 0, ANCHO, ALTO, fill=1, stroke=0)

    columnas, filas = 3, 2
    gap_x, gap_y = 14 * MM, 14 * MM
    ancho_bloque = columnas * ancho_mm * MM + (columnas - 1) * gap_x
    alto_bloque = filas * alto_mm * MM + (filas - 1) * gap_y
    x_inicio = (ANCHO - ancho_bloque) / 2
    y_inicio = (ALTO - alto_bloque) / 2

    for indice, texto in enumerate(textos[:columnas * filas]):
        col = indice % columnas
        fila = indice // columnas
        x0 = x_inicio + col * (ancho_mm * MM + gap_x)
        y0 = y_inicio + (filas - 1 - fila) * (alto_mm * MM + gap_y)
        placa_en(c, x0, y0, texto, ancho_mm, alto_mm)

    c.showPage()


def main():
    c = canvas.Canvas(RUTA_SALIDA, pagesize=(ANCHO, ALTO))

    ancho_espacio_mm = hoja_parqueos(c)

    # Mismo ancho que el espacio dibujado: a esta resolución de cámara
    # (640x480, todo el parqueo en un solo cuadro) más grande es mejor
    # para el OCR -- más píxeles de detalle en la placa.
    ancho_placa_mm = round(ancho_espacio_mm, 1)
    alto_placa_mm = round(ancho_placa_mm / 2, 1)  # proporción 2:1, como la real

    textos = ["P123ABC", "M456DEF", "C789GHJ", "P456DEF", "M234KLM", "C321XYZ"]
    hoja_placas(c, textos, ancho_placa_mm, alto_placa_mm)

    c.save()
    print(f"Generado: {RUTA_SALIDA}")
    print(f"Tamaño de cada placa: {ancho_placa_mm} x {alto_placa_mm} cm"
          if False else f"Tamaño de cada placa: {ancho_placa_mm/10:.1f} x {alto_placa_mm/10:.1f} cm")


if __name__ == "__main__":
    main()
