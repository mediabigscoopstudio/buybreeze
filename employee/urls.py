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
    path("api/employee-login/", android.employee_login, name="employee_login"),
    path("api/verify-employee-otp/", android.verify_employee_otp, name="verify_employee_otp"),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


