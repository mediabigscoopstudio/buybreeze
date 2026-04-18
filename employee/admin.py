from django.contrib import admin
from .models import Attendance

# Register your models here.
@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('employee', 'date', 'punch_in_time', 'punch_out_time')
    list_filter = ('date', 'employee')