from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


# ============================================================
# BRANCH
# ============================================================
class Branch(models.Model):
    name         = models.CharField(max_length=255)
    location     = models.CharField(max_length=255)
    address      = models.TextField(blank=True, null=True)
    phone        = models.CharField(max_length=20, blank=True, null=True)
    email        = models.EmailField(blank=True, null=True)
    gps_lat      = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    gps_lng      = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    gps_radius   = models.IntegerField(default=100, help_text='Radius in meters for HR punch-in')
    status       = models.CharField(max_length=20, default='Enabled')
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


# ============================================================
# USER PROFILE (extends Django User)
# ============================================================
ROLE_CHOICES = [
    ('superadmin', 'Super Admin'),
    ('manager', 'Branch Manager'),
    ('tl', 'Team Leader'),
    ('member', 'Call Team Member'),
    ('hr', 'HR Panel'),
    ('marketing', 'Marketing Admin'),
]

class UserProfile(models.Model):
    user         = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role         = models.CharField(max_length=20, choices=ROLE_CHOICES)
    branch       = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True)
    phone        = models.CharField(max_length=20, blank=True, null=True)
    profile_pic  = models.ImageField(upload_to='profiles/', blank=True, null=True)
    reports_to   = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='team_members')
    status       = models.CharField(max_length=20, default='Enabled')
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.role})"


# ============================================================
# LEAD
# ============================================================
SOURCE_CHOICES = [
    ('meta', 'Meta Ads'),
    ('google', 'Google Ads'),
    ('website', 'Website Form'),
    ('social', 'Social Media (Organic)'),
    ('campaign', 'Campaign'),
    ('referral', 'Referral'),
    ('walkin', 'Walk-in'),
    ('whatsapp', 'WhatsApp Inbound'),
    ('other', 'Other'),
]

TEMPERATURE_CHOICES = [
    ('hot', 'Hot'),
    ('warm', 'Warm'),
    ('cold', 'Cold'),
]

STAGE_CHOICES = [
    ('new', 'New'),
    ('contacted', 'Contacted'),
    ('interested', 'Interested'),
    ('site_visit', 'Site Visit'),
    ('negotiation', 'Negotiation'),
    ('closed', 'Closed'),
    ('lost', 'Lost'),
]

PROPERTY_TYPE_CHOICES = [
    ('apartment', 'Apartment'),
    ('villa', 'Villa'),
    ('plot', 'Plot'),
    ('commercial', 'Commercial'),
    ('studio', 'Studio'),
]

BHK_CHOICES = [
    ('1bhk', '1 BHK'),
    ('2bhk', '2 BHK'),
    ('3bhk', '3 BHK'),
    ('4bhk+', '4 BHK+'),
]

PURPOSE_CHOICES = [
    ('investment', 'Investment'),
    ('selfuse', 'Self Use'),
    ('rental', 'Rental'),
]

TIMELINE_CHOICES = [
    ('immediate', 'Immediate'),
    ('3months', 'Within 3 Months'),
    ('6months', 'Within 6 Months'),
    ('1year', '1 Year+'),
]

READINESS_CHOICES = [
    ('ready', 'Ready to Move'),
    ('underconstruction', 'Under Construction'),
]

class Lead(models.Model):
    # Basic Info
    name             = models.CharField(max_length=255)
    phone            = models.CharField(max_length=20)
    email            = models.EmailField(blank=True, null=True)
    location         = models.CharField(max_length=255, blank=True, null=True)

    # Source
    source           = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    campaign_name    = models.CharField(max_length=255, blank=True, null=True)
    ad_set           = models.CharField(max_length=255, blank=True, null=True)
    ad_creative      = models.CharField(max_length=255, blank=True, null=True)
    landing_page_url = models.URLField(blank=True, null=True)

    # Property Interest
    property_type    = models.CharField(max_length=20, choices=PROPERTY_TYPE_CHOICES, blank=True, null=True)
    budget_min       = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    budget_max       = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    property_location= models.CharField(max_length=255, blank=True, null=True)
    bhk_preference   = models.CharField(max_length=10, choices=BHK_CHOICES, blank=True, null=True)
    purpose          = models.CharField(max_length=20, choices=PURPOSE_CHOICES, blank=True, null=True)
    timeline         = models.CharField(max_length=20, choices=TIMELINE_CHOICES, blank=True, null=True)
    readiness        = models.CharField(max_length=20, choices=READINESS_CHOICES, blank=True, null=True)

    # Lead Status
    temperature      = models.CharField(max_length=10, choices=TEMPERATURE_CHOICES, default='cold')
    stage            = models.CharField(max_length=20, choices=STAGE_CHOICES, default='new')

    # Assignment
    assigned_to      = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='assigned_leads')
    branch           = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True)

    # Meta
    notes            = models.TextField(blank=True, null=True)
    status           = models.CharField(max_length=20, default='Enabled')
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} — {self.phone}"


