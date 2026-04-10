from django.urls import path
from dash import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Auth
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login_view'),
    path('logout/', views.logout_view, name='logout_view'),

    # Branch
    path('branches', views.branch, name='branch'),
    path('add_branch', views.add_branch, name='add_branch'),
    path('edit_branch/<int:id>', views.edit_branch, name='edit_branch'),
    path('delete_branch/<int:id>', views.delete_branch, name='delete_branch'),
    path('enable_branch/<int:id>', views.enable_branch, name='enable_branch'),
    path('disable_branch/<int:id>', views.disable_branch, name='disable_branch'),

    # Users
    path('users', views.users, name='users'),
    path('add_user', views.add_user, name='add_user'),
    path('edit_user/<int:id>', views.edit_user, name='edit_user'),
    path('delete_user/<int:id>', views.delete_user, name='delete_user'),
    path('enable_user/<int:id>', views.enable_user, name='enable_user'),
    path('disable_user/<int:id>', views.disable_user, name='disable_user'),

    # HR Panel
    path('hr', views.hr_panel, name='hr_panel'),
    path('hr/employee/<int:id>', views.employee_detail, name='employee_detail'),

    # Attendance
    path('attendance', views.attendance, name='attendance'),
    path('add_attendance', views.add_attendance, name='add_attendance'),
    path('edit_attendance/<int:id>', views.edit_attendance, name='edit_attendance'),
    path('delete_attendance/<int:id>', views.delete_attendance, name='delete_attendance'),

    # Leaves
    path('leaves', views.leaves, name='leaves'),
    path('add_leave', views.add_leave, name='add_leave'),
    path('edit_leave/<int:id>', views.edit_leave, name='edit_leave'),
    path('delete_leave/<int:id>', views.delete_leave, name='delete_leave'),
    path('approve_leave/<int:id>', views.approve_leave, name='approve_leave'),
    path('reject_leave/<int:id>', views.reject_leave, name='reject_leave'),

    # Payroll
    path('payroll', views.payroll, name='payroll'),
    path('add_payroll', views.add_payroll, name='add_payroll'),
    path('edit_payroll/<int:id>', views.edit_payroll, name='edit_payroll'),
    path('delete_payroll/<int:id>', views.delete_payroll, name='delete_payroll'),

    # Leads
    path('leads', views.leads, name='leads'),
    path('add_lead', views.add_lead, name='add_lead'),
    path('edit_lead/<int:id>', views.edit_lead, name='edit_lead'),
    path('delete_lead/<int:id>', views.delete_lead, name='delete_lead'),
    path('enable_lead/<int:id>', views.enable_lead, name='enable_lead'),
    path('disable_lead/<int:id>', views.disable_lead, name='disable_lead'),
    path('view_lead/<int:id>', views.view_lead, name='view_lead'),
    path('leads/bulk-upload', views.bulk_upload_leads, name='bulk_upload_leads'),
    path('leads/download-template', views.download_lead_template, name='download_lead_template'),

    # Lead Assignment (Super Admin → Manager)
    path('leads/assign_to_manager/<int:lead_id>/', views.assign_lead_to_manager, name='assign_lead_to_manager'),
    path('leads/unassign_from_manager/<int:lead_id>/', views.unassign_lead_from_manager, name='unassign_lead_from_manager'),

    # Calls
    path('calls', views.calls, name='calls'),
    path('add_call', views.add_call, name='add_call'),
    path('edit_call/<int:id>', views.edit_call, name='edit_call'),
    path('delete_call/<int:id>', views.delete_call, name='delete_call'),
    path('enable_call/<int:id>', views.enable_call, name='enable_call'),
    path('disable_call/<int:id>', views.disable_call, name='disable_call'),

    # Wrap-ups
    path('wrapups', views.wrapups, name='wrapups'),

    # Follow-ups
    path('followups', views.followups, name='followups'),
    path('add_followup', views.add_followup, name='add_followup'),
    path('edit_followup/<int:id>', views.edit_followup, name='edit_followup'),
    path('delete_followup/<int:id>', views.delete_followup, name='delete_followup'),
    path('enable_followup/<int:id>', views.enable_followup, name='enable_followup'),
    path('disable_followup/<int:id>', views.disable_followup, name='disable_followup'),

    # Settings
    path('settings', views.settings_view, name='settings'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)