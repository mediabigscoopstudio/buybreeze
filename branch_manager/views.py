from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

@login_required
def manager_dashboard(request):
    if hasattr(request.user, 'profile') and request.user.profile.role == 'manager':
        context = {
            'title': 'Branch Manager Dashboard',
            'role': 'Branch Manager',
        }
        return render(request, 'branch_manager/dashboard.html', context)
    
    # Clean, simple, and no hardcoded URLs!
    return redirect('login_view')