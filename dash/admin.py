from django.contrib import admin
from .models import Branch, UserProfile, Lead, CallLog, CallWrapUp, FollowUp, SystemSetting, Attendance, LeaveRequest, Payroll

admin.site.register(Branch)
admin.site.register(UserProfile)
admin.site.register(Lead)
admin.site.register(CallLog)
admin.site.register(CallWrapUp)
admin.site.register(FollowUp)
admin.site.register(SystemSetting)
admin.site.register(Attendance)
admin.site.register(LeaveRequest)
admin.site.register(Payroll)