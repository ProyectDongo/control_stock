from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, RegexValidator
from django.db.models.signals import post_save, pre_save, pre_delete
from django.dispatch import receiver
from django.core.mail import send_mail
from django.forms import ValidationError
from django.utils import timezone
from django.db import transaction
from django.db.models import F, Case, When, Value

class Empresa(models.Model):
    nombre = models.CharField(max_length=200)
    rut = models.CharField(max_length=12, unique=True,
        validators=[RegexValidator(r'^\d{1,8}-[0-9kK]$', 'Formato de RUT inválido.')])
    direccion = models.CharField(max_length=300)
    telefono = models.CharField(max_length=20,
        validators=[RegexValidator(r'^\+?\d{1,3}?[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}$', 'Formato de teléfono inválido.')])
    def __str__(self):
        return self.nombre

class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Administrador'),
        ('bodeguero', 'Bodeguero'),
        ('trabajador', 'Trabajador'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='trabajador')
    rut = models.CharField(
        max_length=12, unique=True, null=True, blank=True,
        validators=[RegexValidator(r'^\d{1,8}-[0-9kK]$', 'Formato de RUT inválido.')]
    )
    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

class Producto(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField()
    unidad = models.CharField(max_length=50)
    precio_unitario = models.PositiveIntegerField(
         validators=[MinValueValidator(1)],
        verbose_name="Precio Costo"
    )
    precio_venta = models.PositiveIntegerField(
          validators=[MinValueValidator(1)],
        default=0, verbose_name="Precio Venta"
    )
    def __str__(self):
        return self.nombre
    def clean(self):
        if self.precio_venta < self.precio_unitario:
            raise ValidationError("Precio venta no puede ser menor que costo.")

class Inventario(models.Model):
    producto = models.OneToOneField(Producto, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField(default=0)
    stock_reservado = models.PositiveIntegerField(default=0)
    stock_minimo = models.PositiveIntegerField(default=10, validators=[MinValueValidator(1)])
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    def __str__(self):
        return f"{self.producto.nombre} - {self.cantidad}"
    def needs_replenishment(self):
        disponible = self.cantidad - self.stock_reservado
        return disponible < self.stock_minimo

# Signal para alerta de stock bajo (Opcional: Si falla el correo, usa fail_silently=True)
@receiver(post_save, sender=Inventario)
def check_stock_alert(sender, instance, **kwargs):
    if instance.needs_replenishment():
        # fail_silently=True evita que se caiga el sistema si no hay internet
        send_mail(
            'Alerta de Stock Crítico',
            f'El stock disponible de {instance.producto.nombre} es {instance.cantidad - instance.stock_reservado}, por debajo del mínimo {instance.stock_minimo}.',
            'from@example.com',
            ['admin@example.com'],
            fail_silently=True, 
        )

class Transaction(models.Model):
    TIPO_CHOICES = (
        ('ingreso', 'Ingreso'),
        ('egreso', 'Egreso'),
    )
    inventario = models.ForeignKey(Inventario, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    cantidad = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    fecha = models.DateTimeField(auto_now_add=True)
    descripcion = models.CharField(max_length=255, blank=True, null=True)
    def __str__(self):
        return f"{self.tipo} de {self.cantidad} para {self.inventario.producto.nombre}"

class Proveedor(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    contacto = models.CharField(max_length=100)
    email = models.EmailField(
        max_length=254,
        unique=True,
        blank=True,
        null=True,
        error_messages={
            'invalid': 'Por favor ingresa un correo electrónico válido.',
            'unique': 'Ya existe un proveedor con este correo.'
        }
    )
    telefono = models.CharField(
        max_length=20,
        validators=[RegexValidator(r'^\+?\d{1,3}?[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}$', 'Formato inválido.')]
    )
    def __str__(self):
        return self.nombre

class Pedido(models.Model):
    ESTADOS = (
        ('Pendiente', 'Pendiente'),
        ('Entransito', 'En tránsito'),
        ('Completado', 'Completado'),
        ('Cancelado', 'Cancelado'),
    )
    proveedor = models.ForeignKey(Proveedor, on_delete=models.CASCADE)
    fecha_pedido = models.DateTimeField(auto_now_add=True)
    fecha_vencimiento = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='Pendiente')
    
    def __str__(self):
        return f"Pedido {self.id} - {self.proveedor.nombre}"
        
    def esta_vencido(self):
        if self.fecha_vencimiento and self.estado == 'Pendiente':
            return timezone.now().date() > self.fecha_vencimiento
        return False
        
    def clean(self):
        if self.fecha_vencimiento and self.fecha_vencimiento < timezone.now().date():
            raise ValidationError("La fecha de vencimiento no puede ser anterior a hoy.")

# --- SIGNALS CORREGIDOS (Sin envío de mail, solo lógica de stock) ---

@receiver(pre_save, sender=Pedido)
def gestion_cambio_estado(sender, instance, **kwargs):
    if not instance.pk: return # La creación la maneja la vista

    try:
        old = Pedido.objects.get(pk=instance.pk)
    except Pedido.DoesNotExist: return

    reservan = ['Pendiente', 'Entransito']
    
    # CASO: CANCELAR (Devolver reserva)
    if old.estado in reservan and instance.estado == 'Cancelado':
        for item in old.items.all():
            Inventario.objects.filter(producto=item.producto).update(
                stock_reservado=F('stock_reservado') - item.cantidad
            )

    # CASO: COMPLETAR (Consumir stock real y quitar reserva)
    elif old.estado in reservan and instance.estado == 'Completado':
        for item in old.items.all():
            # 1. Registrar Historial
            Transaction.objects.create(
                inventario=item.producto.inventario,
                tipo='egreso',
                cantidad=item.cantidad,
                descripcion=f"Pedido Completado #{instance.id}"
            )
            # 2. Actualizar Inventario (Resta cantidad, Quita reserva)
            Inventario.objects.filter(producto=item.producto).update(
                cantidad=F('cantidad') - item.cantidad,
                stock_reservado=F('stock_reservado') - item.cantidad
            )

@receiver(pre_delete, sender=Pedido)
def liberar_al_eliminar(sender, instance, **kwargs):
    if instance.estado in ['Pendiente', 'Entransito']:
        for item in instance.items.all():
            Inventario.objects.filter(producto=item.producto).update(
                stock_reservado=F('stock_reservado') - item.cantidad
            )

class PedidoItem(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='items')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE ,null=False)
    cantidad = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    def __str__(self):
        return f"{self.cantidad} de {self.producto.nombre}"

class Reporte(models.Model):
    tipo = models.CharField(max_length=100)
    fecha = models.DateTimeField(auto_now_add=True)
    contenido = models.TextField()
    def __str__(self):
        return f"{self.tipo} - {self.fecha}"