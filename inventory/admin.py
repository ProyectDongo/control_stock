from django.contrib import admin
from .models import User, Producto, Inventario, Proveedor, PedidoReposicion, Reporte,Transaction
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm

class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'role', 'is_staff', 'is_active', 'is_superuser')

class CustomUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = ('username', 'email', 'role', 'is_staff', 'is_active', 'is_superuser')

class UserAdmin(BaseUserAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm

    list_display = ('username', 'email', 'role', 'is_staff')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'role')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Información personal', {'fields': ('email', 'role')}),
        ('Permisos', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'role', 'password1', 'password2', 'is_staff', 'is_active', 'is_superuser'),
        }),
    )
    search_fields = ('username', 'email')
    ordering = ('username',)
    filter_horizontal = ()

# Registra el modelo User con el UserAdmin personalizado
admin.site.register(User, UserAdmin)
admin.site.register(Inventario)
admin.site.register(Proveedor)
admin.site.register(PedidoReposicion)
admin.site.register(Reporte)
admin.site.register(Producto)
admin.site.register(Transaction)
