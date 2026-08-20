"""
Crea una cuenta de operador (o convierte una existente en operador).

No hay registro público en el panel a propósito: las cuentas las da de
alta el administrador. Este comando es el atajo para hacerlo desde la
terminal; lo mismo se puede hacer desde /admin/ creando el usuario y
asignándole el grupo "Operador" a mano.

Un operador ve el estado del parqueo y la bitácora, pero NO la
recaudación ni la configuración (ver dashboard/views.py::es_admin).

Uso:
    python manage.py crear_operador juanperez
    python manage.py crear_operador juanperez --password "algo-seguro"
"""

from getpass import getpass

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Crea una cuenta con rol de operador"

    def add_arguments(self, parser):
        parser.add_argument("usuario", help="Nombre de usuario para entrar al panel")
        parser.add_argument(
            "--password",
            help="Contraseña. Si se omite, se pide por teclado sin mostrarla en pantalla.",
        )

    def handle(self, *args, **options):
        nombre = options["usuario"]
        contrasena = options["password"] or getpass(f"Contraseña para '{nombre}': ")
        if not contrasena:
            raise CommandError("La contraseña no puede quedar vacía.")

        grupo, _ = Group.objects.get_or_create(name="Operador")
        usuario, creado = User.objects.get_or_create(username=nombre)
        usuario.set_password(contrasena)
        # Un operador no entra a /admin/: solo ve el panel del parqueo.
        usuario.is_staff = False
        usuario.is_superuser = False
        usuario.save()
        usuario.groups.add(grupo)

        accion = "creada" if creado else "actualizada"
        self.stdout.write(self.style.SUCCESS(
            f"Cuenta '{nombre}' {accion} con rol de operador."))
        self.stdout.write("Puede entrar en http://localhost:5051 -- no tiene acceso a /admin/.")
