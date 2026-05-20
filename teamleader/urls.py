from django.urls import path
from teamleader import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login_view'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('logout/', views.logout_view, name='logout_view'),
    path('profile/', views.profile, name='profile'),
    path('assign-to-employee/', views.assign_to_employee, name='assign_to_employee'),
    path('employee_performance/<int:id>/', views.employee_performance, name='employee_performance'),
    path('view_lead/<int:id>/', views.view_lead, name='view_lead'),
    path('apr-reports/', views.apr_reports, name='apr_reports'),
    path('apr-report/<int:id>/', views.employee_apr_report, name='employee_apr_report'),
    
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)