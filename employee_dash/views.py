from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def employee_dashboard(request):
    context = {
        'title': 'Employee Dashboard',
        'role': request.user.profile.role if hasattr(request.user, 'profile') else 'No Role'
    }
    return render(request, 'employee_dash/dashboard.html', context)