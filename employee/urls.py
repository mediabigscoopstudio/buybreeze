from django.urls import path
from . import views
from . import android
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # web
    path("", views.index, name="index"),
    path("login/", views.login_view, name="login_view"),
    path("verify-otp/", views.verify_otp, name="web_verify_otp"),
    path("logout/", views.logout_view, name="logout_view"),

    # android — auth
    path("api/auth/send-otp/", android.send_otp, name="api_send_otp"),
    path("api/auth/verify-otp/", android.verify_otp, name="api_verify_otp"),

    # android — attendance
    path("api/attendance/punch-out/", android.punch_out, name="api_punch_out"),
    path("api/attendance/status/", android.attendance_status, name="api_attendance_status"),
    path("api/attendance/history/", android.attendance_history, name="api_attendance_history"),

    # android — profile
    path("api/profile/", android.get_profile, name="api_get_profile"),
    path("api/profile/update/", android.update_profile, name="api_update_profile"),

    # android — leads
    path("api/leads/", android.get_leads, name="api_get_leads"),
    path("api/leads/detail/", android.get_lead_detail, name="api_lead_detail"),

    # android — calls
    path("api/calls/save/", android.save_call, name="api_save_call"),
    path("api/calls/upload-recording/", android.upload_recording, name="api_upload_recording"),
    path("api/calls/logs/", android.call_logs, name="api_call_logs"),

    # android — route tracking
    path("api/route/save/", android.save_route, name="api_save_route"),
    path("api/route/history/", android.route_history, name="api_route_history"),

    # android — dashboard
    path("api/dashboard/stats/", android.dashboard_stats, name="api_dashboard_stats"),

    # android — device token (FCM)
    path("api/device-token/", android.save_device_token, name="api_save_device_token"),

    # android — leaves
    path("api/leave/apply/", android.apply_leave, name="api_apply_leave"),
    path("api/leave/my/",    android.my_leaves,   name="api_my_leaves"),

    # web — leaves
    path("apply-leave/", views.apply_leave, name="apply_leave"),
    path("my-leaves/",   views.my_leaves,   name="my_leaves"),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