# ============================================================
# CALL LOG
# ============================================================
CALL_TYPE_CHOICES = [
    ('inbound', 'Inbound'),
    ('outbound', 'Outbound'),
    ('missed', 'Missed'),
]

CALL_OUTCOME_CHOICES = [
    ('interested', 'Interested'),
    ('not_interested', 'Not Interested'),
    ('callback', 'Callback Requested'),
    ('not_answered', 'Not Answered'),
    ('converted', 'Converted'),
    ('site_visit', 'Site Visit Scheduled'),
]

class CallLog(models.Model):
    lead             = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='calls')
    call_type        = models.CharField(max_length=20, choices=CALL_TYPE_CHOICES)
    call_duration    = models.IntegerField(default=0, help_text='Duration in seconds')
    call_outcome     = models.CharField(max_length=20, choices=CALL_OUTCOME_CHOICES)
    call_notes       = models.TextField(blank=True, null=True)
    next_followup_at = models.DateTimeField(blank=True, null=True)
    called_by        = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True,
                                         related_name='call_logs')
    branch           = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True)
    status           = models.CharField(max_length=20, default='Enabled')
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Call: {self.lead.name} — {self.call_outcome}"

    def duration_display(self):
        mins = self.call_duration // 60
        secs = self.call_duration % 60
        return f"{mins}m {secs}s"


# ============================================================
# CALL WRAP-UP
# ============================================================
NEXT_ACTION_CHOICES = [
    ('followup', 'Follow-up'),
    ('site_visit', 'Site Visit'),
    ('send_details', 'Send Details'),
    ('close', 'Close Deal'),
    ('no_action', 'No Action'),
]

class CallWrapUp(models.Model):
    call             = models.OneToOneField(CallLog, on_delete=models.CASCADE, related_name='wrapup')
    lead             = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='wrapups')
    call_outcome     = models.CharField(max_length=20, choices=CALL_OUTCOME_CHOICES)
    call_duration    = models.IntegerField(default=0, help_text='Duration in seconds')
    detailed_notes   = models.TextField(blank=True, null=True)
    temperature_update = models.CharField(max_length=10, choices=TEMPERATURE_CHOICES)
    stage_update     = models.CharField(max_length=20, choices=STAGE_CHOICES)
    next_action      = models.CharField(max_length=20, choices=NEXT_ACTION_CHOICES)
    followup_at      = models.DateTimeField(blank=True, null=True)
    property_type    = models.CharField(max_length=20, choices=PROPERTY_TYPE_CHOICES, blank=True, null=True)
    budget_min       = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    budget_max       = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    property_location= models.CharField(max_length=255, blank=True, null=True)
    submitted_by     = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True)
    is_locked        = models.BooleanField(default=False)
    locked_at        = models.DateTimeField(blank=True, null=True)
    status           = models.CharField(max_length=20, default='Enabled')
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Wrap-up: {self.lead.name}"

    def lock_if_expired(self, window_minutes=10):
        if not self.is_locked:
            elapsed = (timezone.now() - self.created_at).total_seconds() / 60
            if elapsed > window_minutes:
                self.is_locked = True
                self.locked_at = timezone.now()
                self.save()


