# Guía de estudio — Estacionamiento Inteligente

Este documento existe para una sola cosa: que puedas explicarle el proyecto
a tu profesor de pies a cabeza, sin quedarte en blanco si te pregunta "¿en
qué hiciste el dashboard?" o "¿cómo funciona esto por dentro?". No hace
falta memorizar código — hace falta entender qué hace cada pieza y por qué
está ahí.

---

## 1. El proyecto en una frase

Una cámara ve el parqueo, un programa en Python reconoce las placas y
detecta qué espacios están libres, todo eso se guarda en una base de datos
en la nube, y una página web muestra ese estado en tiempo real y calcula
el cobro automáticamente.

---

## 2. Las cuatro piezas grandes

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐     ┌─────────────┐
│   Cámara     │ --> │  Python +    │ --> │  Base de datos │ --> │  Página web  │
│ (ve el carro)│     │  OpenCV +    │     │  en la nube    │     │  (Django)    │
│              │     │  Tesseract   │     │  (TiDB Cloud)  │     │              │
└─────────────┘     └──────────────┘     └───────────────┘     └─────────────┘
```

1. **La cámara** — hoy la webcam de tu laptop, en la entrega final la
   cámara física de la Raspberry Pi.
2. **El "cerebro" que procesa la imagen** — un programa en Python
   (`scripts/monitor.py`) que hace dos cosas con cada cuadro de video:
   - **Detecta ocupación**: mide cuánta "textura" (bordes, detalle) hay en
     cada espacio. Un espacio vacío es una superficie lisa (poco detalle);
     un carro tiene llantas, ventanas, sombras (mucho detalle). Si el
     detalle pasa un umbral, dice "ocupado".
   - **Lee la placa**: usa Tesseract (un motor de OCR — *Optical Character
     Recognition*, reconocimiento óptico de caracteres) para convertir la
     imagen de la placa en texto.
3. **La base de datos** — TiDB Cloud, un servicio en la nube que habla el
   mismo idioma que MySQL (SQL). Ahí se guarda todo: qué placas existen,
   qué espacios hay, quién ocupa cuál, y cuánto se cobró.
4. **La página web (dashboard)** — muestra en el navegador lo que dice la
   base de datos, y ahora también controla quién puede entrar a verla
   (login) y qué puede ver cada quien (roles).

**Lo importante para explicarle al profesor**: estas cuatro piezas están
separadas a propósito. El programa que lee la cámara (`monitor.py`) es el
**único** que escribe en la base de datos. La página web **solo lee**.
Eso significa que podés apagar el dashboard sin que el parqueo deje de
funcionar, y viceversa — son programas independientes que se comunican
únicamente a través de la base de datos.

---

## 3. Django, explicado sin vueltas

**La pregunta que te hizo el profesor y la respuesta corta:**
"El dashboard está hecho con Django, un framework de Python para
construir aplicaciones web."

**Framework** = una caja de herramientas con piezas ya armadas, para no
reinventar cosas que casi todo sitio web necesita (mostrar páginas,
manejar formularios, guardar usuarios).

**¿Por qué Django y no otra cosa?** Al principio el dashboard estaba hecho
con **Flask** (otro framework de Python, más minimalista). Cuando el
profesor pidió login con distintos roles de usuario, se migró a Django
porque trae de fábrica:

- **Un sistema de login y usuarios ya construido** (no hubo que programar
  "cómo se guarda una contraseña de forma segura" desde cero).
- **Un ORM** (explico abajo qué es).
- **Un panel de administración** (`/admin/`) que se genera solo a partir
  de cómo describís tus datos — sirve para gestionar espacios, tarifas y
  usuarios sin construir pantallas propias para eso.

**¿Qué es un ORM?** *Object-Relational Mapper* — un traductor entre
Python y SQL. En vez de escribir:

```sql
SELECT etiqueta, estado FROM espacios WHERE estado = 'ocupado';
```

escribís Python:

```python
Espacio.objects.filter(estado="ocupado")
```

Django lo traduce a SQL por vos. La ventaja: es más fácil de leer, y
Django puede prevenir errores comunes (como inyección SQL) automáticamente.
La base de datos sigue siendo la misma (TiDB/MySQL) — el ORM no la
reemplaza, es una forma más cómoda de hablar con ella.

**Dato importante si te preguntan por las tablas**: las 5 tablas del
proyecto (`vehiculos`, `espacios`, `tarifas`, `sesiones`, `cobros`) las
sigue escribiendo el programa de la cámara (`monitor.py`) con SQL directo,
sin Django de por medio — Django solo las **lee** con su ORM para
mostrarlas en el dashboard. Las únicas tablas que Django administra por
completo son las suyas propias, para el login (`auth_user`, `auth_group`,
etc.), que conviven en la misma base junto a las cinco de negocio.

---

## 4. Los roles: Admin y Operador

- **Operador**: ve el estado en vivo del parqueo (qué espacios están
  ocupados, la bitácora de entradas y salidas). No ve cuánto se ha
  recaudado ni el historial de ocupación por hora, ni puede cambiar la
  tarifa.
- **Admin**: ve todo lo anterior, más la recaudación y el gráfico de
  ocupación por hora, y tiene acceso al panel `/admin/` de Django, donde
  puede gestionar espacios, ver el historial completo, y crear/promover
  usuarios.

**¿Cómo se implementa esto técnicamente?** Django tiene un concepto
llamado **grupo** (`Group`): una etiqueta que se le pone a un usuario.
Cada vista del dashboard revisa "¿este usuario está en el grupo Admin?"
antes de decidir qué datos devolver. Si no está en el grupo Admin, la
respuesta que arma el servidor **ni siquiera incluye** los datos de
recaudación — no es solo que la pantalla los esconda, es que el servidor
nunca se los manda.

**¿Cómo se crea una cuenta?** Cualquiera puede registrarse desde la
pantalla de registro, pero **toda cuenta nueva entra como Operador**.
Nadie puede autoasignarse Admin — un Admin ya existente tiene que
promoverlo a mano desde el panel `/admin/`. Esto es una decisión de
seguridad: si el registro dejara elegir el rol, cualquiera podría
"registrarse como Admin" y ver la recaudación de todos.

---

## 5. Sigamos un carro de principio a fin

Esto es lo más útil para explicar en una presentación: seguir un ejemplo
concreto.

**1. Un carro entra y se estaciona en el espacio A1.**
La cámara sigue mandando cuadros de video, siempre. `ocupacion.py` mide
la textura del espacio A1 en cada cuadro. Antes del carro, poca textura
("libre"). Con el carro, mucha textura ("ocupado"). Para no confundir un
parpadeo (una sombra, alguien caminando) con un cambio real, el sistema
exige ver el mismo resultado varias veces seguidas antes de confirmarlo
(la clase `EstadoEstable` en `ocupacion.py`).

**2. Se confirma el cambio a "ocupado".**
`monitor.py` reacciona: le avisa a `parqueo.py` que abra una sesión nueva
para el espacio A1. Esto se escribe en la base **inmediatamente**, con la
placa como `"DESCONOCIDA"` momentáneamente — el tablero tiene que
reaccionar al instante, no esperar a que termine de leer la placa.

**3. En paralelo, se intenta leer la placa.**
Esto pasa en un hilo aparte (un "carril" separado de ejecución) para que
leer la placa no congele el video. Se prueban varios cuadros seguidos, y
solo se acepta una lectura si se repite dos veces — leer la misma placa
mal dos veces seguidas es mucho menos probable que leerla mal una sola
vez. Si de verdad no se puede leer, la placa se queda como
`"DESCONOCIDA"` — es preferible admitir que no se supo, a cobrarle a la
placa equivocada.

**4. La placa se corrige con el formato guatemalteco.**
Una placa de Guatemala es 1 letra + 3 dígitos + 3 letras (ej. `P123ABC`).
Si el OCR devuelve algo con la forma correcta pero con una confusión
típica (una `S` donde debería ir un `5`, por ejemplo), el sistema la
corrige sabiendo qué posición tiene que ser letra y cuál dígito.

**5. La base de datos queda con una sesión activa.**
Un renglón en la tabla `sesiones`: la placa, el espacio, la hora de
entrada, sin hora de salida todavía.

**6. El dashboard lo muestra en segundos.**
La página web (con JavaScript) le pregunta a Django cada fracción de
segundo "¿qué hay de nuevo?" (`/api/estado`). Django consulta la base
(con su ORM) y devuelve el estado actual en formato JSON. El navegador
actualiza solo las partes que cambiaron.

**7. El carro se va.**
`ocupacion.py` detecta que el espacio volvió a estar "libre" (misma
lógica de confirmar varias veces seguidas). `parqueo.py` cierra la
sesión, calcula cuántos minutos estuvo (cobrando el minuto empezado,
como un parqueo real) y genera el cobro según la tarifa vigente en ese
momento.

**8. El dashboard refleja la salida.**
Aparece en la bitácora de movimientos, y si sos Admin, también en la
recaudación del día.

---

## 6. Por qué el sistema vive en la nube (TiDB Cloud)

La base de datos no está en tu laptop ni en la Raspberry Pi — está en un
servidor de TiDB Cloud (en Tokio). Esto tiene una consecuencia práctica
importante: **cada consulta a la base tarda cerca de 300 milisegundos**,
solo por la distancia. El proyecto tiene varias decisiones de diseño que
existen exclusivamente por esto:

- El dashboard **no pregunta todo de una vez todo el tiempo** — separa lo
  que cambia siempre (ocupación de espacios) de lo que cambia poco
  (recaudación total), y consulta cada cosa con la frecuencia que
  realmente necesita.
- Las conexiones a la base **se reusan** en vez de abrir una nueva por
  cada consulta (abrir una conexión nueva tarda ~2 segundos solo en el
  saludo de seguridad TLS).

Si te preguntan "¿por qué no corre todo más rápido?", esa es la respuesta:
no es lento el código, es la velocidad de la luz entre tu laptop y Tokio.

---

## 7. Preguntas que te puede hacer el profesor (y respuestas cortas)

**¿En qué está hecho el dashboard?**
Django (framework de Python para aplicaciones web), con un ORM para
consultar la base de datos sin escribir SQL a mano.

**¿Por qué Django y no Flask, si Flask ya andaba?**
Django trae login, usuarios y un panel de administración ya construidos.
Al pedir login con roles, reconstruir todo eso a mano en Flask era más
trabajo que aprovechar lo que Django ya resuelve.

**¿Cómo maneja la concurrencia — qué pasa si dos personas entran al
dashboard a la vez?**
El dashboard solo lee, nunca escribe, así que no hay conflicto entre
usuarios viéndolo al mismo tiempo. El único programa que escribe
(`monitor.py`) corre una sola vez, junto a la cámara.

**¿Cómo se calcula el cobro?**
`tarifa_vigente × minutos_estacionado`, redondeando siempre hacia arriba
al minuto (el minuto empezado se cobra completo, como un parqueo real).
La tarifa que se usa es la que estaba vigente en el momento del cobro,
no la de ahora — las tarifas viejas nunca se borran, se cierran con una
fecha de fin, para poder explicar un cobro histórico con la tarifa que
regía ese día.

**¿Qué pasa si el OCR no puede leer la placa?**
Se guarda como `"DESCONOCIDA"`. Es una decisión deliberada: es peor
cobrarle a la placa equivocada que admitir que no se pudo leer.

**¿Cómo decide el sistema si un espacio está ocupado?**
Mide cuánto "detalle visual" (bordes, texturas) hay en la región de la
imagen que corresponde a ese espacio. Un espacio vacío es una superficie
lisa; un carro genera mucho más detalle. Exige ver el mismo resultado
varias veces seguidas antes de confirmar el cambio, para no confundir un
parpadeo con un cambio real.

**¿Los dos roles (Admin/Operador) se implementan cambiando el HTML nomás?**
No — la diferencia empieza en el servidor. Si el usuario no es Admin, el
servidor ni siquiera manda los datos de recaudación en la respuesta. No
es "esconder con CSS", es no enviarlos.

---

## 8. Cómo correr todo (referencia rápida)

```bash
cd "C:\Users\jdcua\dev\estacionamiento-inteligente-bd"
```

Dashboard (Django, dentro de `web_django/`):
```bash
cd web_django
python manage.py runserver 5051
```
→ <http://localhost:5051>

Monitor con cámara (otra terminal, desde la raíz del repo):
```bash
python scripts/monitor.py
```

Sin cámara, para practicar la demo:
```bash
python scripts/monitor.py --simular
```

Crear una cuenta Admin (una vez, desde `web_django/`):
```bash
python manage.py crear_grupos
python manage.py shell -c "
from django.contrib.auth.models import Group, User
u = User.objects.get(username='TU_USUARIO')
u.groups.add(Group.objects.get(name='Admin'))
u.is_staff = True
u.is_superuser = True
u.save()
"
```

---

## 9. Lo que todavía falta (para no prometer de más)

- Probar el OCR con la cámara real de la Pi (hoy solo está validado con
  la webcam y con imágenes de prueba) — ver `docs/superpowers/plans/2026-08-13-ocr-consenso-plan.md`.
  Ya se corrigió un bug real: la lectura en vivo hacía un solo intento en
  vez de pedir varios cuadros y exigir consenso.
- Conectar y probar la cámara física (Raspberry Pi Camera rev 1.3) — el
  código ya está listo (`scripts/camara.py`), falta el paso físico en la
  Pi (ver `docs/superpowers/plans/2026-08-13-camara-pi-y-red-demo-plan.md`).
- Configurar el hotspot del celular como red de respaldo para el día de
  la presentación (mismo plan que la cámara).
- Fase 8 (probar en el parqueo real de la universidad) y Fase 9
  (documentación final) — son las últimas que quedan pendientes.
