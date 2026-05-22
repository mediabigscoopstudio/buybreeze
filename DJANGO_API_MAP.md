# DJANGO API MAP — BuyBreeze CRM
> Generated from urls.py + views.py + models.py across all apps.
> Use this as the master reference when building Android clients.

---

## BASE URLS (Subdomain Routing via django-hosts)

| Subdomain | App | Base URL (local) |
|---|---|---|
| `www` / root | dash (Super Admin) | `http://localhost:8000` |
| `hrpanel` | HR Panel | `http://hrpanel.localhost:8000` |
| `employee` | Employee + Android APIs | `http://employee.localhost:8000` |
| `manager` | Manager | `http://manager.localhost:8000` |
| `teamleader` | Team Leader | `http://teamleader.localhost:8000` |

---

## AUTH MECHANISM

| API Type | Auth Method |
|---|---|
| Android APIs | **Django Session Cookie** (DRF `IsAuthenticated` reads the session set by `login()` in verify-otp) |
| Web panel APIs | Django Session Cookie |

> **Android note:** After calling `verify-otp`, Django calls `login(request, user)` internally.
> The response sets a `sessionid` cookie. All subsequent Android API calls must send this cookie.
> There are **no JWT tokens** — the app must persist the session cookie.

---

## SECTION 1 — ANDROID REST APIs
> Host: `http://employee.localhost:8000`
> These are the only true JSON/REST endpoints designed for the Android app.

---

### POST `/api/auth/send-otp/`

**Purpose:** Step 1 of Android login. Validates employee GPS location against branch geofence, then sends OTP.

- **Auth required:** No
- **Session cookie:** Not required

