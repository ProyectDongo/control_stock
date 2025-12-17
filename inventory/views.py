
from django.forms import ValidationError
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F, Q
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.urls import reverse  
from django.utils import timezone
from .forms import UserRegistrationForm, ProductoForm, StockEntryForm, ProveedorForm, PedidoForm, PedidoItemFormSet, StockExitForm
from .models import Producto, Inventario, Proveedor, Pedido, PedidoItem, Reporte, User, Transaction, Empresa
from django.db import transaction  
import qrcode
from io import BytesIO
import base64
from datetime import datetime, timedelta  
from django.utils import timezone
from django.core.paginator import Paginator

@login_required
def dashboard(request):
    # Definir permisos por rol
    allowed_panels = {
        'trabajador': ['dashboard', 'ingreso', 'egreso', 'lista-pedidos'],
        'bodeguero': ['dashboard', 'ingreso', 'egreso', 'centro', 'concepto-ingreso', 'concepto-egreso', 'rcv', 'lista-pedidos'],
        'admin': ['dashboard', 'ingreso', 'egreso', 'centro', 'concepto-ingreso', 'concepto-egreso', 'rcv', 'parametros-sii', 'lista-pedidos'],
    }
    role = request.user.role
    active_panel = request.GET.get('panel', 'dashboard')
    if active_panel not in allowed_panels.get(role, []):
        messages.warning(request, 'No tienes acceso a esta sección.')
        active_panel = 'dashboard'
  
    vigencia_plan = {'codigo_plan': 'Prototipo Educativo'}
    
    # Obtener datos de la empresa (una sola empresa para el software)
    empresa = Empresa.objects.first()
    
    # Cálculos para dashboard
    total_productos = Producto.objects.count()
    inventarios = Inventario.objects.annotate(
        disponible=F('cantidad') - F('stock_reservado')
    )
    stock_bajo = inventarios.filter(disponible__lt=F('stock_minimo')).count()
    total_inventario = Inventario.objects.aggregate(total=Sum('cantidad'))['total'] or 0
    total_reservado = Inventario.objects.aggregate(total=Sum('stock_reservado'))['total'] or 0
    total_disponible = total_inventario - total_reservado
    total_valor = Inventario.objects.annotate(val=F('cantidad') * F('producto__precio_unitario')).aggregate(sum_val=Sum('val'))['sum_val'] or 0
    movimientos_qs = Transaction.objects.select_related('inventario__producto').order_by('-fecha')

    for t in movimientos_qs:
        t.costo_total = t.cantidad * t.inventario.producto.precio_unitario
        t.venta_total = t.cantidad * t.inventario.producto.precio_venta
        if t.tipo == 'ingreso':
            t.valor_display = t.costo_total
        else:
            t.valor_display = -(t.venta_total - t.costo_total)

    # Paginación de movimientos (10 por página)
    paginator_mov = Paginator(movimientos_qs, 10)
    page_mov = request.GET.get('page_mov', 1)
    ultimos_movimientos = paginator_mov.get_page(page_mov)

    # Inventario - PAGINACIÓN
    paginator_inv = Paginator(inventarios, 10)
    page_inv = request.GET.get('page_inv', 1)
    inventarios_paginados = paginator_inv.get_page(page_inv)
    
    # Inventarios con valor y ganancia estimada (asumiendo margen del 20%)
    inventarios = inventarios.annotate(
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
    

    # Pedidos vencidos
    hoy = timezone.now().date()
    pedidos_vencidos_qs = Pedido.objects.filter(
        fecha_vencimiento__lt=hoy,
        estado='Pendiente'
    )
    pedidos_vencidos = [(ped, (hoy - ped.fecha_vencimiento).days) for ped in pedidos_vencidos_qs]

    # Datos para gráficos 
    fecha_inicio = timezone.now() - timedelta(days=7)
    fecha_inicio = fecha_inicio.replace(hour=0, minute=0, second=0, microsecond=0)
    transacciones = Transaction.objects.filter(fecha__gte=fecha_inicio).order_by('fecha')
    from django.db.models.functions import TruncDate
    ingresos_por_dia = transacciones.filter(tipo='ingreso').annotate(dia=TruncDate('fecha')).values('dia').annotate(total=Sum('cantidad'))
    egresos_por_dia = transacciones.filter(tipo='egreso').annotate(dia=TruncDate('fecha')).values('dia').annotate(total=Sum('cantidad'))

    labels = [ (fecha_inicio + timedelta(days=i)).strftime('%d/%m') for i in range(8) ]
    ingresos = [0] * 8
    egresos = [0] * 8
    for ing in ingresos_por_dia:
        index = (ing['dia'] - fecha_inicio.date()).days
        if 0 <= index < 8:
            ingresos[index] = ing['total']
    for egr in egresos_por_dia:
        index = (egr['dia'] - fecha_inicio.date()).days
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

    # Listas 
    proveedores = Proveedor.objects.all()
    productos = Producto.objects.all()
    pedidos = Pedido.objects.all().order_by('-fecha_pedido')  # Para lista de pedidos
    reportes = Reporte.objects.all()
    usuarios = User.objects.all()
    for rep in reportes:
        rep.lineas = []  # Lista de líneas procesadas
        rep.total_resumen = 0  # Total solo para Resumen

        for raw_line in rep.contenido.strip().split('\n'):
            if not raw_line.strip():
                continue
            
            if rep.tipo == 'Resumen':
                # Formato esperado: "Producto: cantidad (Valor: $valor_total)"
                try:
                    nombre, resto = raw_line.split(':', 1)
                    nombre = nombre.strip()
                    
                    # Extraer cantidad
                    cantidad_str = resto.split('(')[0].strip()
                    
                    # Extraer valor total (el que está entre $ y ))
                    valor_total_str = resto.split('$')[1].split(')')[0].strip()
                    valor_total = int(valor_total_str.replace('.', ''))
                    
                    # Obtener precio unitario de venta desde el inventario
                    inv = Inventario.objects.get(producto__nombre__icontains=nombre)
                    precio_venta = inv.producto.precio_venta
                    
                    # Acumular total
                    rep.total_resumen += valor_total
                except Exception:
                    # Si falla el parsing, mostramos la línea cruda
                    nombre = raw_line.strip()
                    cantidad_str = 'N/A'
                    precio_venta = 0
                    valor_total = 0
                
                rep.lineas.append({
                    'nombre': nombre,
                    'cantidad': cantidad_str,
                    'precio_venta': precio_venta,
                    'valor_total': valor_total
                })
            else:
                # Para Ingreso/Egreso: solo el texto completo
                rep.lineas.append({
                    'texto': raw_line.strip()
                })
    # Forms 
    stock_entry_form = StockEntryForm(
        request.POST if request.POST.get('form_type') == 'ingreso' else None, 
        prefix='ingreso'
    )
    stock_exit_form = StockExitForm(
        request.POST if request.POST.get('form_type') == 'egreso' else None, 
        prefix='egreso'
    )
    proveedor_form = ProveedorForm(request.POST if request.POST.get('form_type') == 'proveedor' else None)
    producto_form = ProductoForm(request.POST if request.POST.get('form_type') == 'producto' else None)
    pedido_form = PedidoForm(request.POST if request.POST.get('form_type') == 'pedido' else None)
    pedido_item_formset = PedidoItemFormSet(request.POST if request.POST.get('form_type') == 'pedido' else None)
    user_form = UserRegistrationForm(request.POST if request.POST.get('form_type') == 'usuario' else None)

    # Filtros para lista de pedidos
    if active_panel == 'lista-pedidos':
        estado_filtro = request.GET.get('estado')
        proveedor_filtro = request.GET.get('proveedor')
        fecha_desde = request.GET.get('fecha_desde')
        fecha_hasta = request.GET.get('fecha_hasta')
        if estado_filtro:
            pedidos = pedidos.filter(estado=estado_filtro)
        if proveedor_filtro:
            pedidos = pedidos.filter(proveedor__id=proveedor_filtro)
        if fecha_desde:
            fecha_desde_dt = datetime.strptime(fecha_desde, '%Y-%m-%d')
            fecha_desde_dt = timezone.make_aware(fecha_desde_dt)
            pedidos = pedidos.filter(fecha_pedido__gte=fecha_desde_dt)
        if fecha_hasta:
            fecha_hasta_dt = datetime.strptime(fecha_hasta, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            fecha_hasta_dt = timezone.make_aware(fecha_hasta_dt)
            pedidos = pedidos.filter(fecha_pedido__lte=fecha_hasta_dt)

    redirect_url = None 
    
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
            pedido_instance = get_object_or_404(Pedido, pk=edit_pk)
            pedido_form = PedidoForm(instance=pedido_instance)
            pedido_item_formset = PedidoItemFormSet(instance=pedido_instance)
            active_panel = 'concepto-egreso'
    
    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        

        if form_type in ['ingreso', 'egreso']:
            form = stock_entry_form if form_type == 'ingreso' else stock_exit_form
            if form.is_valid():
                producto = form.cleaned_data['producto']
                cantidad = form.cleaned_data['cantidad']

                with transaction.atomic(): 
                    inv, _ = Inventario.objects.get_or_create(
                        producto=producto,
                        defaults={'stock_minimo': 10}
                    )
                    operacion_exitosa = False

                    if form_type == 'ingreso':
                        if cantidad <= 0:
                            messages.error(request, 'Cantidad debe ser positiva para ingreso.')
                        else:
                            inv.cantidad += cantidad
                            inv.save()
                            Transaction.objects.create(
                                inventario=inv,
                                tipo=form_type,
                                cantidad=cantidad
                            )
                            messages.success(request, 'Ingreso registrado.')
                            return redirect(reverse('dashboard'))
                    elif form_type == 'completar_pedido':
                            if role not in ['trabajador', 'bodeguero', 'admin']:
                                return JsonResponse({'success': False, 'message': 'No tienes permiso.'})
                            
                            pedido_id = request.POST.get('pedido_id')
                            try:
                                pedido = get_object_or_404(Pedido, pk=pedido_id)
                                if pedido.estado != 'Pendiente':
                                    return JsonResponse({'success': False, 'message': 'El pedido ya no está pendiente.'})
                                
                                with transaction.atomic():
                                    pedido.estado = 'Completado'
                                    pedido.save()  # Esto activará el post_save que hace el egreso y libera reserva
                                    
                                return JsonResponse({
                                    'success': True,
                                    'message': f'Pedido #{pedido_id} completado exitosamente. Stock actualizado.'
                                })
                            except Exception as e:
                                return JsonResponse({'success': False, 'message': str(e)})
                    elif form_type == 'egreso':
                        if cantidad <= 0:
                            messages.error(request, 'Cantidad debe ser positiva para egreso.')
                        elif cantidad > (inv.cantidad - inv.stock_reservado):  # Usar disponible en lugar de cantidad
                            messages.error(request, f'No hay suficiente stock disponible de "{producto.nombre}". Stock disponible: {inv.cantidad - inv.stock_reservado}. Solicitado: {cantidad}.')
                        else:
                            inv.cantidad -= cantidad
                            inv.save()
                            Transaction.objects.create(
                                inventario=inv,
                                tipo=form_type,
                                cantidad=cantidad
                            )
                            messages.success(request, 'Egreso registrado.')
                            return redirect(reverse('dashboard'))

                    active_panel = 'ingreso' if form_type == 'ingreso' else 'egreso'

            else:
                messages.error(request, 'Error en el formulario de stock.')
                active_panel = 'ingreso' if form_type == 'ingreso' else 'egreso'
                
        elif form_type == 'producto' and role in ['bodeguero', 'admin']:
            pk = request.POST.get('pk')
            instance = get_object_or_404(Producto, pk=pk) if pk else None
            producto_form = ProductoForm(request.POST, instance=instance)
            if producto_form.is_valid():
                producto_form.save()
                messages.success(request, 'Producto guardado exitosamente.')
                return redirect(reverse('dashboard') + '?panel=concepto-ingreso')
            else:
                messages.error(request, 'Error en el formulario de producto.')
                active_panel = 'concepto-ingreso'  # Quedarse para mostrar errores
           
        elif form_type == 'delete_producto' and role in ['bodeguero', 'admin']:
            pk = request.POST.get('pk')
            get_object_or_404(Producto, pk=pk).delete()
            messages.success(request, 'Producto eliminado.')
           
        
        elif form_type == 'proveedor' and role in ['bodeguero', 'admin']:
            pk = request.POST.get('pk')
            instance = get_object_or_404(Proveedor, pk=pk) if pk else None
            proveedor_form = ProveedorForm(request.POST, instance=instance)
            if proveedor_form.is_valid():
                proveedor_form.save()
                messages.success(request, 'Proveedor guardado exitosamente.')
            else:
                messages.error(request, 'Error en el formulario de proveedor.')
                active_panel = 'centro'  
        
        elif form_type == 'delete_proveedor' and role in ['bodeguero', 'admin']:
            pk = request.POST.get('pk')
            get_object_or_404(Proveedor, pk=pk).delete()
            messages.success(request, 'Proveedor eliminado.')
            return redirect(reverse('dashboard') + '?panel=centro')
        
        elif form_type == 'pedido' and role in ['bodeguero', 'admin']:
            pk = request.POST.get('pk')
            es_nuevo = pk is None or pk == ''
            
            instance = get_object_or_404(Pedido, pk=pk) if pk else None
            pedido_form = PedidoForm(request.POST, instance=instance)
            pedido_item_formset = PedidoItemFormSet(request.POST, instance=instance)

            if pedido_form.is_valid() and pedido_item_formset.is_valid():
                try:
                    with transaction.atomic():
                        pedido = pedido_form.save()
                        
                        # Guardar ítems
                        pedido_item_formset.instance = pedido
                        items = pedido_item_formset.save(commit=False)

                        # Filtrar ítems válidos (con producto y cantidad > 0)
                        items_validos = []
                        for item in items:
                            if item.producto and item.cantidad and item.cantidad > 0:
                                items_validos.append(item)
                            elif not item.pk:  # Si es nuevo y está vacío, eliminarlo
                                pass
                            else:  # Si existe y se dejó vacío, eliminarlo
                                item.delete()

                        if not items_validos:
                            raise ValidationError("Debe agregar al menos un producto con cantidad mayor a 0.")

                        # Guardar los válidos
                        for item in items_validos:
                            item.save()

                        
                        if es_nuevo and pedido.estado in ['Pendiente', 'Entransito']:
                            for item in pedido.items.all():
                                inv = Inventario.objects.get_or_create(producto=item.producto)[0]
                                disponible = inv.cantidad - inv.stock_reservado
                                if disponible < item.cantidad:
                                    raise ValidationError(f"Stock insuficiente para {item.producto.nombre}.")
                                inv.stock_reservado += item.cantidad
                                inv.save()

                    messages.success(request, 'Pedido guardado exitosamente.')
                    return redirect(reverse('dashboard') + '?panel=concepto-egreso')

                except ValidationError as e:
                    messages.error(request, f'Error: {e.message if hasattr(e, "message") else str(e)}')
                    active_panel = 'concepto-egreso'
            else:
                messages.error(request, 'Error en el formulario. Revisa los campos.')
                active_panel = 'concepto-egreso'
            
        
        elif form_type == 'delete_pedido' and role in ['bodeguero', 'admin']:
            pk = request.POST.get('pk')
            get_object_or_404(Pedido, pk=pk).delete()
            messages.success(request, 'Pedido eliminado.')
            return redirect(reverse('dashboard') + '?panel=concepto-egreso')
            
        
        elif form_type == 'reporte' and role in ['bodeguero', 'admin']:
            tipo = request.POST.get('tipo')
            fecha_desde = request.POST.get('fecha_desde')
            fecha_hasta = request.POST.get('fecha_hasta')
            content = ''
            qs = Transaction.objects.all()
            if fecha_desde:
                fecha_desde_dt = datetime.strptime(fecha_desde, '%Y-%m-%d')
                fecha_desde_dt = timezone.make_aware(fecha_desde_dt)
                qs = qs.filter(fecha__gte=fecha_desde_dt)
            if fecha_hasta:
                fecha_hasta_dt = datetime.strptime(fecha_hasta, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
                fecha_hasta_dt = timezone.make_aware(fecha_hasta_dt)
                qs = qs.filter(fecha__lte=fecha_hasta_dt)
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
                 # Parsear las líneas para facilitar el uso en template
                lineas = []
                for raw_line in content.strip().split('\n'):
                    if raw_line.strip():
                        if tipo == 'Resumen':
                            # Ejemplo: "Producto: 10 (Valor: $50000)"
                            # Extraemos: nombre, cantidad, valor_venta, valor_total
                            try:
                                nombre = raw_line.split(':')[0].strip()
                                resto = raw_line.split(':')[1].strip()
                                cantidad = resto.split('(')[0].strip()
                                valor_total_str = resto.split('$')[1].split(')')[0].strip()
                                valor_total = int(valor_total_str.replace('.', ''))
                                # Buscamos el producto para obtener precio_venta
                                inv = Inventario.objects.get(producto__nombre=nombre)
                                valor_unitario_venta = inv.producto.precio_venta
                            except:
                                nombre = raw_line
                                cantidad = 'N/A'
                                valor_unitario_venta = 0
                                valor_total = 0
                            lineas.append({
                                'nombre': nombre,
                                'cantidad': cantidad,
                                'valor_unitario_venta': valor_unitario_venta,
                                'valor_total': valor_total,
                            })
                        else:
                            # Ingreso/Egreso: solo la línea completa
                            lineas.append({'texto': raw_line.strip()})

                Reporte.objects.create(tipo=tipo, contenido=content)
                messages.success(request, f'Reporte de {tipo} generado.')
        
        elif form_type == 'usuario' and role == 'admin':
            if user_form.is_valid():
                user_form.save()
                messages.success(request, 'Usuario registrado.')
                return redirect(reverse('dashboard') + '?panel=parametros-sii')
            else:
                messages.error(request, 'Error en el formulario de usuario.')
                active_panel = 'parametros-sii'
                  
            
        
        else:
            messages.error(request, 'Acción no permitida para tu rol.')
            redirect_panel = 'dashboard'
        
        
    context = {
        'ultimos_movimientos': ultimos_movimientos,
        'inventarios': inventarios_paginados,
        'empresa': empresa,
        'stock_exit_form': stock_exit_form,
        'vigencia_plan': vigencia_plan,
        'total_productos': total_productos,
        'stock_bajo': stock_bajo,
        'total_inventario': total_inventario,
        'total_reservado': total_reservado,
        'total_disponible': total_disponible,
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
        'pedido_item_formset': pedido_item_formset,
        'user_form': user_form,
        'active_panel': active_panel,
        'role': role,  
        'ganancia_real': int(ganancia_real or 0),
        'ganancia_estimada_total': int(ganancia_estimada_total or 0),
        
        
    }
    return render(request, 'dashboard.html', context)

def pedido_detalle(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk)
    context = {'pedido': pedido}
    return render(request, 'pedido_detalle.html', context)

def generar_qr(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk)
    url = request.build_absolute_uri(reverse('pedido_detalle', args=[pk]))
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    return JsonResponse({'qr_base64': qr_base64})

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


@login_required
def completar_pedido_qr(request):
    if request.method == 'POST':
        pedido_id = request.POST.get('pedido_id')
        if not pedido_id:
            return JsonResponse({'success': False, 'message': 'ID de pedido no proporcionado.'}, status=400)

        try:
            pedido = get_object_or_404(Pedido, id=pedido_id)

            if pedido.estado == 'Completado':
                return JsonResponse({'success': False, 'message': 'Este pedido ya fue completado anteriormente.'})

            with transaction.atomic():
                for item in pedido.items.all():
                    # Asumiendo que PedidoItem tiene campo 'cantidad' en unidades base
                    cantidad_necesaria = item.cantidad  # Ajusta si hay factor_conversion

                    inv = get_object_or_404(Inventario, producto=item.producto)

                    if inv.cantidad < cantidad_necesaria:
                        return JsonResponse({
                            'success': False,
                            'message': f'Stock insuficiente para {item.producto.nombre}. Disponible: {inv.cantidad}'
                        })

                    # Descontar stock físico
                    inv.cantidad -= cantidad_necesaria
                    # Liberar reserva (si estaba reservado al crear pedido)
                    if inv.stock_reservado >= cantidad_necesaria:
                        inv.stock_reservado -= cantidad_necesaria
                    else:
                        inv.stock_reservado = 0
                    inv.save()

                    # Registrar movimiento
                    Transaction.objects.create(
                        inventario=inv,
                        tipo='egreso',
                        cantidad=cantidad_necesaria,
                        descripcion=f"Egreso por completado de Pedido #{pedido.id}"
                    )

                pedido.estado = 'Completado'
                pedido.save()

            return JsonResponse({
                'success': True,
                'message': f'Pedido #{pedido.id} completado exitosamente. Stock actualizado.'
            })

        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)

    return JsonResponse({'success': False, 'message': 'Método no permitido.'}, status=405)
def pedido_qr_publico(request, pk):
    """
    Vista pública: Muestra el detalle del pedido con QR grande.
    Accesible sin login, ideal para enviar por WhatsApp.
    """
    pedido = get_object_or_404(Pedido, pk=pk)
    
    # Generar QR (mismo código que en generar_qr)
    url_detalle = request.build_absolute_uri(reverse('pedido_qr_publico', args=[pk]))
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(url_detalle)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

    context = {
        'pedido': pedido,
        'qr_base64': qr_base64,
        'url_qr': url_detalle,  # Para compartir
    }
    return render(request, 'pedido_qr_publico.html', context)