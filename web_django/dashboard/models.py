"""
Modelos de solo lectura sobre las 5 tablas de negocio (managed=False:
Django nunca las crea ni las altera, ya existen y las escribe
parqueo.py). Reflejan exactamente schema.sql -- si el schema cambia, este
archivo se actualiza a mano.
"""

from django.db import models
from django.utils import timezone


class Vehiculo(models.Model):
    placa = models.CharField(max_length=15, primary_key=True)
    # default=timezone.now (no auto_now_add) porque schema.sql define
    # DEFAULT CURRENT_TIMESTAMP, no algo que Django deba forzar en cada
    # UPDATE -- coincide con lo que ya hacía la base antes de tener ORM.
    primera_deteccion = models.DateTimeField(default=timezone.now)
    notas = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        managed = False
        db_table = "vehiculos"

    def __str__(self):
        return self.placa


class Espacio(models.Model):
    etiqueta = models.CharField(max_length=10, unique=True)
    estado = models.CharField(max_length=10)  # 'libre' | 'ocupado'
    actualizado_en = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = "espacios"
        ordering = ["etiqueta"]

    def __str__(self):
        return self.etiqueta


class Tarifa(models.Model):
    nombre = models.CharField(max_length=50)
    precio_por_hora = models.DecimalField(max_digits=8, decimal_places=2)
    vigente_desde = models.DateTimeField(default=timezone.now)
    vigente_hasta = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "tarifas"

    def __str__(self):
        return f"{self.nombre} (Q{self.precio_por_hora}/h)"


class TarifaTramo(models.Model):
    """
    Un rango de cobro: 'desde este minuto se cobra tanto'.

    Rige hasta que empieza el tramo siguiente; el último queda abierto y
    puede sumar un extra por cada hora empezada de más.
    Ver el cálculo en scripts/parqueo.py::calcular_monto_por_tramos.
    """

    tarifa = models.ForeignKey(
        Tarifa, on_delete=models.DO_NOTHING, db_column="tarifa_id",
        related_name="tramos",
    )
    desde_minuto = models.IntegerField(
        help_text="Desde qué minuto acumulado aplica este cobro (0 = desde que entra)")
    monto_fijo = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        help_text="Lo que se cobra si el tiempo cae en este tramo. 0.00 = gratis")
    precio_por_hora_adicional = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        help_text="Solo para el último tramo: cuánto suma cada hora empezada "
                  "más allá del minuto de inicio. En los tramos del medio va en 0")

    class Meta:
        managed = False
        db_table = "tarifa_tramos"
        ordering = ["desde_minuto"]

    def __str__(self):
        if float(self.monto_fijo) == 0 and float(self.precio_por_hora_adicional) == 0:
            return f"desde {self.desde_minuto} min: gratis"
        if float(self.precio_por_hora_adicional):
            return (f"desde {self.desde_minuto} min: Q{self.monto_fijo} + "
                    f"Q{self.precio_por_hora_adicional} por hora de más")
        return f"desde {self.desde_minuto} min: Q{self.monto_fijo}"


class Sesion(models.Model):
    placa = models.CharField(max_length=15)
    espacio = models.ForeignKey(
        Espacio, on_delete=models.DO_NOTHING, db_column="espacio_id",
        related_name="sesiones",
    )
    hora_entrada = models.DateTimeField()
    hora_salida = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(max_length=10)  # 'activa' | 'cerrada'

    class Meta:
        managed = False
        db_table = "sesiones"

    def __str__(self):
        return f"{self.placa} en {self.espacio_id}"


class Cobro(models.Model):
    sesion = models.OneToOneField(
        Sesion, on_delete=models.DO_NOTHING, db_column="sesion_id",
        related_name="cobro",
    )
    tarifa = models.ForeignKey(Tarifa, on_delete=models.DO_NOTHING, db_column="tarifa_id")
    minutos_totales = models.IntegerField()
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_cobro = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = "cobros"
