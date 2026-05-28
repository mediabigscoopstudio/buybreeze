from math import radians, sin, cos, sqrt, atan2
from datetime import datetime
import os
import pytz

from django.utils import timezone
from django.utils.dateparse import parse_datetime
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
# ATTENDANCE HISTORY
# -----------------------------------------
@csrf_exempt
@api_view(["GET"])
@permission_classes([AllowAny])
def attendance_history(request):
    phone = request.query_params.get("phone")
    month = request.query_params.get("month")
    year = request.query_params.get("year")

    if not all([phone, month, year]):
        return Response({
            "success": False,
            "message": "phone, month and year required"
        })

    try:
        profile = UserProfile.objects.get(phone=phone, role="employee")

        records = Attendance.objects.filter(
            employee=profile,
            date__month=int(month),
            date__year=int(year)
        ).order_by("-date")

        ist = pytz.timezone("Asia/Kolkata")
        record_data = []
        total_hours = 0
        present_days = 0

        for record in records:
            hours = float(record.total_hours) if record.total_hours else 0
            total_hours += hours
            if record.punch_in:
                present_days += 1

            record_data.append({
                "date": str(record.date),
                "punch_in":    record.punch_in.astimezone(ist).strftime("%I:%M %p") if record.punch_in else None,
                "punch_out":   record.punch_out.astimezone(ist).strftime("%I:%M %p") if record.punch_out else None,
                "total_hours": str(round(hours, 2)) if hours else None,
                "status":      "present" if record.punch_in else "absent"
            })

        avg_hours = round(total_hours / present_days, 2) if present_days > 0 else 0

        return Response({
            "success": True,
            "records": record_data,
            "present_days": present_days,
            "total_hours": str(round(total_hours, 2)),
            "avg_hours": str(avg_hours)
        })

    except UserProfile.DoesNotExist:
        return Response({"success": False, "message": "Employee not found"})


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

        ist = pytz.timezone("Asia/Kolkata")
        call_log_data = []
        for call in call_logs:
            recording_url = None
            if call.recording:
                try:
                    recording_url = request.build_absolute_uri(call.recording.url)
                except Exception:
                    recording_url = None

            wrapup = getattr(call, "wrapup", None)
            followup_at_str = None
            if wrapup and wrapup.followup_at:
                try:
                    followup_at_str = wrapup.followup_at.astimezone(ist).strftime("%d %b %Y %I:%M %p")
                except Exception:
                    followup_at_str = str(wrapup.followup_at)

            call_log_data.append({
                "id":             call.id,
                "call_outcome":   call.call_outcome,
                "call_duration":  call.call_duration,
                "call_notes":     call.call_notes,
                "created_at":     call.created_at.astimezone(ist).strftime("%d %b %Y %I:%M %p"),
                "called_by_name": call.called_by.user.get_full_name() if call.called_by else None,
                "next_action":    wrapup.next_action if wrapup else None,
                "followup_at":    followup_at_str,
                "temperature":    wrapup.temperature_update if wrapup else None,
                "stage":          wrapup.stage_update if wrapup else None,
                "recording_url":  recording_url,
                "detailed_notes": wrapup.detailed_notes if wrapup else None,
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
            parsed = parse_datetime(str(followup_at).replace("Z", "+00:00"))
            if parsed is None:
                parsed = datetime.fromisoformat(str(followup_at).replace("Z", "+00:00"))
            if parsed and parsed.tzinfo is None:
                parsed = timezone.make_aware(parsed)
            followup_dt = parsed
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
# UPLOAD CALL RECORDING
# -----------------------------------------
@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def upload_recording(request):
    phone          = request.data.get("phone")
    call_id        = request.data.get("call_id")
    recording_file = request.FILES.get("recording")
    duration       = request.data.get("duration", 0)

    if not phone:
        return Response(
            {"success": False, "message": "phone required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        profile = UserProfile.objects.get(phone=phone, role="employee")
    except UserProfile.DoesNotExist:
        return Response(
            {"success": False, "message": "Employee not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    try:
        if call_id:
            call_log = CallLog.objects.get(id=int(call_id), called_by=profile)
        else:
            call_log = CallLog.objects.filter(called_by=profile).latest("created_at")
    except CallLog.DoesNotExist:
        return Response(
            {"success": False, "message": "Call log not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    # Update duration if provided
    if duration:
        call_log.call_duration = int(duration)
        call_log.save()

    # Save recording file
    if recording_file:
        from django.core.files.storage import default_storage
        from django.core.files.base import ContentFile

        ext       = os.path.splitext(recording_file.name)[1] or ".mp3"
        file_path = f"recordings/call_{call_log.id}_{phone}{ext}"
        saved_path = default_storage.save(file_path, ContentFile(recording_file.read()))

        # Store on the FileField so the audio player works in the dashboard
        call_log.recording = saved_path
        call_log.save()

        recording_url = request.build_absolute_uri(f"/media/{saved_path}")
        return Response({
            "success": True,
            "message": "Recording uploaded",
            "recording_url": recording_url,
            "call_id": call_log.id
        })

    return Response({
        "success": True,
        "message": "Duration updated",
        "call_id": call_log.id
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

    today = timezone.localdate()

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


# -----------------------------------------
# APPLY LEAVE (Android API)
# -----------------------------------------
@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def apply_leave(request):
    phone      = request.data.get("phone")
    leave_type = request.data.get("leave_type")
    from_date  = request.data.get("from_date")
    to_date    = request.data.get("to_date")
    reason     = request.data.get("reason")

    if not all([phone, leave_type, from_date, to_date, reason]):
        return Response(
            {"success": False, "message": "All fields required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        profile = UserProfile.objects.get(phone=phone, role="employee")
    except UserProfile.DoesNotExist:
        return Response(
            {"success": False, "message": "Employee not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    try:
        from dash.models import LeaveRequest
        leave = LeaveRequest.objects.create(
            employee     = profile,
            leave_type   = leave_type,
            from_date    = from_date,
            to_date      = to_date,
            reason       = reason,
            leave_status = "pending",
        )
        return Response({
            "success":  True,
            "message":  "Leave request submitted",
            "leave_id": leave.id
        })
    except Exception as e:
        return Response(
            {"success": False, "message": str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


# -----------------------------------------
# MY LEAVES (Android API)
# -----------------------------------------
@csrf_exempt
@api_view(["GET"])
@permission_classes([AllowAny])
def my_leaves(request):
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

    from dash.models import LeaveRequest
    leaves = LeaveRequest.objects.filter(employee=profile).order_by("-created_at")

    ist = pytz.timezone("Asia/Kolkata")
    leave_data = [
        {
            "id":         leave.id,
            "leave_type": leave.leave_type,
            "from_date":  str(leave.from_date),
            "to_date":    str(leave.to_date),
            "reason":     leave.reason,
            "status":     leave.leave_status,
            "total_days": leave.total_days(),
            "remarks":    leave.remarks,
            "created_at": leave.created_at.astimezone(ist).strftime("%d %b %Y"),
        }
        for leave in leaves
    ]

    return Response({"success": True, "leaves": leave_data})
