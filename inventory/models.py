from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.utils import timezone

class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Administrador'),
        ('bodeguero', 'Bodeguero'),
        ('trabajador', 'Trabajador'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='trabajador')
    rut = models.CharField(max_length=12, unique=True, null=True, blank=True)

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

class Producto(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField()
    unidad = models.CharField(max_length=50)  # e.g., kg, unidad
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], verbose_name="Precio Costo")
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], default=0, verbose_name="Precio Venta")

    def __str__(self):
        return self.nombre

class Inventario(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField(default=0)
    stock_minimo = models.PositiveIntegerField(default=10)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.producto.nombre} - {self.cantidad}"

    def needs_replenishment(self):
        return self.cantidad < self.stock_minimo

@receiver(post_save, sender=Inventario)
def check_stock_alert(sender, instance, **kwargs):
    if instance.needs_replenishment():
        send_mail(
            'Alerta de Stock Crítico',
            f'El stock de {instance.producto.nombre} es {instance.cantidad}, por debajo del mínimo {instance.stock_minimo}.',
            'from@example.com',
            ['admin@example.com'],
            fail_silently=False,
        )

class Transaction(models.Model):
    TIPO_CHOICES = (
        ('ingreso', 'Ingreso'),
        ('egreso', 'Egreso'),
    )
    inventario = models.ForeignKey(Inventario, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    cantidad = models.PositiveIntegerField()
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.tipo} de {self.cantidad} para {self.inventario.producto.nombre}"

class Proveedor(models.Model):
    nombre = models.CharField(max_length=100)
    contacto = models.CharField(max_length=100)
    email = models.EmailField()
    telefono = models.CharField(max_length=20)

    def __str__(self):
        return self.nombre

class PedidoReposicion(models.Model):
    proveedor = models.ForeignKey(Proveedor, on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()
    fecha_pedido = models.DateTimeField(auto_now_add=True)
    fecha_vencimiento = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=50, default='Pendiente')  # Pendiente, Completado, etc.

    def __str__(self):
        return f"Pedido {self.id} - {self.producto.nombre}"

    def esta_vencido(self):
        if self.fecha_vencimiento and self.estado == 'Pendiente':
            return timezone.now().date() > self.fecha_vencimiento
        return False

@receiver(post_save, sender=PedidoReposicion)
def notify_new_pedido(sender, instance, created, **kwargs):
    if created:
        send_mail(
            'Nuevo Pedido Añadido',
            f'Se ha añadido un nuevo pedido para {instance.producto.nombre} de {instance.cantidad} unidades del proveedor {instance.proveedor.nombre}.',
            'from@example.com',
            ['admin@example.com'],
            fail_silently=False,
        )

class Reporte(models.Model):
    tipo = models.CharField(max_length=100)  # e.g., Inventario, Proveedores
    fecha = models.DateTimeField(auto_now_add=True)
    contenido = models.TextField()  # JSON or text summary

    def __str__(self):
        return f"{self.tipo} - {self.fecha}"