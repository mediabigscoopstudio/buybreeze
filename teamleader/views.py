from django.shortcuts import render, redirect
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

    # Leads assigned to this TL
    leads = Lead.objects.filter(
        assigned_to=tl_profile
    ).select_related('branch').order_by('-created_at')

    total_leads      = leads.count()
    hot_leads        = leads.filter(temperature='hot').count()
    closed_leads     = leads.filter(stage='closed').count()
    total_employees  = employees.count()

    return render(request, 'teamleader/index.html', {
        'employees': employees,
        'leads': leads,
        'total_leads': total_leads,
        'hot_leads': hot_leads,
        'closed_leads': closed_leads,
        'total_employees': total_employees,
    })