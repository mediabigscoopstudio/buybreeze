from django.urls import path
from hrpanel import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Auth
    path('', views.hr_panel, name='index'),
    path('login', views.login_view, name='login_view'),
    path('logout', views.logout_view, name='logout_view'),

    # Branch
    path('branches', views.branch, name='branch'),
    path('add_branch', views.add_branch, name='add_branch'),
    path('edit_branch/<int:id>', views.edit_branch, name='edit_branch'),
    path('delete_branch/<int:id>', views.delete_branch, name='delete_branch'),
    path('enable_branch/<int:id>', views.enable_branch, name='enable_branch'),
    path('disable_branch/<int:id>', views.disable_branch, name='disable_branch'),
    

    # HR Panel
    path('', views.hr_panel, name='hr_panel'),
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

    # Users
    path('users', views.users, name='users'),
    path('add_user', views.add_user, name='add_user'),
    path('edit_user/<int:id>', views.edit_user, name='edit_user'),
    path('delete_user/<int:id>', views.delete_user, name='delete_user'),
    path('enable_user/<int:id>', views.enable_user, name='enable_user'),
    path('disable_user/<int:id>', views.disable_user, name='disable_user'),

    # Settings
    path('settings', views.settings_view, name='settings'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
