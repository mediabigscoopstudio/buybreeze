from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.db.models import Q
from dash.models import Attendance, Branch, LeaveRequest, UserProfile, Lead, CallLog
from dash.notifications import (
    create_notification, get_admins,
    get_user_notifications, get_unread_count,
    mark_all_read, mark_read,
)
from django.http import JsonResponse
import json
from dash.otp_utils import generate_otp, send_otp
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import timedelta, datetime, date, time as time_obj
from employee.models import LocationPing


# ============================================================
# AUTH GUARD
# ============================================================
def tl_required(user):

    return (
        user.is_authenticated and
         hasattr(user, 'profile') and
        user.profile.role == 'tl'
    )


# ============================================================
# AUTH VIEWS
# ============================================================
def login_view(request):

    # =========================================
    # ALREADY LOGGED IN
    # =========================================
    if request.user.is_authenticated:

        if tl_required(request.user):
            return redirect('/')

        logout(request)

        return redirect('/login/')

    # =========================================
    # LOGIN POST
    # =========================================
    if request.method == 'POST':

        phone = request.POST.get('phone')

        # =====================================
        # FIND USER PROFILE
        # =====================================
        try:

            profile = UserProfile.objects.get(
                phone=phone,
                role='tl'
            )

            user = profile.user

        except UserProfile.DoesNotExist:

            messages.error(
                request,
                'Phone number not registered.'
            )

            return redirect('/login/')

        # =====================================
        # GENERATE OTP
        # =====================================
        otp = generate_otp()

        # =====================================
        # SEND OTP
        # =====================================
        otp_sent = send_otp(
            profile.phone,
            otp
        )

        if not otp_sent:

            messages.error(
                request,
                'Failed to send OTP.'
            )

            return redirect('/login/')

        # =====================================
        # STORE SESSION
        # =====================================
        request.session['pending_user_id'] = user.id

        request.session['otp_code'] = otp

        expiry_time = timezone.now() + timedelta(minutes=5)

        request.session['otp_expiry'] = expiry_time.isoformat()

        messages.success(
            request,
            'OTP sent successfully.'
        )

        return redirect('verify_otp')

    return render(
        request,
        'teamleader/signin.html'
    )


# ============================================================
# VERIFY OTP
# ============================================================
def verify_otp(request):

    pending_user_id = request.session.get('pending_user_id')

    stored_otp = request.session.get('otp_code')

    otp_expiry = request.session.get('otp_expiry')

    # =========================================
    # SESSION CHECK
    # =========================================
    if not pending_user_id or not stored_otp or not otp_expiry:

        messages.error(
            request,
            'Session expired. Please login again.'
        )

        return redirect('/login/')

    # =========================================
    # OTP EXPIRY CHECK
    # =========================================
    expiry_time = datetime.fromisoformat(otp_expiry)

    if timezone.now() > expiry_time:

        request.session.flush()

        messages.error(
            request,
            'OTP expired. Please login again.'
        )

        return redirect('/login/')

    # =========================================
    # VERIFY OTP POST
    # =========================================
    if request.method == 'POST':

        entered_otp = request.POST.get('otp')

        # =====================================
        # OTP MATCH
        # =====================================
        if entered_otp == stored_otp:

            try:

                user = User.objects.get(
                    id=pending_user_id
                )

            except User.DoesNotExist:

                messages.error(
                    request,
                    'User not found.'
                )

                return redirect('/login/')

            # =====================================
            # FINAL LOGIN
            # =====================================
            login(request, user)

            request.session.save()

            # =====================================
            # CLEAN SESSION
            # =====================================
            request.session.pop(
                'pending_user_id',
                None
            )

            request.session.pop(
                'otp_code',
                None
            )

            request.session.pop(
                'otp_expiry',
                None
            )

            # =====================================
            # TEAMLEADER REDIRECT
            # =====================================
            return redirect(
                '/'
            )

        # =====================================
        # INVALID OTP
        # =====================================
        else:

            messages.error(
                request,
                'Invalid OTP.'
            )

    return render(
        request,
        'teamleader/verify_otp.html'
    )


