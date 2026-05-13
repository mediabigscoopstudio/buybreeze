from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Count, Avg, Q
from django.utils import timezone
from datetime import timedelta
import io
import csv
import openpyxl
from django.http import HttpResponse

from dash.models import (
    Branch, UserProfile, Lead, CallLog, CallWrapUp, FollowUp, SystemSetting
)
from dash.otp_utils import generate_otp, send_otp



# ============================================================
# AUTH GUARD
# ============================================================
def hr_required(user):
    return (
        user.is_authenticated and 
        hasattr(user, 'profile') and 
        user.profile.role == 'hr'
    )


# ============================================================
# HR LOGIN VIEW
# ============================================================
def login_view(request):

    if request.user.is_authenticated:
        return redirect('/')

    if request.method == 'POST':

        phone = request.POST.get('phone')

        try:
            profile = UserProfile.objects.get(
                phone=phone,
                role='hr'
            )

            user = profile.user

            otp = generate_otp()

            request.session['pending_user_id'] = user.id
            request.session['otp_code'] = otp
            request.session['otp_expiry'] = (
                timezone.now() + timedelta(minutes=5)
            ).isoformat()

            send_otp(phone, otp)

            messages.success(
                request,
                'OTP sent successfully.'
            )

            return redirect('verify_otp')

        except UserProfile.DoesNotExist:

            messages.error(
                request,
                'HR account not found.'
            )

    return render(request, 'hrpanel/signin.html')

# ============================================================
# HR VERIFY OTP
# ============================================================
def verify_otp(request):

    pending_user_id = request.session.get('pending_user_id')
    stored_otp = request.session.get('otp_code')
    otp_expiry = request.session.get('otp_expiry')

    if not pending_user_id or not stored_otp or not otp_expiry:

        messages.error(
            request,
            'Session expired. Please login again.'
        )

        return redirect('/login/')

    expiry_time = timezone.datetime.fromisoformat(otp_expiry)

    if timezone.now() > expiry_time:

        messages.error(
            request,
            'OTP expired.'
        )

        return redirect('/login/')

    if request.method == 'POST':

        entered_otp = request.POST.get('otp')

        if entered_otp == stored_otp:

            user = User.objects.get(id=pending_user_id)

            login(request, user)

            del request.session['pending_user_id']
            del request.session['otp_code']
            del request.session['otp_expiry']

            return redirect('/')

        else:

            messages.error(
                request,
                'Invalid OTP.'
            )

    return render(request, 'hrpanel/verify_otp.html')


def logout_view(request):
    logout(request)
    return redirect('/login/')


# ============================================================
# DASHBOARD HOME
# ============================================================
@user_passes_test(hr_required, login_url='/login')
def index(request):
    total_leads    = Lead.objects.count()
    hot_leads      = Lead.objects.filter(temperature='hot').count()
    total_calls    = CallLog.objects.count()
    total_branches = Branch.objects.filter(status='Enabled').count()
    total_users    = UserProfile.objects.filter(status='Enabled').count()
    pending_followups = FollowUp.objects.filter(followup_status='pending').count()

    # Stage breakdown
    stage_data = Lead.objects.values('stage').annotate(count=Count('id'))

    # Branch-wise leads
    branch_leads = Branch.objects.annotate(lead_count=Count('lead')).filter(status='Enabled')

    # Recent leads
    recent_leads = Lead.objects.order_by('-created_at')[:8]

    # Upcoming follow-ups (next 24 hrs)
    upcoming_followups = FollowUp.objects.filter(
        followup_status='pending',
        followup_at__gte=timezone.now(),
        followup_at__lte=timezone.now() + timedelta(hours=24)
    ).order_by('followup_at')[:5]

    context = {
        'total_leads': total_leads,
        'hot_leads': hot_leads,
        'total_calls': total_calls,
        'total_branches': total_branches,
        'total_users': total_users,
        'pending_followups': pending_followups,
        'stage_data': stage_data,
        'branch_leads': branch_leads,
        'recent_leads': recent_leads,
        'upcoming_followups': upcoming_followups,
    }
    return render(request, 'hrpanel/index.html', context)


# ============================================================
# BRANCH MANAGEMENT
# ============================================================
@user_passes_test(hr_required, login_url='/login')
def branch(request):
    branches = Branch.objects.all().order_by('-id')
    return render(request, 'hrpanel/branch/branches.html', {'branches': branches})


