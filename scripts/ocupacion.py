"""
Detección de ocupación de espacios por visión por computadora.

Idea: la cámara está fija y cada espacio de parqueo es una región
rectangular fija dentro del cuadro. Para decidir si un espacio está
ocupado se mide cuánta "textura" (bordes, detalle) hay dentro de esa
región:

  - Un espacio vacío es una superficie plana y uniforme (asfalto, piso,
    cartulina) -> casi no genera bordes.
  - Un espacio con un vehículo tiene llantas, ventanas, sombras, reflejos
    -> genera muchos bordes.

Se usa umbral adaptativo (no un umbral fijo) porque el brillo cambia entre
el día y la noche, y entre una zona con sombra y otra soleada del mismo
parqueo. El adaptativo compara cada píxel con sus vecinos, no con un valor
global, así que aguanta mucho mejor esos cambios de iluminación.

Este módulo no usa la cámara ni la base de datos: recibe un cuadro y
devuelve un veredicto. Eso lo hace probable sin hardware.
"""

import json
from pathlib import Path

import cv2
import numpy as np

ARCHIVO_CONFIG = Path(__file__).resolve().parent.parent / "config_espacios.json"

# Porcentaje de píxeles "con detalle" a partir del cual se considera que
# hay un vehículo. Se calibra con calibrar_umbral() y se guarda en el JSON.
UMBRAL_OCUPADO_POR_DEFECTO = 0.18


def preparar(cuadro):
    """
    Deja el cuadro listo para medir textura: gris -> desenfoque -> umbral
    adaptativo -> dilatación.

    El desenfoque quita el ruido del sensor (que si no se contaría como
    detalle) y la dilatación engorda los bordes detectados para que un
    vehículo dé una señal clara y no un puñado de píxeles sueltos.
    """
    gris = cv2.cvtColor(cuadro, cv2.COLOR_BGR2GRAY)
    suave = cv2.GaussianBlur(gris, (3, 3), 1)
    binaria = cv2.adaptiveThreshold(
        suave, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        blockSize=25, C=16,
    )
    sin_ruido = cv2.medianBlur(binaria, 5)
    return cv2.dilate(sin_ruido, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)), iterations=1)


def densidad_de_region(procesado, region):
    """
    Proporción de píxeles con detalle dentro de la región (0.0 a 1.0).

    region es (x, y, ancho, alto) en píxeles del cuadro.
    """
    x, y, ancho, alto = region
    recorte = procesado[y:y + alto, x:x + ancho]
    if recorte.size == 0:
        return 0.0
    return float(cv2.countNonZero(recorte)) / recorte.size


def evaluar_espacios(cuadro, espacios):
    """
    Evalúa todos los espacios de una vez sobre el mismo cuadro.

    espacios: lista de dicts con 'etiqueta', 'region' y 'umbral'.
    Devuelve lista de dicts con etiqueta, ocupado (bool) y densidad.
    """
    procesado = preparar(cuadro)
    resultados = []
    for espacio in espacios:
        densidad = densidad_de_region(procesado, espacio["region"])
        umbral = espacio.get("umbral", UMBRAL_OCUPADO_POR_DEFECTO)
        resultados.append({
            "etiqueta": espacio["etiqueta"],
            "ocupado": densidad >= umbral,
            "densidad": round(densidad, 4),
            "umbral": umbral,
        })
    return resultados


UMBRAL_DIFERENCIA_COLOR_POR_DEFECTO = 25.0


def color_promedio(cuadro, region):
    """Color BGR promedio de una región (para detección por diferencia de color)."""
    x, y, ancho, alto = region
    recorte = cuadro[y:y + alto, x:x + ancho]
    if recorte.size == 0:
        return None
    return recorte.reshape(-1, recorte.shape[2]).mean(axis=0)


def capturar_referencias_de_color(cuadro, espacios):
    """
    Color promedio de cada zona en el cuadro dado -- se llama una sola vez
    al arrancar, con todos los espacios VACÍOS, para tener contra qué
    comparar después. Devuelve {etiqueta: color BGR promedio}.
    """
    return {
        espacio["etiqueta"]: color_promedio(cuadro, espacio["region"])
        for espacio in espacios
    }