# ============================================================
# LOGOUT
# ============================================================
def logout_view(request):

    logout(request)

    return redirect(
        '/login/'
    )

@user_passes_test(tl_required, login_url='/login/')
def index(request):
    tl_profile = request.user.profile
    today = timezone.localdate()

    employees = UserProfile.objects.filter(
        reports_to=tl_profile,
        role='employee',
        status='Enabled',
    ).select_related('user', 'branch')

    total_leads = Lead.objects.filter(assigned_to__in=employees).count()
    leads_today = Lead.objects.filter(
        assigned_to__in=employees,
        created_at__date=today,
    ).count()
    calls_today = CallLog.objects.filter(
        called_by__in=employees,
        created_at__date=today,
    ).count()
    present_today = Attendance.objects.filter(
        employee__in=employees,
        date=today,
        punch_in__isnull=False,
    ).count()
    on_leave_today = LeaveRequest.objects.filter(
        employee__in=employees,
        leave_status='approved',
        from_date__lte=today,
        to_date__gte=today,
    ).count()
    absent_today = max(employees.count() - present_today - on_leave_today, 0)
    hot_leads = Lead.objects.filter(
        assigned_to__in=employees,
        temperature='hot',
    ).count()
    converted_leads = Lead.objects.filter(
        assigned_to__in=employees,
        stage__in=['closed', 'converted'],
    ).count()
    recent_calls = CallLog.objects.filter(
        called_by__in=employees
    ).select_related('lead', 'called_by__user').order_by('-created_at')[:10]
    recent_leads = Lead.objects.filter(
        assigned_to__in=employees
    ).select_related('assigned_to__user').order_by('-created_at')[:10]
    pending_leaves = LeaveRequest.objects.filter(
        employee__in=employees,
        leave_status='pending',
    ).count()

    # Leads sitting with the TL — not yet pushed to any employee
    unassigned_leads = Lead.objects.filter(
        assigned_to=tl_profile,
    ).select_related('branch').order_by('-created_at')

    # Per-employee tile stats
    employee_tile_data = []
    for emp in employees:
        emp_leads = Lead.objects.filter(assigned_to=emp)
        employee_tile_data.append({
            'employee': emp,
            'total': emp_leads.count(),
            'hot':   emp_leads.filter(temperature='hot').count(),
            'warm':  emp_leads.filter(temperature='warm').count(),
            'cold':  emp_leads.filter(temperature='cold').count(),
        })

    return render(request, 'teamleader/index.html', {
        'total_leads': total_leads,
        'leads_today': leads_today,
        'calls_today': calls_today,
        'present_today': present_today,
        'absent_today': absent_today,
        'hot_leads': hot_leads,
        'converted_leads': converted_leads,
        'recent_calls': recent_calls,
        'recent_leads': recent_leads,
        'total_team': employees.count(),
        'pending_leaves': pending_leaves,
        'unassigned_leads': unassigned_leads,
        'employees': employees,
        'employee_tile_data': employee_tile_data,
    })

@user_passes_test(tl_required, login_url='/login/')
def assign_to_employee(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)

            lead_ids = data.get('lead_ids', [])
            employee_id = data.get('employee_id')

            if not lead_ids or not employee_id:
                return JsonResponse({'status': 'error', 'message': 'Missing data'})

            tl = request.user.profile

            # Get employee (must be under this TL)
            employee = UserProfile.objects.get(
                id=employee_id,
                role='employee',
                reports_to=tl
            )

            # Only assign leads that belong to this TL
            leads = Lead.objects.filter(
                id__in=lead_ids,
                assigned_to=tl
            )

            for lead in leads:
                lead.assigned_to = employee
                lead.save()

            try:
                create_notification(
                    from_user=request.user,
                    to_users=[employee.user],
                    title="📋 New Lead(s) Assigned",
                    description=f"Team Leader {request.user.get_full_name()} assigned {len(lead_ids)} lead(s) to you.",
                )
            except Exception:
                pass

            return JsonResponse({'status': 'success'})

        except Exception as e:
            print("ERROR:", e)
            return JsonResponse({'status': 'error', 'message': str(e)})

    return JsonResponse({'status': 'error'})

