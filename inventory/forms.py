from django import forms
from django.contrib.auth.forms import UserCreationForm
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django.utils import timezone
from .models import User, Producto, Inventario, Proveedor, Pedido, PedidoItem
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.forms import inlineformset_factory

class UserRegistrationForm(UserCreationForm):
    role = forms.ChoiceField(choices=User.ROLE_CHOICES, label="Rol de usuario")
    rut = forms.CharField(
        max_length=12,
        validators=[RegexValidator(r'^\d{1,8}-[\dkK]$', 'Formato de RUT inválido (ej: 12345678-9).')],
        error_messages={'unique': 'Este RUT ya está registrado.'}
    )

    class Meta:
        model = User
        fields = ['username', 'password1', 'password2', 'role', 'rut']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Registrar Usuario', css_class='btn-success'))

    def clean_rut(self):
        rut = self.cleaned_data.get('rut')
        if User.objects.filter(rut=rut).exists():
            raise ValidationError("Este RUT ya está en uso.")
        return rut

class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = '__all__'
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 3}),
            'precio_unitario': forms.TextInput(attrs={'placeholder': 'Ej: 10000 o 10.000 o 10,000.00'}),
            'precio_venta': forms.TextInput(attrs={'placeholder': 'Ej: 15000 o 15.000 o 15,000.00'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Guardar Producto', css_class='btn-primary'))

    def clean(self):
        cleaned_data = super().clean()
        for campo in ['precio_unitario', 'precio_venta']:
            valor_raw = self.data.get(campo)
            if valor_raw:
                valor_limpio = valor_raw.replace('.', '').replace(',', '')
                try:
                    valor_decimal = Decimal(valor_limpio)
                    if valor_decimal < 0:
                        cleaned_data[campo] = abs(valor_decimal) 
                    elif valor_decimal <= 0:
                        self.add_error(campo, "El precio debe ser mayor que 0.")
                    cleaned_data[campo] = valor_decimal
                except (InvalidOperation, ValueError):
                    self.add_error(campo, "Formato de precio inválido. Usa números, punto o coma.")
            else:
                self.add_error(campo, f"El {campo.replace('_', ' ')} es requerido y debe ser positivo.")

        costo = cleaned_data.get('precio_unitario')
        venta = cleaned_data.get('precio_venta')
        if costo and venta and venta < costo:
            self.add_error('precio_venta', "El precio de venta no puede ser menor que el precio costo.")

        return cleaned_data

    def clean_unidad(self):
        unidad = self.cleaned_data.get('unidad')
        try:
            num = float(unidad)
            if num < 0:
                unidad = str(abs(num))  
        except ValueError:
            pass 
        if not unidad:
            raise ValidationError("La unidad es requerida.")
        return unidad

class StockEntryForm(forms.Form):
    producto = forms.ModelChoiceField(
        queryset=Producto.objects.all().order_by('nombre'),
        label="Producto",
        empty_label="Seleccione un producto"
    )
    cantidad = forms.IntegerField(
        min_value=1,
        label="Cantidad",
        widget=forms.NumberInput(attrs={'min': 1, 'step': 1, 'class': 'form-control'}),
        error_messages={
            'min_value': 'La cantidad no puede ser negativa ni cero.',
            'invalid': 'Debe ingresar un número entero válido.',
            'required': 'El campo Cantidad es obligatorio.'
        }
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'

    def clean_cantidad(self):
        cantidad = self.cleaned_data.get('cantidad')
        if cantidad < 0:
            cantidad = abs(cantidad)  
        return cantidad

class StockExitForm(forms.Form):
    producto = forms.ModelChoiceField(
        queryset=Producto.objects.all().order_by('nombre'),
        label="Producto",
        empty_label="Seleccione un producto"
    )
    cantidad = forms.IntegerField(
        min_value=1,
        label="Cantidad a sacar",
        widget=forms.NumberInput(attrs={'min': 1, 'step': 1}),
        error_messages={
            'min_value': 'La cantidad no puede ser negativa ni cero.',
            'invalid': 'Debe ingresar un número entero válido.',
            'required': 'El campo Cantidad es obligatorio.'
        }
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'

    def clean(self):
        cleaned_data = super().clean()
        producto = cleaned_data.get('producto')
        cantidad = cleaned_data.get('cantidad')
        if cantidad < 0:
            cleaned_data['cantidad'] = abs(cantidad)  
            try:
                inventario = Inventario.objects.get(producto=producto)
                disponible = inventario.cantidad - inventario.stock_reservado
                if cantidad > disponible:
                    raise ValidationError(f"No hay suficiente stock disponible. Disponible: {disponible}, solicitaste {cantidad}.")
                if cantidad <= 0:
                    raise ValidationError("La cantidad debe ser positiva.")
            except Inventario.DoesNotExist:
                raise ValidationError("Este producto no tiene registro en inventario.")
        
        return cleaned_data

class ProveedorForm(forms.ModelForm):
    telefono = forms.CharField(
        max_length=20,
        validators=[RegexValidator(r'^\+?\d{1,3}?[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}$', 'Formato de teléfono inválido (ej: +56 9 1234 5678).')]
    )

    class Meta:
        model = Proveedor
        fields = '__all__'
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'Ej: Distribuidora XYZ'}),
            'contacto': forms.TextInput(attrs={'placeholder': 'Juan Pérez'}),
            'email': forms.EmailInput(attrs={'placeholder': 'juan@proveedor.cl'}),
            'telefono': forms.TextInput(attrs={'placeholder': '+56 9 8765 4321'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Guardar Proveedor', css_class='btn-primary'))
        # Opcional: hacer que no sea requerido visualmente
        self.fields['email'].required = False

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get('email'):
            self.add_error('email', "El email es requerido.")
        return cleaned_data

class PedidoForm(forms.ModelForm):
    class Meta:
        model = Pedido
        fields = ['proveedor', 'estado', 'fecha_vencimiento']
        widgets = {
            'fecha_vencimiento': forms.DateInput(attrs={'type': 'date'}),
            'estado': forms.Select(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_tag = False

    def clean(self):
        cleaned_data = super().clean()
        fecha = cleaned_data.get('fecha_vencimiento')
        if fecha and fecha < timezone.now().date():
            raise ValidationError("La fecha de vencimiento no puede ser pasada.")
        return cleaned_data

PedidoItemFormSet = inlineformset_factory(
    Pedido, PedidoItem, fields=('producto', 'cantidad'), extra=1, can_delete=True,
    widgets={
        'producto': forms.Select(attrs={'class': 'form-control'}),
        'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
    }
)