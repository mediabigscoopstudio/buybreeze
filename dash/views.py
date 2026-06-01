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
from .services import assign_lead, can_assign
from .models import (
    Branch, UserProfile, Lead, CallLog, CallWrapUp, FollowUp, SystemSetting
)
from django.contrib.admin.views.decorators import staff_member_required
from django.apps import apps  # <--- Add this at the very top of your file with your other imports!
from django.http import JsonResponse
from employee.models import LocationPing # <-- Make sure this is imported at the top!
from datetime import datetime
from django.shortcuts import get_object_or_404
from .otp_utils import generate_otp, send_otp
from django.contrib.auth.decorators import login_required
from dash.models import NotificationRecipient
from dash.notifications import (
    create_notification, get_admins,
    get_hr_users, get_manager_for_employee,
    get_user_notifications, get_unread_count,
    mark_all_read, mark_read,
)

# ============================================================
# AUTH GUARD
# ============================================================
def superadmin_required(user):
    return (
        user.is_authenticated and
        hasattr(user, 'profile') and
        user.profile.role == 'admin'
    )




# ============================================================
# AUTH VIEWS
# ============================================================
def login_view(request):

    # =========================================
    # ALREADY LOGGED IN
    # =========================================
    if request.user.is_authenticated:

        # ONLY SUPERADMIN ALLOWED
        if request.user.is_superuser:
            return redirect('/')

        # FORCE LOGOUT OTHER USERS
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
                role='admin'
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
        'dash/signin.html'
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
            # SUPERADMIN REDIRECT
            # =====================================
            return redirect('/')

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
        'dash/verify_otp.html'
    )

# ============================================================
# LOGOUT
# ============================================================
def logout_view(request):
    logout(request)
    return redirect('/login/')

@login_required
def get_notifications(request):
    notifications = NotificationRecipient.objects.filter(
        user=request.user
    ).select_related('notification', 'notification__from_user').order_by(
        '-notification__created_at'
    )[:15]

    data = []
    unread_count = 0

    for item in notifications:
        if not item.is_read:
            unread_count += 1

        data.append({
            'id': item.id,
            'title': item.notification.title,
            'description': item.notification.description,
            'created_at': item.notification.created_at.strftime('%d %b %Y %I:%M %p'),
            'is_read': item.is_read,
        })

    return JsonResponse({
        'notifications': data,
        'unread_count': unread_count
    })


@login_required
def mark_notification_read(request, notification_id):
    try:
        notification = NotificationRecipient.objects.get(
            id=notification_id,
            user=request.user
        )

        notification.is_read = True
        notification.save()

        unread_count = NotificationRecipient.objects.filter(
            user=request.user,
            is_read=False
        ).count()

        return JsonResponse({
            'success': True,
            'unread_count': unread_count
        })

    except NotificationRecipient.DoesNotExist:
        return JsonResponse({
            'success': False
        })


# ============================================================
# DASHBOARD HOME
# ============================================================
@user_passes_test(superadmin_required, login_url='/login/')
def index(request):
    today = timezone.localdate()
    now = timezone.now()
    total_leads = Lead.objects.count()
    total_employees = UserProfile.objects.filter(
        role='employee',
        status='Enabled',
    ).count()
    total_calls_today = CallLog.objects.filter(created_at__date=today).count()
    followups_due_today = FollowUp.objects.filter(
        followup_status='pending',
        followup_at__date=today,
    ).count()
    pending_leaves = LeaveRequest.objects.filter(leave_status='pending').count()

    stage_data = Lead.objects.values('stage').annotate(count=Count('id'))
    branch_leads = Branch.objects.filter(status='Enabled').annotate(
        lead_count=Count('lead')
    ).order_by('name')
    recent_leads = Lead.objects.select_related(
        'assigned_to__user',
        'branch',
    ).order_by('-created_at')[:10]
    recent_calls = CallLog.objects.select_related(
        'lead',
        'called_by__user',
    ).order_by('-created_at')[:10]

    today_attendance = Attendance.objects.filter(date=today)
    present_count = today_attendance.filter(punch_in__isnull=False).count()
    active_count = today_attendance.filter(
        punch_in__isnull=False,
        punch_out__isnull=True,
    ).count()
    absent_count = today_attendance.filter(punch_in__isnull=True).count()

    upcoming_followups = FollowUp.objects.select_related('lead').filter(
        followup_status='pending',
        followup_at__gte=now,
        followup_at__lte=now + timedelta(hours=24)
    ).order_by('followup_at')[:5]

    context = {
        'total_leads': total_leads,
        'total_employees': total_employees,
        'total_calls_today': total_calls_today,
        'followups_due_today': followups_due_today,
        'pending_followups': followups_due_today,
        'pending_leaves': pending_leaves,
        'stage_data': stage_data,
        'branch_leads': branch_leads,
        'recent_leads': recent_leads,
        'recent_calls': recent_calls,
        'present_count': present_count,
        'absent_count': absent_count,
        'active_count': active_count,
        'upcoming_followups': upcoming_followups,
    }
    return render(request, 'dash/index.html', context)


# ============================================================
# BRANCH MANAGEMENT
# ============================================================
@user_passes_test(superadmin_required, login_url='/login/')
def branch(request):
    branches = Branch.objects.all().order_by('-id')
    return render(request, 'dash/branch/branches.html', {'branches': branches})


