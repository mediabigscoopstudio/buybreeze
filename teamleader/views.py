from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.db.models import Count, Q
from dash.models import Branch, UserProfile, Lead, CallLog


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
    if request.user.is_authenticated:
        return redirect('index')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            try:
                if user.profile.role == 'tl':
                    login(request, user)
                    return redirect('index')
                else:
                    messages.error(request, 'Access Denied: This panel is for Team Leaders only.')
            except UserProfile.DoesNotExist:
                messages.error(request, 'Profile not configured. Contact Admin.')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'teamleader/signin.html')


def logout_view(request):
    logout(request)
    return redirect('login_view')


# ============================================================
# DASHBOARD
# ============================================================
@user_passes_test(tl_required, login_url='/login/')
def index(request):
    tl_profile = request.user.profile

    # Employees reporting to this TL
    employees = UserProfile.objects.filter(
        reports_to=tl_profile, status='Enabled'
    ).select_related('user', 'branch').annotate(
        assigned_leads_count=Count('assigned_leads'),
        hot_leads_count=Count('assigned_leads', filter=Q(assigned_leads__temperature='hot')),
        closed_leads_count=Count('assigned_leads', filter=Q(assigned_leads__stage='closed')),
        calls_count=Count('call_logs'),
    )

    # Only leads assigned TO this TL by Manager
    leads = Lead.objects.filter(
        assigned_to_tl=tl_profile
    ).select_related('assigned_to__user', 'branch').order_by('-created_at')

    total_leads      = leads.count()
    hot_leads        = leads.filter(temperature='hot').count()
    closed_leads     = leads.filter(stage='closed').count()
    total_employees  = employees.count()
    assigned_leads   = leads.filter(assigned_to__isnull=False).count()
    unassigned_leads = leads.filter(assigned_to__isnull=True).count()

    return render(request, 'teamleader/index.html', {
        'employees': employees,
        'leads': leads,
        'total_leads': total_leads,
        'hot_leads': hot_leads,
        'closed_leads': closed_leads,
        'total_employees': total_employees,
        'assigned_leads': assigned_leads,
        'unassigned_leads': unassigned_leads,
    })


# ============================================================
# ASSIGN LEAD TO EMPLOYEE (TL)
# ============================================================
@user_passes_test(tl_required, login_url='/login/')
def assign_lead(request, lead_id):
    if request.method == 'POST':
        tl_profile = request.user.profile
        lead = get_object_or_404(Lead, id=lead_id, assigned_to_tl=tl_profile)
        emp_id = request.POST.get('emp_id')
        if emp_id:
            emp_profile = get_object_or_404(UserProfile, id=emp_id, reports_to=tl_profile)
            lead.assigned_to = emp_profile
            lead.save()
            messages.success(request, f'Lead "{lead.name}" assigned to {emp_profile.user.get_full_name()}.')
        else:
            messages.error(request, 'Please select an Employee.')
    return redirect('index')


# ============================================================
# UNASSIGN LEAD FROM EMPLOYEE (TL)
# ============================================================
@user_passes_test(tl_required, login_url='/login/')
def unassign_lead(request, lead_id):
    if request.method == 'POST':
        tl_profile = request.user.profile
        lead = get_object_or_404(Lead, id=lead_id, assigned_to_tl=tl_profile)
        lead.assigned_to = None
        lead.save()
        messages.success(request, f'Lead "{lead.name}" unassigned from employee.')
    return redirect('index')