from django.urls import path
from manager import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login_view'),
    path('logout/', views.logout_view, name='logout_view'),
    path('assign-to-tl/', views.assign_to_tl, name='assign_to_tl'),
    path('unassign_lead/<int:lead_id>/', views.unassign_lead, name='unassign_lead'),
    path('tl_performance/<int:id>/', views.tl_performance, name='tl_performance'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)