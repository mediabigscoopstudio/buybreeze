from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.db.models import Count, Q
from dash.models import Branch, UserProfile, Lead
from django.http import JsonResponse
import json
from dash.otp_utils import generate_otp, send_otp
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import timedelta, datetime


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

    # Only leads assigned to this TL
    leads = Lead.objects.filter(
        assigned_to=tl
    ).order_by('-created_at')

    # KPIs
    total_leads = leads.count()
    hot_leads = leads.filter(temperature='hot').count()
    new_leads = leads.filter(stage='new').count()
    closed_leads = leads.filter(stage='closed').count()
    employees = UserProfile.objects.filter(
    role='employee',
    status='Enabled',
    reports_to=tl
    ).select_related('user').annotate(

    # Leads assigned to this employee
    total_leads=Count('assigned_leads', distinct=True),

    hot_leads=Count(
        'assigned_leads',
        filter=Q(assigned_leads__temperature='hot'),
        distinct=True
    ),

    # 🔥 New = leads recently assigned (or stage='new')
    new_leads=Count(
        'assigned_leads',
        filter=Q(assigned_leads__stage='new'),
        distinct=True
    )
    )

    return render(request, 'teamleader/index.html', {
        'leads': leads,
        'total_leads': total_leads,
        'hot_leads': hot_leads,
        'new_leads': new_leads,
        'closed_leads': closed_leads,
        'employees':employees,
    })

@user_passes_test(tl_required)
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

from django.contrib.auth.decorators import user_passes_test
from dash.models import UserProfile, Lead

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