**Request Body (JSON):**
```json
{
  "phone": "9876543210",
  "latitude": "22.572646",
  "longitude": "88.363895"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `phone` | string | Yes | Employee's registered phone number |
| `latitude` | string/float | Yes | Employee's current GPS latitude |
| `longitude` | string/float | Yes | Employee's current GPS longitude |

**Response — Success (200):**
```json
{
  "success": true,
  "message": "OTP sent successfully"
}
```

**Response — Employee not found (404):**
```json
{
  "success": false,
  "message": "Employee not found"
}
```

**Response — Outside geofence (403):**
```json
{
  "success": false,
  "message": "Outside branch range"
}
```

**Response — No branch assigned (400):**
```json
{
  "success": false,
  "message": "No branch assigned"
}
```

**Response — Missing fields (400):**
```json
{
  "success": false,
  "message": "Phone + GPS required"
}
```

> **Note:** OTP is currently hardcoded to `"123456"` (test mode). Replace with SMS provider.
> OTP, phone, lat, lng are stored in Django session for verification in next step.

---

### POST `/api/auth/verify-otp/`

**Purpose:** Step 2 of Android login. Verifies OTP from session, logs in user, auto-creates today's attendance record and punch-in.

- **Auth required:** No
- **Session cookie:** Must send the session cookie received from `send-otp` call

**Request Body (JSON):**
```json
{
  "otp": "123456"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `otp` | string | Yes | OTP entered by user |

**Response — Success (200):**
```json
{
  "success": true,
  "message": "Login successful",
  "user_id": 42,
  "name": "Rahul Sharma",
  "role": "employee"
}
```

| Field | Type | Description |
|---|---|---|
| `success` | boolean | true on success |
| `message` | string | Human-readable status |
| `user_id` | integer | Django User ID |
| `name` | string | Full name from `user.get_full_name()` |
| `role` | string | Always `"employee"` for this endpoint |

**Response — Invalid OTP (400):**
```json
{
  "success": false,
  "message": "Invalid OTP"
}
```

**Response — Employee not found (404):**
```json
{
  "success": false,
  "message": "Employee not found"
}
```

> **Side Effect:** On success, automatically creates/gets today's `Attendance` record and sets `punch_in` + `punch_in_lat` + `punch_in_lng` if not already punched in.
> The response also sets the Django `sessionid` cookie — **store this cookie for all future authenticated requests.**

---

### POST `/api/attendance/punch-out/`

**Purpose:** Records employee punch-out with GPS coordinates. Calculates total hours.

- **Auth required:** Yes (session cookie from verify-otp)
- **Session cookie:** Required

**Request Body (JSON):**
```json
{
  "latitude": "22.572646",
  "longitude": "88.363895"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `latitude` | string/float | Yes | Employee's GPS latitude at punch-out |
| `longitude` | string/float | Yes | Employee's GPS longitude at punch-out |

**Response — Success (200):**
```json
{
  "success": true,
  "message": "Punch out successful",
  "hours": 8.5
}
```

| Field | Type | Description |
|---|---|---|
| `success` | boolean | true on success |
| `message` | string | Status message |
| `hours` | float | Total hours worked today |

**Response — No punch-in found (404):**
```json
{
  "success": false,
  "message": "No punch-in found"
}
```

---

### GET `/api/attendance/status/`

**Purpose:** Returns today's attendance status for the logged-in employee.

- **Auth required:** Yes (session cookie)
- **Session cookie:** Required
- **Request Body:** None

**Response — Not punched in (200):**
```json
{
  "punched_in": false
}
```

**Response — Punched in / out (200):**
```json
{
  "punched_in": true,
  "punched_out": true,
  "punch_in": "2026-05-22T09:00:00Z",
  "punch_out": "2026-05-22T18:00:00Z",
  "hours": 9.0
}
```

| Field | Type | Description |
|---|---|---|
| `punched_in` | boolean | Whether punch_in exists today |
| `punched_out` | boolean | Whether punch_out exists today |
| `punch_in` | datetime string (ISO) | Punch-in timestamp (null if not punched in) |
| `punch_out` | datetime string (ISO) | Punch-out timestamp (null if not punched out) |
| `hours` | float | Total hours (null if not complete) |

---

## SECTION 2 — DASH (SUPER ADMIN) JSON APIs
> Host: `http://localhost:8000`
> Auth: Django session cookie, role = `admin` (superuser)

---

### GET `/notifications/`

- **Auth required:** Yes (login_required)
- **Session cookie:** Required

**Response (200):**
```json
{
  "notifications": [
    {
      "id": 1,
      "title": "New lead assigned",
      "description": "Lead Rahul Sharma has been assigned to you.",
      "created_at": "22 May 2026 09:30 AM",
      "is_read": false
    }
  ],
  "unread_count": 3
}
```

| Field | Type | Description |
|---|---|---|
| `notifications` | array | Last 15 notifications for logged-in user |
| `notifications[].id` | integer | NotificationRecipient ID |
| `notifications[].title` | string | Notification title |
| `notifications[].description` | string | Notification body |
| `notifications[].created_at` | string | Formatted as `"DD Mon YYYY HH:MM AM/PM"` |
| `notifications[].is_read` | boolean | Read status |
| `unread_count` | integer | Total unread notifications |

---

### GET `/notifications/read/<notification_id>/`

- **Auth required:** Yes
- **Session cookie:** Required

**Response — Success (200):**
```json
{
  "success": true,
  "unread_count": 2
}
```

**Response — Not found (200):**
```json
{
  "success": false
}
```

---

### POST `/assign-leads/`

**Purpose:** Bulk assign multiple leads to a manager.

- **Auth required:** Yes (superadmin only)
- **CSRF:** Exempt (`@csrf_exempt`)

**Request Body (JSON):**
```json
{
  "lead_ids": [1, 2, 3],
  "manager_id": 5
}
```

| Field | Type | Required |
|---|---|---|
| `lead_ids` | array of integers | Yes |
| `manager_id` | integer | Yes |

**Response — Success (200):**
```json
{ "status": "success" }
```

**Response — Error (200):**
```json
{ "status": "error", "message": "Missing data" }
```

---

### GET `/api/route/<username>/<date_str>/`

**Purpose:** Returns GPS ping route for an employee on a given date (for map rendering).

- **Auth required:** Yes (staff_member_required)
- **URL params:** `username` = Django username, `date_str` = `YYYY-MM-DD`

**Response — Success (200):**
```json
{
  "status": "success",
  "route": [
    { "lat": 22.572646, "lng": 88.363895, "time": "09:00 AM" },
    { "lat": 22.573000, "lng": 88.364000, "time": "10:15 AM" }
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `route` | array | Ordered list of GPS pings |
| `route[].lat` | float | Latitude |
| `route[].lng` | float | Longitude |
| `route[].time` | string | Formatted as `"HH:MM AM/PM"` |

**Response — Error (400):**
```json
{ "status": "error", "message": "..." }
```

---

### GET `/api/meta/webhook/`

**Purpose:** Meta webhook verification (called by Meta, not Android).

Query params: `hub.mode`, `hub.verify_token`, `hub.challenge`
Verify token: `"buybreeze_meta_verify"`
Response: returns `hub.challenge` as plain text if valid.

---

### POST `/api/meta/webhook/`

**Purpose:** Receives incoming Meta Ads leads (called by Meta, not Android).

- **Auth required:** No (csrf_exempt)
- **Request Body:** Meta-format JSON payload
- **Response:** `{ "status": "received" }`

---

## SECTION 3 — MANAGER JSON APIs
> Host: `http://manager.localhost:8000`
> Auth: Django session cookie, role = `manager`

---

### POST `/assign-to-tl/`

**Purpose:** Manager bulk-assigns leads to a Team Leader.

- **Auth required:** Yes (manager role)

**Request Body (JSON):**
```json
{
  "lead_ids": [1, 2, 3],
  "tl_id": 7
}
```

| Field | Type | Required |
|---|---|---|
| `lead_ids` | array of integers | Yes |
| `tl_id` | integer | Yes (UserProfile ID with role=tl) |

**Response — Success (200):**
```json
{ "status": "success" }
```

**Response — Error (200):**
```json
{ "status": "error", "message": "Missing data" }
```

---

## SECTION 4 — TEAMLEADER JSON APIs
> Host: `http://teamleader.localhost:8000`
> Auth: Django session cookie, role = `tl`

---

### POST `/assign-to-employee/`

**Purpose:** Team Leader bulk-assigns leads to an employee under them.

- **Auth required:** Yes (tl role)

**Request Body (JSON):**
```json
{
  "lead_ids": [1, 2, 3],
  "employee_id": 12
}
```

| Field | Type | Required |
|---|---|---|
| `lead_ids` | array of integers | Yes |
| `employee_id` | integer | Yes (UserProfile ID with role=employee, reports_to=this TL) |

**Response — Success (200):**
```json
{ "status": "success" }
```

**Response — Error (200):**
```json
{ "status": "error", "message": "..." }
```

---

## SECTION 5 — WEB-ONLY ENDPOINTS (HTML, not for Android)
> These return HTML pages or redirects. Not usable directly from Android.
> Listed for completeness. Build Android-specific endpoints for these if needed.

### DASH (Super Admin) — `http://localhost:8000`

| Method | URL | Purpose | Auth |
|---|---|---|---|
| GET/POST | `/login/` | Superadmin phone login | No |
| GET/POST | `/verify-otp/` | OTP verification | No |
| GET | `/logout/` | Logout | Yes |
| GET | `/` | Dashboard home | Yes (admin) |
| GET | `/branches` | List branches | Yes (admin) |
| GET/POST | `/add_branch` | Add branch | Yes (admin) |
| GET/POST | `/edit_branch/<id>` | Edit branch | Yes (admin) |
| GET | `/delete_branch/<id>` | Delete branch | Yes (admin) |
| GET | `/enable_branch/<id>` | Enable branch | Yes (admin) |
| GET | `/disable_branch/<id>` | Disable branch | Yes (admin) |
| GET | `/users` | List users | Yes (admin) |
| GET/POST | `/add_user` | Add user | Yes (admin) |
| GET/POST | `/edit_user/<id>` | Edit user | Yes (admin) |
| GET | `/delete_user/<id>` | Delete user | Yes (admin) |
| GET | `/enable_user/<id>` | Enable user | Yes (admin) |
| GET | `/disable_user/<id>` | Disable user | Yes (admin) |
| GET | `/hr` | HR panel | Yes (admin) |
| GET | `/hr/employee/<id>` | Employee detail | Yes (admin) |
| GET | `/attendance` | List attendance | Yes (admin) |
| GET/POST | `/add_attendance` | Add attendance | Yes (admin) |
| GET/POST | `/edit_attendance/<id>` | Edit attendance | Yes (admin) |
| GET | `/delete_attendance/<id>` | Delete attendance | Yes (admin) |
| GET | `/leaves` | List leave requests | Yes (admin) |
| GET/POST | `/add_leave` | Add leave | Yes (admin) |
| GET/POST | `/edit_leave/<id>` | Edit leave | Yes (admin) |
| GET | `/delete_leave/<id>` | Delete leave | Yes (admin) |
| GET | `/approve_leave/<id>` | Approve leave | Yes (admin) |
| GET | `/reject_leave/<id>` | Reject leave | Yes (admin) |
| GET | `/payroll` | List payroll | Yes (admin) |
| GET/POST | `/add_payroll` | Add payroll | Yes (admin) |
| GET/POST | `/edit_payroll/<id>` | Edit payroll | Yes (admin) |
| GET | `/delete_payroll/<id>` | Delete payroll | Yes (admin) |
| GET | `/leads` | List leads | Yes (admin) |
| GET/POST | `/add_lead` | Add lead | Yes (admin) |
| GET/POST | `/edit_lead/<id>` | Edit lead | Yes (admin) |
| GET | `/delete_lead/<id>` | Delete lead | Yes (admin) |
| GET | `/enable_lead/<id>` | Enable lead | Yes (admin) |
| GET | `/disable_lead/<id>` | Disable lead | Yes (admin) |
| GET | `/view_lead/<id>` | View lead detail | Yes (admin) |
| GET/POST | `/leads/bulk-upload` | Bulk upload leads (CSV/XLSX) | Yes (admin) |
| GET | `/leads/download-template` | Download CSV template | Yes (admin) |
| POST | `/leads/assign_to_manager/<lead_id>/` | Assign lead to manager | Yes (admin) |
| POST | `/leads/unassign_from_manager/<lead_id>/` | Unassign lead | Yes (admin) |
| GET | `/manager_performance/<id>/` | Manager performance view | Yes (admin) |
| GET | `/calls` | List call logs | Yes (admin) |
| GET/POST | `/add_call` | Add call | Yes (admin) |
| GET/POST | `/edit_call/<id>` | Edit call | Yes (admin) |
| GET | `/delete_call/<id>` | Delete call | Yes (admin) |
| GET | `/wrapups` | List call wrap-ups | Yes (admin) |
| GET | `/followups` | List follow-ups | Yes (admin) |
| GET/POST | `/add_followup` | Add follow-up | Yes (admin) |
| GET/POST | `/edit_followup/<id>` | Edit follow-up | Yes (admin) |
| GET | `/delete_followup/<id>` | Delete follow-up | Yes (admin) |
| GET/POST | `/settings` | System settings | Yes (admin) |
| GET | `/apr-report/` | APR attendance report | Yes (staff) |

### EMPLOYEE — `http://employee.localhost:8000`

| Method | URL | Purpose | Auth |
|---|---|---|---|
| GET/POST | `/login/` | Employee web login | No |
| GET/POST | `/verify-otp/` | OTP verification (web) | No |
| GET | `/logout/` | Logout | Yes |
| GET | `/` | Employee dashboard | Yes (employee) |

### HR PANEL — `http://hrpanel.localhost:8000`

| Method | URL | Purpose | Auth |
|---|---|---|---|
| GET/POST | `/login/` | HR login | No |
| GET/POST | `/verify-otp/` | OTP verification | No |
| GET | `/logout/` | Logout | Yes |
| GET | `/` | HR dashboard | Yes (hr) |
| GET | `/profile` | HR profile | Yes (hr) |
| GET | `/branches` | Branches | Yes (hr) |
| GET | `/hr/employee/<id>` | Employee detail | Yes (hr) |
| GET | `/attendance` | Attendance records | Yes (hr) |
| GET | `/leaves` | Leave requests | Yes (hr) |
| GET | `/payroll` | Payroll records | Yes (hr) |
| GET | `/users` | User management | Yes (hr) |
| GET | `/settings` | Settings | Yes (hr) |
| GET | `/apr-reports/` | APR reports list | Yes (hr) |
| GET | `/apr-report/<id>/` | Individual APR report | Yes (hr) |

### MANAGER — `http://manager.localhost:8000`

| Method | URL | Purpose | Auth |
|---|---|---|---|
| GET/POST | `/login/` | Manager login | No |
| GET/POST | `/verify-otp/` | OTP verification | No |
| GET | `/logout/` | Logout | Yes |
| GET | `/` | Manager dashboard | Yes (manager) |
| POST | `/unassign_lead/<lead_id>/` | Unassign lead from TL | Yes (manager) |
| GET | `/tl_performance/<id>/` | TL performance | Yes (manager) |
| GET/POST | `/profile_settings` | Profile settings | Yes (manager) |
| GET | `/view_lead/<id>/` | View lead detail | Yes (manager) |
| GET | `/apr-reports/` | APR reports | Yes (manager) |
| GET | `/apr-report/<id>/` | Individual APR report | Yes (manager) |

### TEAM LEADER — `http://teamleader.localhost:8000`

| Method | URL | Purpose | Auth |
|---|---|---|---|
| GET/POST | `/login/` | TL login | No |
| GET/POST | `/verify-otp/` | OTP verification | No |
| GET | `/logout/` | Logout | Yes |
| GET | `/` | TL dashboard | Yes (tl) |
| GET/POST | `/profile/` | TL profile | Yes (tl) |
| GET | `/employee_performance/<id>/` | Employee performance | Yes (tl) |
| GET | `/view_lead/<id>/` | View lead detail | Yes (tl) |
| GET | `/apr-reports/` | APR reports | Yes (tl) |
| GET | `/apr-report/<id>/` | Individual APR report | Yes (tl) |

---

## QUICK REFERENCE — Android API Summary

| # | Method | URL (employee subdomain) | Auth | Purpose |
|---|---|---|---|---|
| 1 | POST | `/api/auth/send-otp/` | No | Send OTP (with GPS check) |
| 2 | POST | `/api/auth/verify-otp/` | Session | Verify OTP + auto punch-in |
| 3 | POST | `/api/attendance/punch-out/` | Session | Punch out |
| 4 | GET | `/api/attendance/status/` | Session | Today's attendance status |

---

## KNOWN ISSUES / NOTES FOR ANDROID DEVELOPER

1. **Session-based auth (not JWT):** The Android app must persist the Django `sessionid` cookie across requests. Consider using `OkHttp CookieJar` or Retrofit's cookie interceptor.

2. **OTP is hardcoded:** `android.py` line 86 — `otp = "123456"`. Replace with real SMS provider before production.

3. **Import inconsistency in android.py:** `from .models import UserProfile, Attendance` — `UserProfile` does not exist in `employee/models.py`. It's defined in `dash/models.py`. The `Attendance` model used also appears to be `dash.models.Attendance` (which has `punch_in`, `punch_in_lat` fields), not `employee.models.Attendance` (which has `punch_in_time`). This will cause an `ImportError` at runtime — needs to be fixed before testing.

4. **No token refresh:** No logout/token invalidation endpoint exists for Android. Call `/logout/` (web redirect) or invalidate session server-side.

5. **CSRF on Android APIs:** Android APIs use DRF `@api_view` which exempts CSRF by default for non-session-based auth. However since auth is session-based, DRF's `SessionAuthentication` enforces CSRF. Include `X-CSRFToken` header in POST requests or use `@csrf_exempt` on the views.
