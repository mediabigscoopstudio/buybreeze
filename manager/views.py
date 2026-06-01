from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.db.models import Q
from dash.models import Attendance, Branch, LeaveRequest, UserProfile, Lead
from datetime import timedelta, datetime
from dash.otp_utils import generate_otp, send_otp
from django.utils import timezone
from django.contrib.auth.models import User
from dash.notifications import (
    create_notification, get_admins,
    get_user_notifications, get_unread_count,
    mark_all_read, mark_read,
)
import json
from django.http import JsonResponse




# ============================================================
# AUTH GUARD
# ============================================================
def manager_required(user):

    return (
        user.is_authenticated and
        hasattr(user, 'profile') and
        user.profile.role == 'manager'
    )


# ============================================================
# AUTH VIEWS
# ============================================================
def login_view(request):

    if request.user.is_authenticated:
        return redirect('index')

    if request.method == 'POST':

        phone = request.POST.get('phone')

        # =====================================
        # FIND USER PROFILE
        # =====================================
        try:

            phone = phone.strip()

            profile = UserProfile.objects.filter(
                phone__icontains=phone,
                role='manager'
            ).first()

            print("\n===================================")
            print("PHONE ENTERED :", phone)
            print("PROFILE FOUND :", profile)
            print("===================================\n")

            if not profile:

                messages.error(
                    request,
                    'Phone number not registered.'
                )

                return redirect('/login/')

            user = profile.user

        except Exception as e:

            print(e)

            messages.error(
                request,
                'Login error.'
            )

            return redirect('/login/')

        # =====================================
        # GENERATE OTP
        # =====================================
        otp = generate_otp()

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

        return redirect('verify_otp')

    return render(
        request,
        'manager/signin.html'
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
            # MANAGER REDIRECT
            # =====================================
            return redirect(
                'https://manager.bigscooptesting.online/'
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
        'manager/verify_otp.html'
    )


# ============================================================
# LOGOUT
# ============================================================
def logout_view(request):
    logout(request)
    return redirect(
        '/login/'
    )

# ============================================================
# DASHBOARD HOME
# ============================================================
@user_passes_test(
    manager_required,
    login_url='/login/'
)
def index(request):
    manager_profile = request.user.profile
    today = timezone.localdate()

    team_leaders = UserProfile.objects.filter(
        reports_to=manager_profile,
        role='tl',
        status='Enabled',
    ).select_related('user', 'branch')
    employees = UserProfile.objects.filter(
        reports_to__in=list(team_leaders) + [manager_profile],
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
    pending_leaves = LeaveRequest.objects.filter(
        employee__in=employees,
        leave_status='pending',
    ).count()
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

    return render(request, 'manager/index.html', {
        'total_leads': total_leads,
        'leads_today': leads_today,
        'calls_today': calls_today,
        'present_today': present_today,
        'absent_today': absent_today,
        'pending_leaves': pending_leaves,
        'hot_leads': hot_leads,
        'converted_leads': converted_leads,
        'recent_calls': recent_calls,
        'recent_leads': recent_leads,
        'total_team': employees.count(),
    })


# ============================================================
# ASSIGN LEAD TO TL (Manager)
# ============================================================

@user_passes_test(manager_required)
def assign_to_tl(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)

            lead_ids = data.get('lead_ids', [])
            tl_id = data.get('tl_id')

            if not lead_ids or not tl_id:
                return JsonResponse({'status': 'error', 'message': 'Missing data'})

            tl = UserProfile.objects.get(id=tl_id, role='tl')

            leads = Lead.objects.filter(id__in=lead_ids)

            for lead in leads:
                lead.assigned_to = tl
                lead.save()

            try:
                create_notification(
                    from_user=request.user,
                    to_users=[tl.user],
                    title="📋 New Lead(s) Assigned",
                    description=f"{request.user.get_full_name()} assigned {len(lead_ids)} lead(s) to you.",
                )
            except Exception:
                pass

            return JsonResponse({'status': 'success'})

        except Exception as e:
            print("ERROR:", e)
            return JsonResponse({'status': 'error', 'message': str(e)})

    return JsonResponse({'status': 'error'})


# ============================================================
# UNASSIGN LEAD FROM TL (Manager)
# ============================================================
@user_passes_test(manager_required, login_url='/login/')
def unassign_lead(request, lead_id):
    if request.method == 'POST':
        manager_profile = request.user.profile
        lead = get_object_or_404(Lead, id=lead_id, assigned_to_manager=manager_profile)
        lead.assigned_to_tl = None
        lead.assigned_to    = None
        lead.save()
        messages.success(request, f'Lead "{lead.name}" unassigned from TL.')
    return redirect('index')

@user_passes_test(manager_required, login_url='/login/')
def tl_performance(request, id):
    manager = request.user.profile

    # Get TL (must belong to same branch for safety)
    tl = get_object_or_404(
        UserProfile,
        id=id,
        role='tl',
        branch=manager.branch
    )

    # Leads assigned to this TL
    leads = Lead.objects.filter(
    Q(assigned_to=manager) |
    Q(assigned_to__reports_to=manager)
    ).order_by('-created_at')

    # KPIs
    total_leads = leads.count()
    hot_leads = leads.filter(temperature='hot').count()
    new_leads = leads.filter(stage='new').count()
    closed_leads = leads.filter(stage='closed').count()

    return render(request, 'manager/tl_performance.html', {
        'tl': tl,
        'leads': leads,
        'total_leads': total_leads,
        'hot_leads': hot_leads,
        'new_leads': new_leads,
        'closed_leads': closed_leads,
    })


from dash.models import UserProfile 
from dash.models import Lead
@user_passes_test(manager_required, login_url='/login/')
def profile_settings(request):
    user = request.user
    profile = user.profile
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name  = request.POST.get('last_name')
        email      = request.POST.get('email')
        phone      = request.POST.get('phone')
        # Update User model
        user.first_name = first_name
        user.last_name  = last_name
        user.email      = email
        user.save()
        # Update UserProfile model
        profile.phone = phone
        if request.FILES.get('profile_pic'):
            profile.profile_pic = request.FILES['profile_pic']
        profile.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('profile_settings')

    return render(request, 'manager/profile.html', {
        'profile': profile
    })

from dash.models import (
    Lead,
    LeadAssignmentHistory,
    CallLog,
    CallWrapUp,
    FollowUp
)

@user_passes_test(manager_required, login_url='/login/')
def view_lead(request, id):
    manager = request.user.profile

    team_ids = UserProfile.objects.filter(
        reports_to=manager
    ).values_list('id', flat=True)

    allowed_user_ids = list(team_ids) + [manager.id]

    item = get_object_or_404(
        Lead.objects.select_related(
            'assigned_to',
            'assigned_to__user',
            'assigned_to__reports_to',
            'assigned_to__reports_to__user',
            'assigned_to__reports_to__reports_to',
            'assigned_to__reports_to__reports_to__user',
            'branch'
        ),
        id=id,
        assigned_to_id__in=allowed_user_ids
    )

    # Assignment hierarchy
    employee = item.assigned_to
    tl = None
    assigned_manager = None

    if employee:
        tl = employee.reports_to

    if tl:
        assigned_manager = tl.reports_to

    calls = item.calls.order_by('-created_at')
    followups = item.followups.order_by('followup_at')
    wrapups = item.wrapups.order_by('-created_at')

    return render(
        request,
        'manager/lead.html',
        {
            'lead': item,
            'employee': employee,
            'tl': tl,
            'assigned_manager': assigned_manager,
            'calls': calls,
            'followups': followups,
            'wrapups': wrapups,
        }
    )

@user_passes_test(manager_required, login_url='/login/')
def apr_reports(request):
    manager_profile = request.user.profile
    current_month = timezone.now().month
    current_year = timezone.now().year

    team_leaders = UserProfile.objects.filter(
        reports_to=manager_profile,
        role='tl',
        status='Enabled',
    )
    employee_profiles = UserProfile.objects.filter(
        reports_to__in=list(team_leaders) + [manager_profile],
        role='employee',
        status='Enabled',
    ).select_related('user', 'branch')

    employee_data = []
    total_present_this_month = 0
    total_calls_this_month = 0
    for emp in employee_profiles:
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

    return render(
        request,
        'manager/apr_reports.html',
        {
            'employee_data': employee_data,
            'month': timezone.now().strftime('%B %Y'),
            'total_team_members': len(employee_data),
            'total_present_this_month': total_present_this_month,
            'total_calls_this_month': total_calls_this_month,
        }
    )


@user_passes_test(manager_required, login_url='/login/')
def individual_apr_report(request, id):
    from employee.models import Attendance as EmployeeAttendance

    manager = request.user.profile
    team_leaders = UserProfile.objects.filter(reports_to=manager, role='tl')
    employee_profile = get_object_or_404(
        UserProfile.objects.select_related(
            'user',
            'reports_to',
            'reports_to__user'
        ),
        id=id,
        role='employee',
        reports_to__in=list(team_leaders) + [manager],
    )
    attendance_qs = EmployeeAttendance.objects.filter(
        employee=employee_profile.user
    ).order_by('-date')

    attendances = []
    late_marks = 0
    for attendance in attendance_qs:
        is_late = bool(attendance.punch_in_time and attendance.punch_in_time.time() > datetime.strptime('09:30', '%H:%M').time())
        if is_late:
            late_marks += 1
        working_hours = None
        if attendance.punch_in_time and attendance.punch_out_time:
            working_hours = round((attendance.punch_out_time - attendance.punch_in_time).total_seconds() / 3600, 2)
        status = 'present' if attendance.punch_in_time else 'absent'
        attendances.append({
            'date': attendance.date,
            'check_in': attendance.punch_in_time,
            'check_out': attendance.punch_out_time,
            'working_hours': working_hours,
            'status': status,
            'is_late': is_late,
            'notes': '',
        })

    total_days = attendance_qs.count()
    present_days = attendance_qs.filter(punch_in_time__isnull=False).count()
    absent_days = max(total_days - present_days, 0)
    leave_days = 0
    half_days = 0
    attendance_percentage = round((present_days / total_days) * 100, 1) if total_days else 0
    last_attendance_date = attendances[0]['date'] if attendances else None
    last_attendance_status = attendances[0]['status'].title() if attendances else None

    return render(
        request,
        'manager/individual_apr_report.html',
        {
            'employee': employee_profile,
            'attendances': attendances,
            'total_days': total_days,
            'present_days': present_days,
            'absent_days': absent_days,
            'leave_days': leave_days,
            'half_days': half_days,
            'late_marks': late_marks,
            'attendance_percentage': attendance_percentage,
            'last_attendance_date': last_attendance_date,
            'last_attendance_status': last_attendance_status,
        }
    )


@user_passes_test(manager_required, login_url='/login/')
def apr_day_detail(request, report_id, date_str):
    from employee.models import Attendance as EmployeeAttendance, LocationPing
    from dash.models import Lead
    import json as _json

    manager = request.user.profile
    team_leaders = UserProfile.objects.filter(reports_to=manager, role='tl')
    employee_profile = get_object_or_404(
        UserProfile,
        id=report_id,
        role='employee',
        reports_to__in=list(team_leaders) + [manager],
    )

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        from django.http import Http404
        raise Http404("Invalid date format")

    legacy_attendance = EmployeeAttendance.objects.filter(
        employee=employee_profile.user,
        date=target_date
    ).first()

    total_hours = None
    if legacy_attendance and legacy_attendance.punch_in_time and legacy_attendance.punch_out_time:
        delta = legacy_attendance.punch_out_time - legacy_attendance.punch_in_time
        total_hours = round(delta.total_seconds() / 3600, 2)

    call_logs = CallLog.objects.filter(
        called_by=employee_profile,
        created_at__date=target_date
    ).select_related('lead').order_by('created_at')

    lead_ids = call_logs.values_list('lead_id', flat=True).distinct()
    leads = Lead.objects.filter(id__in=lead_ids)

    pings = LocationPing.objects.filter(
        employee=employee_profile.user,
        timestamp__date=target_date
    ).order_by('timestamp')

    ping_coords = _json.dumps([
        {'lat': float(p.latitude), 'lng': float(p.longitude), 'time': p.timestamp.strftime('%I:%M %p')}
        for p in pings
    ])

    return render(request, 'manager/apr_day_detail.html', {
        'employee': employee_profile,
        'date': target_date,
        'attendance': legacy_attendance,
        'total_hours': total_hours,
        'call_logs': call_logs,
        'leads': leads,
        'ping_coords': ping_coords,
        'ping_count': pings.count(),
        'report_id': report_id,
    })

# ============================================================
# NOTIFICATIONS PAGE (Manager)
# ============================================================
@user_passes_test(manager_required, login_url='/login/')
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
    return render(request, 'manager/notifications.html', {
        'notifications': notifications,
        'unread_count':  unread_count,
    })
