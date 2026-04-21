from django.contrib import admin
from .models import Attendance
from .models import Attendance, LocationPing  # <-- Make sure LocationPing is imported here!

# Register your models here.
@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('employee', 'date', 'punch_in_time', 'punch_out_time')
    list_filter = ('date', 'employee')

@admin.register(LocationPing)
class LocationPingAdmin(admin.ModelAdmin):
    list_display = ('employee', 'latitude', 'longitude', 'timestamp')
    list_filter = ('employee', 'timestamp')    