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


UMBRAL_TEXTURA_POR_DEFECTO = 0.030

# Cuánto se ACHICA la región antes de medirla, por lado.
#
# Se mide solo el corazón del espacio, no sus bordes. El recuadro impreso
# tiene líneas negras gruesas justo en el borde de la región, y una línea
# negra es lo que más cambia el promedio de color y la densidad de textura
# de toda la escena. Si la hoja se corre unos milímetros -- lo que pasa
# cada vez que alguien estira el brazo por encima de la mesa -- esa línea
# entra o sale de la región y el espacio se marca ocupado sin que haya
# ningún vehículo. Pasó de verdad: la foto guardada en el instante de la
# detección mostraba la hoja VACÍA, corrida ~15 px respecto de la
# referencia.
#
# Midiendo hacia adentro, el borde puede bailar sin que la medición se
# entere: dentro solo hay papel blanco. Un vehículo igual cae en el centro
# del espacio, así que no se pierde detección (medido: el carrito daba
# textura 0.09-0.11 contra un umbral de 0.03, sobra margen).
INSET_HORIZONTAL = 0.28
INSET_VERTICAL = 0.10


def region_de_medicion(region, inset_x=INSET_HORIZONTAL, inset_y=INSET_VERTICAL):
    """Encoge una región hacia su centro, para medir lejos de sus bordes."""
    x, y, ancho, alto = region
    dx, dy = int(ancho * inset_x), int(alto * inset_y)
    return (x + dx, y + dy, max(1, ancho - 2 * dx), max(1, alto - 2 * dy))


def densidad_de_textura(cuadro, region):
    """
    Densidad de bordes/detalle de una región, con el mismo preparado que
    evaluar_espacios().

    Filtra el cuadro entero y después recorta, no al revés. Se probó lo
    contrario (recortar primero para filtrar menos píxeles, buscando bajar
    la temperatura de la Pi) y medido resultó MÁS LENTO: 4.40 ms contra
    3.73 ms por vuelta. OpenCV procesa el cuadro completo en una sola
    pasada muy eficiente, y cuatro llamadas chicas cuestan más en
    sobrecarga por llamada de lo que ahorran en píxeles. El costo real de
    CPU de la demo no está acá (son ~4 ms) sino en Tesseract.
    """
    return densidad_de_region(preparar(cuadro), region)


def capturar_referencias_completas(cuadro, espacios):
    """
    Referencia de "vacío" con las DOS medidas: color promedio y densidad de
    textura. Se llama una sola vez al arrancar, con los espacios vacíos.
    """
    procesado = preparar(cuadro)
    referencias = {}
    for espacio in espacios:
        medida = region_de_medicion(espacio["region"])
        referencias[espacio["etiqueta"]] = {
            "color": color_promedio(cuadro, medida),
            "textura": densidad_de_region(procesado, medida),
        }
    return referencias


def evaluar_espacios_combinado(cuadro, espacios, referencias,
                               umbral_color=UMBRAL_DIFERENCIA_COLOR_POR_DEFECTO,
                               umbral_textura=UMBRAL_TEXTURA_POR_DEFECTO):
    """
    Ocupado = cambió el COLOR **y** cambió la TEXTURA respecto del vacío.

    Por qué hacen falta las dos y no alcanza con subir el umbral de color:
    medido en la Pi con el kit impreso, la sombra de una persona inclinándose
    sobre la mesa daba diferencias de color de 28 a 93, y un carrito de
    verdad daba 100-111. Los rangos SE SOLAPAN, así que ningún umbral sobre
    el color solo puede separarlos -- hay que mirar otra característica.

    La textura es esa característica. Una sombra oscurece la zona pero no
    dibuja nada: los bordes que había siguen estando y no aparecen nuevos,
    porque el umbral adaptativo de preparar() compara cada píxel con sus
    vecinos y por eso es (casi) inmune a un cambio parejo de iluminación. Un
    vehículo, en cambio, mete contorno, ruedas y el texto de la placa dentro
    de la región: la densidad de bordes se mueve mucho.

    Se mide el cambio ABSOLUTO de textura, no "más textura que un umbral":
    un vehículo puede tapar las líneas negras del recuadro impreso y hacer
    BAJAR la densidad. Lo que delata al vehículo es que la textura cambie,
    para cualquier lado; lo que delata a la sombra es que no cambie.
    """
    procesado = preparar(cuadro)
    resultados = []
    for espacio in espacios:
        etiqueta = espacio["etiqueta"]
        referencia = referencias.get(etiqueta) or {}
        medida = region_de_medicion(espacio["region"])

        promedio = color_promedio(cuadro, medida)
        referencia_color = referencia.get("color")
        if promedio is None or referencia_color is None:
            dif_color = 0.0
        else:
            dif_color = float(np.linalg.norm(promedio - referencia_color))

        textura = densidad_de_region(procesado, medida)
        referencia_textura = referencia.get("textura")
        dif_textura = 0.0 if referencia_textura is None else abs(textura - referencia_textura)

        resultados.append({
            "etiqueta": etiqueta,
            "ocupado": dif_color >= umbral_color and dif_textura >= umbral_textura,
            "densidad": round(dif_color, 2),
            "textura": round(dif_textura, 4),
            "umbral": umbral_color,
            "umbral_textura": umbral_textura,
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

        # Con valor por defecto y no acceso directo: _confirmado viene
        # sembrado desde la base de datos, pero _candidato arranca vacío.
        # Si la PRIMERA lectura de la cámara ya contradice a la base (por
        # ejemplo, la base tiene una sesión abierta de antes y el espacio
        # en realidad está libre), acá no había todavía ninguna entrada
        # para esa etiqueta y el monitor entero se caía con KeyError.
        propuesto, veces = self._candidato.get(etiqueta, (ocupado_ahora, 0))
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
