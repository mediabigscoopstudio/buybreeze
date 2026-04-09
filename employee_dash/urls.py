from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.employee_dashboard, name='employee_home'),
    path('accounts/', include('django.contrib.auth.urls')),
]