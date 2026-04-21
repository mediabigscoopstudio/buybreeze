from django.shortcuts import render
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.db.models import Count, Q
from dash.models import Branch, UserProfile
import math
import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Attendance
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone
import json
from django.http import JsonResponse
from .models import LocationPing # Make sure LocationPing is imported at the top!

def get_distance(lat1, lon1, lat2, lon2):
    R = 6371.0 # Radius of the Earth in km
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad

    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance_km = R * c
    return distance_km * 1000 # Convert to meters



def employee_required(user):
    return (
        user.is_authenticated and
        hasattr(user, 'userprofile') and
        user.userprofile.role == 'employee'
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
                if user.userprofile.role == 'employee':
                    login(request, user)
                    return redirect('index')
                else:
                    messages.error(request, 'Access Denied: This panel is for employee only.')
            except UserProfile.DoesNotExist:
                messages.error(request, 'Profile not configured. Contact Admin.')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'employee/signin.html')

def logout_view(request):
    logout(request)
    return redirect('login_view')

def index(request):
     return render(request,'employee/index.html')

@login_required
@require_POST
def process_punch(request):
    user_profile = request.user.userprofile
    COMPANY_LAT = user_profile.branch.gps_lat
    COMPANY_LON = user_profile.branch.gps_lng
    ALLOWED_RADIUS_METERS = user_profile.branch.gps_radius
    try:
        data = json.loads(request.body)
        action = data.get('action') 
        emp_lat = float(data.get('latitude'))
        emp_lon = float(data.get('longitude'))

        # Calculate distance using the helper above
        distance = get_distance(COMPANY_LAT, COMPANY_LON, emp_lat, emp_lon)

        # Check if within geofence
        if distance > ALLOWED_RADIUS_METERS:
            return JsonResponse({
                'status': 'error', 
                'message': f'You are {int(distance)} meters away. Please move closer to the office to punch in.'
            }, status=403)

        # Process the Punch based on your models
        if action == 'punch_in':
            today = timezone.now().date()
            
            # Check if they already punched in today
            attendance, created = Attendance.objects.get_or_create(
                employee=request.user, 
                date=today
            )
            
            if attendance.punch_in_time:
                return JsonResponse({'status': 'error', 'message': 'You have already punched in today!'})
            
            # Save the punch in time
            attendance.punch_in_time = timezone.now()
            attendance.save()
            
            return JsonResponse({'status': 'success', 'message': 'Successfully Punched In!'})
            
        elif action == 'punch_out':
            today = timezone.now().date()
            
            try:
                # Find today's record
                record = Attendance.objects.get(employee=request.user, date=today)
                
                if record.punch_out_time:
                    return JsonResponse({'status': 'error', 'message': 'You have already punched out today!'})
                    
                # Save the punch out time
                record.punch_out_time = timezone.now()
                record.save()
                
                return JsonResponse({'status': 'success', 'message': 'Successfully Punched Out!'})
                
            except Attendance.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'You must punch in first before you can punch out!'})

    # THIS is the part that was missing! It matches the 'try:' on line 84.
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
def save_location_ping(request):
    if request.method == 'POST' and request.user.is_authenticated:
        try:
            # Catch the data sent from our Javascript
            data = json.loads(request.body)
            lat = data.get('latitude')
            lng = data.get('longitude')
            
            # Save it to our new Database table!
            LocationPing.objects.create(
                employee=request.user,
                latitude=lat,
                longitude=lng
            )
            return JsonResponse({'status': 'success', 'message': 'Ping saved!'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)