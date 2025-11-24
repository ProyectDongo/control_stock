# core/views.py
# =================================================================
# VISTA PRINCIPAL: dashboard()
# =================================================================
# Esta es una vista "todo en uno" que maneja:
# - Dashboard con estadísticas
# - Todos los formularios (ingreso, egreso, productos, etc.)
# - Control de permisos por rol
# - Generación de reportes
# - Edición inline mediante GET parameters

@login_required
def dashboard(request):
    """
    Vista principal del sistema. Un solo template con múltiples paneles.
    Usa el parámetro ?panel=nombre para cambiar de sección.
    """
    # === CONTROL DE PERMISOS ===
    allowed_panels = {
        'trabajador': ['dashboard', 'ingreso', 'egreso'],
        'bodeguero': ['dashboard', 'ingreso', 'egreso', 'centro', 'concepto-ingreso', 
                      'concepto-egreso', 'rcv'],
        'admin': ['dashboard', 'ingreso', 'egreso', 'centro', 'concepto-ingreso', 
                 'concepto-egreso', 'rcv', 'parametros-sii'],
    }
    
    active_panel = request.GET.get('panel', 'dashboard')
    if active_panel not in allowed_panels.get(request.user.role, []):
        active_panel = 'dashboard'
        messages.warning(request, 'Acceso denegado a esta sección.')

    # === ESTADÍSTICAS Y GRÁFICOS ===
    # Total productos, stock bajo, valor del inventario, ganancias reales y estimadas
    # Gráficos de últimos 7 días (ingresos vs egresos)
    # Ganancia potencial por producto

    # === PROCESAMIENTO DE FORMULARIOS ===
    # Todos los formularios POST se manejan aquí mediante el campo oculto 'form_type'
    # Soporta: ingreso, egreso, producto, proveedor, pedido, reporte, usuario

    # === EDICIÓN INLINE ===
    # Usa parámetros GET como ?edit_producto=5 para precargar formularios

    # === REDIRECCIÓN INTELIGENTE ===
    # Al enviar formulario, redirige al panel correcto manteniendo el flujo

    return render(request, 'dashboard.html', context)