@user_passes_test(tl_required, login_url='/login/')
def employee_performance(request, id):
    tl = request.user.profile

    # Get employee (must belong to this TL)
    employee = get_object_or_404(
        UserProfile,
        id=id,
        role='employee',
        reports_to=tl
    )

    # Leads assigned to this employee
    leads = Lead.objects.filter(
        assigned_to=employee
    ).order_by('-created_at')

    # KPIs
    total_leads = leads.count()

    hot_leads = leads.filter(temperature='hot').count()

    # 🔥 New = stage 'new' OR recently assigned
    new_leads = leads.filter(stage='new').count()

    closed_leads = leads.filter(stage='closed').count()

    return render(request, 'teamleader/employee_performance.html', {
        'employee': employee,
        'leads': leads,
        'total_leads': total_leads,
        'hot_leads': hot_leads,
        'new_leads': new_leads,
        'closed_leads': closed_leads,
    })

@user_passes_test(tl_required, login_url='/login/')
def profile(request):
    user = request.user
    profile = user.profile

    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')

        # Update User model
        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        user.save()

        # Update UserProfile model
        profile.phone = phone

        if request.FILES.get('profile_pic'):
            profile.profile_pic = request.FILES.get('profile_pic')

        profile.save()

        messages.success(request, 'Profile updated successfully.')
        return redirect('profile')

    return render(
        request,
        'teamleader/profile.html',
        {
            'profile': profile,
            'user_obj': user,
        }
    )

@user_passes_test(tl_required, login_url='/login/')
def view_lead(request, id):
    tl = request.user.profile

    # employees under this TL
    team_ids = UserProfile.objects.filter(
        reports_to=tl
    ).values_list('id', flat=True)

    allowed_user_ids = list(team_ids) + [tl.id]

    item = get_object_or_404(
        Lead.objects.select_related(
            'assigned_to',
            'assigned_to__user',
            'assigned_to__reports_to',
            'assigned_to__reports_to__user',
            'branch'
        ),
        id=id,
        assigned_to_id__in=allowed_user_ids
    )

    # hierarchy
    employee = item.assigned_to
    assigned_tl = None
    assigned_manager = None

    if employee:
        if employee.role == 'employee':
            assigned_tl = employee.reports_to
        elif employee.role == 'tl':
            assigned_tl = employee

    if assigned_tl:
        assigned_manager = assigned_tl.reports_to

    calls = item.calls.order_by('-created_at')
    followups = item.followups.order_by('followup_at')
    wrapups = item.wrapups.order_by('-created_at')

    return render(
        request,
        'teamleader/lead.html',
        {
            'lead': item,
            'employee': employee,
            'tl': assigned_tl,
            'assigned_manager': assigned_manager,
            'calls': calls,
            'followups': followups,
            'wrapups': wrapups,
        }
    )

@user_passes_test(tl_required, login_url='/login/')
def apr_reports(request):
    tl_profile = request.user.profile
    from zoneinfo import ZoneInfo
    now_ist = timezone.now().astimezone(ZoneInfo('Asia/Kolkata'))
    current_month = now_ist.month
    current_year = now_ist.year

    employees = UserProfile.objects.filter(
        reports_to=tl_profile,
        role='employee',
        status='Enabled',
    ).select_related('user', 'branch')

    employee_data = []
    total_present_this_month = 0
    total_calls_this_month = 0
    for emp in employees:
        present_days = Attendance.objects.filter(
            employee=emp,
            date__month=current_month,
            date__year=current_year,
            punch_in__isnull=False,
        ).count()
        total_calls = CallLog.objects.filter(
            called_by=emp,
            created_at__month=current_month,
            created_at__year=current_year,
        ).count()
        total_present_this_month += present_days
        total_calls_this_month += total_calls
        employee_data.append({
            'profile': emp,
            'name': emp.user.get_full_name(),
            'phone': emp.phone,
            'branch': emp.branch.name if emp.branch else 'N/A',
            'present_days': present_days,
            'total_calls': total_calls,
        })

    return render(request, 'teamleader/apr_reports.html', {
        'employee_data': employee_data,
        'month': now_ist.strftime('%B %Y'),
        'total_team_members': len(employee_data),
        'total_present_this_month': total_present_this_month,
        'total_calls_this_month': total_calls_this_month,
    })

