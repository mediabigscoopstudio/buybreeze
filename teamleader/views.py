from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.db.models import Count, Q
from dash.models import Branch, UserProfile, Lead
from django.http import JsonResponse
import json

def tl_required(user):
    return (
        user.is_authenticated and
        hasattr(user, 'userprofile') and
        user.userprofile.role == 'tl'
    )

def login_view(request):
    if request.user.is_authenticated:
        return redirect('index')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            try:
                if user.userprofile.role == 'tl':
                    login(request, user)
                    return redirect('index')
                else:
                    messages.error(request, 'Access Denied: This panel is for team leaders only.')
            except UserProfile.DoesNotExist:
                messages.error(request, 'Profile not configured. Contact Admin.')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'teamleader/signin.html')

def logout_view(request):
    logout(request)
    return redirect('login_view')

@user_passes_test(tl_required, login_url='/login/')
def index(request):
    tl = request.user.userprofile

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

            tl = request.user.userprofile

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
    tl = request.user.userprofile

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