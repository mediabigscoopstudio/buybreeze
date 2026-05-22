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
    # android API
    path("api/auth/send-otp/", android.send_otp, name="api_send_otp"),
    path("api/auth/verify-otp/", android.verify_otp, name="api_verify_otp"),
    path("api/attendance/punch-out/", android.punch_out, name="api_punch_out"),
    path("api/attendance/status/", android.attendance_status, name="api_attendance_status"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)