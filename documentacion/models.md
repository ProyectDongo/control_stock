
---

### Documentación Detallada de Modelos (`models.py`)

```python
# core/models.py
# =================================================================
# MODELOS DEL SISTEMA DE GESTIÓN DE STOCK
# =================================================================

class User(AbstractUser):
    """
    Extensión del modelo User de Django con rol personalizado.
    Roles disponibles: admin, bodeguero, trabajador
    """
    ROLE_CHOICES = (
        ('admin', 'Administrador'),
        ('bodeguero', 'Bodeguero'),
        ('trabajador', 'Trabajador'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='trabajador')
    rut = models.CharField(max_length=12, unique=True, null=True, blank=True, help_text="RUT chileno con puntos y guión")

class Producto(models.Model):
    """
    Representa un producto marino bentónico (loco, almeja, erizo, etc.)
    """
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(help_text="Descripción detallada del producto")
    unidad = models.CharField(max_length=50, default="kg", help_text="Ej: kg, unidad, docena")
    precio_unitario = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Precio Costo"
    )
    precio_venta = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(0)],
        default=0,
        verbose_name="Precio Venta"
    )

    def __str__(self):
        return self.nombre

class Inventario(models.Model):
    """
    Stock físico actual de cada producto.
    Se crea automáticamente al registrar movimientos.
    """
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField(default=0)
    stock_minimo = models.PositiveIntegerField(default=10, help_text="Umbral para alerta")
    fecha_actualización = models.DateTimeField(auto_now=True)

    def needs_replenishment(self):
        """Devuelve True si el stock está bajo"""
        return self.cantidad < self.stock_minimo

    def __str__(self):
        return f"{self.producto.nombre} - {self.cantidad} {self.producto.unidad}"

# Signal: Envía email cuando el stock baja del mínimo
@receiver(post_save, sender=Inventario)
def check_stock_alert(sender, instance, **kwargs):
    if instance.needs_replenishment():
        send_mail(
            subject='Alerta de Stock Crítico',
            message=f'El stock de {instance.producto.nombre} es {instance.cantidad}, '
                    f'por debajo del mínimo {instance.stock_minimo}.',
            from_email='from@example.com',
            recipient_list=['admin@example.com'],
        )

class Transaction(models.Model):
    """
    Registro histórico de movimientos de stock (ingreso o egreso)
    """
    TIPO_CHOICES = (('ingreso', 'Ingreso'), ('egreso', 'Egreso'))
    inventario = models.ForeignKey(Inventario, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    cantidad = models.PositiveIntegerField()
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.tipo.title()} de {self.cantidad} {self.inventario.producto.unidad}"

class Proveedor(models.Model):
    """
    Proveedores de productos marinos
    """
    nombre = models.CharField(max_length=100)
    contacto = models.CharField(max_length=100)
    email = models.EmailField()
    telefono = models.CharField(max_length=20)

    def __str__(self):
        return self.nombre

class PedidoReposicion(models.Model):
    """
    Pedidos de reposición a proveedores
    """
    proveedor = models.ForeignKey(Proveedor, on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()
    fecha_pedido = models.DateTimeField(auto_now_add=True)
    fecha_vencimiento = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=50, default='Pendiente')

    def esta_vencido(self):
        """Verifica si el pedido está vencido y pendiente"""
        if self.fecha_vencimiento and self.estado == 'Pendiente':
            return timezone.now().date() > self.fecha_vencimiento
        return False

    def __str__(self):
        return f"Pedido {self.producto.nombre} - {self.proveedor.nombre}"

# Signal: Notifica nuevo pedido
@receiver(post_save, sender=PedidoReposicion)
def notify_new_pedido(sender, instance, created, **kwargs):
    if created:
        send_mail(
            'Nuevo Pedido de Reposición',
            f'Nuevo pedido de {instance.cantidad} {instance.producto.unidad} '
            f'de {instance.producto.nombre} al proveedor {instance.proveedor.nombre}.',
            'from@example.com',
            ['admin@example.com'],
        )

class Reporte(models.Model):
    """
    Reportes generados por el sistema (texto plano)
    """
    tipo = models.CharField(max_length=100)
    fecha = models.DateTimeField(auto_now_add=True)
    contenido = models.TextField()  # Puede ser texto plano o JSON

    def __str__(self):
        return f"{self.tipo} - {self.fecha.strftime('%d/%m/%Y')}"