@user_passes_test(hr_required, login_url='/login')
def add_branch(request):
    if request.method == 'POST':
        Branch.objects.create(
            name       = request.POST.get('name'),
            location   = request.POST.get('location'),
            address    = request.POST.get('address'),
            phone      = request.POST.get('phone'),
            email      = request.POST.get('email'),
            gps_lat    = request.POST.get('gps_lat') or None,
            gps_lng    = request.POST.get('gps_lng') or None,
            gps_radius = request.POST.get('gps_radius') or 100,
        )
        messages.success(request, 'Branch added successfully.')
        return redirect('branch')
    return render(request, 'hrpanel/branch/add_branch.html')


@user_passes_test(hr_required, login_url='/login')
def edit_branch(request, id):
    item = get_object_or_404(Branch, id=id)
    if request.method == 'POST':
        item.name       = request.POST.get('name')
        item.location   = request.POST.get('location')
        item.address    = request.POST.get('address')
        item.phone      = request.POST.get('phone')
        item.email      = request.POST.get('email')
        item.gps_lat    = request.POST.get('gps_lat') or None
        item.gps_lng    = request.POST.get('gps_lng') or None
        item.gps_radius = request.POST.get('gps_radius') or 100
        item.save()
        messages.success(request, 'Branch updated successfully.')
        return redirect('branch')
    return render(request, 'hrpanel/branch/edit_branch.html', {'data': item})


@user_passes_test(hr_required, login_url='/login')
def delete_branch(request, id):
    item = get_object_or_404(Branch, id=id)
    item.delete()
    messages.success(request, 'Branch deleted.')
    return redirect('branch')


@user_passes_test(hr_required, login_url='/login')
def enable_branch(request, id):
    item = get_object_or_404(Branch, id=id)
    item.status = 'Enabled'
    item.save()
    return redirect('branch')


@user_passes_test(hr_required, login_url='/login')
def disable_branch(request, id):
    item = get_object_or_404(Branch, id=id)
    item.status = 'Disabled'
    item.save()
    return redirect('branch')


# ============================================================
# USER MANAGEMENT
# ============================================================
@user_passes_test(hr_required, login_url='/login')
def users(request):
    all_users = UserProfile.objects.select_related('user', 'branch').order_by('-id')
    branches  = Branch.objects.filter(status='Enabled')
    role_filter   = request.GET.get('role', '')
    branch_filter = request.GET.get('branch', '')
    if role_filter:
        all_users = all_users.filter(role=role_filter)
    if branch_filter:
        all_users = all_users.filter(branch_id=branch_filter)
    return render(request, 'hrpanel/users/users.html', {
        'users': all_users,
        'branches': branches,
        'role_filter': role_filter,
        'branch_filter': branch_filter,
    })


@user_passes_test(hr_required, login_url='/login')
def add_user(request):
    branches = Branch.objects.filter(status='Enabled')
    all_profiles = UserProfile.objects.select_related('user').filter(status='Enabled')
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name  = request.POST.get('last_name')
        username   = request.POST.get('username')
        email      = request.POST.get('email')
        password   = request.POST.get('password')
        role       = request.POST.get('role')
        branch_id  = request.POST.get('branch')
        phone      = request.POST.get('phone')
        reports_to_id = request.POST.get('reports_to')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
        else:
            user = User.objects.create_user(
                username=username, email=email,
                password=password, first_name=first_name, last_name=last_name
            )
            profile = UserProfile(
                user=user, role=role, phone=phone,
                branch_id=branch_id if branch_id else None,
                reports_to_id=reports_to_id if reports_to_id else None,
            )
            if request.FILES.get('profile_pic'):
                profile.userprofile_pic = request.FILES['profile_pic']
            profile.save()
            messages.success(request, 'User created successfully.')
            return redirect('users')
    return render(request, 'hrpanel/users/add_user.html', {
        'branches': branches,
        'all_profiles': all_profiles,
    })


@user_passes_test(hr_required, login_url='/login')
def edit_user(request, id):
    profile  = get_object_or_404(UserProfile, id=id)
    branches = Branch.objects.filter(status='Enabled')
    all_profiles = UserProfile.objects.select_related('user').filter(status='Enabled').exclude(id=id)
    if request.method == 'POST':
        profile.user.first_name = request.POST.get('first_name')
        profile.user.last_name  = request.POST.get('last_name')
        profile.user.email      = request.POST.get('email')
        profile.user.save()
        profile.role       = request.POST.get('role')
        profile.phone      = request.POST.get('phone')
        profile.branch_id  = request.POST.get('branch') or None
        profile.reports_to_id = request.POST.get('reports_to') or None
        if request.FILES.get('profile_pic'):
            profile.userprofile_pic = request.FILES['profile_pic']
        profile.save()
        messages.success(request, 'User updated successfully.')
        return redirect('users')
    return render(request, 'hrpanel/users/edit_user.html', {
        'data': profile,
        'branches': branches,
        'all_profiles': all_profiles,
    })


