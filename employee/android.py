from math import radians, sin, cos, sqrt, atan2
from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.auth import login
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.views.decorators.csrf import csrf_exempt 
from dash.models import UserProfile, Attendance

# -----------------------------------------
# HAVERSINE DISTANCE
# -----------------------------------------
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000  # meters

    lat1 = radians(float(lat1))
    lon1 = radians(float(lon1))
    lat2 = radians(float(lat2))
    lon2 = radians(float(lon2))

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c


# -----------------------------------------
# SEND OTP
# -----------------------------------------
@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def send_otp(request):
    phone = request.data.get("phone")
    latitude = request.data.get("latitude")
    longitude = request.data.get("longitude")

    if not all([phone, latitude, longitude]):
        return Response(
            {"success": False, "message": "Phone + GPS required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        profile = UserProfile.objects.select_related("branch").get(
            phone=phone,
            role="employee",
            status="Enabled"
        )
    except UserProfile.DoesNotExist:
        return Response(
            {"success": False, "message": "Employee not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    branch = profile.branch

    if not branch:
        return Response(
            {"success": False, "message": "No branch assigned"},
            status=status.HTTP_400_BAD_REQUEST
        )

    distance = calculate_distance(
        latitude,
        longitude,
        branch.gps_lat,
        branch.gps_lng
    )

    if distance > branch.gps_radius:
        return Response(
            {
                "success": False,
                "message": "Outside branch range"
            },
            status=status.HTTP_403_FORBIDDEN
        )

    # TEMP OTP (replace with SMS provider)
    otp = "123456"

    request.session["otp"] = otp
    request.session["phone"] = phone
    request.session["lat"] = latitude
    request.session["lng"] = longitude

    return Response({
        "success": True,
        "message": "OTP sent successfully"
    })


# -----------------------------------------
# VERIFY OTP + AUTO PUNCH IN
# -----------------------------------------
@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def verify_otp(request):
    otp = request.data.get("otp")

    session_otp = request.session.get("otp")
    phone = request.session.get("phone")
    lat = request.session.get("lat")
    lng = request.session.get("lng")

    if otp != session_otp:
        return Response(
            {"success": False, "message": "Invalid OTP"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        profile = UserProfile.objects.select_related("user", "branch").get(
            phone=phone,
            role="employee"
        )
    except UserProfile.DoesNotExist:
        return Response(
            {"success": False, "message": "Employee not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    user = profile.user
    login(request, user)

    today = timezone.now().date()

    attendance, created = Attendance.objects.get_or_create(
        employee=profile,
        date=today,
        defaults={
            "branch": profile.branch
        }
    )

    if not attendance.punch_in:
        attendance.punch_in = timezone.now()
        attendance.punch_in_lat = lat
        attendance.punch_in_lng = lng
        attendance.is_out_of_zone = False
        attendance.save()

    return Response({
        "success": True,
        "message": "Login successful",
        "user_id": user.id,
        "name": user.get_full_name(),
        "role": profile.role
    })


# -----------------------------------------
# PUNCH OUT
# -----------------------------------------
@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def punch_out(request):
    lat = request.data.get("latitude")
    lng = request.data.get("longitude")

    profile = request.user.profile
    today = timezone.now().date()

    try:
        attendance = Attendance.objects.get(
            employee=profile,
            date=today
        )
    except Attendance.DoesNotExist:
        return Response(
            {"success": False, "message": "No punch-in found"},
            status=status.HTTP_404_NOT_FOUND
        )

    attendance.punch_out = timezone.now()
    attendance.punch_out_lat = lat
    attendance.punch_out_lng = lng
    attendance.calculate_hours()
    attendance.save()

    return Response({
        "success": True,
        "message": "Punch out successful",
        "hours": attendance.total_hours
    })


# -----------------------------------------
# ATTENDANCE STATUS
# -----------------------------------------
@csrf_exempt
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def attendance_status(request):
    profile = request.user.profile
    today = timezone.now().date()

    attendance = Attendance.objects.filter(
        employee=profile,
        date=today
    ).first()

    if not attendance:
        return Response({
            "punched_in": False
        })

    return Response({
        "punched_in": bool(attendance.punch_in),
        "punched_out": bool(attendance.punch_out),
        "punch_in": attendance.punch_in,
        "punch_out": attendance.punch_out,
        "hours": attendance.total_hours
    })