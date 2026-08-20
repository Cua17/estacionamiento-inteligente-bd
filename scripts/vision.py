"""
Lectura de placas: preprocesamiento de imagen + OCR + corrección por formato.

Funciona igual con una imagen guardada en disco o con un cuadro capturado
en vivo por la cámara, así que el mismo código sirve para la demo sin
cámara, para la webcam de la laptop y para la cámara de la Raspberry Pi.

Sobre la robustez: leer una placa de una foto limpia es fácil; leerla de una
cámara en vivo NO lo es. La placa puede estar chica en el cuadro, torcida,
con sombra, o (caso muy común en demos) mostrada en la pantalla de un
celular, que va retroiluminada y con reflejos. Un solo umbral fijo falla en
casi todos esos casos, así que acá se prueban VARIAS versiones de la misma
imagen y varios modos de Tesseract, y se elige la primera lectura que calce
con el formato de placa guatemalteco.
"""

import platform
import re
from collections import Counter

import cv2
import numpy as np
import pytesseract

# En Windows Tesseract no queda en el PATH; en Linux/Raspberry Pi sí.
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

LISTA_BLANCA = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

# 7 = una sola línea de texto, 8 = una sola palabra, 13 = línea cruda sin
# segmentar. Distintos modos ganan según cuánto fondo rodee a la placa.
MODOS_PSM = (7, 8, 13)

# Tesseract fue entrenado con texto a ~300 DPI. Una placa que ocupa poco
# del cuadro queda muy por debajo de eso, y ahí es donde más falla. Se
# agranda cualquier recorte que no llegue a este ancho.
ANCHO_MINIMO_PARA_OCR = 700

# Formato de placa particular de Guatemala: 1 letra + 3 dígitos + 3 letras.
LARGO_PLACA = 7
POSICIONES_LETRA = (0, 4, 5, 6)
POSICIONES_DIGITO = (1, 2, 3)
PATRON_PLACA = re.compile(r"[A-Z]\d{3}[A-Z]{3}")

# Confusiones clásicas de OCR: caracteres que se ven casi iguales.
# Se usan para corregir según lo que DEBERÍA ir en cada posición.
DIGITO_A_LETRA = {"0": "O", "1": "I", "5": "S", "8": "B", "4": "A", "2": "Z", "6": "G"}
LETRA_A_DIGITO = {v: k for k, v in DIGITO_A_LETRA.items()}


# ─────────────────────────────────────────────────────────────────────
# Preprocesamiento
# ─────────────────────────────────────────────────────────────────────

def _a_gris(imagen):
    if imagen.ndim == 2:
        return imagen
    return cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)


def _agrandar(gris, ancho_minimo=ANCHO_MINIMO_PARA_OCR):
    """Escala la imagen hasta un ancho mínimo, para darle píxeles al OCR."""
    alto, ancho = gris.shape[:2]
    if ancho >= ancho_minimo:
        return gris
    factor = ancho_minimo / max(ancho, 1)
    return cv2.resize(gris, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC)


# Una placa es claramente apaisada (la de Guatemala ronda 2:1). Filtrar por
# esto es lo que separa la placa de los recuadros del parqueo dibujados en la
# hoja de prueba, que son más altos que anchos.
ASPECTO_MINIMO_PLACA = 1.6
ASPECTO_MAXIMO_PLACA = 6.0

# Cuántas regiones candidatas se le pasan al OCR, de la más grande a la más
# chica. Más candidatos = más chance de acertar, pero cada uno cuesta varias
# llamadas a Tesseract.
MAX_CANDIDATOS = 3


def _ordenar_esquinas(puntos):
    """Ordena 4 puntos como arriba-izq, arriba-der, abajo-der, abajo-izq."""
    puntos = np.array(puntos, dtype="float32").reshape(4, 2)
    suma = puntos.sum(axis=1)
    resta = puntos[:, 0] - puntos[:, 1]
    return np.array([
        puntos[np.argmin(suma)],    # arriba-izquierda: menor x+y
        puntos[np.argmax(resta)],   # arriba-derecha:   mayor x-y
        puntos[np.argmax(suma)],    # abajo-derecha
        puntos[np.argmin(resta)],   # abajo-izquierda
    ], dtype="float32")


