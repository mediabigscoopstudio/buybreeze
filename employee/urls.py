from django.urls import path
from employee import views
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path
from . import views
from . import android

urlpatterns = [
    #web
    path("", views.index, name="index"),
    path("login/", views.login_view, name="login_view"),
    path("verify-otp/", views.verify_otp, name="verify_otp"),
    path("logout/", views.logout_view, name="logout_view"),
    #android APP
    path("api/auth/send-otp/", android.send_otp, name="send_otp"),
    path("api/auth/verify-otp/", android.verify_otp, name="verify_otp"),
    path("api/attendance/punch-out/", android.punch_out, name="punch_out"),
    path("api/attendance/status/", android.attendance_status, name="attendance_status"),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


