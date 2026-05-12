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
from datetime import timedelta, datetime
from dash.otp_utils import generate_otp, send_otp
from django.utils import timezone
from django.contrib.auth.models import User

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



# ============================================================
# AUTH GUARD
# ============================================================
def employee_required(user):

    return (
        user.is_authenticated and
        hasattr(user, 'profile') and
        user.profile.role == 'employee'
    )


# ============================================================
# AUTH VIEWS
# ============================================================
def login_view(request):

    # =========================================
    # ALREADY LOGGED IN
    # =========================================
    if request.user.is_authenticated:

        if employee_required(request.user):
            return redirect('/')

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
                role='employee'
            )

            user = profile.user

        except UserProfile.DoesNotExist:

            messages.error(
                request,
                'Phone number not registered.'
            )

            return redirect('login_view')

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

            return redirect('login_view')

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
        'employee/signin.html'
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

        return redirect('login_view')

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

        return redirect('login_view')

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

                return redirect('login_view')

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
            # EMPLOYEE REDIRECT
            # =====================================
            return redirect(
                'http://employee.localhost:8000/'
            )

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
        'employee/verify_otp.html'
    )


# ============================================================
# LOGOUT
# ============================================================
def logout_view(request):

    logout(request)

    return redirect(
        'http://employee.localhost:8000/login/'
    )

# ============================================================
# DASHBOARD HOME
# ============================================================
@user_passes_test(
    employee_required,
    login_url='/login/'
)

def index(request):
     return render(request,'employee/index.html')

@login_required
@require_POST
def process_punch(request):
    user_profile = request.user.profile
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