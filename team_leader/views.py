from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

@login_required
def tl_dashboard(request):
    if hasattr(request.user, 'profile') and request.user.profile.role == 'tl':
        context = {
            'title': 'Team Leader Dashboard',
            'role': 'Team Leader',
        }
        return render(request, 'team_leader/dashboard.html', context)
    
    # Clean, simple, and no hardcoded URLs!
    return redirect('login_view')