@user_passes_test(hr_required, login_url='/login')
def delete_user(request, id):
    profile = get_object_or_404(UserProfile, id=id)
    profile.user.delete()
    messages.success(request, 'User deleted.')
    return redirect('users')


@user_passes_test(hr_required, login_url='/login')
def enable_user(request, id):
    item = get_object_or_404(UserProfile, id=id)
    item.status = 'Enabled'
    item.save()
    return redirect('users')


@user_passes_test(hr_required, login_url='/login')
def disable_user(request, id):
    item = get_object_or_404(UserProfile, id=id)
    item.status = 'Disabled'
    item.save()
    return redirect('users')

# ============================================================
# SETTINGS
# ============================================================
@user_passes_test(hr_required, login_url='/login')
def settings_view(request):
    setting_keys = ['wrapup_window_minutes', 'lead_auto_assign', 'whatsapp_provider']
    settings_data = {}
    for key in setting_keys:
        obj, _ = SystemSetting.objects.get_or_create(key=key, defaults={'value': ''})
        settings_data[key] = obj
    if request.method == 'POST':
        for key in setting_keys:
            val = request.POST.get(key, '')
            SystemSetting.objects.filter(key=key).update(value=val)
        messages.success(request, 'Settings saved.')
        return redirect('settings')
    return render(request, 'hrpanel/settings/settings.html', {'settings': settings_data})


# ============================================================
# HR PANEL
# ============================================================
from dash.models import Attendance, LeaveRequest, Payroll

@user_passes_test(hr_required, login_url='/login')
def hr_panel(request):
    branches  = Branch.objects.filter(status='Enabled')
    employees = UserProfile.objects.filter(status='Enabled').select_related('user', 'branch')

    branch_filter = request.GET.get('branch', '')
    role_filter   = request.GET.get('role', '')
    search        = request.GET.get('q', '')

    if branch_filter:
        employees = employees.filter(branch_id=branch_filter)
    if role_filter:
        employees = employees.filter(role=role_filter)
    if search:
        employees = employees.filter(
            Q(user__first_name__icontains=search) | Q(user__last_name__icontains=search)
        )

    total_employees  = employees.count()
    present_today    = Attendance.objects.filter(
        date=timezone.now().date(), status='present'
    ).count()
    on_leave_today   = Attendance.objects.filter(
        date=timezone.now().date(), status='on_leave'
    ).count()
    pending_leaves   = LeaveRequest.objects.filter(leave_status='pending').count()

    return render(request, 'hrpanel/hr/hr_panel.html', {
        'employees': employees,
        'branches': branches,
        'branch_filter': branch_filter,
        'role_filter': role_filter,
        'search': search,
        'total_employees': total_employees,
        'present_today': present_today,
        'on_leave_today': on_leave_today,
        'pending_leaves': pending_leaves,
    })


# --- ATTENDANCE ---
@user_passes_test(hr_required, login_url='/login')
def attendance(request):
    branches  = Branch.objects.filter(status='Enabled')
    records   = Attendance.objects.select_related('employee__user', 'branch').order_by('-date', '-created_at')

    branch_filter = request.GET.get('branch', '')
    date_filter   = request.GET.get('date', '')
    status_filter = request.GET.get('status', '')
    search        = request.GET.get('q', '')

    if branch_filter:
        records = records.filter(branch_id=branch_filter)
    if date_filter:
        records = records.filter(date=date_filter)
    if status_filter:
        records = records.filter(status=status_filter)
    if search:
        records = records.filter(
            Q(employee__user__first_name__icontains=search) |
            Q(employee__user__last_name__icontains=search)
        )

    return render(request, 'hrpanel/hr/attendance.html', {
        'records': records,
        'branches': branches,
        'branch_filter': branch_filter,
        'date_filter': date_filter,
        'status_filter': status_filter,
        'search': search,
    })


@user_passes_test(hr_required, login_url='/login')
def add_attendance(request):
    employees = UserProfile.objects.filter(status='Enabled').select_related('user')
    branches  = Branch.objects.filter(status='Enabled')
    if request.method == 'POST':
        record = Attendance.objects.create(
            employee_id    = request.POST.get('employee'),
            branch_id      = request.POST.get('branch') or None,
            date           = request.POST.get('date'),
            punch_in       = request.POST.get('punch_in') or None,
            punch_out      = request.POST.get('punch_out') or None,
            status         = request.POST.get('status', 'present'),
            is_out_of_zone = request.POST.get('is_out_of_zone') == 'on',
            notes          = request.POST.get('notes', ''),
        )
        record.calculate_hours()
        messages.success(request, 'Attendance record added.')
        return redirect('attendance')
    return render(request, 'hrpanel/hr/add_attendance.html', {
        'employees': employees, 'branches': branches
    })


