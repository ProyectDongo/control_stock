
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F, Q
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.urls import reverse  
from django.utils import timezone
from .forms import UserRegistrationForm, ProductoForm, StockEntryForm, ProveedorForm, PedidoReposicionForm
from .models import Producto, Inventario, Proveedor, PedidoReposicion, Reporte, User, Transaction

@login_required
def dashboard(request):
    # Definir permisos por rol
    allowed_panels = {
        'trabajador': ['dashboard', 'ingreso', 'egreso'],
        'bodeguero': ['dashboard', 'ingreso', 'egreso', 'centro', 'concepto-ingreso', 'concepto-egreso', 'rcv'],
        'admin': ['dashboard', 'ingreso', 'egreso', 'centro', 'concepto-ingreso', 'concepto-egreso', 'rcv', 'parametros-sii'],
    }
    role = request.user.role
    active_panel = request.GET.get('panel', 'dashboard')
    if active_panel not in allowed_panels.get(role, []):
        messages.warning(request, 'No tienes acceso a esta sección.')
        active_panel = 'dashboard'

    empresa = {
        'nombre': 'Empresa de Productos Marinos Bentónicos',
        'rut': '76.123.456-7',
        'direccion': 'Calle Ficticia 123, Valdivia, Chile',
        'telefono': '+56 9 1234 5678'
    }
    vigencia_plan = {'codigo_plan': 'Prototipo Educativo'}
    
    # Cálculos para dashboard
    total_productos = Producto.objects.count()
    stock_bajo = Inventario.objects.filter(cantidad__lt=F('stock_minimo')).count()
    total_inventario = Inventario.objects.aggregate(total=Sum('cantidad'))['total'] or 0
    total_valor = Inventario.objects.annotate(val=F('cantidad') * F('producto__precio_unitario')).aggregate(sum_val=Sum('val'))['sum_val'] or 0
    
    # Inventarios con valor y ganancia estimada (asumiendo margen del 20%)
    inventarios = Inventario.objects.annotate(
        val=F('cantidad') * F('producto__precio_unitario'),
        ganancia_estimada=F('cantidad') * (F('producto__precio_venta') - F('producto__precio_unitario'))
    )
    
    total_costo = Inventario.objects.annotate(
        costo=F('cantidad') * F('producto__precio_unitario')
    ).aggregate(total=Sum('costo'))['total'] or 0

    total_venta_potencial = Inventario.objects.annotate(
        venta=F('cantidad') * F('producto__precio_venta')
    ).aggregate(total=Sum('venta'))['total'] or 0

    ganancia_estimada_total = total_venta_potencial - total_costo

    # Ganancia real (solo egresos registrados)
    ventas_realizadas = Transaction.objects.filter(tipo='egreso').annotate(
        valor=F('cantidad') * F('inventario__producto__precio_venta')
    ).aggregate(total=Sum('valor'))['total'] or 0

    costo_vendido = Transaction.objects.filter(tipo='egreso').annotate(
        costo=F('cantidad') * F('inventario__producto__precio_unitario')
    ).aggregate(total=Sum('costo'))['total'] or 0

    ganancia_real = ventas_realizadas - costo_vendido

    # Últimos movimientos con valores
    ultimos_movimientos = Transaction.objects.select_related('inventario__producto').order_by('-fecha')[:20]
    for t in ultimos_movimientos:
        t.costo_total = t.cantidad * t.inventario.producto.precio_unitario
        t.venta_total = t.cantidad * t.inventario.producto.precio_venta

    # Pedidos vencidos
    hoy = timezone.now().date()
    pedidos_vencidos_qs = PedidoReposicion.objects.filter(
        fecha_vencimiento__lt=hoy,
        estado='Pendiente'
    )
    pedidos_vencidos = [(ped, (hoy - ped.fecha_vencimiento).days) for ped in pedidos_vencidos_qs]

    # Datos para gráficos (últimos 7 días, por ejemplo)
    from datetime import timedelta
    fecha_inicio = timezone.now().date() - timedelta(days=7)
    transacciones = Transaction.objects.filter(fecha__gte=fecha_inicio).order_by('fecha')
    from django.db.models.functions import TruncDate
    ingresos_por_dia = transacciones.filter(tipo='ingreso').annotate(dia=TruncDate('fecha')).values('dia').annotate(total=Sum('cantidad'))
    egresos_por_dia = transacciones.filter(tipo='egreso').annotate(dia=TruncDate('fecha')).values('dia').annotate(total=Sum('cantidad'))

    labels = [ (fecha_inicio + timedelta(days=i)).strftime('%d/%m') for i in range(8) ]
    ingresos = [0] * 8
    egresos = [0] * 8
    for ing in ingresos_por_dia:
        index = (ing['dia'] - fecha_inicio).days
        if 0 <= index < 8:
            ingresos[index] = ing['total']
    for egr in egresos_por_dia:
        index = (egr['dia'] - fecha_inicio).days
        if 0 <= index < 8:
            egresos[index] = egr['total']

    stock_data = {
        'labels': labels,
        'ingresos': ingresos,
        'egresos': egresos
    }

    # Ganancias estimadas por producto
    profits_data = {
        'labels': [inv.producto.nombre for inv in inventarios],
        'ganancias': [float(inv.ganancia_estimada or 0) for inv in inventarios]
    }

    # Listas (filtradas si es necesario, pero por ahora todas)
    proveedores = Proveedor.objects.all()
    productos = Producto.objects.all()
    pedidos = PedidoReposicion.objects.all()
    reportes = Reporte.objects.all()
    usuarios = User.objects.all()
    
    # Forms (con instances si edit)
    stock_entry_form = StockEntryForm(request.POST if request.POST.get('form_type') in ['ingreso', 'egreso'] else None)
    proveedor_form = ProveedorForm(request.POST if request.POST.get('form_type') == 'proveedor' else None)
    producto_form = ProductoForm(request.POST if request.POST.get('form_type') == 'producto' else None)
    pedido_form = PedidoReposicionForm(request.POST if request.POST.get('form_type') == 'pedido' else None)
    user_form = UserRegistrationForm(request.POST if request.POST.get('form_type') == 'usuario' else None)
    
    # Handle edit (set instance)
    edit_pk = None
    if request.method == 'GET':
        if 'edit_producto' in request.GET and role in ['bodeguero', 'admin']:
            edit_pk = request.GET['edit_producto']
            producto_form = ProductoForm(instance=get_object_or_404(Producto, pk=edit_pk))
            active_panel = 'concepto-ingreso'
        elif 'edit_proveedor' in request.GET and role in ['bodeguero', 'admin']:
            edit_pk = request.GET['edit_proveedor']
            proveedor_form = ProveedorForm(instance=get_object_or_404(Proveedor, pk=edit_pk))
            active_panel = 'centro'
        elif 'edit_pedido' in request.GET and role in ['bodeguero', 'admin']:
            edit_pk = request.GET['edit_pedido']
            pedido_form = PedidoReposicionForm(instance=get_object_or_404(PedidoReposicion, pk=edit_pk))
            active_panel = 'concepto-egreso'
    
    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        redirect_panel = active_panel
        
        if form_type in ['ingreso', 'egreso']:
            if stock_entry_form.is_valid():
                producto = stock_entry_form.cleaned_data['producto']
                cantidad = stock_entry_form.cleaned_data['cantidad']
                inv, _ = Inventario.objects.get_or_create(producto=producto, defaults={'stock_minimo': 10})
                if form_type == 'ingreso':
                    inv.cantidad += cantidad
                else:
                    inv.cantidad -= cantidad
                    if inv.cantidad < 0:
                        inv.cantidad = 0
                inv.save()
                # Registrar transacción
                Transaction.objects.create(
                    inventario=inv,
                    tipo=form_type,
                    cantidad=cantidad
                )
                messages.success(request, f'{form_type.capitalize()} registrado exitosamente.')
                redirect_panel = 'dashboard'
            else:
                messages.error(request, 'Error en el formulario de stock.')
        
        elif form_type == 'producto' and role in ['bodeguero', 'admin']:
            pk = request.POST.get('pk')
            instance = get_object_or_404(Producto, pk=pk) if pk else None
            producto_form = ProductoForm(request.POST, instance=instance)
            if producto_form.is_valid():
                producto_form.save()
                messages.success(request, 'Producto guardado exitosamente.')
            else:
                messages.error(request, 'Error en el formulario de producto.')
            redirect_panel = 'concepto-ingreso'
        
        elif form_type == 'delete_producto' and role in ['bodeguero', 'admin']:
            pk = request.POST.get('pk')
            get_object_or_404(Producto, pk=pk).delete()
            messages.success(request, 'Producto eliminado.')
            redirect_panel = 'concepto-ingreso'
        
        elif form_type == 'proveedor' and role in ['bodeguero', 'admin']:
            pk = request.POST.get('pk')
            instance = get_object_or_404(Proveedor, pk=pk) if pk else None
            proveedor_form = ProveedorForm(request.POST, instance=instance)
            if proveedor_form.is_valid():
                proveedor_form.save()
                messages.success(request, 'Proveedor guardado exitosamente.')
            else:
                messages.error(request, 'Error en el formulario de proveedor.')
            redirect_panel = 'centro'
        
        elif form_type == 'delete_proveedor' and role in ['bodeguero', 'admin']:
            pk = request.POST.get('pk')
            get_object_or_404(Proveedor, pk=pk).delete()
            messages.success(request, 'Proveedor eliminado.')
            redirect_panel = 'centro'
        
        elif form_type == 'pedido' and role in ['bodeguero', 'admin']:
            pk = request.POST.get('pk')
            instance = get_object_or_404(PedidoReposicion, pk=pk) if pk else None
            pedido_form = PedidoReposicionForm(request.POST, instance=instance)
            if pedido_form.is_valid():
                pedido_form.save()
                messages.success(request, 'Pedido guardado exitosamente.')
            else:
                messages.error(request, 'Error en el formulario de pedido.')
            redirect_panel = 'concepto-egreso'
        
        elif form_type == 'delete_pedido' and role in ['bodeguero', 'admin']:
            pk = request.POST.get('pk')
            get_object_or_404(PedidoReposicion, pk=pk).delete()
            messages.success(request, 'Pedido eliminado.')
            redirect_panel = 'concepto-egreso'
        
        elif form_type == 'reporte' and role in ['bodeguero', 'admin']:
            tipo = request.POST.get('tipo')
            fecha_desde = request.POST.get('fecha_desde')
            fecha_hasta = request.POST.get('fecha_hasta')
            content = ''
            qs = Transaction.objects.all()
            if fecha_desde:
                qs = qs.filter(fecha__gte=fecha_desde)
            if fecha_hasta:
                qs = qs.filter(fecha__lte=fecha_hasta)
            if tipo == 'Ingreso':
                qs = qs.filter(tipo='ingreso')
                content = "\n".join([f"{t.inventario.producto.nombre}: +{t.cantidad} el {t.fecha}" for t in qs])
            elif tipo == 'Egreso':
                qs = qs.filter(tipo='egreso')
                content = "\n".join([f"{t.inventario.producto.nombre}: -{t.cantidad} el {t.fecha}" for t in qs])
            elif tipo == 'Resumen':
                inventarios_list = Inventario.objects.all()
                content = "\n".join([f"{inv.producto.nombre}: {inv.cantidad} (Valor: {inv.cantidad * inv.producto.precio_venta})" for inv in inventarios_list])
            if content:
                Reporte.objects.create(tipo=tipo, contenido=content)
                messages.success(request, f'Reporte de {tipo} generado.')
            else:
                messages.error(request, 'Tipo de reporte inválido o no hay datos.')
            redirect_panel = 'rcv'
        
        elif form_type == 'usuario' and role == 'admin':
            if user_form.is_valid():
                user_form.save()
                messages.success(request, 'Usuario registrado.')
            else:
                messages.error(request, 'Error en el formulario de usuario.')
            redirect_panel = 'parametros-sii'
        
        else:
            messages.error(request, 'Acción no permitida para tu rol.')
            redirect_panel = 'dashboard'
        
        # Use reverse for the view name and append query param
        return redirect(reverse('dashboard') + f'?panel={redirect_panel}')
        
    context = {
        'empresa': empresa,
        'vigencia_plan': vigencia_plan,
        'total_productos': total_productos,
        'stock_bajo': stock_bajo,
        'total_inventario': total_inventario,
        'total_valor': total_valor,
        'inventarios': inventarios,
        'pedidos_vencidos': pedidos_vencidos,
        'stock_data': stock_data,
        'profits_data': profits_data,
        'proveedores': proveedores,
        'productos': productos,
        'pedidos': pedidos,
        'reportes': reportes,
        'usuarios': usuarios,
        'stock_entry_form': stock_entry_form,
        'proveedor_form': proveedor_form,
        'producto_form': producto_form,
        'pedido_form': pedido_form,
        'user_form': user_form,
        'active_panel': active_panel,
        'role': role,  # Para usar en template si es necesario
        'ganancia_real': int(ganancia_real or 0),
        'ganancia_estimada_total': int(ganancia_estimada_total or 0),
        'ultimos_movimientos': ultimos_movimientos,
    }
    return render(request, 'dashboard.html', context)

def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, 'Inicio de sesión exitoso.')
            return redirect('dashboard')
        else:
            messages.error(request, 'Credenciales inválidas.')
    return render(request, 'login.html')

def user_logout(request):
    logout(request)
    messages.success(request, 'Sesión cerrada.')
    return redirect('login')