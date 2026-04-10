from django.urls import path
from manager import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login_view'),
    path('logout/', views.logout_view, name='logout_view'),
    path('assign_lead/<int:lead_id>/', views.assign_lead, name='assign_lead'),
    path('unassign_lead/<int:lead_id>/', views.unassign_lead, name='unassign_lead'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)