@user_passes_test(hr_required, login_url='/login')
def edit_attendance(request, id):
    record    = get_object_or_404(Attendance, id=id)
    employees = UserProfile.objects.filter(status='Enabled').select_related('user')
    branches  = Branch.objects.filter(status='Enabled')
    if request.method == 'POST':
        record.employee_id    = request.POST.get('employee')
        record.branch_id      = request.POST.get('branch') or None
        record.date           = request.POST.get('date')
        record.punch_in       = request.POST.get('punch_in') or None
        record.punch_out      = request.POST.get('punch_out') or None
        record.status         = request.POST.get('status', 'present')
        record.is_out_of_zone = request.POST.get('is_out_of_zone') == 'on'
        record.notes          = request.POST.get('notes', '')
        record.save()
        record.calculate_hours()
        messages.success(request, 'Attendance updated.')
        return redirect('attendance')
    return render(request, 'hrpanel/hr/edit_attendance.html', {
        'data': record, 'employees': employees, 'branches': branches
    })


@user_passes_test(hr_required, login_url='/login')
def delete_attendance(request, id):
    get_object_or_404(Attendance, id=id).delete()
    messages.success(request, 'Record deleted.')
    return redirect('attendance')


# --- LEAVE ---
@user_passes_test(hr_required, login_url='/login')
def leaves(request):
    branches  = Branch.objects.filter(status='Enabled')
    records   = LeaveRequest.objects.select_related('employee__user', 'approved_by__user').order_by('-created_at')

    status_filter = request.GET.get('status', '')
    branch_filter = request.GET.get('branch', '')
    search        = request.GET.get('q', '')

    if status_filter:
        records = records.filter(leave_status=status_filter)
    if branch_filter:
        records = records.filter(employee__branch_id=branch_filter)
    if search:
        records = records.filter(
            Q(employee__user__first_name__icontains=search) |
            Q(employee__user__last_name__icontains=search)
        )
    return render(request, 'hrpanel/hr/leaves.html', {
        'records': records, 'branches': branches,
        'status_filter': status_filter,
        'branch_filter': branch_filter,
        'search': search,
    })


@user_passes_test(hr_required, login_url='/login')
def add_leave(request):
    employees = UserProfile.objects.filter(status='Enabled').select_related('user')
    if request.method == 'POST':
        LeaveRequest.objects.create(
            employee_id  = request.POST.get('employee'),
            leave_type   = request.POST.get('leave_type'),
            from_date    = request.POST.get('from_date'),
            to_date      = request.POST.get('to_date'),
            reason       = request.POST.get('reason'),
            leave_status = request.POST.get('leave_status', 'pending'),
        )
        messages.success(request, 'Leave request added.')
        return redirect('leaves')
    return render(request, 'hrpanel/hr/add_leave.html', {'employees': employees})


@user_passes_test(hr_required, login_url='/login')
def edit_leave(request, id):
    record    = get_object_or_404(LeaveRequest, id=id)
    employees = UserProfile.objects.filter(status='Enabled').select_related('user')
    profiles  = UserProfile.objects.filter(status='Enabled').select_related('user')
    if request.method == 'POST':
        record.employee_id  = request.POST.get('employee')
        record.leave_type   = request.POST.get('leave_type')
        record.from_date    = request.POST.get('from_date')
        record.to_date      = request.POST.get('to_date')
        record.reason       = request.POST.get('reason')
        record.leave_status = request.POST.get('leave_status', 'pending')
        record.approved_by_id = request.POST.get('approved_by') or None
        record.remarks      = request.POST.get('remarks', '')
        record.save()
        messages.success(request, 'Leave updated.')
        return redirect('leaves')
    return render(request, 'hrpanel/hr/edit_leave.html', {
        'data': record, 'employees': employees, 'profiles': profiles
    })


@user_passes_test(hr_required, login_url='/login')
def delete_leave(request, id):
    get_object_or_404(LeaveRequest, id=id).delete()
    messages.success(request, 'Leave request deleted.')
    return redirect('leaves')


@user_passes_test(hr_required, login_url='/login')
def approve_leave(request, id):
    record = get_object_or_404(LeaveRequest, id=id)
    record.leave_status = 'approved'
    record.approved_by  = request.user.userprofile
    record.save()
    messages.success(request, 'Leave approved.')
    return redirect('leaves')


