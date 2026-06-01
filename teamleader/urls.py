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
    path('notifications/', views.notifications_list, name='notifications_list'),
    path('apr-reports/', views.apr_reports, name='apr_reports'),
    path('apr-report/<int:id>/', views.employee_apr_report, name='employee_apr_report'),
    path('apr-report/<int:report_id>/day/<str:date_str>/', views.apr_day_detail, name='apr_day_detail'),
    path('apr-report/<int:profile_id>/detail/', views.apr_report_detail, name='tl_apr_report_detail'),
    path('lead-list/', views.lead_list, name='tl_lead_list'),
    path('lead/<int:lead_id>/', views.lead_detail, name='tl_lead_detail'),
    path('lead/<int:lead_id>/assign/', views.assign_lead, name='tl_assign_lead'),
    path('employee/<int:employee_id>/leads/', views.employee_leads, name='tl_employee_leads'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)