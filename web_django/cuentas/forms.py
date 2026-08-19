"""Registro público de cuentas -- toda cuenta nueva entra como Operador."""

from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class FormularioRegistro(UserCreationForm):
    class Meta:
        model = User
        fields = ["username"]
