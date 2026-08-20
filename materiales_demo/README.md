# Materiales para la demo

- **`kit_impresion.pdf`** — el que se usa. Página 1: los 4 espacios de
  parqueo (A1-A4), fondo blanco, 6.2cm de ancho cada uno. Página 2: 6
  placas para recortar, del mismo ancho que un espacio (6.2cm) — se
  probó más chico primero y se agrandó a propósito porque a la
  resolución de la cámara (640x480) más grande lee mejor. Ya impreso y
  recortado (20 de agosto).
- **`generar_kit_impresion.py`** — el script que lo generó (`reportlab`).
  Correrlo de nuevo regenera `kit_impresion.pdf` si hace falta ajustar
  algo (cambiar las placas, el tamaño, etc.).
- **`parqueo_ipad_descartado.pdf`** — la primera versión, pensada para
  mostrar en un iPad (fondo oscuro tipo asfalto). Se probó y se descartó:
  la pantalla del iPad daba mucho reflejo/glare para la cámara de foco
  fijo de la Pi. Queda por si en algún momento se quiere retomar con
  mejor control de luz.
