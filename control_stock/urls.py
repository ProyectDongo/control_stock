from django.urls import path
from inventory import views
from django.contrib import admin

urlpatterns = [
    path('', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('admin/', admin.site.urls),

]