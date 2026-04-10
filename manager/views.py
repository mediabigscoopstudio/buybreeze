from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.db.models import Count, Q
from dash.models import Branch, UserProfile, Lead


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
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            try:
                if user.profile.role == 'manager':
                    login(request, user)
                    return redirect('index')
                else:
                    messages.error(request, 'Access Denied: This panel is for managers only.')
            except UserProfile.DoesNotExist:
                messages.error(request, 'Profile not configured. Contact Admin.')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'manager/signin.html')


def logout_view(request):
    logout(request)
    return redirect('login_view')


# ============================================================
# DASHBOARD
# ============================================================
@user_passes_test(manager_required, login_url='/login/')
def index(request):
    # Get manager's branch
    manager_profile = request.user.profile
    branch = manager_profile.branch

    # Team leaders under this branch
    team_leaders = UserProfile.objects.filter(
        role='tl', status='Enabled', branch=branch
    ).select_related('user', 'branch').annotate(
        assigned_leads_count=Count('assigned_leads'),
        hot_leads_count=Count('assigned_leads', filter=Q(assigned_leads__temperature='hot')),
        closed_leads_count=Count('assigned_leads', filter=Q(assigned_leads__stage='closed')),
    )

    # Leads in this branch
    leads = Lead.objects.filter(branch=branch).select_related('assigned_to__user').order_by('-created_at')

    total_leads     = leads.count()
    assigned_leads  = leads.filter(assigned_to__isnull=False).count()
    unassigned_leads = leads.filter(assigned_to__isnull=True).count()
    total_tls       = team_leaders.count()

    return render(request, 'manager/index.html', {
        'team_leaders': team_leaders,
        'leads': leads,
        'total_leads': total_leads,
        'assigned_leads': assigned_leads,
        'unassigned_leads': unassigned_leads,
        'total_tls': total_tls,
    })


# ============================================================
# ASSIGN LEAD TO TL
# ============================================================
@user_passes_test(manager_required, login_url='/login/')
def assign_lead(request, lead_id):
    if request.method == 'POST':
        lead   = get_object_or_404(Lead, id=lead_id)
        tl_id  = request.POST.get('tl_id')
        if tl_id:
            tl_profile = get_object_or_404(UserProfile, id=tl_id, role='tl')
            lead.assigned_to = tl_profile
            lead.save()
            messages.success(request, f'Lead "{lead.name}" assigned to {tl_profile.user.get_full_name()}.')
        else:
            messages.error(request, 'Please select a Team Leader.')
    return redirect('index')


# ============================================================
# UNASSIGN LEAD
# ============================================================
@user_passes_test(manager_required, login_url='/login/')
def unassign_lead(request, lead_id):
    if request.method == 'POST':
        lead = get_object_or_404(Lead, id=lead_id)
        lead.assigned_to = None
        lead.save()
        messages.success(request, f'Lead "{lead.name}" unassigned.')
    return redirect('index')