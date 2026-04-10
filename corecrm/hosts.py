from django.conf import settings
from django_hosts import patterns, host

host_patterns = patterns(
    '',
    # Main Dashboard / Root
    host(r'www|', 'dash.urls', name='dash'),  
    
    # HR Panel Subdomain
    host(r'hrpanel', 'hrpanel.urls', name='hrpanel'),  
    host(r'employee', 'employee.urls', name='employee'),  
    host(r'manager', 'manager.urls', name='manager'),  
    host(r'teamleader', 'teamleader.urls', name='teamleader'),  
)