@user_passes_test(superadmin_required, login_url='/login/')
def add_branch(request):
    if request.method == 'POST':
        branch = Branch.objects.create(
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
        return redirect('/branch')
    return render(request, 'dash/branch/add_branch.html')


@user_passes_test(superadmin_required, login_url='/login/')
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
    return render(request, 'dash/branch/edit_branch.html', {'data': item})


@user_passes_test(superadmin_required, login_url='/login/')
def delete_branch(request, id):
    item = get_object_or_404(Branch, id=id)
    item.delete()
    messages.success(request, 'Branch deleted.')
    return redirect('branch')


@user_passes_test(superadmin_required, login_url='/login/')
def enable_branch(request, id):
    item = get_object_or_404(Branch, id=id)
    item.status = 'Enabled'
    item.save()
    return redirect('branch')


@user_passes_test(superadmin_required, login_url='/login/')
def disable_branch(request, id):
    item = get_object_or_404(Branch, id=id)
    item.status = 'Disabled'
    item.save()
    return redirect('branch')


# ============================================================
# USER MANAGEMENT
# ============================================================
@user_passes_test(superadmin_required, login_url='/login/')
def users(request):
    all_users     = UserProfile.objects.select_related('user', 'branch').order_by('-id')
    branches      = Branch.objects.filter(status='Enabled')
    role_filter   = request.GET.get('role', '')
    branch_filter = request.GET.get('branch', '')
    if role_filter:
        all_users = all_users.filter(role=role_filter)
    if branch_filter:
        all_users = all_users.filter(branch_id=branch_filter)
    return render(request, 'dash/users/users.html', {
        'users': all_users,
        'branches': branches,
        'role_filter': role_filter,
        'branch_filter': branch_filter,
    })


@user_passes_test(superadmin_required, login_url='/login/')
def add_user(request):
    branches     = Branch.objects.filter(status='Enabled')
    all_profiles = UserProfile.objects.select_related('user', 'branch')\
    .filter(
        status='Enabled',
        role__in=['manager', 'tl']   # 👈 IMPORTANT
    )
    if request.method == 'POST':
        first_name    = request.POST.get('first_name')
        last_name     = request.POST.get('last_name')
        username      = request.POST.get('username')
        email         = request.POST.get('email')
        password      = request.POST.get('password')
        role          = request.POST.get('role')
        branch_id     = request.POST.get('branch')
        phone         = request.POST.get('phone')
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
                profile.profile_pic = request.FILES['profile_pic']
            profile.save()
            messages.success(request, 'User created successfully.')
            return redirect('users')
    return render(request, 'dash/users/add_user.html', {
        'branches': branches,
        'all_profiles': all_profiles,
    })


@user_passes_test(superadmin_required, login_url='/login/')
def edit_user(request, id):
    profile      = get_object_or_404(UserProfile, id=id)
    branches     = Branch.objects.filter(status='Enabled')
    all_profiles = UserProfile.objects.select_related('user', 'branch')\
    .filter(
        status='Enabled',
        role__in=['manager', 'tl']   # 👈 IMPORTANT
    ).exclude(id=id)
    if request.method == 'POST':
        profile.user.first_name = request.POST.get('first_name')
        profile.user.last_name  = request.POST.get('last_name')
        profile.user.email      = request.POST.get('email')
        profile.user.save()
        profile.role          = request.POST.get('role')
        profile.phone         = request.POST.get('phone')
        profile.branch_id     = request.POST.get('branch') or None
        profile.reports_to_id = request.POST.get('reports_to') or None
        if request.FILES.get('profile_pic'):
            profile.profile_pic = request.FILES['profile_pic']
        profile.save()
        messages.success(request, 'User updated successfully.')
        return redirect('users')
    return render(request, 'dash/users/edit_user.html', {
        'data': profile,
        'branches': branches,
        'all_profiles': all_profiles,
    })


@user_passes_test(superadmin_required, login_url='/login/')
def delete_user(request, id):
    profile = get_object_or_404(UserProfile, id=id)
    profile.user.delete()
    messages.success(request, 'User deleted.')
    return redirect('users')


@user_passes_test(superadmin_required, login_url='/login/')
def enable_user(request, id):
    item = get_object_or_404(UserProfile, id=id)
    item.status = 'Enabled'
    item.save()
    return redirect('users')


@user_passes_test(superadmin_required, login_url='/login/')
def disable_user(request, id):
    item = get_object_or_404(UserProfile, id=id)
    item.status = 'Disabled'
    item.save()
    return redirect('users')


# ============================================================
# LEAD MANAGEMENT
# ============================================================

def assign_lead_view(request, lead_id):
    lead = get_object_or_404(Lead, id=lead_id)

    assigned_by = request.user.profile
    assigned_to_id = request.POST.get('assigned_to')

    assigned_to = get_object_or_404(UserProfile, id=assigned_to_id)

    # Validate role hierarchy
    if not can_assign(assigned_by, assigned_to):
        return HttpResponse("Not allowed", status=403)

    assign_lead(lead, assigned_by, assigned_to)

    return redirect('dashboard')

from django.shortcuts import render
from django.db.models import Q, Count
from django.http import JsonResponse
from .models import Lead, Branch, UserProfile, FollowUp, LeadAssignmentHistory
import json

@user_passes_test(superadmin_required, login_url='/login/')
def leads(request):

    # KPIs
    total_leads = Lead.objects.count()
    hot_leads = Lead.objects.filter(temperature='hot').count()
    pending_followups = FollowUp.objects.filter(followup_status='pending').count()
    unassigned_leads_count = Lead.objects.filter(assigned_to__isnull=True).count()
    closed_leads = Lead.objects.filter(stage='closed').count()

    conversion_rate = round((closed_leads / total_leads) * 100, 2) if total_leads > 0 else 0

    # Unassigned leads
    unassigned_leads = Lead.objects.filter(
        assigned_to__isnull=True
    ).order_by('-created_at')[:100]

    # Recent leads
    recent_leads = Lead.objects.select_related(
        'assigned_to__user'
    ).order_by('-updated_at')[:50]

    # Managers list
    managers = UserProfile.objects.filter(
        role='manager',
        status='Enabled'
    ).select_related('user')

    # Manager tracking stats
    manager_stats = UserProfile.objects.filter(role='manager').annotate(
        total_leads=Count('assigned_leads'),
        hot_leads=Count('assigned_leads', filter=Q(assigned_leads__temperature='hot')),
        new_leads=Count('assigned_leads', filter=Q(assigned_leads__stage='new'))
    )

    return render(request, 'dash/leads/leads.html', {
        'total_leads': total_leads,
        'hot_leads': hot_leads,
        'pending_followups': pending_followups,
        'unassigned_leads_count': unassigned_leads_count,
        'conversion_rate': conversion_rate,

        'unassigned_leads': unassigned_leads,
        'recent_leads': recent_leads,
        'managers': managers,
        'manager_stats': manager_stats,
    })

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

@csrf_exempt
@user_passes_test(superadmin_required)
def bulk_assign_leads(request):
    try:
        if request.method != "POST":
            return JsonResponse({'status': 'error', 'message': 'Invalid method'})

        data = json.loads(request.body)

        lead_ids = data.get('lead_ids', [])
        manager_id = data.get('manager_id')

        if not lead_ids or not manager_id:
            return JsonResponse({'status': 'error', 'message': 'Missing data'})

        manager = UserProfile.objects.get(id=manager_id)

        leads = Lead.objects.filter(id__in=lead_ids)

        for lead in leads:
            lead.assigned_to = manager
            lead.save()

        return JsonResponse({'status': 'success'})

    except Exception as e:
        print("ERROR:", str(e))  # 🔥 this will show real issue in terminal
        return JsonResponse({'status': 'error', 'message': str(e)})
    
@user_passes_test(superadmin_required)
def manager_performance(request, id):

    manager = get_object_or_404(UserProfile, id=id, role='manager')

    # Get all employees under this manager
    leads = Lead.objects.filter(
    Q(assigned_to=manager) |
    Q(assigned_to__reports_to=manager) |
    Q(assigned_to__reports_to__reports_to=manager)).select_related(
    'assigned_to__user',
    'assigned_to__reports_to__user',
    'assigned_to__reports_to__reports_to__user').order_by('-created_at')

    # KPIs
    total_leads = leads.count()
    hot_leads = leads.filter(temperature='hot').count()
    new_leads = leads.filter(stage='new').count()
    closed_leads = leads.filter(stage='closed').count()

    return render(request, 'dash/leads/manager_performance.html', {
        'manager': manager,
        'leads': leads,
        'total_leads': total_leads,
        'hot_leads': hot_leads,
        'new_leads': new_leads,
        'closed_leads': closed_leads,
    })

@user_passes_test(superadmin_required, login_url='/login/')
def add_lead(request):
    branches = Branch.objects.filter(status='Enabled')
    members  = UserProfile.objects.filter(role='member', status='Enabled').select_related('user')
    if request.method == 'POST':
        new_lead = Lead.objects.create(
            name              = request.POST.get('name'),
            phone             = request.POST.get('phone'),
            email             = request.POST.get('email') or None,
            location          = request.POST.get('location'),
            source            = request.POST.get('source'),
            campaign_name     = request.POST.get('campaign_name'),
            ad_set            = request.POST.get('ad_set'),
            ad_creative       = request.POST.get('ad_creative'),
            landing_page_url  = request.POST.get('landing_page_url') or None,
            property_type     = request.POST.get('property_type') or None,
            budget_min        = request.POST.get('budget_min') or None,
            budget_max        = request.POST.get('budget_max') or None,
            property_location = request.POST.get('property_location'),
            bhk_preference    = request.POST.get('bhk_preference') or None,
            purpose           = request.POST.get('purpose') or None,
            timeline          = request.POST.get('timeline') or None,
            readiness         = request.POST.get('readiness') or None,
            temperature       = request.POST.get('temperature', 'cold'),
            stage             = request.POST.get('stage', 'new'),
            assigned_to_id    = request.POST.get('assigned_to') or None,
            branch_id         = request.POST.get('branch') or None,
            notes             = request.POST.get('notes'),
        )
        try:
            create_notification(
                from_user=request.user,
                to_users=get_admins(),
                title="🆕 New Lead Added",
                description=f"{request.user.get_full_name()} added new lead: {new_lead.name} ({new_lead.phone})",
            )
        except Exception:
            pass
        messages.success(request, 'Lead added successfully.')
        return redirect('leads')
    return render(request, 'dash/leads/add_lead.html', {'branches': branches, 'members': members})


@user_passes_test(superadmin_required, login_url='/login/')
def edit_lead(request, id):
    item     = get_object_or_404(Lead, id=id)
    branches = Branch.objects.filter(status='Enabled')
    members  = UserProfile.objects.filter(role='member', status='Enabled').select_related('user')
    if request.method == 'POST':
        item.name              = request.POST.get('name')
        item.phone             = request.POST.get('phone')
        item.email             = request.POST.get('email') or None
        item.location          = request.POST.get('location')
        item.source            = request.POST.get('source')
        item.campaign_name     = request.POST.get('campaign_name')
        item.ad_set            = request.POST.get('ad_set')
        item.ad_creative       = request.POST.get('ad_creative')
        item.landing_page_url  = request.POST.get('landing_page_url') or None
        item.property_type     = request.POST.get('property_type') or None
        item.budget_min        = request.POST.get('budget_min') or None
        item.budget_max        = request.POST.get('budget_max') or None
        item.property_location = request.POST.get('property_location')
        item.bhk_preference    = request.POST.get('bhk_preference') or None
        item.purpose           = request.POST.get('purpose') or None
        item.timeline          = request.POST.get('timeline') or None
        item.readiness         = request.POST.get('readiness') or None
        item.temperature       = request.POST.get('temperature', 'cold')
        new_stage              = request.POST.get('stage', 'new')
        item.stage             = new_stage
        item.assigned_to_id    = request.POST.get('assigned_to') or None
        item.branch_id         = request.POST.get('branch') or None
        item.notes             = request.POST.get('notes')
        item.save()
        if new_stage in ('converted', 'closed'):
            try:
                create_notification(
                    from_user=request.user,
                    to_users=get_admins(),
                    title=f"🎯 Lead {new_stage.title()}",
                    description=f"{item.name} has been marked as {new_stage} by {request.user.get_full_name()}",
                )
            except Exception:
                pass
        messages.success(request, 'Lead updated successfully.')
        return redirect('leads')
    return render(request, 'dash/leads/edit_lead.html', {
        'data': item, 'branches': branches, 'members': members
    })


@user_passes_test(superadmin_required, login_url='/login/')
def delete_lead(request, id):
    item = get_object_or_404(Lead, id=id)
    item.delete()
    messages.success(request, 'Lead deleted.')
    return redirect('leads')


@user_passes_test(superadmin_required, login_url='/login/')
def enable_lead(request, id):
    item = get_object_or_404(Lead, id=id)
    item.status = 'Enabled'
    item.save()
    return redirect('leads')


@user_passes_test(superadmin_required, login_url='/login/')
def disable_lead(request, id):
    item = get_object_or_404(Lead, id=id)
    item.status = 'Disabled'
    item.save()
    return redirect('leads')


@user_passes_test(superadmin_required, login_url='/login/')
def view_lead(request, id):
    item      = get_object_or_404(Lead, id=id)
    calls     = item.calls.select_related('called_by__user').order_by('-created_at')
    followups = FollowUp.objects.filter(lead=item).select_related('assigned_to__user').order_by('followup_at')
    wrapups   = item.wrapups.order_by('-created_at')
    return render(request, 'dash/leads/view_lead.html', {
        'lead': item, 'calls': calls, 'followups': followups, 'wrapups': wrapups
    })


# ============================================================
# ASSIGN LEAD TO MANAGER (Super Admin)
# ============================================================
@user_passes_test(superadmin_required, login_url='/login/')
def assign_lead_to_manager(request, lead_id):
    if request.method == 'POST':
        lead       = get_object_or_404(Lead, id=lead_id)
        manager_id = request.POST.get('manager_id')
        if manager_id:
            manager = get_object_or_404(UserProfile, id=manager_id, role='manager')
            lead.assigned_to_manager = manager
            # Clear downstream assignments when reassigning
            lead.assigned_to_tl = None
            lead.assigned_to    = None
            lead.save()
            try:
                create_notification(
                    from_user=request.user,
                    to_users=[manager.user],
                    title="📋 New Lead Assigned",
                    description=f"You have been assigned a new lead: {lead.name} ({lead.phone})",
                )
            except Exception:
                pass
            messages.success(request, f'Lead "{lead.name}" assigned to Manager {manager.user.get_full_name()}.')
        else:
            messages.error(request, 'Please select a Manager.')
    return redirect('leads')


@user_passes_test(superadmin_required, login_url='/login/')
def unassign_lead_from_manager(request, lead_id):
    if request.method == 'POST':
        lead = get_object_or_404(Lead, id=lead_id)
        lead.assigned_to_manager = None
        lead.assigned_to_tl      = None
        lead.assigned_to         = None
        lead.save()
        messages.success(request, f'Lead "{lead.name}" unassigned.')
    return redirect('leads')


# ============================================================
# CALL LOG MANAGEMENT
# ============================================================
@user_passes_test(superadmin_required, login_url='/login/')
def calls(request):
    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    all_calls      = CallLog.objects.select_related('lead', 'called_by__user', 'branch').order_by('-created_at')
    branches       = Branch.objects.filter(status='Enabled')
    branch_filter  = request.GET.get('branch', '')
    outcome_filter = request.GET.get('outcome', '')
    search         = request.GET.get('q', '')
    if branch_filter:
        all_calls = all_calls.filter(branch_id=branch_filter)
    if outcome_filter:
        all_calls = all_calls.filter(call_outcome=outcome_filter)
    if search:
        all_calls = all_calls.filter(lead__name__icontains=search)
    month_calls = CallLog.objects.filter(created_at__date__gte=month_start)
    avg_duration = month_calls.aggregate(avg=Avg('call_duration'))['avg'] or 0
    return render(request, 'dash/calls/calls.html', {
        'calls': all_calls, 'branches': branches,
        'branch_filter': branch_filter, 'outcome_filter': outcome_filter, 'search': search,
        'calls_today': CallLog.objects.filter(created_at__date=today).count(),
        'calls_this_week': CallLog.objects.filter(created_at__date__gte=week_start).count(),
        'calls_this_month': month_calls.count(),
        'avg_call_duration_month': round(avg_duration),
    })


@user_passes_test(superadmin_required, login_url='/login/')
def add_call(request):
    all_leads = Lead.objects.filter(status='Enabled').order_by('name')
    members   = UserProfile.objects.filter(role='employee', status='Enabled').select_related('user')
    branches  = Branch.objects.filter(status='Enabled')
    if request.method == 'POST':
        CallLog.objects.create(
            lead_id          = request.POST.get('lead'),
            call_type        = request.POST.get('call_type'),
            call_duration    = request.POST.get('call_duration') or 0,
            call_outcome     = request.POST.get('call_outcome'),
            call_notes       = request.POST.get('call_notes'),
            next_followup_at = request.POST.get('next_followup_at') or None,
            called_by_id     = request.POST.get('called_by') or None,
            branch_id        = request.POST.get('branch') or None,
        )
        messages.success(request, 'Call log added.')
        return redirect('calls')
    return render(request, 'dash/calls/add_call.html', {
        'all_leads': all_leads, 'members': members, 'branches': branches
    })


@user_passes_test(superadmin_required, login_url='/login/')
def edit_call(request, id):
    item      = get_object_or_404(CallLog, id=id)
    all_leads = Lead.objects.filter(status='Enabled').order_by('name')
    members   = UserProfile.objects.filter(role='employee', status='Enabled').select_related('user')
    branches  = Branch.objects.filter(status='Enabled')
    if request.method == 'POST':
        item.lead_id          = request.POST.get('lead')
        item.call_type        = request.POST.get('call_type')
        item.call_duration    = request.POST.get('call_duration') or 0
        item.call_outcome     = request.POST.get('call_outcome')
        item.call_notes       = request.POST.get('call_notes')
        item.next_followup_at = request.POST.get('next_followup_at') or None
        item.called_by_id     = request.POST.get('called_by') or None
        item.branch_id        = request.POST.get('branch') or None
        item.save()
        messages.success(request, 'Call log updated.')
        return redirect('calls')
    return render(request, 'dash/calls/edit_call.html', {
        'data': item, 'all_leads': all_leads, 'members': members, 'branches': branches
    })


@user_passes_test(superadmin_required, login_url='/login/')
def delete_call(request, id):
    item = get_object_or_404(CallLog, id=id)
    item.delete()
    messages.success(request, 'Call log deleted.')
    return redirect('calls')


@user_passes_test(superadmin_required, login_url='/login/')
def enable_call(request, id):
    item = get_object_or_404(CallLog, id=id)
    item.status = 'Enabled'
    item.save()
    return redirect('calls')


@user_passes_test(superadmin_required, login_url='/login/')
def disable_call(request, id):
    item = get_object_or_404(CallLog, id=id)
    item.status = 'Disabled'
    item.save()
    return redirect('calls')


# ============================================================
# FOLLOW-UP MANAGEMENT
# ============================================================
@user_passes_test(superadmin_required, login_url='/login/')
def followups(request):
    all_followups = FollowUp.objects.select_related('lead', 'assigned_to__user', 'branch').order_by('followup_at')
    branches      = Branch.objects.filter(status='Enabled')
    status_filter = request.GET.get('status', '')
    branch_filter = request.GET.get('branch', '')
    search        = request.GET.get('q', '')
    if status_filter:
        all_followups = all_followups.filter(followup_status=status_filter)
    if branch_filter:
        all_followups = all_followups.filter(branch_id=branch_filter)
    if search:
        all_followups = all_followups.filter(lead__name__icontains=search)
    return render(request, 'dash/followups/followups.html', {
        'followups': all_followups, 'branches': branches,
        'status_filter': status_filter, 'branch_filter': branch_filter, 'search': search,
    })


@user_passes_test(superadmin_required, login_url='/login/')
def add_followup(request):
    all_leads = Lead.objects.filter(status='Enabled').order_by('name')
    members   = UserProfile.objects.filter(role='employee', status='Enabled').select_related('user')
    branches  = Branch.objects.filter(status='Enabled')
    if request.method == 'POST':
        FollowUp.objects.create(
            lead_id         = request.POST.get('lead'),
            followup_at     = request.POST.get('followup_at'),
            followup_type   = request.POST.get('followup_type'),
            notes           = request.POST.get('notes'),
            followup_status = request.POST.get('followup_status', 'pending'),
            assigned_to_id  = request.POST.get('assigned_to') or None,
            branch_id       = request.POST.get('branch') or None,
        )
        messages.success(request, 'Follow-up added.')
        return redirect('followups')
    return render(request, 'dash/followups/add_followup.html', {
        'all_leads': all_leads, 'members': members, 'branches': branches
    })


@user_passes_test(superadmin_required, login_url='/login/')
def edit_followup(request, id):
    item      = get_object_or_404(FollowUp, id=id)
    all_leads = Lead.objects.filter(status='Enabled').order_by('name')
    members   = UserProfile.objects.filter(role='employee', status='Enabled').select_related('user')
    branches  = Branch.objects.filter(status='Enabled')
    if request.method == 'POST':
        item.lead_id         = request.POST.get('lead')
        item.followup_at     = request.POST.get('followup_at')
        item.followup_type   = request.POST.get('followup_type')
        item.notes           = request.POST.get('notes')
        item.followup_status = request.POST.get('followup_status', 'pending')
        item.assigned_to_id  = request.POST.get('assigned_to') or None
        item.branch_id       = request.POST.get('branch') or None
        item.save()
        messages.success(request, 'Follow-up updated.')
        return redirect('followups')
    return render(request, 'dash/followups/edit_followup.html', {
        'data': item, 'all_leads': all_leads, 'members': members, 'branches': branches
    })


@user_passes_test(superadmin_required, login_url='/login/')
def delete_followup(request, id):
    item = get_object_or_404(FollowUp, id=id)
    item.delete()
    messages.success(request, 'Follow-up deleted.')
    return redirect('followups')


@user_passes_test(superadmin_required, login_url='/login/')
def enable_followup(request, id):
    item = get_object_or_404(FollowUp, id=id)
    item.status = 'Enabled'
    item.save()
    return redirect('followups')


@user_passes_test(superadmin_required, login_url='/login/')
def disable_followup(request, id):
    item = get_object_or_404(FollowUp, id=id)
    item.status = 'Disabled'
    item.save()
    return redirect('followups')


# ============================================================
# WRAP-UP MANAGEMENT
# ============================================================
@user_passes_test(superadmin_required, login_url='/login/')
def wrapups(request):
    all_wrapups   = CallWrapUp.objects.select_related('lead', 'submitted_by__user').order_by('-created_at')
    branch_filter = request.GET.get('branch', '')
    locked_filter = request.GET.get('locked', '')
    if branch_filter:
        all_wrapups = all_wrapups.filter(lead__branch_id=branch_filter)
    if locked_filter == '1':
        all_wrapups = all_wrapups.filter(is_locked=True)
    elif locked_filter == '0':
        all_wrapups = all_wrapups.filter(is_locked=False)
    branches = Branch.objects.filter(status='Enabled')
    return render(request, 'dash/calls/wrapups.html', {
        'wrapups': all_wrapups, 'branches': branches,
        'branch_filter': branch_filter, 'locked_filter': locked_filter,
    })


# ============================================================
# SETTINGS
# ============================================================
@user_passes_test(superadmin_required, login_url='/login/')
def settings_view(request):
    setting_keys  = ['wrapup_window_minutes', 'lead_auto_assign', 'whatsapp_provider']
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
    return render(request, 'dash/settings/settings.html', {'settings': settings_data})


# ============================================================
# BULK LEAD UPLOAD
# ============================================================
@user_passes_test(superadmin_required, login_url='/login/')
def bulk_upload_leads(request):
    branches = Branch.objects.filter(status='Enabled')
    members  = UserProfile.objects.filter(role='member', status='Enabled').select_related('user')

    if request.method == 'POST':
        uploaded_file  = request.FILES.get('bulk_file')
        branch_id      = request.POST.get('branch') or None
        assigned_to_id = request.POST.get('assigned_to') or None

        if not uploaded_file:
            messages.error(request, 'Please select a file to upload.')
            return redirect('bulk_upload_leads')

        filename = uploaded_file.name.lower()
        rows     = []
        errors   = []

        try:
            if filename.endswith('.csv'):
                decoded = uploaded_file.read().decode('utf-8-sig')
                reader  = csv.DictReader(io.StringIO(decoded))
                for i, row in enumerate(reader, start=2):
                    rows.append((i, row))

            elif filename.endswith(('.xlsx', '.xls')):
                wb = openpyxl.load_workbook(uploaded_file, read_only=True, data_only=True)
                ws = wb.active
                headers = [
                    str(cell.value).strip().lower().replace(' ', '_') if cell.value else ''
                    for cell in next(ws.iter_rows(min_row=1, max_row=1))
                ]
                for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                    row_dict = {
                        headers[j]: (str(val).strip() if val is not None else '')
                        for j, val in enumerate(row)
                    }
                    rows.append((i, row_dict))
                wb.close()
            else:
                messages.error(request, 'Unsupported file. Upload .csv or .xlsx only.')
                return redirect('bulk_upload_leads')

        except Exception as e:
            messages.error(request, f'Error reading file: {str(e)}')
            return redirect('bulk_upload_leads')

        VALID_SOURCES = ['meta','google','website','social','campaign','referral','walkin','whatsapp','other']
        VALID_TEMPS   = ['hot','warm','cold']
        VALID_STAGES  = ['new','contacted','interested','site_visit','negotiation','closed','lost']

        created_count = 0
        skip_count    = 0

        for row_num, row in rows:
            if not any(row.values()):
                skip_count += 1
                continue

            name  = row.get('name', '').strip()
            phone = row.get('phone', '').strip()

            if not name or not phone:
                errors.append(f'Row {row_num}: Skipped — name and phone are required.')
                skip_count += 1
                continue

            source = row.get('source', 'other').strip().lower()
            if source not in VALID_SOURCES:
                source = 'other'

            temperature = row.get('temperature', 'cold').strip().lower()
            if temperature not in VALID_TEMPS:
                temperature = 'cold'

            stage = row.get('stage', 'new').strip().lower().replace(' ', '_')
            if stage not in VALID_STAGES:
                stage = 'new'

            def safe_decimal(val):
                try:
                    return float(str(val).replace(',', '').strip()) if val else None
                except:
                    return None

            try:
                Lead.objects.create(
                    name              = name,
                    phone             = phone,
                    email             = row.get('email', '') or None,
                    location          = row.get('location', ''),
                    source            = source,
                    campaign_name     = row.get('campaign_name', ''),
                    ad_set            = row.get('ad_set', ''),
                    ad_creative       = row.get('ad_creative', ''),
                    landing_page_url  = row.get('landing_page_url', '') or None,
                    property_type     = row.get('property_type', '') or None,
                    budget_min        = safe_decimal(row.get('budget_min')),
                    budget_max        = safe_decimal(row.get('budget_max')),
                    property_location = row.get('property_location', ''),
                    bhk_preference    = row.get('bhk_preference', '') or None,
                    purpose           = row.get('purpose', '') or None,
                    timeline          = row.get('timeline', '') or None,
                    readiness         = row.get('readiness', '') or None,
                    temperature       = temperature,
                    stage             = stage,
                    notes             = row.get('notes', ''),
                    branch_id         = branch_id,
                    assigned_to_id    = assigned_to_id,
                )
                created_count += 1
            except Exception as e:
                errors.append(f'Row {row_num}: Error — {str(e)}')
                skip_count += 1

        if created_count:
            messages.success(request, f'{created_count} leads imported successfully.')
            try:
                create_notification(
                    from_user=request.user,
                    to_users=get_admins(),
                    title="📊 Bulk Leads Uploaded",
                    description=f"{request.user.get_full_name()} uploaded {created_count} leads via bulk upload.",
                )
            except Exception:
                pass
        if errors:
            for err in errors[:10]:
                messages.warning(request, err)
        if skip_count and not errors:
            messages.warning(request, f'{skip_count} rows skipped.')

        return redirect('leads')

    return render(request, 'dash/leads/bulk_upload.html', {
        'branches': branches,
        'members': members,
    })


@user_passes_test(superadmin_required, login_url='/login/')
def download_lead_template(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="CoreCRM_Lead_Template.csv"'
    writer = csv.writer(response)
    writer.writerow([
        'name', 'phone', 'email', 'location',
        'source', 'campaign_name', 'ad_set', 'ad_creative', 'landing_page_url',
        'property_type', 'budget_min', 'budget_max', 'property_location',
        'bhk_preference', 'purpose', 'timeline', 'readiness',
        'temperature', 'stage', 'notes'
    ])
    writer.writerow([
        'Rahul Sharma', '9876543210', 'rahul@email.com', 'Salt Lake Kolkata',
        'meta', 'Diwali Campaign 2026', 'Ad Set 1', 'Creative A', '',
        'apartment', '3000000', '6000000', 'Newtown',
        '2bhk', 'selfuse', '3months', 'ready',
        'warm', 'new', 'Interested in 2BHK near IT hub'
    ])
    return response


# ============================================================
# HR PANEL
# ============================================================
from .models import Attendance, LeaveRequest, SystemAPISettings

@user_passes_test(superadmin_required, login_url='/login/')
def hr_panel(request):
    today = timezone.localdate()
    branches = Branch.objects.filter(status='Enabled')
    employees = UserProfile.objects.filter(
        status='Enabled',
        role='employee',
    ).select_related('user', 'branch')
    branch_filter = request.GET.get('branch', '')
    search = request.GET.get('q', '')
    if branch_filter:
        employees = employees.filter(branch_id=branch_filter)
    if search:
        employees = employees.filter(
            Q(user__first_name__icontains=search) | Q(user__last_name__icontains=search)
        )

    employee_ids = list(employees.values_list('id', flat=True))
    recent_attendance = Attendance.objects.filter(
        employee_id__in=employee_ids
    ).select_related('employee__user', 'branch').order_by('-date', '-created_at')[:10]
    recent_leaves = LeaveRequest.objects.filter(
        employee_id__in=employee_ids
    ).select_related('employee__user', 'approved_by__user').order_by('-created_at')[:10]
    today_attendance = {
        record.employee_id: record
        for record in Attendance.objects.filter(
            employee_id__in=employee_ids,
            date=today,
        ).select_related('employee__user')
    }

    employee_rows = []
    present_today = 0
    for employee in employees:
        attendance_record = today_attendance.get(employee.id)
        leave_record = LeaveRequest.objects.filter(
            employee=employee,
            leave_status='approved',
            from_date__lte=today,
            to_date__gte=today,
        ).first()

        if leave_record:
            attendance_status = 'on_leave'
        elif attendance_record:
            attendance_status = attendance_record.computed_status
        else:
            attendance_status = 'absent'

        if attendance_status == 'present':
            present_today += 1

        employee_rows.append({
            'profile': employee,
            'attendance_status': attendance_status,
        })

    total_employees = len(employee_rows)
    on_leave_today = LeaveRequest.objects.filter(
        employee_id__in=employee_ids,
        leave_status='approved',
        from_date__lte=today,
        to_date__gte=today,
    ).count()
    absent_today = max(total_employees - present_today - on_leave_today, 0)
    pending_leaves = LeaveRequest.objects.filter(
        employee_id__in=employee_ids,
        leave_status='pending',
    ).count()

    return render(request, 'dash/hr/hr_panel.html', {
        'employees': employee_rows,
        'branches': branches,
        'branch_filter': branch_filter,
        'search': search,
        'total_employees': total_employees,
        'present_today': present_today,
        'on_leave_today': on_leave_today,
        'absent_today': absent_today,
        'pending_leaves': pending_leaves,
        'recent_attendance': recent_attendance,
        'recent_leaves': recent_leaves,
    })


@user_passes_test(superadmin_required, login_url='/login/')
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
        if status_filter == 'active':
            records = records.filter(punch_in__isnull=False, punch_out__isnull=True)
        elif status_filter == 'absent':
            records = records.filter(punch_in__isnull=True)
        elif status_filter == 'present':
            records = records.filter(punch_in__isnull=False, punch_out__isnull=False)
        else:
            records = records.filter(status=status_filter)
    if search:
        records = records.filter(
            Q(employee__user__first_name__icontains=search) |
            Q(employee__user__last_name__icontains=search)
        )
    return render(request, 'dash/hr/attendance.html', {
        'records': records, 'branches': branches,
        'branch_filter': branch_filter, 'date_filter': date_filter,
        'status_filter': status_filter, 'search': search,
    })


@user_passes_test(superadmin_required, login_url='/login/')
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
    return render(request, 'dash/hr/add_attendance.html', {
        'employees': employees, 'branches': branches
    })


@user_passes_test(superadmin_required, login_url='/login/')
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
    return render(request, 'dash/hr/edit_attendance.html', {
        'data': record, 'employees': employees, 'branches': branches
    })


@user_passes_test(superadmin_required, login_url='/login/')
def delete_attendance(request, id):
    get_object_or_404(Attendance, id=id).delete()
    messages.success(request, 'Record deleted.')
    return redirect('attendance')


@user_passes_test(superadmin_required, login_url='/login/')
def leaves(request):
    branches    = Branch.objects.filter(status='Enabled')
    all_leaves  = LeaveRequest.objects.all()
    records     = all_leaves.select_related('employee__user', 'approved_by__user').order_by('-created_at')
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
    return render(request, 'dash/hr/leaves.html', {
        'records': records, 'branches': branches,
        'status_filter': status_filter, 'branch_filter': branch_filter, 'search': search,
        'pending_leaves': all_leaves.filter(leave_status='pending'),
        'approved_leaves': all_leaves.filter(leave_status='approved'),
        'rejected_leaves': all_leaves.filter(leave_status='rejected'),
        'pending_leaves_count':  all_leaves.filter(leave_status='pending').count(),
        'approved_leaves_count': all_leaves.filter(leave_status='approved').count(),
        'rejected_leaves_count': all_leaves.filter(leave_status='rejected').count(),
    })


@user_passes_test(superadmin_required, login_url='/login/')
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
    return render(request, 'dash/hr/add_leave.html', {'employees': employees})


@user_passes_test(superadmin_required, login_url='/login/')
def edit_leave(request, id):
    record    = get_object_or_404(LeaveRequest, id=id)
    employees = UserProfile.objects.filter(status='Enabled').select_related('user')
    profiles  = UserProfile.objects.filter(status='Enabled').select_related('user')
    if request.method == 'POST':
        record.employee_id    = request.POST.get('employee')
        record.leave_type     = request.POST.get('leave_type')
        record.from_date      = request.POST.get('from_date')
        record.to_date        = request.POST.get('to_date')
        record.reason         = request.POST.get('reason')
        record.leave_status   = request.POST.get('leave_status', 'pending')
        record.approved_by_id = request.POST.get('approved_by') or None
        record.remarks        = request.POST.get('remarks', '')
        record.save()
        messages.success(request, 'Leave updated.')
        return redirect('leaves')
    return render(request, 'dash/hr/edit_leave.html', {
        'data': record, 'employees': employees, 'profiles': profiles
    })


@user_passes_test(superadmin_required, login_url='/login/')
def delete_leave(request, id):
    get_object_or_404(LeaveRequest, id=id).delete()
    messages.success(request, 'Leave request deleted.')
    return redirect('leaves')


@user_passes_test(superadmin_required, login_url='/login/')
def approve_leave(request, id):
    record = get_object_or_404(LeaveRequest, id=id)
    record.leave_status = 'approved'
    record.approved_by = request.user.profile
    record.save()
    try:
        create_notification(
            from_user=request.user,
            to_users=[record.employee.user],
            title="✅ Leave Approved",
            description=f"Your {record.leave_type} leave from {record.from_date} to {record.to_date} has been approved.",
        )
    except Exception:
        pass
    messages.success(request, 'Leave approved.')
    return redirect('leaves')


@user_passes_test(superadmin_required, login_url='/login/')
def reject_leave(request, id):
    record = get_object_or_404(LeaveRequest, id=id)
    record.leave_status = 'rejected'
    record.approved_by = request.user.profile
    record.save()
    try:
        create_notification(
            from_user=request.user,
            to_users=[record.employee.user],
            title="❌ Leave Rejected",
            description=f"Your {record.leave_type} leave has been rejected. Remarks: {record.remarks or 'No remarks'}",
        )
    except Exception:
        pass
    messages.success(request, 'Leave rejected.')
    return redirect('leaves')


@user_passes_test(superadmin_required, login_url='/login/')
def employee_detail(request, id):
    employee        = get_object_or_404(UserProfile, id=id)
    branches        = Branch.objects.filter(status='Enabled')
    att_records     = Attendance.objects.filter(employee=employee).order_by('-date')
    leave_records   = LeaveRequest.objects.filter(employee=employee).order_by('-created_at')

    if request.method == 'POST':
        record = Attendance.objects.create(
            employee       = employee,
            branch_id      = request.POST.get('branch') or employee.branch_id,
            date           = request.POST.get('date'),
            punch_in       = request.POST.get('punch_in') or None,
            punch_out      = request.POST.get('punch_out') or None,
            status         = request.POST.get('status', 'present'),
            is_out_of_zone = request.POST.get('is_out_of_zone') == 'on',
            notes          = request.POST.get('notes', ''),
        )
        record.calculate_hours()
        messages.success(request, f'Attendance added for {employee.user.get_full_name()}.')
        return redirect('employee_detail', id=id)

    return render(request, 'dash/hr/employee_detail.html', {
        'employee': employee,
        'att_records': att_records,
        'leave_records': leave_records,
        'branches': branches,
    })

@staff_member_required
def apr_report(request):
    # 1. SUPER ADMIN: Keep your exact same code!
    if request.user.is_superuser:
        from django.apps import apps 
        RealAttendanceModel = apps.get_model('employee', 'Attendance')
        
        # Fetch the records
        attendances = RealAttendanceModel.objects.select_related('employee').all().order_by('-date')
        
        report_data = []
        for att in attendances:
            report_data.append({
                'employee_name': att.employee.username,
                'date': att.date,
                'punch_in': att.punch_in_time,
                'punch_out': att.punch_out_time,
                'new_leads': 12,
                'closed_contacts': 3,
                'avg_call_time': "4m 30s",
            })
            
        return render(request, 'dash/apr_report.html', {'report_data': report_data})
    
    # 2. HR & MANAGER: The New Directory View
    else:
        from django.contrib.auth.models import User
        
        # Grab all regular employees. 
        # Using select_related makes the database query lightning fast!
        employees = User.objects.filter(is_superuser=False).select_related(
            'profile', 
            'profile__branch', 
            'profile__reports_to', 
            'profile__reports_to__user'
        )
        
        directory_data = []
        for emp in employees:
            # We safely check if they have a UserProfile built
            if hasattr(emp, 'profile'):
                # Grab the Branch name
                branch_name = emp.profile.branch.name if emp.profile.branch else "N/A"
                
                # Grab the Team Leader's username (following the reports_to -> user link)
                tl_name = emp.profile.reports_to.user.username if emp.profile.reports_to else "N/A"
            else:
                branch_name = "N/A"
                tl_name = "N/A"
            
            directory_data.append({
                'username': emp.username,
                'profile_id': emp.profile.id if hasattr(emp, 'profile') else None,
                'branch': branch_name,
                'team_leader': tl_name,
            })
            
        return render(request, 'dash/apr_directory.html', {'directory_data': directory_data})

@staff_member_required
def get_employee_route(request, username, date_str):
    try:
        # Convert date string to real date
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Grab all pings for this EXACT username on this specific day
        pings = LocationPing.objects.filter(
            employee__username=username,
            timestamp__date=target_date
        ).order_by('timestamp')

        # Package the coordinates for the map
        route_data = []
        for p in pings:
            route_data.append({
                'lat': float(p.latitude), 
                'lng': float(p.longitude), 
                'time': p.timestamp.strftime('%I:%M %p')
            })
            
        return JsonResponse({'status': 'success', 'route': route_data})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
@staff_member_required
def individual_apr_report(request, username):
    employee_user = get_object_or_404(User, username=username)
    profile = get_object_or_404(UserProfile, user=employee_user)

    attendances = Attendance.objects.filter(
        employee=profile
    ).order_by('-date')

    report_data = []
    for att in attendances:
        day_calls = CallLog.objects.filter(
            called_by=profile,
            created_at__date=att.date,
        )
        call_count = day_calls.count()
        closed = day_calls.filter(call_outcome__in=['converted', 'site_visit']).count()

        total_secs = sum(c.call_duration for c in day_calls)
        if call_count:
            avg_secs = total_secs // call_count
            avg_call_time = f"{avg_secs // 60}m {avg_secs % 60}s"
        else:
            avg_call_time = "—"

        total_hours = None
        if att.punch_in and att.punch_out:
            delta = att.punch_out - att.punch_in
            total_hours = round(delta.total_seconds() / 3600, 2)

        report_data.append({
            'employee_name': employee_user.get_full_name() or employee_user.username,
            'date': att.date,
            'punch_in': att.punch_in,
            'punch_out': att.punch_out,
            'total_hours': total_hours,
            'new_leads': call_count,
            'closed_contacts': closed,
            'avg_call_time': avg_call_time,
        })

    return render(request, 'dash/individual_apr_report.html', {
        'report_data': report_data,
        'target_employee': employee_user,
        'profile': profile,
    })


@staff_member_required
def apr_day_detail(request, report_id, date_str):
    import json as _json

    employee_user = get_object_or_404(User, id=report_id)
    employee_profile = get_object_or_404(UserProfile, user=employee_user)

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        from django.http import Http404
        raise Http404("Invalid date format")

    attendance = Attendance.objects.filter(
        employee=employee_profile,
        date=target_date
    ).first()

    total_hours = None
    if attendance and attendance.punch_in and attendance.punch_out:
        delta = attendance.punch_out - attendance.punch_in
        total_hours = round(delta.total_seconds() / 3600, 2)

    call_logs = CallLog.objects.filter(
        called_by=employee_profile,
        created_at__date=target_date
    ).select_related('lead').order_by('created_at')

    lead_ids = call_logs.values_list('lead_id', flat=True).distinct()
    leads = Lead.objects.filter(id__in=lead_ids)

    pings = LocationPing.objects.filter(
        employee=employee_user,
        timestamp__date=target_date
    ).order_by('timestamp')

    ping_coords = _json.dumps([
        {'lat': float(p.latitude), 'lng': float(p.longitude), 'time': p.timestamp.strftime('%I:%M %p')}
        for p in pings
    ])

    return render(request, 'dash/apr_day_detail.html', {
        'employee': employee_profile,
        'target_employee': employee_user,
        'date': target_date,
        'attendance': attendance,
        'total_hours': total_hours,
        'call_logs': call_logs,
        'leads': leads,
        'ping_coords': ping_coords,
        'ping_count': pings.count(),
        'report_id': report_id,
    })


from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
import json

@csrf_exempt
def meta_webhook(request):

    # Meta verification
    if request.method == "GET":

        VERIFY_TOKEN = "buybreeze_meta_verify"

        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            return HttpResponse(challenge)

        return HttpResponse("Verification failed", status=403)

    # Incoming leads
    if request.method == "POST":

        data = json.loads(request.body)

        print("META WEBHOOK DATA:", data)

        return JsonResponse({
            "status": "received"
        })


# ── SETTINGS: API KEYS ──────────────────────────────────────────────────────
@user_passes_test(superadmin_required, login_url='/login/')
def api_settings(request):
    from .utils import API_KEY_DEFAULTS, ensure_api_settings
    ensure_api_settings()

    if request.method == 'POST':
        for key, _ in API_KEY_DEFAULTS:
            val = request.POST.get(key, '').strip()
            SystemAPISettings.objects.filter(key=key).update(value=val)
        messages.success(request, 'API settings saved successfully.')
        return redirect('api_settings')

    settings_qs = SystemAPISettings.objects.all()
    settings_map = {s.key: s for s in settings_qs}

    groups = [
        {
            'label': 'Meta / Facebook Ads',
            'icon':  'bi-facebook',
            'keys':  ['META_APP_ID', 'META_APP_SECRET', 'META_AD_ACCOUNT_ID', 'META_ACCESS_TOKEN'],
        },
        {
            'label': 'Google Ads',
            'icon':  'bi-google',
            'keys':  ['GOOGLE_DEVELOPER_TOKEN', 'GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET',
                      'GOOGLE_REFRESH_TOKEN', 'GOOGLE_CUSTOMER_ID'],
        },
        {
            'label': 'WhatsApp Business API',
            'icon':  'bi-whatsapp',
            'keys':  ['WHATSAPP_API_KEY', 'WHATSAPP_PHONE_NUMBER_ID'],
        },
        {
            'label': 'SMS (Fast2SMS)',
            'icon':  'bi-chat-dots-fill',
            'keys':  ['FAST2SMS_API_KEY'],
        },
    ]

    for group in groups:
        group['items'] = [settings_map.get(k) for k in group['keys'] if k in settings_map]

    return render(request, 'dash/api_settings.html', {'groups': groups})


# ── META ADS DASHBOARD ───────────────────────────────────────────────────────
@user_passes_test(superadmin_required, login_url='/login/')
def meta_ads_dashboard(request):
    from .utils import get_setting
    keys_configured = all([
        get_setting('META_APP_ID'),
        get_setting('META_APP_SECRET'),
        get_setting('META_ACCESS_TOKEN'),
        get_setting('META_AD_ACCOUNT_ID'),
    ])

    campaigns = []
    leads     = []
    error     = None

    if keys_configured:
        date_preset = request.GET.get('date_preset', 'last_30d')
        try:
            from .meta_ads import get_meta_campaigns, get_meta_leads
            campaigns = get_meta_campaigns(date_preset=date_preset)
            leads     = get_meta_leads(limit=100)
        except Exception as e:
            error = str(e)
    else:
        date_preset = 'last_30d'

    return render(request, 'dash/meta_ads.html', {
        'keys_configured': keys_configured,
        'campaigns':       campaigns,
        'leads':           leads,
        'error':           error,
        'date_preset':     date_preset,
        'date_preset_options': [
            ('today',       'Today'),
            ('yesterday',   'Yesterday'),
            ('last_7d',     'Last 7 Days'),
            ('last_30d',    'Last 30 Days'),
            ('last_90d',    'Last 90 Days'),
            ('this_month',  'This Month'),
            ('last_month',  'Last Month'),
        ],
    })


# ── GOOGLE ADS DASHBOARD ─────────────────────────────────────────────────────
@user_passes_test(superadmin_required, login_url='/login/')
def google_ads_dashboard(request):
    from .utils import get_setting
    keys_configured = all([
        get_setting('GOOGLE_DEVELOPER_TOKEN'),
        get_setting('GOOGLE_CLIENT_ID'),
        get_setting('GOOGLE_CLIENT_SECRET'),
        get_setting('GOOGLE_REFRESH_TOKEN'),
        get_setting('GOOGLE_CUSTOMER_ID'),
    ])

    campaigns = []
    error     = None

    if keys_configured:
        date_range = request.GET.get('date_range', 'LAST_30_DAYS')
        try:
            from .google_ads import get_google_campaigns
            campaigns = get_google_campaigns(date_range=date_range)
        except Exception as e:
            error = str(e)
    else:
        date_range = 'LAST_30_DAYS'

    return render(request, 'dash/google_ads.html', {
        'keys_configured': keys_configured,
        'campaigns':       campaigns,
        'error':           error,
        'date_range':      date_range,
        'date_range_options': [
            ('TODAY',        'Today'),
            ('YESTERDAY',    'Yesterday'),
            ('LAST_7_DAYS',  'Last 7 Days'),
            ('LAST_30_DAYS', 'Last 30 Days'),
            ('THIS_MONTH',   'This Month'),
            ('LAST_MONTH',   'Last Month'),
        ],
    })


# ── WHATSAPP DASHBOARD ────────────────────────────────────────────────────────
@user_passes_test(superadmin_required, login_url='/login/')
def whatsapp_dashboard(request):
    from .utils import get_setting
    keys_configured = all([
        get_setting('WHATSAPP_API_KEY'),
        get_setting('WHATSAPP_PHONE_NUMBER_ID'),
    ])

    templates = []
    send_result = None
    error       = None

    if keys_configured:
        try:
            from .whatsapp import get_whatsapp_templates
            templates = get_whatsapp_templates()
        except Exception as e:
            error = str(e)

    if request.method == 'POST' and keys_configured:
        phone    = request.POST.get('phone', '').strip()
        template = request.POST.get('template_name', '').strip()
        language = request.POST.get('language_code', 'en_US').strip()
        try:
            from .whatsapp import send_whatsapp_message
            send_result = send_whatsapp_message(phone, template, language)
        except Exception as e:
            error = str(e)

    return render(request, 'dash/whatsapp.html', {
        'keys_configured': keys_configured,
        'templates':       templates,
        'send_result':     send_result,
        'error':           error,
    })



# ============================================================
# NOTIFICATIONS PAGE (Dash)
# ============================================================
@user_passes_test(superadmin_required, login_url='/login/')
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
    return render(request, 'dash/notifications.html', {
        'notifications': notifications,
        'unread_count':  unread_count,
    })
