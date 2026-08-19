# Cámara Pi + red del día de la demo — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que la cámara CSI (Raspberry Pi Camera rev 1.3) funcione con el
mismo pipeline que hoy usa la webcam, y que la Raspberry Pi se conecte
sola al hotspot del celular el día de la presentación sin depender del
router de la universidad.

**Architecture:** `camara.py` gana un segundo camino de captura
(`picamera2`, específico de Linux/Pi) detrás de la misma interfaz que ya
usa `cv2.VideoCapture` (`.read()` → `(bool, cuadro)`, `.release()`), así
que `monitor.py` y todo lo que sigue en el pipeline (`ocupacion.py`,
`vision.py`) no necesitan enterarse de cuál cámara está activa. La parte
de red es en su mayoría configuración de la Raspberry Pi (NetworkManager),
no código.

**Tech Stack:** `picamera2` (paquete del sistema, no de pip — ver Tarea
2), NetworkManager (`nmcli`, ya viene con Raspberry Pi OS trixie).

## Global Constraints

- `requirements.txt` NO debe listar `picamera2` — no existe fuera de
  Linux/Pi y rompería la instalación en la laptop Windows. Se importa de
  forma diferida (dentro de la función, no al inicio del archivo).
- El comportamiento en la laptop (Windows, webcam por DirectShow) no debe
  cambiar en nada.
- Todo el trabajo de Tareas 2 y 3 pasa por SSH a la Pi — quien ejecute
  este plan necesita el acceso ya documentado en `CONTEXTO.md`
  (`ssh -i ~/.ssh/id_ed25519_parqueo_pi cua@parqueo-pi.local`).

---

## File Structure

- Modificar: `scripts/camara.py` — agregar `_CamaraPi`, `hay_camara_pi()`,
  y el parámetro `usar_pi_camera` en `abrir_camara()`.
- Modificar: `scripts/monitor.py` — flag `--camara-pi`, pasar
  `usar_pi_camera` a `abrir_camara()`.
- Sin archivos nuevos de código — las Tareas 2 y 3 son comandos a correr
  en la Pi (documentados acá y también van a `CONTEXTO.md` al terminar).

---

### Task 1: Camino de captura para la cámara CSI en `camara.py`

**Files:**
- Modify: `scripts/camara.py`
- Test: manual (Tarea 3 — no hay forma de probar picamera2 fuera de la Pi)

**Interfaces:**
- Produces: `abrir_camara(indice=0, ancho=640, alto=480, usar_pi_camera=False)`
  (firma existente + un parámetro nuevo con default `False`, así que
  ningún llamador actual se rompe) y `hay_camara_pi() -> bool`.
- Consumes: nada nuevo — `picamera2` se importa solo dentro de
  `_CamaraPi.__init__`, así que en Windows ese import nunca se ejecuta.

- [ ] **Step 1: Agregar la clase adaptadora y la detección**

Agregar al final de `scripts/camara.py`:

```python
class _CamaraPi:
    """
    Envoltorio de picamera2 con la misma interfaz que cv2.VideoCapture
    (read() -> (bool, cuadro BGR), release()), para que monitor.py no
    tenga que saber qué cámara está usando.

    picamera2 se importa acá adentro (no al inicio del archivo) porque
    solo existe como paquete del sistema en Linux/Raspberry Pi — si este
    archivo se importa en Windows, ese import nunca se ejecuta.
    """

    def __init__(self, ancho=640, alto=480):
        from picamera2 import Picamera2
        self._picam2 = Picamera2()
        config = self._picam2.create_video_configuration(
            main={"size": (ancho, alto), "format": "BGR888"}
        )
        self._picam2.configure(config)
        self._picam2.start()
        # Igual que con la webcam: los primeros cuadros vienen con la
        # exposición todavía ajustándose.
        for _ in range(5):
            self._picam2.capture_array()

    def read(self):
        return True, self._picam2.capture_array()

    def release(self):
        self._picam2.stop()
        self._picam2.close()

    def isOpened(self):
        return True


def hay_camara_pi():
    """
    True si hay una cámara CSI detectada por libcamera (típico en la Pi).

    Se usa para elegir automáticamente el camino de captura correcto sin
    que haga falta pasar un flag a mano.
    """
    if platform.system() != "Linux":
        return False
    try:
        from picamera2 import Picamera2
        return len(Picamera2.global_camera_info()) > 0
    except Exception:
        return False
```

- [ ] **Step 2: Usar la nueva clase en `abrir_camara`**

Reemplazar la firma y el cuerpo de `abrir_camara` (líneas 14-39):