def enderezar(imagen, esquinas):
    """
    Corrige la perspectiva de un cuadrilátero y lo devuelve visto de frente.

    Esto es lo que permite leer una placa que NO está perpendicular a la
    cámara: Tesseract fue entrenado con texto derecho, y una placa
    fotografiada en ángulo le llega con las letras estiradas de un lado y
    comprimidas del otro. Deshacer esa deformación antes del OCR es la
    diferencia entre leerla y no leerla.
    """
    orden = _ordenar_esquinas(esquinas)
    arriba_izq, arriba_der, abajo_der, abajo_izq = orden
    ancho = int(round(max(np.linalg.norm(arriba_der - arriba_izq),
                          np.linalg.norm(abajo_der - abajo_izq))))
    alto = int(round(max(np.linalg.norm(abajo_izq - arriba_izq),
                         np.linalg.norm(abajo_der - arriba_der))))
    if ancho < 40 or alto < 15:
        return None

    destino = np.array([[0, 0], [ancho - 1, 0], [ancho - 1, alto - 1], [0, alto - 1]],
                       dtype="float32")
    matriz = cv2.getPerspectiveTransform(orden, destino)
    return cv2.warpPerspective(imagen, matriz, (ancho, alto))


def localizar_candidatos_placa(imagen, maximo=MAX_CANDIDATOS):
    """
    Busca regiones con forma de placa y las devuelve ya enderezadas.

    Antes el pipeline recortaba "la zona más brillante" del cuadro, y en la
    práctica eso agarraba la hoja blanca entera del parqueo de prueba (con
    los rótulos A1..A4 escritos a mano), no la placa: el OCR terminaba
    leyendo "AA2" en vez de la patente. Buscar cuadriláteros con relación
    de aspecto de placa resuelve justamente eso, y de paso da las cuatro
    esquinas necesarias para corregir la perspectiva.
    """
    gris = _a_gris(imagen)
    suave = cv2.bilateralFilter(gris, 7, 50, 50)
    bordes = cv2.Canny(suave, 40, 140)
    # Cerrar cortes en el contorno: un borde interrumpido no forma un
    # cuadrilátero cerrado y se perdería el candidato.
    bordes = cv2.dilate(bordes, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))

    contornos, _ = cv2.findContours(bordes, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    alto_img, ancho_img = gris.shape[:2]
    area_total = alto_img * ancho_img

    candidatos = []
    for contorno in contornos:
        area = cv2.contourArea(contorno)
        # Ni una mancha diminuta ni casi todo el cuadro (eso sería la hoja).
        if area < area_total * 0.008 or area > area_total * 0.6:
            continue

        perimetro = cv2.arcLength(contorno, True)
        aprox = cv2.approxPolyDP(contorno, 0.03 * perimetro, True)
        if len(aprox) != 4 or not cv2.isContourConvex(aprox):
            continue

        # El rectángulo rotado da el aspecto REAL de la placa aunque esté
        # inclinada; el bounding box normal la haría parecer más cuadrada.
        (_, (ancho_r, alto_r), _) = cv2.minAreaRect(aprox)
        if ancho_r < 1 or alto_r < 1:
            continue
        aspecto = max(ancho_r, alto_r) / min(ancho_r, alto_r)
        if not ASPECTO_MINIMO_PLACA <= aspecto <= ASPECTO_MAXIMO_PLACA:
            continue

        candidatos.append((area, aprox))

    candidatos.sort(key=lambda par: -par[0])
    recortes = []
    for _, aprox in candidatos[:maximo]:
        recorte = enderezar(imagen, aprox)
        if recorte is not None and recorte.size > 0:
            recortes.append(recorte)
    return recortes


def recortar_zona_brillante(imagen, margen=0.06):
    """
    Busca la región más brillante y rectangular del cuadro y la recorta.

    Sirve para el caso de mostrar la placa en la pantalla de un celular: la
    pantalla es mucho más brillante que todo lo demás, así que aislarla
    quita de un golpe el fondo del salón, las manos y la mesa, que es lo
    que más confunde al OCR. Si no encuentra nada claro, devuelve None y el
    resto del pipeline sigue con la imagen completa.
    """
    gris = _a_gris(imagen)
    # Umbral de Otsu: calcula solo dónde separar brillante de oscuro, en vez
    # de usar un valor fijo que depende de la luz del lugar.
    _, brillante = cv2.threshold(gris, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    brillante = cv2.morphologyEx(
        brillante, cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15)),
    )

    contornos, _ = cv2.findContours(brillante, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contornos:
        return None

    alto_img, ancho_img = gris.shape[:2]
    area_total = alto_img * ancho_img
    candidatos = []
    for contorno in contornos:
        x, y, ancho, alto = cv2.boundingRect(contorno)
        area = ancho * alto
        # Ni una mancha diminuta ni prácticamente todo el cuadro.
        if area < area_total * 0.02 or area > area_total * 0.95:
            continue
        if ancho < 40 or alto < 20:
            continue
        candidatos.append((area, (x, y, ancho, alto)))

    if not candidatos:
        return None

    _, (x, y, ancho, alto) = max(candidatos, key=lambda c: c[0])
    dx, dy = int(ancho * margen), int(alto * margen)
    x0, y0 = max(0, x - dx), max(0, y - dy)
    x1, y1 = min(ancho_img, x + ancho + dx), min(alto_img, y + alto + dy)
    return imagen[y0:y1, x0:x1]


def variantes_binarizadas(imagen, rapido=False):
    """
    Devuelve varias versiones en blanco y negro de la misma imagen.

    Cada una gana en un escenario distinto: Otsu es el mejor caso general,
    el adaptativo aguanta iluminación despareja (media placa con sombra), y
    las versiones invertidas cubren el caso de texto claro sobre fondo
    oscuro, que es como se ve una placa en modo oscuro o con reflejo fuerte.

    En modo rápido se prueban solo las dos que más aciertan, para que una
    lectura en vivo no tarde segundos.
    """
    gris = _agrandar(_a_gris(imagen))
    # Ecualización local: sube el contraste del texto cuando la foto sale
    # lavada por el brillo de la pantalla del celular.
    contraste = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(gris)

    _, otsu_contraste = cv2.threshold(contraste, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if rapido:
        return [otsu_contraste, cv2.bitwise_not(otsu_contraste)]

    # El filtro bilateral es caro, así que solo se usa en el modo completo.
    suave = cv2.bilateralFilter(gris, 9, 75, 75)
    variantes = [otsu_contraste, cv2.bitwise_not(otsu_contraste)]
    _, otsu = cv2.threshold(suave, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variantes += [otsu, cv2.bitwise_not(otsu)]

    adaptativo = cv2.adaptiveThreshold(
        contraste, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, blockSize=35, C=11,
    )
    variantes += [adaptativo, cv2.bitwise_not(adaptativo)]
    return variantes


# Se mantiene el nombre viejo para no romper nada que lo importe.
def preprocesar(imagen):
    """Versión simple (Otsu). Las lecturas reales usan variantes_binarizadas."""
    gris = _agrandar(_a_gris(imagen))
    _, binaria = cv2.threshold(gris, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binaria


# ─────────────────────────────────────────────────────────────────────
# Corrección por formato
# ─────────────────────────────────────────────────────────────────────

def corregir_por_formato(texto):
    """
    Corrige confusiones de OCR usando el formato conocido de la placa.

    Si el OCR devuelve 'PAS6DEF', sabemos que las posiciones 1-3 tienen que
    ser dígitos, así que 'A'->'4' y 'S'->'5', dando 'P456DEF'.

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


def formato_valido(placa):
    """True si la placa calza con el formato guatemalteco (1 letra + 3 dígitos + 3 letras)."""
    return bool(placa) and bool(re.fullmatch(r"[A-Z]\d{3}[A-Z]{3}", placa))


def _extraer_placa(texto_crudo, corregir):
    """
    Saca una placa del texto que devolvió Tesseract.

    Tesseract suele traer basura alrededor (bordes leídos como letras,
    parte del marco del celular). Se limpia y se busca el patrón de placa
    DENTRO del texto, en vez de exigir que todo el texto sea la placa.
    """
    limpio = re.sub(r"[^A-Z0-9]", "", texto_crudo.upper())
    if not limpio:
        return ""

    # 1) ¿Aparece el patrón exacto en alguna parte?
    encontrado = PATRON_PLACA.search(limpio)
    if encontrado:
        return encontrado.group()

    if not corregir:
        return limpio

    # 2) Probar cada ventana de 7 caracteres, corregida por posición.
    for inicio in range(0, max(1, len(limpio) - LARGO_PLACA + 1)):
        candidato = corregir_por_formato(limpio[inicio:inicio + LARGO_PLACA])
        if formato_valido(candidato):
            return candidato

    return corregir_por_formato(limpio)


# ─────────────────────────────────────────────────────────────────────
# Lectura
# ─────────────────────────────────────────────────────────────────────

def leer_placa(imagen, corregir=True, buscar_zona=True, rapido=False):
    """
    Lee la placa de un cuadro BGR de OpenCV.

    Prueba varias binarizaciones × varios modos de Tesseract y se queda con
    la primera lectura que calce con el formato guatemalteco. Si ninguna
    calza, devuelve la lectura más repetida (mejor pista disponible), que
    el que llama puede descartar con formato_valido().

    rapido=True reduce las combinaciones a probar. Se usa cuando la lectura
    se repite muchas veces seguidas sobre cuadros distintos (video en vivo),
    donde conviene fallar rápido y reintentar con el cuadro siguiente antes
    que insistir mucho sobre uno solo.
    """
    if imagen is None or getattr(imagen, "size", 0) == 0:
        return ""

    modos = MODOS_PSM[:2] if rapido else MODOS_PSM

    # Orden de las regiones a probar, de la que más acierta a la que menos:
    #   1. Candidatos con forma de placa, ya enderezados (corrige el ángulo).
    #   2. La zona más brillante del cuadro, como red de seguridad.
    #   3. La imagen entera, último recurso.
    # La 1 es la que hace la diferencia: sin ella, en un cuadro dominado por
    # una hoja blanca el OCR terminaba leyendo el fondo en vez de la placa.
    regiones = []
    if buscar_zona:
        regiones.extend(localizar_candidatos_placa(
            imagen, maximo=1 if rapido else MAX_CANDIDATOS))
        recorte = recortar_zona_brillante(imagen)
        if recorte is not None and recorte.size > 0:
            regiones.append(recorte)
    regiones.append(imagen)

    if rapido:
        # En vivo conviene fallar rápido y reintentar con el cuadro
        # siguiente, en vez de insistir mucho sobre uno solo.
        regiones = regiones[:2]

    intentos = []
    validos = Counter()
    for region in regiones:
        for binaria in variantes_binarizadas(region, rapido=rapido):
            for psm in modos:
                config = f"--psm {psm} -c tessedit_char_whitelist={LISTA_BLANCA}"
                try:
                    crudo = pytesseract.image_to_string(binaria, config=config)
                except Exception:
                    continue
                candidato = _extraer_placa(crudo, corregir)
                if not candidato:
                    continue
                if formato_valido(candidato):
                    # No se devuelve la PRIMERA lectura con forma de placa:
                    # una lectura equivocada puede tener forma válida igual
                    # (ej. leer M254KLM en vez de M234KLM) y ganaba solo por
                    # llegar primero. Se acumulan votos y se corta apenas
                    # DOS binarizaciones distintas coinciden en lo mismo,
                    # que es una señal mucho más fuerte.
                    validos[candidato] += 1
                    if validos[candidato] >= 2:
                        return candidato
                else:
                    intentos.append(candidato)

    if validos:
        return validos.most_common(1)[0][0]
    if not intentos:
        return ""
    return Counter(intentos).most_common(1)[0][0]


def leer_placa_de_archivo(ruta, corregir=True, buscar_zona=False):
    """
    Lee la placa de una imagen guardada en disco.

    buscar_zona va en False por defecto porque las imágenes de prueba YA
    son el recorte de la placa; recortar de nuevo solo puede empeorarlo.
    """
    imagen = cv2.imread(str(ruta))
    if imagen is None:
        raise FileNotFoundError(f"No se pudo abrir la imagen: {ruta}")
    return leer_placa(imagen, corregir=corregir, buscar_zona=buscar_zona)
