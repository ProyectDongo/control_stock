Markdown# Sistema de Gestión de Stock - Productos Marinos Bentónicos

Un sistema completo de control de inventario desarrollado en **Django 4/5** para una empresa dedicada a la comercialización de productos marinos bentónicos (locos, erizos, almejas, etc.).

## Características Principales

- Control de stock en tiempo real (ingresos y egresos)
- Roles de usuario: Administrador, Bodeguero y Trabajador
- Alertas automáticas por stock bajo (email)
- Gestión de proveedores y pedidos de reposición
- Reportes descargables en PDF
- Panel de administración con gráficos (Chart.js)
- Cálculo automático de ganancias reales y potenciales
- Interfaz moderna con Bootstrap 5 + Font Awesome

## Roles y Permisos

| Rol          | Permisos                                                                 |
|-------------|--------------------------------------------------------------------------|
| Trabajador  | Ver dashboard, registrar ingresos y egresos                              |
| Bodeguero   | Todo lo anterior + gestionar productos, proveedores, pedidos y reportes |
| Admin       | Todo + gestión de usuarios                                               |

## Tecnologías Usadas

- Django 4/5
- Bootstrap 5 + Font Awesome
- Chart.js (gráficos)
- html2pdf.js (exportar reportes)
- Crispy Forms + Bootstrap5
- SQLite (por defecto) / PostgreSQL recomendado en producción

## Instalación

```bash
git clone https://github.com/tu-usuario/gestion-stock-marinos.git
cd gestion-stock-marinos

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Instalar dependencias
pip install django crispy-forms django-crispy-bootstrap5

# Migraciones
python manage.py makemigrations
python manage.py migrate

# Crear superusuario
python manage.py createsuperuser

# Ejecutar servidor
python manage.py runserver
Accede a: http://127.0.0.1:8000