@user_passes_test(tl_required, login_url='/login/')
def employee_apr_report(request, id):
    import json as _json
    from dash.models import Attendance as DashAttendance
    tl = request.user.profile

    employee = get_object_or_404(
        UserProfile.objects.select_related('user', 'branch'),
        id=id,
        reports_to=tl,
        role='employee',
    )

    attendance_qs = DashAttendance.objects.filter(
        employee=employee,
    ).order_by('-date')

    daily_data = []
    late_count = 0

    for att in attendance_qs:
        is_present = att.punch_in is not None
        is_late = False
        if att.punch_in:
            is_late = att.punch_in.time() > time_obj(9, 30)
            if is_late:
                late_count += 1

        day_calls = list(
            CallLog.objects.filter(
                called_by=employee,
                created_at__date=att.date,
            ).select_related('lead')
        )

        day_pings = list(
            LocationPing.objects.filter(
                employee=employee.user,
                timestamp__date=att.date,
            ).order_by('timestamp')
        )

        ping_coords = _json.dumps(
            [[float(p.latitude), float(p.longitude)] for p in day_pings]
        )

        daily_data.append({
            'date':       att.date,
            'punch_in':   att.punch_in,
            'punch_out':  att.punch_out,
            'is_present': is_present,
            'is_late':    is_late,
            'calls':      day_calls,
            'call_count': len(day_calls),
            'ping_count': len(day_pings),
            'ping_coords': ping_coords,
        })

    total_days   = attendance_qs.count()
    present_days = attendance_qs.filter(punch_in__isnull=False).count()
    absent_days  = total_days - present_days
    att_pct      = round((present_days / total_days * 100), 1) if total_days else 0

    return render(request, 'teamleader/individual_apr_report.html', {
        'employee':              employee,
        'daily_data':            daily_data,
        'total_days':            total_days,
        'present_days':          present_days,
        'absent_days':           absent_days,
        'late_marks':            late_count,
        'leave_days':            0,
        'attendance_percentage': att_pct,
    })


@user_passes_test(tl_required, login_url='/login/')
def apr_day_detail(request, report_id, date_str):
    from dash.models import Attendance as DashAttendance
    tl = request.user.profile

    employee = get_object_or_404(
        UserProfile.objects.select_related('user', 'branch'),
        id=report_id,
        reports_to=tl,
        role='employee',
    )

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        from django.http import Http404
        raise Http404("Invalid date format")

    attendance = DashAttendance.objects.filter(
        employee=employee,
        date=target_date
    ).first()

    total_hours = None
    if attendance and attendance.punch_in and attendance.punch_out:
        delta = attendance.punch_out - attendance.punch_in
        total_hours = round(delta.total_seconds() / 3600, 2)

    call_logs = list(
        CallLog.objects.filter(
            called_by=employee,
            created_at__date=target_date,
        ).select_related('lead').order_by('created_at')
    )

    lead_ids = [c.lead_id for c in call_logs if c.lead_id]
    from dash.models import Lead
    leads = Lead.objects.filter(id__in=lead_ids)

    pings = list(
        LocationPing.objects.filter(
            employee=employee.user,
            timestamp__date=target_date,
        ).order_by('timestamp')
    )

    import json as _json
    ping_coords = _json.dumps([
        {'lat': float(p.latitude), 'lng': float(p.longitude), 'time': p.timestamp.strftime('%I:%M %p')}
        for p in pings
    ])

    return render(request, 'teamleader/apr_day_detail.html', {
        'employee': employee,
        'date': target_date,
        'attendance': attendance,
        'total_hours': total_hours,
        'call_logs': call_logs,
        'leads': leads,
        'ping_coords': ping_coords,
        'ping_count': len(pings),
        'report_id': report_id,
    })

