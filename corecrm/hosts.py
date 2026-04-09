from django.conf import settings
from django_hosts import patterns, host

host_patterns = patterns(
    '',
    # Main Dashboard / Root
    host(r'www|', 'dash.urls', name='dash'),  
    
    # HR Panel Subdomain
    host(r'hrpanel', 'hrpanel.urls', name='hrpanel'),  
    
    # Branch Manager Subdomain
    host(r'manager', 'branch_manager.urls', name='manager'),
    
    # Team Leader Subdomain
    host(r'tl', 'team_leader.urls', name='tl'),
    
    # Employee Subdomain
    host(r'employee', 'employee_dash.urls', name='employee'),
)