@user_passes_test(hr_required, login_url='/login')
def reject_leave(request, id):
    record = get_object_or_404(LeaveRequest, id=id)
    record.leave_status = 'rejected'
    record.approved_by  = request.user.userprofile
    record.save()
    messages.success(request, 'Leave rejected.')
    return redirect('leaves')


# --- PAYROLL ---
@user_passes_test(hr_required, login_url='/login')
def payroll(request):
    branches  = Branch.objects.filter(status='Enabled')
    records   = Payroll.objects.select_related('employee__user').order_by('-year', '-created_at')

    branch_filter = request.GET.get('branch', '')
    month_filter  = request.GET.get('month', '')
    search        = request.GET.get('q', '')

    if branch_filter:
        records = records.filter(employee__branch_id=branch_filter)
    if month_filter:
        records = records.filter(month=month_filter)
    if search:
        records = records.filter(
            Q(employee__user__first_name__icontains=search) |
            Q(employee__user__last_name__icontains=search)
        )
    return render(request, 'hrpanel/hr/payroll.html', {
        'records': records, 'branches': branches,
        'branch_filter': branch_filter,
        'month_filter': month_filter,
        'search': search,
    })


@user_passes_test(hr_required, login_url='/login')
def add_payroll(request):
    employees = UserProfile.objects.filter(status='Enabled').select_related('user')
    if request.method == 'POST':
        base      = float(request.POST.get('base_salary', 0))
        bonus     = float(request.POST.get('bonus', 0))
        deductions= float(request.POST.get('deductions', 0))
        Payroll.objects.create(
            employee_id = request.POST.get('employee'),
            month       = request.POST.get('month'),
            year        = request.POST.get('year'),
            base_salary = base,
            bonus       = bonus,
            deductions  = deductions,
            net_salary  = base + bonus - deductions,
            notes       = request.POST.get('notes', ''),
        )
        messages.success(request, 'Payroll record added.')
        return redirect('payroll')
    return render(request, 'hrpanel/hr/add_payroll.html', {'employees': employees})


@user_passes_test(hr_required, login_url='/login')
def edit_payroll(request, id):
    record    = get_object_or_404(Payroll, id=id)
    employees = UserProfile.objects.filter(status='Enabled').select_related('user')
    if request.method == 'POST':
        base       = float(request.POST.get('base_salary', 0))
        bonus      = float(request.POST.get('bonus', 0))
        deductions = float(request.POST.get('deductions', 0))
        record.employee_id = request.POST.get('employee')
        record.month       = request.POST.get('month')
        record.year        = request.POST.get('year')
        record.base_salary = base
        record.bonus       = bonus
        record.deductions  = deductions
        record.net_salary  = base + bonus - deductions
        record.notes       = request.POST.get('notes', '')
        record.save()
        messages.success(request, 'Payroll updated.')
        return redirect('payroll')
    return render(request, 'hrpanel/hr/edit_payroll.html', {
        'data': record, 'employees': employees
    })


@user_passes_test(hr_required, login_url='/login')
def delete_payroll(request, id):
    get_object_or_404(Payroll, id=id).delete()
    messages.success(request, 'Payroll record deleted.')
    return redirect('payroll')

# ============================================================
# EMPLOYEE DETAIL — Attendance, Leave, Payroll in one page
# ============================================================
@user_passes_test(hr_required, login_url='/login')
def employee_detail(request, id):
    employee     = get_object_or_404(UserProfile, id=id)
    branches     = Branch.objects.filter(status='Enabled')
    att_records  = Attendance.objects.filter(employee=employee).order_by('-date')
    leave_records = LeaveRequest.objects.filter(employee=employee).order_by('-created_at')
    payroll_records = Payroll.objects.filter(employee=employee).order_by('-year', '-created_at')

    # Quick add attendance from this page
    if request.method == 'POST':
        record = Attendance.objects.create(
            employee    = employee,
            branch_id   = request.POST.get('branch') or employee.branch_id,
            date        = request.POST.get('date'),
            punch_in    = request.POST.get('punch_in') or None,
            punch_out   = request.POST.get('punch_out') or None,
            status      = request.POST.get('status', 'present'),
            is_out_of_zone = request.POST.get('is_out_of_zone') == 'on',
            notes       = request.POST.get('notes', ''),
        )
        record.calculate_hours()
        messages.success(request, f'Attendance added for {employee.user.get_full_name()}.')
        return redirect('employee_detail', id=id)

    return render(request, 'hrpanel/hr/employee_detail.html', {
        'employee': employee,
        'att_records': att_records,
        'leave_records': leave_records,
        'payroll_records': payroll_records,
        'branches': branches,
    })