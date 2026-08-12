"""
Prueba de concepto de OCR: corre el pipeline de lectura de placas sobre
las imágenes de test_images/ y compara contra la placa esperada.

Muestra el resultado con y sin la corrección por formato, para poder medir
cuánto aporta ese paso.

Uso:
    python scripts/test_ocr.py
"""

from pathlib import Path

from vision import formato_valido, leer_placa_de_archivo

CARPETA_IMAGENES = Path(__file__).resolve().parent.parent / "test_images"

# Para las placas generadas por generar_placas_prueba.py, el nombre del
# archivo ES la placa esperada. La foto de referencia real no sigue esa
# convención (tiene un nombre descriptivo), así que se mapea a mano acá.
PLACA_ESPERADA_POR_ARCHIVO = {
    "Placa_vehicular_de_Guatemala.png": "P123ABC",
}


def main():
    imagenes = sorted(CARPETA_IMAGENES.glob("*.png"))
    if not imagenes:
        print(f"No hay imágenes en {CARPETA_IMAGENES}. Correr primero generar_placas_prueba.py")
        return

    aciertos_crudo = 0
    aciertos_corregido = 0

    print(f"{'ARCHIVO':<38} {'ESPERADO':<10} {'OCR CRUDO':<10} {'CORREGIDO':<10} RESULTADO")
    print("-" * 88)

    for ruta in imagenes:
        esperado = PLACA_ESPERADA_POR_ARCHIVO.get(ruta.name, ruta.stem.upper())
        crudo = leer_placa_de_archivo(ruta, corregir=False)
        corregido = leer_placa_de_archivo(ruta, corregir=True)

        aciertos_crudo += crudo == esperado
        ok = corregido == esperado
        aciertos_corregido += ok

        print(f"{ruta.name:<38} {esperado:<10} {crudo:<10} {corregido:<10} {'OK' if ok else 'FALLO'}")

    total = len(imagenes)
    print("-" * 88)
    print(f"Sin corrección por formato: {aciertos_crudo}/{total}")
    print(f"Con corrección por formato: {aciertos_corregido}/{total}")

    invalidas = [
        ruta.name for ruta in imagenes
        if not formato_valido(leer_placa_de_archivo(ruta))
    ]
    if invalidas:
        print(f"\nLecturas que no calzan con el formato guatemalteco: {', '.join(invalidas)}")


if __name__ == "__main__":
    main()
