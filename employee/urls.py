from django.urls import path
from employee import views
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path
from . import views

urlpatterns = [
    path("",views.index,name='index'),
    path('login/', views.login_view, name='login_view'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('logout/', views.logout_view, name='logout_view'),
    path('api/process-punch/', views.process_punch, name='process_punch'),
    path('api/save-location/', views.save_location_ping, name='save_location'),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


