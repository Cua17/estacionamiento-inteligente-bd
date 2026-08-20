"""
Genera escenas de prueba que imitan la demo real: una placa de papel
sostenida sobre la hoja del parqueo (con los rótulos A1..A4), en varios
ángulos y tamaños.

Existe porque las imágenes de test_images/ son recortes limpios de la
placa sola -- no se parecen a lo que ve la cámara en la demo, donde la
placa es una parte chica de un cuadro dominado por una hoja blanca con
letras grandes escritas a mano. Medir contra recortes limpios daba 4/4 y
escondía que en vivo no leía nada.

Uso:
    python scripts/generar_escenas_prueba.py
"""

from pathlib import Path

import cv2
import numpy as np

CARPETA = Path(__file__).resolve().parent.parent / "test_scenes"

ANCHO_CUADRO, ALTO_CUADRO = 640, 480


def _placa_plana(texto, ancho=260, alto=130):
    """Una placa de papel: fondo blanco, texto negro grande, borde fino."""
    placa = np.full((alto, ancho, 3), 250, dtype=np.uint8)
    cv2.rectangle(placa, (3, 3), (ancho - 4, alto - 4), (40, 40, 40), 2)
    escala = 1.9
    grosor = 5
    (tw, th), _ = cv2.getTextSize(texto, cv2.FONT_HERSHEY_SIMPLEX, escala, grosor)
    while tw > ancho - 30 and escala > 0.4:
        escala -= 0.1
        (tw, th), _ = cv2.getTextSize(texto, cv2.FONT_HERSHEY_SIMPLEX, escala, grosor)
    cv2.putText(placa, texto, ((ancho - tw) // 2, (alto + th) // 2),
                cv2.FONT_HERSHEY_SIMPLEX, escala, (25, 25, 25), grosor, cv2.LINE_AA)
    return placa


def _hoja_de_parqueo():
    """El fondo de la demo: hoja blanca con A1..A4 dibujados en marcador."""
    fondo = np.full((ALTO_CUADRO, ANCHO_CUADRO, 3), 232, dtype=np.uint8)
    # mesa de madera abajo
    fondo[int(ALTO_CUADRO * 0.82):] = (120, 160, 195)
    for i in range(4):
        x = 40 + i * 145
        cv2.rectangle(fondo, (x, 60), (x + 110, 210), (45, 45, 45), 6)
        cv2.putText(fondo, f"A{i + 1}", (x + 20, 155),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.6, (35, 35, 35), 6, cv2.LINE_AA)
    return fondo


def _pegar_con_perspectiva(fondo, parche, esquinas_destino):
    """Pega `parche` dentro del cuadrilátero dado, deformándolo (simula ángulo)."""
    alto, ancho = parche.shape[:2]
    origen = np.float32([[0, 0], [ancho, 0], [ancho, alto], [0, alto]])
    destino = np.float32(esquinas_destino)
    matriz = cv2.getPerspectiveTransform(origen, destino)
    deformado = cv2.warpPerspective(parche, matriz, (fondo.shape[1], fondo.shape[0]))
    mascara = cv2.warpPerspective(
        np.full((alto, ancho), 255, dtype=np.uint8), matriz,
        (fondo.shape[1], fondo.shape[0]),
    )
    fondo[mascara > 0] = deformado[mascara > 0]
    return fondo


ESCENAS = {
    # nombre -> (placa esperada, esquinas donde se "sostiene" la placa)
    "P456DEF_frente": ("P456DEF", [[190, 250], [450, 250], [450, 380], [190, 380]]),
    "C789GHJ_angulo_leve": ("C789GHJ", [[180, 255], [455, 240], [460, 375], [185, 390]]),
    "M234KLM_angulo_fuerte": ("M234KLM", [[175, 270], [440, 225], [455, 355], [190, 400]]),
    "P123ABC_chica": ("P123ABC", [[250, 280], [400, 280], [400, 355], [250, 355]]),
    "P456DEF_inclinada": ("P456DEF", [[185, 235], [450, 285], [440, 405], [175, 355]]),
}


def main():
    CARPETA.mkdir(exist_ok=True)
    for nombre, (placa_texto, esquinas) in ESCENAS.items():
        escena = _pegar_con_perspectiva(
            _hoja_de_parqueo(), _placa_plana(placa_texto), esquinas
        )
        # Un poco de desenfoque y ruido: la cámara de la Pi es de foco fijo
        # y 640x480, nunca entrega una imagen perfectamente nítida.
        escena = cv2.GaussianBlur(escena, (3, 3), 0.8)
        ruido = np.random.default_rng(7).normal(0, 4, escena.shape)
        escena = np.clip(escena.astype(np.int16) + ruido, 0, 255).astype(np.uint8)

        ruta = CARPETA / f"{nombre}.png"
        cv2.imwrite(str(ruta), escena)
        print(f"{ruta.name:<32} placa esperada: {placa_texto}")

    print(f"\n{len(ESCENAS)} escenas en {CARPETA}")


if __name__ == "__main__":
    main()
