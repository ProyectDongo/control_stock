# core/forms.py
# =================================================================
# FORMULARIOS DEL SISTEMA
# =================================================================

class UserRegistrationForm(UserCreationForm):
    """Registro de usuarios con rol personalizado"""
    role = forms.ChoiceField(choices=User.ROLE_CHOICES)

    class Meta:
        model = User
        fields = ['username', 'password1', 'password2', 'role']

class ProductoForm(forms.ModelForm):
    """CRUD completo de productos"""
    class Meta:
        model = Producto
        fields = '__all__'

class StockEntryForm(forms.Form):
    """
    Formulario reutilizado para ingresos y egresos de stock
    Usa campo oculto 'form_type' para distinguir acción
    """
    producto = forms.ModelChoiceField(queryset=Producto.objects.all())
    cantidad = forms.IntegerField(min_value=1)

class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = '__all__'

class PedidoReposicionForm(forms.ModelForm):
    """
    Formulario para crear/editar pedidos de reposición
    No incluye fecha_vencimiento (se puede agregar después)
    """
    class Meta:
        model = PedidoReposicion
        fields = ['proveedor', 'producto', 'cantidad', 'estado']