def evaluar_espacios_por_color(cuadro, espacios, referencias,
                                umbral_diferencia=UMBRAL_DIFERENCIA_COLOR_POR_DEFECTO):
    """
    Detección alternativa a evaluar_espacios(): compara el color promedio de
    cada zona contra la referencia de cuando estaba vacía, en vez de contar
    bordes/detalle fino.

    Más simple y más robusta cuando el fondo es uniforme (una hoja blanca de
    prueba) y lo que la ocupa cambia el color de forma clara: no depende de
    que la cámara esté perfectamente enfocada ni de que el objeto tenga
    detalle a pequeña escala -- por eso sirve para probar rápido con
    objetos chicos o de foco fijo. Para el parqueo real (asfalto, luz
    variable, sombras) evaluar_espacios() sigue siendo la idea correcta;
    hay que calibrarla ahí con fotos reales.
    """
    resultados = []
    for espacio in espacios:
        etiqueta = espacio["etiqueta"]
        promedio = color_promedio(cuadro, espacio["region"])
        referencia = referencias.get(etiqueta)
        if promedio is None or referencia is None:
            diferencia = 0.0
        else:
            diferencia = float(np.linalg.norm(promedio - referencia))
        resultados.append({
            "etiqueta": etiqueta,
            "ocupado": diferencia >= umbral_diferencia,
            "densidad": round(diferencia, 2),
            "umbral": umbral_diferencia,
        })
    return resultados


class EstadoEstable:
    """
    Filtro anti-parpadeo.

    La detección cuadro a cuadro tiembla: una sombra, una persona pasando
    o el ruido de la cámara pueden cambiar el veredicto por un instante.
    Sin filtrar, eso abriría y cerraría sesiones falsas en la base de datos
    muchas veces por segundo.

    Esta clase solo confirma un cambio de estado cuando se repite durante
    N lecturas seguidas.
    """

    def __init__(self, lecturas_para_confirmar=8, estado_inicial=None):
        """
        estado_inicial: dict etiqueta -> bool con lo que dice la base de
        datos al arrancar. Es importante inicializar desde ahí y NO desde
        la primera lectura de la cámara: si al encender el sistema ya hay
        un carro estacionado, tomar esa lectura como "estado inicial"
        haría que ese carro nunca se registre. Partiendo del estado de la
        base, la cámara confirma un cambio y la sincroniza.
        """
        self.lecturas_para_confirmar = lecturas_para_confirmar
        self._confirmado = dict(estado_inicial or {})  # etiqueta -> bool ocupado confirmado
        self._candidato = {}    # etiqueta -> (bool propuesto, cuántas veces seguidas)

    def actualizar(self, etiqueta, ocupado_ahora):
        """
        Registra una lectura. Devuelve el nuevo estado si acaba de
        confirmarse un cambio, o None si no hay cambio confirmado.
        """
        if etiqueta not in self._confirmado:
            # Espacio que no venía en el estado inicial: se toma esta lectura.
            self._confirmado[etiqueta] = ocupado_ahora
            self._candidato[etiqueta] = (ocupado_ahora, 0)
            return None

        if ocupado_ahora == self._confirmado[etiqueta]:
            self._candidato[etiqueta] = (ocupado_ahora, 0)
            return None

        propuesto, veces = self._candidato[etiqueta]
        veces = veces + 1 if propuesto == ocupado_ahora else 1
        self._candidato[etiqueta] = (ocupado_ahora, veces)

        if veces >= self.lecturas_para_confirmar:
            self._confirmado[etiqueta] = ocupado_ahora
            self._candidato[etiqueta] = (ocupado_ahora, 0)
            return ocupado_ahora
        return None

    def estado(self, etiqueta):
        return self._confirmado.get(etiqueta)


# ─────────────────────────────────────────────────────────────────────
# Configuración de las regiones (se crea con configurar_espacios.py)
# ─────────────────────────────────────────────────────────────────────

def cargar_config(ruta=ARCHIVO_CONFIG):
    """Carga las regiones definidas. Lanza FileNotFoundError si no existen."""
    ruta = Path(ruta)
    if not ruta.exists():
        raise FileNotFoundError(
            f"No existe {ruta.name}. Corré primero:\n"
            "    python scripts/configurar_espacios.py"
        )
    with open(ruta, encoding="utf-8") as archivo:
        return json.load(archivo)


def guardar_config(espacios, ruta=ARCHIVO_CONFIG):
    with open(ruta, "w", encoding="utf-8") as archivo:
        json.dump(espacios, archivo, indent=2, ensure_ascii=False)
