from django.urls import path
from teamleader import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login_view'),
    path('logout/', views.logout_view, name='logout_view'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)