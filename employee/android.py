from math import radians, sin, cos, sqrt, atan2
from datetime import datetime

from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.views.decorators.csrf import csrf_exempt

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from dash.models import (
    UserProfile, Attendance, Lead,
    CallLog, CallWrapUp, FollowUp, Branch
)
from employee.models import LocationPing, Attendance as EmployeeAttendance


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
            phone=phone, role="employee", status="Enabled"
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

    distance = calculate_distance(latitude, longitude, branch.gps_lat, branch.gps_lng)
    if distance > branch.gps_radius:
        return Response(
            {"success": False, "message": "Outside branch range"},
            status=status.HTTP_403_FORBIDDEN
        )

    # TEMP OTP — replace with SMS provider
    otp = "123456"
    request.session["otp"] = otp
    request.session["phone"] = phone
    request.session["lat"] = latitude
    request.session["lng"] = longitude

    return Response({"success": True, "message": "OTP sent successfully"})


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
            phone=phone, role="employee"
        )
    except UserProfile.DoesNotExist:
        return Response(
            {"success": False, "message": "Employee not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    user = profile.user
    login(request, user)

    today = timezone.now().date()
    attendance, _ = Attendance.objects.get_or_create(
        employee=profile,
        date=today,
        defaults={"branch": profile.branch}
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
@permission_classes([AllowAny])
def punch_out(request):
    phone = request.data.get("phone")
    lat = request.data.get("latitude")
    lng = request.data.get("longitude")

    if not phone:
        return Response(
            {"success": False, "message": "Phone required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        profile = UserProfile.objects.get(phone=phone, role="employee")
    except UserProfile.DoesNotExist:
        return Response(
            {"success": False, "message": "Employee not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    today = timezone.now().date()
    try:
        attendance = Attendance.objects.get(employee=profile, date=today)
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
        "hours": str(attendance.total_hours)
    })


# -----------------------------------------
# ATTENDANCE STATUS
# -----------------------------------------
@csrf_exempt
@api_view(["GET"])
@permission_classes([AllowAny])
def attendance_status(request):
    phone = request.query_params.get("phone")

    if not phone:
        return Response({"punched_in": False})

    try:
        profile = UserProfile.objects.get(phone=phone, role="employee")
    except UserProfile.DoesNotExist:
        return Response({"punched_in": False})

    today = timezone.now().date()
    attendance = Attendance.objects.filter(employee=profile, date=today).first()

    if not attendance:
        return Response({"punched_in": False})

    return Response({
        "punched_in": bool(attendance.punch_in),
        "punched_out": bool(attendance.punch_out),
        "punch_in": str(attendance.punch_in) if attendance.punch_in else None,
        "punch_out": str(attendance.punch_out) if attendance.punch_out else None,
        "hours": str(attendance.total_hours) if attendance.total_hours else None
    })


# -----------------------------------------
# GET PROFILE
# -----------------------------------------
@csrf_exempt
@api_view(["GET"])
@permission_classes([AllowAny])
def get_profile(request):
    phone = request.query_params.get("phone")

    if not phone:
        return Response(
            {"success": False, "message": "Phone required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        profile = UserProfile.objects.select_related(
            "user", "branch", "reports_to__user"
        ).get(phone=phone, role="employee")
    except UserProfile.DoesNotExist:
        return Response(
            {"success": False, "message": "Employee not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    return Response({
        "success": True,
        "first_name": profile.user.first_name,
        "last_name": profile.user.last_name,
        "email": profile.user.email,
        "phone": profile.phone,
        "role": profile.role,
        "branch": profile.branch.name if profile.branch else "Not Assigned",
        "reports_to": profile.reports_to.user.get_full_name() if profile.reports_to else "Super Admin",
        "status": profile.status,
        "profile_pic": profile.profile_pic.url if profile.profile_pic else None,
    })


# -----------------------------------------
# UPDATE PROFILE
# -----------------------------------------
@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def update_profile(request):
    phone = request.data.get("phone")

    if not phone:
        return Response(
            {"success": False, "message": "Phone required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        profile = UserProfile.objects.select_related("user").get(
            phone=phone, role="employee"
        )
    except UserProfile.DoesNotExist:
        return Response(
            {"success": False, "message": "Employee not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    user = profile.user
    user.first_name = request.data.get("first_name", user.first_name)
    user.last_name = request.data.get("last_name", user.last_name)
    user.email = request.data.get("email", user.email)
    user.save()

    return Response({"success": True, "message": "Profile updated successfully"})


# -----------------------------------------
# GET LEADS
# -----------------------------------------
@csrf_exempt
@api_view(["GET"])
@permission_classes([AllowAny])
def get_leads(request):
    phone = request.query_params.get("phone")

    if not phone:
        return Response(
            {"success": False, "message": "Phone required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        profile = UserProfile.objects.get(phone=phone, role="employee")
    except UserProfile.DoesNotExist:
        return Response(
            {"success": False, "message": "Employee not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    leads = Lead.objects.filter(
        assigned_to=profile,
        status="Enabled"
    ).values(
        "id", "name", "phone", "email",
        "stage", "temperature", "location",
        "property_type", "budget_min", "budget_max",
        "purpose", "source", "created_at"
    )

    return Response({
        "success": True,
        "count": leads.count(),
        "leads": list(leads)
    })


# -----------------------------------------
# GET LEAD DETAIL
# -----------------------------------------
@csrf_exempt
@api_view(["GET"])
@permission_classes([AllowAny])
def get_lead_detail(request):
    lead_id = request.query_params.get("lead_id")
    phone = request.query_params.get("phone")

    if not lead_id or not phone:
        return Response({
            "success": False,
            "message": "lead_id and phone required"
        })

    try:
        profile = UserProfile.objects.get(phone=phone, role="employee")
        lead = Lead.objects.get(id=lead_id, assigned_to=profile)

        call_logs = CallLog.objects.filter(
            lead=lead
        ).order_by("-created_at")[:10]

        call_log_data = []
        for call in call_logs:
            call_log_data.append({
                "id": call.id,
                "call_outcome": call.call_outcome,
                "call_duration": call.call_duration,
                "call_notes": call.call_notes,
                "created_at": call.created_at.strftime("%d %b %Y %I:%M %p"),
                "called_by_name": call.called_by.user.get_full_name()
                    if call.called_by else None
            })

        return Response({
            "success": True,
            "id": lead.id,
            "name": lead.name,
            "phone": lead.phone,
            "email": lead.email,
            "location": lead.location,
            "stage": lead.stage,
            "temperature": lead.temperature,
            "property_type": lead.property_type,
            "budget_min": str(lead.budget_min) if lead.budget_min else None,
            "budget_max": str(lead.budget_max) if lead.budget_max else None,
            "purpose": lead.purpose,
            "source": lead.source,
            "notes": lead.notes,
            "call_logs": call_log_data
        })

    except Lead.DoesNotExist:
        return Response({"success": False, "message": "Lead not found"})
    except UserProfile.DoesNotExist:
        return Response({"success": False, "message": "Employee not found"})


# -----------------------------------------
# SAVE CALL + WRAPUP
# -----------------------------------------
@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def save_call(request):
    phone = request.data.get("phone")
    lead_id = request.data.get("lead_id")
    call_outcome = request.data.get("call_outcome", "not_answered")
    call_duration = request.data.get("call_duration", 0)
    temperature = request.data.get("temperature", "cold")
    stage = request.data.get("stage", "contacted")
    next_action = request.data.get("next_action", "no_action")
    followup_at = request.data.get("followup_at")
    notes = request.data.get("notes", "")

    if not phone or not lead_id:
        return Response(
            {"success": False, "message": "Phone and lead_id required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        profile = UserProfile.objects.select_related("branch").get(
            phone=phone, role="employee"
        )
    except UserProfile.DoesNotExist:
        return Response(
            {"success": False, "message": "Employee not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    try:
        lead = Lead.objects.get(id=lead_id)
    except Lead.DoesNotExist:
        return Response(
            {"success": False, "message": "Lead not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    # Create CallLog
    call_log = CallLog.objects.create(
        lead=lead,
        call_type="outbound",
        call_duration=int(call_duration),
        call_outcome=call_outcome,
        call_notes=notes,
        called_by=profile,
        branch=profile.branch,
    )

    # Parse followup_at if provided
    followup_dt = None
    if followup_at:
        try:
            followup_dt = datetime.fromisoformat(followup_at.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            followup_dt = None

    # Create CallWrapUp
    CallWrapUp.objects.create(
        call=call_log,
        lead=lead,
        call_outcome=call_outcome,
        call_duration=int(call_duration),
        detailed_notes=notes,
        temperature_update=temperature,
        stage_update=stage,
        next_action=next_action,
        followup_at=followup_dt,
        submitted_by=profile,
    )

    # Update Lead temperature and stage
    lead.temperature = temperature
    lead.stage = stage
    lead.save()

    # Create FollowUp if followup_at provided
    if followup_dt:
        FollowUp.objects.create(
            lead=lead,
            followup_at=followup_dt,
            followup_type="call",
            notes=notes,
            assigned_to=profile,
            branch=profile.branch,
        )

    return Response({
        "success": True,
        "message": "Call saved successfully",
        "call_id": call_log.id
    })


# -----------------------------------------
# SAVE ROUTE PING
# -----------------------------------------
@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def save_route(request):
    phone = request.data.get("phone")
    latitude = request.data.get("latitude")
    longitude = request.data.get("longitude")

    if not all([phone, latitude, longitude]):
        return Response(
            {"success": False, "message": "Phone, latitude and longitude required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        profile = UserProfile.objects.select_related("user").get(
            phone=phone, role="employee"
        )
    except UserProfile.DoesNotExist:
        return Response(
            {"success": False, "message": "Employee not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    LocationPing.objects.create(
        employee=profile.user,
        latitude=latitude,
        longitude=longitude,
    )

    return Response({"success": True, "message": "Location saved"})


# -----------------------------------------
# ROUTE HISTORY
# -----------------------------------------
@csrf_exempt
@api_view(["GET"])
@permission_classes([AllowAny])
def route_history(request):
    phone = request.query_params.get("phone")
    date_str = request.query_params.get("date")

    if not phone or not date_str:
        return Response(
            {"success": False, "message": "Phone and date required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return Response(
            {"success": False, "message": "Invalid date format. Use YYYY-MM-DD"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        profile = UserProfile.objects.select_related("user").get(
            phone=phone, role="employee"
        )
    except UserProfile.DoesNotExist:
        return Response(
            {"success": False, "message": "Employee not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    pings = LocationPing.objects.filter(
        employee=profile.user,
        timestamp__date=target_date
    ).order_by("timestamp")

    ping_list = [
        {
            "lat": str(p.latitude),
            "lng": str(p.longitude),
            "timestamp": p.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        }
        for p in pings
    ]

    return Response({
        "success": True,
        "date": date_str,
        "pings": ping_list
    })


# -----------------------------------------
# DASHBOARD STATS
# -----------------------------------------
@csrf_exempt
@api_view(["GET"])
@permission_classes([AllowAny])
def dashboard_stats(request):
    phone = request.query_params.get("phone")

    if not phone:
        return Response(
            {"success": False, "message": "Phone required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        profile = UserProfile.objects.select_related("user").get(
            phone=phone, role="employee"
        )
    except UserProfile.DoesNotExist:
        return Response(
            {"success": False, "message": "Employee not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    today = timezone.now().date()

    leads_count = Lead.objects.filter(
        assigned_to=profile, status="Enabled"
    ).count()

    calls_today = CallLog.objects.filter(
        called_by=profile,
        created_at__date=today
    ).count()

    attendance = Attendance.objects.filter(
        employee=profile, date=today
    ).first()

    if attendance and attendance.punch_in and not attendance.punch_out:
        punch_status = "in"
    else:
        punch_status = "out"

    route_points = LocationPing.objects.filter(
        employee=profile.user,
        timestamp__date=today
    ).count()

    return Response({
        "success": True,
        "leads_count": leads_count,
        "calls_today": calls_today,
        "punch_status": punch_status,
        "route_points": route_points
    })
