"""
Crea los grupos Admin y Operador si no existen. Idempotente: correrlo de
nuevo no duplica nada.

Uso:
    python manage.py crear_grupos
"""

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Crea los grupos de rol Admin y Operador"

    def handle(self, *args, **options):
        for nombre in ("Admin", "Operador"):
            _, creado = Group.objects.get_or_create(name=nombre)
            estado = "creado" if creado else "ya existía"
            self.stdout.write(f"Grupo '{nombre}': {estado}")
