from django.urls import path
from manager import views
from django.conf import settings
from django.conf.urls.static import static 

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login_view'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('logout/', views.logout_view, name='logout_view'),
    path('assign-to-tl/', views.assign_to_tl, name='assign_to_tl'),
    path('unassign_lead/<int:lead_id>/', views.unassign_lead, name='unassign_lead'),
    path('tl_performance/<int:id>/', views.tl_performance, name='tl_performance'),
    path('profile_settings', views.profile_settings, name='profile_settings'),
    path('view_lead/<int:id>/', views.view_lead, name='view_lead'),
    path('notifications/', views.notifications_list, name='notifications_list'),
    path('apr-reports/', views.apr_reports, name='apr_reports'),
    path('apr-report/<int:id>/', views.individual_apr_report, name='individual_apr_report'),
    path('apr-report/<int:report_id>/day/<str:date_str>/', views.apr_day_detail, name='apr_day_detail'),
    path('apr-report/<int:profile_id>/detail/', views.apr_report_detail, name='manager_apr_report_detail'),
    path('lead-list/', views.lead_list, name='manager_lead_list'),
    path('lead/<int:lead_id>/', views.lead_detail, name='manager_lead_detail'),
    path('lead/<int:lead_id>/assign/', views.assign_lead, name='manager_assign_lead'),
    path('team/<int:tl_id>/', views.team_detail, name='manager_team_detail'),
    path('employee/<int:employee_id>/leads/', views.employee_leads, name='manager_employee_leads'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)