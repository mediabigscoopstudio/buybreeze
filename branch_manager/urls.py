from django.urls import path
from . import views
from dash import views as dash_views  # <-- Import the views from your main app

urlpatterns = [
    path('', views.manager_dashboard, name='manager_home'),
    
    # This makes 'login_view' available without hardcoding URLs!
    path('login/', dash_views.login_view, name='login_view'),
    path('logout/', dash_views.logout_view, name='logout_view'),
]