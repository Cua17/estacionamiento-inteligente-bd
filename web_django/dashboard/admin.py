"""
Panel /admin/ de Django: lo usa el rol Admin para gestionar espacios,
tarifas y usuarios -- sin construir pantallas propias para eso.
"""

from django.contrib import admin
from django.utils import timezone

from .models import Cobro, Espacio, Sesion, Tarifa, TarifaTramo, Vehiculo


@admin.register(Espacio)
class EspacioAdmin(admin.ModelAdmin):
    list_display = ["etiqueta", "estado", "actualizado_en"]
    # El estado lo escribe monitor.py en tiempo real -- acá solo se
    # gestiona la etiqueta/alta de espacios, no se fuerza el estado a mano.
    readonly_fields = ["estado", "actualizado_en"]


@admin.register(Vehiculo)
class VehiculoAdmin(admin.ModelAdmin):
    list_display = ["placa", "primera_deteccion", "notas"]
    readonly_fields = ["placa", "primera_deteccion"]


@admin.register(Sesion)
class SesionAdmin(admin.ModelAdmin):
    list_display = ["placa", "espacio", "hora_entrada", "hora_salida", "estado"]
    list_filter = ["estado"]

    # Solo lectura: abrir/cerrar sesiones es responsabilidad exclusiva de
    # parqueo.py (ver decisiones de diseño en README.md) -- el panel no
    # debe poder tocar esto a mano y desincronizarlo de la cámara.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Cobro)
class CobroAdmin(admin.ModelAdmin):
    list_display = ["sesion", "tarifa", "minutos_totales", "monto", "fecha_cobro"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class TarifaTramoInline(admin.TabularInline):
    """
    Los tramos se editan dentro de la tarifa, no como una lista aparte: un
    tramo suelto no significa nada sin saber a qué tarifa pertenece.
    """
    model = TarifaTramo
    extra = 1
    ordering = ["desde_minuto"]


@admin.register(Tarifa)
class TarifaAdmin(admin.ModelAdmin):
    list_display = ["nombre", "precio_por_hora", "escalonado", "vigente_desde", "vigente_hasta"]
    inlines = [TarifaTramoInline]

    @admin.display(description="Escalonado")
    def escalonado(self, obj):
        """Resumen legible de los tramos, para no tener que abrir cada tarifa."""
        tramos = list(obj.tramos.all())
        if not tramos:
            return "precio plano"
        partes = []
        for indice, tramo in enumerate(tramos):
            siguiente = tramos[indice + 1].desde_minuto if indice + 1 < len(tramos) else None
            rango = f"{tramo.desde_minuto}-{siguiente}" if siguiente else f"{tramo.desde_minuto}+"
            precio = "gratis" if float(tramo.precio_por_hora) == 0 else f"Q{tramo.precio_por_hora}"
            partes.append(f"{rango} min: {precio}")
        return " · ".join(partes)

    def save_model(self, request, obj, form, change):
        """
        La tarifa nunca se borra, se cierra (ver README.md): al crear
        una fila nueva sin vigente_hasta, se le pone vigente_hasta=ahora a
        la que estaba vigente antes, para que un cobro viejo se siga
        pudiendo explicar con la tarifa que regía ese día.
        """
        if not change:  # solo al CREAR una tarifa nueva, no al editar una existente
            Tarifa.objects.filter(vigente_hasta__isnull=True).update(
                vigente_hasta=timezone.now()
            )
        super().save_model(request, obj, form, change)