# ============================================================
# FOLLOW-UP
# ============================================================
FOLLOWUP_TYPE_CHOICES = [
    ('call', 'Call'),
    ('whatsapp', 'WhatsApp'),
    ('email', 'Email'),
    ('site_visit', 'Site Visit'),
]

FOLLOWUP_STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('completed', 'Completed'),
    ('rescheduled', 'Rescheduled'),
    ('missed', 'Missed'),
]

class FollowUp(models.Model):
    lead             = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='followups')
    followup_at      = models.DateTimeField()
    followup_type    = models.CharField(max_length=20, choices=FOLLOWUP_TYPE_CHOICES)
    notes            = models.TextField(blank=True, null=True)
    followup_status  = models.CharField(max_length=20, choices=FOLLOWUP_STATUS_CHOICES, default='pending')
    assigned_to      = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, blank=True)
    branch           = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True)
    status           = models.CharField(max_length=20, default='Enabled')
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Follow-up: {self.lead.name} at {self.followup_at}"


# ============================================================
# SYSTEM SETTINGS
# ============================================================
class SystemSetting(models.Model):
    key          = models.CharField(max_length=100, unique=True)
    value        = models.TextField()
    description  = models.CharField(max_length=255, blank=True, null=True)
    updated_at   = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.key

# ============================================================
# HR PANEL
# ============================================================
ATTENDANCE_STATUS_CHOICES = [
    ('present', 'Present'),
    ('absent', 'Absent'),
    ('late', 'Late'),
    ('half_day', 'Half Day'),
    ('wfh', 'Work From Home'),
    ('on_leave', 'On Leave'),
    ('holiday', 'Holiday'),
]

class Attendance(models.Model):
    employee       = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='attendances')
    branch         = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True)
    date           = models.DateField()
    punch_in       = models.DateTimeField(blank=True, null=True)
    punch_out      = models.DateTimeField(blank=True, null=True)
    punch_in_lat   = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    punch_in_lng   = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    punch_out_lat  = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    punch_out_lng  = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    status         = models.CharField(max_length=20, choices=ATTENDANCE_STATUS_CHOICES, default='present')
    is_out_of_zone = models.BooleanField(default=False)
    total_hours    = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    notes          = models.TextField(blank=True, null=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.employee.user.get_full_name()} — {self.date}"

    def calculate_hours(self):
        if self.punch_in and self.punch_out:
            delta = self.punch_out - self.punch_in
            self.total_hours = round(delta.total_seconds() / 3600, 2)
            self.save()


LEAVE_TYPE_CHOICES = [
    ('casual', 'Casual Leave'),
    ('sick', 'Sick Leave'),
    ('annual', 'Annual Leave'),
    ('unpaid', 'Unpaid Leave'),
    ('maternity', 'Maternity Leave'),
    ('compoff', 'Comp Off'),
]

LEAVE_STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
]

class LeaveRequest(models.Model):
    employee       = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='leave_requests')
    leave_type     = models.CharField(max_length=20, choices=LEAVE_TYPE_CHOICES)
    from_date      = models.DateField()
    to_date        = models.DateField()
    reason         = models.TextField()
    leave_status   = models.CharField(max_length=20, choices=LEAVE_STATUS_CHOICES, default='pending')
    approved_by    = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='approved_leaves')
    remarks        = models.TextField(blank=True, null=True)
    status         = models.CharField(max_length=20, default='Enabled')
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.employee.user.get_full_name()} — {self.leave_type} ({self.from_date})"

    def total_days(self):
        return (self.to_date - self.from_date).days + 1


class Payroll(models.Model):
    employee       = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='payrolls')
    month          = models.CharField(max_length=20)
    year           = models.IntegerField()
    base_salary    = models.DecimalField(max_digits=10, decimal_places=2)
    bonus          = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    deductions     = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_salary     = models.DecimalField(max_digits=10, decimal_places=2)
    notes          = models.TextField(blank=True, null=True)
    status         = models.CharField(max_length=20, default='Enabled')
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.employee.user.get_full_name()} — {self.month} {self.year}"

    def calculate_net(self):
        self.net_salary = self.base_salary + self.bonus - self.deductions
        self.save()