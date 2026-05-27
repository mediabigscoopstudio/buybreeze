from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.db.models import Count, Q
from dash.models import Branch, UserProfile, Lead, CallLog
from django.http import JsonResponse
import json
from dash.otp_utils import generate_otp, send_otp
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import timedelta, datetime, date, time as time_obj
from employee.models import Attendance, LocationPing


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
    tl = request.user.profile
    period = request.GET.get('period', 'all')
    today = date.today()

    if period == 'today':
        start_date, end_date, period_label = today, today, 'Today'
    elif period == 'yesterday':
        yd = today - timedelta(days=1)
        start_date, end_date, period_label = yd, yd, 'Yesterday'
    elif period == 'this_week':
        start_date = today - timedelta(days=today.weekday())
        end_date, period_label = today, 'This Week'
    elif period == 'this_month':
        start_date = today.replace(day=1)
        end_date, period_label = today, 'This Month'
    elif period == 'this_quarter':
        qm = ((today.month - 1) // 3) * 3 + 1
        start_date = today.replace(month=qm, day=1)
        end_date, period_label = today, 'This Quarter'
    else:
        start_date = end_date = None
        period_label = 'All Time'

    leads = Lead.objects.filter(assigned_to=tl)
    if start_date:
        leads = leads.filter(created_at__date__range=(start_date, end_date))
    leads = leads.order_by('-created_at')

    total_leads  = leads.count()
    hot_leads    = leads.filter(temperature='hot').count()
    new_leads    = leads.filter(stage='new').count()
    closed_leads = leads.filter(stage='closed').count()

    if start_date:
        dr       = Q(assigned_leads__created_at__date__range=(start_date, end_date))
        hot_q    = dr & Q(assigned_leads__temperature='hot')
        new_q    = dr & Q(assigned_leads__stage='new')
    else:
        dr    = Q()
        hot_q = Q(assigned_leads__temperature='hot')
        new_q = Q(assigned_leads__stage='new')

    employees = UserProfile.objects.filter(
        role='employee',
        status='Enabled',
        reports_to=tl,
    ).select_related('user').annotate(
        total_leads=Count('assigned_leads', filter=dr,    distinct=True),
        hot_leads  =Count('assigned_leads', filter=hot_q, distinct=True),
        new_leads  =Count('assigned_leads', filter=new_q, distinct=True),
    )

    return render(request, 'teamleader/index.html', {
        'leads':        leads,
        'total_leads':  total_leads,
        'hot_leads':    hot_leads,
        'new_leads':    new_leads,
        'closed_leads': closed_leads,
        'employees':    employees,
        'period':       period,
        'period_label': period_label,
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
    tl = request.user.profile

    employees = UserProfile.objects.filter(
        reports_to=tl,
        role='employee',
        status='Enabled',
    ).select_related('user', 'branch')

    apr_records     = []
    total_present_all = 0
    att_pcts        = []

    for emp in employees:
        qs         = Attendance.objects.filter(employee=emp.user)
        total_days = qs.count()
        present    = qs.filter(punch_in_time__isnull=False).count()
        absent     = total_days - present

        late_marks = sum(
            1 for att in qs
            if att.punch_in_time and att.punch_in_time.time() > time_obj(9, 30)
        )

        pct = round((present / total_days * 100), 1) if total_days else 0.0
        total_present_all += present
        att_pcts.append(pct)

        apr_records.append({
            'id':                  emp.id,
            'name':                emp.user.get_full_name() or emp.user.username,
            'role':                emp.role,
            'branch':              emp.branch.name if emp.branch else '—',
            'phone':               emp.phone,
            'profile_pic':         emp.profile_pic,
            'present_days':        present,
            'absent_days':         absent,
            'leave_days':          0,
            'late_marks':          late_marks,
            'attendance_percentage': pct,
        })

    avg_attendance = round(sum(att_pcts) / len(att_pcts), 1) if att_pcts else 0.0

    return render(request, 'teamleader/apr_reports.html', {
        'apr_records':      apr_records,
        'total_employees':  len(apr_records),
        'avg_attendance':   avg_attendance,
        'total_present':    total_present_all,
        'total_leave':      0,
    })

@user_passes_test(tl_required, login_url='/login/')
def employee_apr_report(request, id):
    import json as _json
    tl = request.user.profile

    employee = get_object_or_404(
        UserProfile.objects.select_related('user', 'branch'),
        id=id,
        reports_to=tl,
        role='employee',
    )

    attendance_qs = Attendance.objects.filter(
        employee=employee.user,
    ).order_by('-date')

    daily_data = []
    late_count = 0

    for att in attendance_qs:
        is_present = att.punch_in_time is not None
        is_late    = False
        if att.punch_in_time:
            is_late = att.punch_in_time.time() > time_obj(9, 30)
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
            'punch_in':   att.punch_in_time,
            'punch_out':  att.punch_out_time,
            'is_present': is_present,
            'is_late':    is_late,
            'calls':      day_calls,
            'call_count': len(day_calls),
            'ping_count': len(day_pings),
            'ping_coords': ping_coords,
        })

    total_days   = attendance_qs.count()
    present_days = attendance_qs.filter(punch_in_time__isnull=False).count()
    absent_days  = total_days - present_days
    att_pct      = round((present_days / total_days * 100), 1) if total_days else 0

    return render(request, 'teamleader/individual_apr_report.html', {
        'employee':             employee,
        'daily_data':           daily_data,
        'total_days':           total_days,
        'present_days':         present_days,
        'absent_days':          absent_days,
        'late_marks':           late_count,
        'leave_days':           0,
        'attendance_percentage': att_pct,
    })


@user_passes_test(tl_required, login_url='/login/')
def apr_day_detail(request, report_id, date_str):
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

    attendance = Attendance.objects.filter(
        employee=employee.user,
        date=target_date
    ).first()

    total_hours = None
    if attendance and attendance.punch_in_time and attendance.punch_out_time:
        delta = attendance.punch_out_time - attendance.punch_in_time
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