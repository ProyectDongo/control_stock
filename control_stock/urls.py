from django.urls import path
from inventory import views
from django.contrib import admin

urlpatterns = [
    path('', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('pedido/<int:pk>/detalle/', views.pedido_detalle, name='pedido_detalle'),
    path('generar_qr/<int:pk>/', views.generar_qr, name='generar_qr'),
    path('admin/', admin.site.urls),
    path('completar-pedido-qr/', views.completar_pedido_qr, name='completar_pedido_qr'),
    path('pedido/<int:pk>/qr/', views.pedido_qr_publico, name='pedido_qr_publico'),
]