```python
def abrir_camara(indice=0, ancho=640, alto=480, usar_pi_camera=False):
    """
    Abre la cámara y devuelve un objeto con .read()/.release()/.isOpened()
    ya configurado.

    usar_pi_camera=True usa la cámara CSI de la Raspberry Pi (picamera2)
    en vez de una webcam genérica. En Windows se fuerza el backend
    DirectShow: con el backend por defecto, OpenCV puede tardar varios
    segundos en abrir la webcam o devolver cuadros negros al principio.
    """
    if usar_pi_camera:
        return _CamaraPi(ancho, alto)

    backend = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_ANY
    camara = cv2.VideoCapture(indice, backend)
    camara.set(cv2.CAP_PROP_FRAME_WIDTH, ancho)
    camara.set(cv2.CAP_PROP_FRAME_HEIGHT, alto)

    if not camara.isOpened():
        raise RuntimeError(
            f"No se pudo abrir la cámara {indice}. "
            "Verificá que no esté siendo usada por otro programa "
            "(Zoom, Teams, Meet) y que Windows le dé permiso de cámara."
        )

    for _ in range(5):
        camara.read()

    return camara
```

- [ ] **Step 3: Verificar que Windows sigue funcionando igual**

Run: `python scripts/monitor.py` (en la laptop)
Expected: la webcam abre exactamente igual que antes — `usar_pi_camera`
nunca se activa sola en Windows (`hay_camara_pi()` devuelve `False` de
entrada por el chequeo de plataforma, sin siquiera intentar importar
picamera2).

- [ ] **Step 4: Commit**

```bash
git add scripts/camara.py
git commit -m "Agregar soporte para la camara CSI de la Raspberry Pi

_CamaraPi envuelve picamera2 con la misma interfaz que ya usa
cv2.VideoCapture, para que el resto del pipeline no tenga que saber cual
camara esta activa. picamera2 se importa de forma diferida asi que Windows
no se ve afectado.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: Flag y detección automática en `monitor.py`

**Files:**
- Modify: `scripts/monitor.py`

**Interfaces:**
- Consumes: `abrir_camara(indice, usar_pi_camera=...)`, `hay_camara_pi()`
  de la Tarea 1.

- [ ] **Step 1: Agregar el argumento y la detección**

En `scripts/monitor.py`, importar `hay_camara_pi` junto al resto:

```python
from camara import abrir_camara, hay_camara_pi
```

Agregar el argumento en `main()` (junto a `--camara`):

```python
    parser.add_argument("--camara-pi", action="store_true",
                        help="Forzar el uso de la cámara CSI de la Raspberry Pi "
                             "(por defecto se detecta sola)")
```

En `bucle_camara`, cambiar la apertura de la cámara:

```python
def bucle_camara(args, conexion, espacios, zona_placa):
    usar_pi_camera = args.camara_pi or hay_camara_pi()
    if usar_pi_camera:
        registrar("Usando la cámara CSI de la Raspberry Pi (picamera2).")
    camara = abrir_camara(args.camara, usar_pi_camera=usar_pi_camera)
    ...
```

(el resto de la función sigue igual — no hay más cambios).

- [ ] **Step 2: Probar en la laptop que nada cambió**

Run: `python scripts/monitor.py --sin-ventana` unos segundos, Ctrl+C.
Expected: arranca igual que siempre, sin el mensaje de "Usando la cámara
CSI..." (porque `hay_camara_pi()` es `False` en Windows).

- [ ] **Step 3: Commit**

```bash
git add scripts/monitor.py
git commit -m "Detectar y usar la camara CSI de la Pi automaticamente en monitor.py

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: Runbook — habilitar la cámara en la Pi (correr vos, por SSH)

Esto no es código para mí, son comandos que corrés vos por SSH — no tengo
acceso a tu red local desde acá para hacerlo directamente.

- [ ] **Step 1: Conectarte y confirmar que el sistema ve la cámara**

```bash
ssh -i ~/.ssh/id_ed25519_parqueo_pi cua@parqueo-pi.local
rpicam-hello --list-cameras
```

Expected: aparece un sensor `ov5647` (es el sensor de la Camera Module
v1 / rev 1.3) con sus resoluciones soportadas. Si dice "no cameras
available", revisar que el cable esté bien enchufado (el lado azul del
cable mira hacia el puerto USB de la Pi) y correr
`sudo raspi-config nonint do_camera 0` para habilitar la interfaz, después
reiniciar (`sudo reboot`) y probar de nuevo.

- [ ] **Step 2: Instalar picamera2 a nivel de sistema (NO con pip)**

```bash
sudo apt update
sudo apt install -y python3-picamera2 --no-install-recommends
```

picamera2 depende de bindings nativos de `libcamera` que no se instalan
bien vía pip — por eso va con `apt`, no dentro del venv como el resto de
`requirements.txt`.

- [ ] **Step 3: Recrear el venv del proyecto para que vea los paquetes del sistema**

```bash
cd ~/estacionamiento-inteligente-bd
python3 -m venv --system-site-packages venv --clear
source venv/bin/activate
pip install -r requirements.txt
```

`--system-site-packages` hace que el venv pueda importar `picamera2`
(instalado por apt) además de sus propios paquetes. `--clear` borra lo
que había en el venv viejo — por eso el `pip install -r requirements.txt`
después, para reinstalar `mysql-connector-python`, `opencv-python`, etc.
Puede tardar varios minutos (OpenCV es un paquete grande).