# ============================================================
# APR REPORT DETAIL (alias with profile_id param)
# ============================================================
@user_passes_test(tl_required, login_url='/login/')
def apr_report_detail(request, profile_id):
    return employee_apr_report(request, id=profile_id)


# ============================================================
# LEAD LIST
# ============================================================
@user_passes_test(tl_required, login_url='/login/')
def lead_list(request):
    tl = request.user.profile
    employees = UserProfile.objects.filter(reports_to=tl, role='employee', status='Enabled')
    leads = Lead.objects.filter(
        Q(assigned_to__in=employees) | Q(assigned_to=tl)
    ).select_related('assigned_to__user', 'branch').order_by('-created_at')
    return render(request, 'teamleader/lead_list.html', {'leads': leads})


# ============================================================
# LEAD DETAIL
# ============================================================
@user_passes_test(tl_required, login_url='/login/')
def lead_detail(request, lead_id):
    from dash.models import FollowUp, CallWrapUp
    tl = request.user.profile
    employees = UserProfile.objects.filter(reports_to=tl, role='employee', status='Enabled')
    allowed_ids = list(employees.values_list('id', flat=True)) + [tl.id]
    lead = get_object_or_404(Lead, id=lead_id, assigned_to_id__in=allowed_ids)
    call_logs = CallLog.objects.filter(lead=lead).select_related('called_by__user').order_by('-created_at')
    call_log_data = []
    for call in call_logs:
        wrapup = getattr(call, 'wrapup', None)
        recording_url = call.recording.url if call.recording else None
        call_log_data.append({
            'call': call,
            'wrapup': wrapup,
            'recording_url': recording_url,
        })
    follow_ups = FollowUp.objects.filter(lead=lead).order_by('followup_at')
    return render(request, 'teamleader/lead_detail.html', {
        'lead': lead,
        'call_log_data': call_log_data,
        'follow_ups': follow_ups,
    })


# ============================================================
# ASSIGN LEAD (POST assigns lead to employee)
# ============================================================
@user_passes_test(tl_required, login_url='/login/')
def assign_lead(request, lead_id):
    from dash.models import FollowUp
    if request.method == 'POST':
        tl = request.user.profile
        lead = get_object_or_404(Lead, id=lead_id, assigned_to=tl)
        employee_id = request.POST.get('employee_id')
        employee = get_object_or_404(UserProfile, id=employee_id, role='employee', reports_to=tl)
        lead.assigned_to = employee
        lead.save()
        messages.success(request, f'Lead assigned to {employee.user.get_full_name()}.')
    return redirect('index')


# ============================================================
# EMPLOYEE LEADS
# ============================================================
@user_passes_test(tl_required, login_url='/login/')
def employee_leads(request, employee_id):
    from dash.models import FollowUp
    tl = request.user.profile
    employee = get_object_or_404(UserProfile, id=employee_id, role='employee', reports_to=tl)
    leads = Lead.objects.filter(assigned_to=employee).select_related('branch').order_by('-created_at')
    lead_data = []
    for lead in leads:
        last_call = CallLog.objects.filter(lead=lead).order_by('-created_at').first()
        followup = FollowUp.objects.filter(lead=lead, followup_status='pending').order_by('followup_at').first()
        lead_data.append({
            'lead': lead,
            'last_call': last_call,
            'followup': followup,
        })
    return render(request, 'teamleader/employee_leads.html', {
        'employee': employee,
        'lead_data': lead_data,
    })


# ============================================================
# NOTIFICATIONS PAGE (Team Leader)
# ============================================================
@user_passes_test(tl_required, login_url='/login/')
def notifications_list(request):
    if request.method == 'POST':
        action   = request.POST.get('action')
        notif_id = request.POST.get('notification_id')
        if action == 'mark_all_read':
            mark_all_read(request.user)
        elif action == 'mark_read' and notif_id:
            mark_read(request.user, notif_id)
        return redirect('notifications_list')
    notifications = get_user_notifications(request.user, limit=50)
    unread_count  = get_unread_count(request.user)
    return render(request, 'teamleader/notifications.html', {
        'notifications': notifications,
        'unread_count':  unread_count,
    })
