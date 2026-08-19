from django.contrib.auth import login
from django.contrib.auth.models import Group
from django.shortcuts import redirect, render

from .forms import FormularioRegistro


def registro(request):
    if request.method == "POST":
        formulario = FormularioRegistro(request.POST)
        if formulario.is_valid():
            usuario = formulario.save()
            # Toda cuenta nueva entra como Operador. Nadie se autoasigna
            # Admin desde acá -- un Admin existente promueve desde /admin/.
            grupo_operador, _ = Group.objects.get_or_create(name="Operador")
            usuario.groups.add(grupo_operador)
            login(request, usuario)
            return redirect("dashboard:index")
    else:
        formulario = FormularioRegistro()
    return render(request, "cuentas/registro.html", {"form": formulario})