- [ ] **Step 4: Confirmar que Python ve la cámara desde el venv**

```bash
python3 -c "from picamera2 import Picamera2; print(Picamera2.global_camera_info())"
```

Expected: una lista con un diccionario describiendo el sensor `ov5647`.
Si da `ImportError`, el venv no quedó con `--system-site-packages` bien
aplicado — repetir el Step anterior.

- [ ] **Step 5: Sincronizar el código nuevo (Tareas 1 y 2) y probarlo en vivo**

Desde la laptop:

```bash
cd "C:\Users\jdcua\dev\estacionamiento-inteligente-bd"
scp -i ~/.ssh/id_ed25519_parqueo_pi -r scripts web schema.sql requirements.txt \
  cua@parqueo-pi.local:~/estacionamiento-inteligente-bd/
```

Desde la Pi:

```bash
cd ~/estacionamiento-inteligente-bd && source venv/bin/activate
python scripts/configurar_espacios.py --rejilla 4   # o a mano si preferís ver la ventana por ssh -X
python scripts/monitor.py --sin-ventana
```

Expected: en los logs aparece "Usando la cámara CSI de la Raspberry Pi
(picamera2)." y el monitor detecta cambios de ocupación igual que con la
webcam.

---

### Task 4: Runbook — la Pi se conecta sola al hotspot del celular

- [ ] **Step 1: Activar el hotspot del celular una vez, y conectar la Pi**

Con el hotspot ya prendido y con vos parado cerca de la Pi (esta parte,
sí, hace falta hacerla una vez con ambos dispositivos cerca — después
queda guardado para siempre):

```bash
ssh -i ~/.ssh/id_ed25519_parqueo_pi cua@parqueo-pi.local
sudo nmcli device wifi connect "NOMBRE_DE_TU_HOTSPOT" password "CONTRASEÑA_DEL_HOTSPOT"
```

- [ ] **Step 2: Confirmar que quedó guardada como red conocida**

```bash
nmcli connection show
```

Expected: aparece una fila con el nombre del hotspot, tipo `wifi`, además
de la red de tu casa. La Pi se va a conectar sola a la que esté
disponible la próxima vez que arranque.

- [ ] **Step 3 (opcional pero recomendado): priorizar el hotspot sobre la red de casa**

```bash
sudo nmcli connection modify "NOMBRE_DE_TU_HOTSPOT" connection.autoconnect-priority 10
```

Así, si por error las dos redes están al alcance el día de la demo (poco
probable, pero por las dudas), la Pi prefiere el hotspot.

- [ ] **Step 4: Probar de punta a punta con el hotspot activo (antes del día de la demo, no ese día)**

Con el celular en modo hotspot, laptop y Pi ambos conectados a él:

```bash
ping parqueo-pi.local
ssh -i ~/.ssh/id_ed25519_parqueo_pi cua@parqueo-pi.local "echo conectado OK"
```

Y ya en la Pi, confirmar que llega a TiDB Cloud por datos móviles:

```bash
cd ~/estacionamiento-inteligente-bd && source venv/bin/activate
python3 -c "from db import conectar; c = conectar(); print('TiDB OK')"
```

Expected: los tres comandos responden bien. Si `ping` no encuentra el
hostname pero el hotspot sí tiene internet, probar con la IP directa
(`ip a` en la Pi para verla) en vez de `parqueo-pi.local` — algunos
hotspots de celular no reenvían mDNS tan bien como una red doméstica.

- [ ] **Step 5: Llevar un plan B físico el día de la demo**

No es código, es una recomendación: llevar un monitor HDMI chico y un
teclado USB como respaldo, por si el hotspot falla en el momento y hay
que revisar la Pi directamente. Es la única red de seguridad real contra
"algo de red salió distinto a como lo probamos en casa".

---

## Self-review

- **Cobertura**: Tarea 1-2 cubren el código (probado hasta donde se puede
  sin hardware — Windows sigue igual). Tarea 3-4 cubren el hardware real
  y la red, como runbook explícito ya que no tengo acceso a la Pi desde
  este entorno.
- **Placeholders**: los nombres de red/contraseña en la Tarea 4 son
  literalmente los tuyos — no hay forma de saberlos de antemano, quedan
  marcados en mayúsculas para que los reemplaces vos al ejecutar.
- **Consistencia**: `abrir_camara()` mantiene la firma vieja con un
  parámetro nuevo de default `False` — ningún código existente
  (`monitor.py` antes de la Tarea 2) se rompe hasta que se actualiza a
  propósito.

## Qué NO se hace acá

- No se prueba con la cámara real desde este entorno — no tengo acceso a
  tu Raspberry Pi. Las Tareas 3 y 4 quedan como runbook para que las
  corras vos, y avisame los resultados para ajustar si algo no calza.
- No se configura un servidor DB local de respaldo por si falla
  totalmente el internet en la demo — la arquitectura entera depende de
  TiDB Cloud; si eso te preocupa como riesgo residual, es una conversación
  aparte (cambiaría el diseño).
