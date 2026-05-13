from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.db.models import Count, Q
from dash.models import Branch, UserProfile, Lead
from datetime import timedelta, datetime
from dash.otp_utils import generate_otp, send_otp
from django.utils import timezone
from django.contrib.auth.models import User




# ============================================================
# AUTH GUARD
# ============================================================
def manager_required(user):

    return (
        user.is_authenticated and
        hasattr(user, 'profile') and
        user.userprofile.role == 'manager'
    )


# ============================================================
# AUTH VIEWS
# ============================================================
def login_view(request):

    # =========================================
    # ALREADY LOGGED IN
    # =========================================
    if request.user.is_authenticated:

        if manager_required(request.user):
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
                role='manager'
            )

            user = profile.user

        except UserProfile.DoesNotExist:

            messages.error(
                request,
                'Phone number not registered.'
            )

            return redirect('login_view')

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

            return redirect('login_view')

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

        return redirect('login_view')

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

        return redirect('login_view')

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

                return redirect('login_view')

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
                'http://manager.localhost:8000/'
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
        'http://manager.localhost:8000/login/'
    )

# ============================================================
# DASHBOARD HOME
# ============================================================
@user_passes_test(
    manager_required,
    login_url='/login/'
)
def index(request):
    manager = request.user.userprofile

    # ONLY leads assigned to this manager
    leads = Lead.objects.filter(
        assigned_to=manager
    ).order_by('-created_at')

    # KPIs
    total_leads = leads.count()
    hot_leads = leads.filter(temperature='hot').count()
    new_leads = leads.filter(stage='new').count()
    closed_leads = leads.filter(stage='closed').count()
    team_leaders = UserProfile.objects.filter(
    role='tl',
    status='Enabled',
    branch=manager.branch
    ).select_related('user').annotate(
    total_leads=Count('assigned_leads'),
    hot_leads=Count('assigned_leads', filter=Q(assigned_leads__temperature='hot')),
    new_leads=Count('assigned_leads', filter=Q(assigned_leads__stage='new'))
    )
    return render(request, 'manager/index.html', {
        'leads': leads,
        'total_leads': total_leads,
        'hot_leads': hot_leads,
        'new_leads': new_leads,
        'closed_leads': closed_leads,
        'team_leaders':team_leaders,
    })


# ============================================================
# ASSIGN LEAD TO TL (Manager)
# ============================================================
from django.http import JsonResponse
import json

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
                lead.assigned_to = tl   # 🔥 THIS IS THE KEY LINE
                lead.save()

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
        manager_profile = request.user.userprofile
        lead = get_object_or_404(Lead, id=lead_id, assigned_to_manager=manager_profile)
        lead.assigned_to_tl = None
        lead.assigned_to    = None
        lead.save()
        messages.success(request, f'Lead "{lead.name}" unassigned from TL.')
    return redirect('index')

@user_passes_test(manager_required, login_url='/login/')
def tl_performance(request, id):
    manager = request.user.userprofile

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