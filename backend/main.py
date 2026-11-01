"""
FastAPI Application Entry Point for Institute Laptop & Asset Management.
Provides REST APIs, RBAC enforcement, Static file hosting, and CSV reports.
"""

import os
import csv
import io
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse

from backend.database import init_db, get_connection
from backend.models import (
    FastIssueRequest, FastReturnRequest, SendToRepairRequest,
    ReturnFromRepairRequest, BatchTransferRequest, StudentAckRequest,
    AddStudentRequest, AddLaptopRequest, AddAccessoryRequest, UpdateStudentEmailRequest
)
from backend.auth import (
    CurrentUser, get_current_user, require_admin,
    require_issue_return, require_manage_repairs, lookup_user_by_email
)
from backend.service import AssetService

# Initialize database tables & seed sample data
init_db()

app = FastAPI(
    title="Institute Laptop & Asset Management System",
    description="Enterprise-grade system for Computer Training Institutes in India.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Current session mock storage for instant demo switching
active_demo_email = "director.vikram@sample-institute.in"

def get_session_user() -> CurrentUser:
    global active_demo_email
    user = lookup_user_by_email(active_demo_email)
    if not user:
        return CurrentUser(email=active_demo_email, role="Admin", id_="STAFF-01", name="Admin", can_issue_return=True, can_manage_repairs=True)
    return user

# ======================== AUTH & ROLES ========================

@app.get("/api/auth/me")
def get_me(user: CurrentUser = Depends(get_session_user)):
    return user.to_dict()

@app.post("/api/auth/switch-demo-role")
def switch_demo_role(email: str = Query(...)):
    """Allows testing as Admin, Staff (with/without privileges), or Student."""
    global active_demo_email
    user = lookup_user_by_email(email.strip().lower())
    if not user:
        raise HTTPException(status_code=404, detail=f"No account registered with email: {email}")
    active_demo_email = email.strip().lower()
    return {"status": "switched", "user": user.to_dict()}

# ======================== DASHBOARD ========================

@app.get("/api/dashboard/stats")
def get_dashboard(user: CurrentUser = Depends(get_session_user)):
    return AssetService.get_dashboard_stats()

# ======================== LAPTOPS ========================

@app.get("/api/laptops")
def get_laptops(
    status: Optional[str] = None,
    search: Optional[str] = None,
    user: CurrentUser = Depends(get_session_user)
):
    conn = get_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM Laptop_Master WHERE 1=1"
    params = []

    if status and status != "All":
        query += " AND Status = ?"
        params.append(status)

    if search:
        s = f"%{search.strip()}%"
        query += " AND (Laptop_ID LIKE ? OR Asset_Tag LIKE ? OR Serial_Number LIKE ? OR Brand LIKE ? OR Model LIKE ? OR Current_Holder_ID LIKE ?)"
        params.extend([s, s, s, s, s, s])

    query += " ORDER BY Laptop_ID ASC"
    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

@app.post("/api/laptops")
def add_laptop(req: AddLaptopRequest, user: CurrentUser = Depends(get_session_user)):
    if user.role not in ["Admin", "Staff"]:
        raise HTTPException(status_code=403, detail="Permission denied.")
    return AssetService.add_laptop(req, user)

# ======================== ACCESSORIES / CHARGERS ========================

@app.get("/api/accessories")
def get_accessories(
    type: Optional[str] = None,
    user: CurrentUser = Depends(get_session_user)
):
    conn = get_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM Accessories_Master WHERE 1=1"
    params = []
    if type:
        query += " AND Asset_Type = ?"
        params.append(type)
    query += " ORDER BY Accessory_ID ASC"
    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

# ======================== STUDENTS ========================

@app.get("/api/students")
def get_students(
    search: Optional[str] = None,
    course: Optional[str] = None,
    batch: Optional[str] = None,
    user: CurrentUser = Depends(get_session_user)
):
    # Security Rule: Students cannot browse all students' personal data
    if user.role == "Student":
        raise HTTPException(
            status_code=403,
            detail="Access forbidden: Students are not permitted to view other students' records or email addresses."
        )

    conn = get_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM Students_Master WHERE 1=1"
    params = []

    if course and course != "All":
        query += " AND Course_Name = ?"
        params.append(course)

    if batch and batch != "All":
        query += " AND Batch_Name = ?"
        params.append(batch)

    if search:
        s = f"%{search.strip()}%"
        query += " AND (Student_ID LIKE ? OR Student_Name LIKE ? OR Registered_Gmail LIKE ? OR Course_Name LIKE ? OR Batch_Name LIKE ?)"
        params.extend([s, s, s, s, s])

    query += " ORDER BY Student_ID ASC"
    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

@app.post("/api/students")
def add_student(req: AddStudentRequest, user: CurrentUser = Depends(get_session_user)):
    if user.role not in ["Admin", "Staff"]:
        raise HTTPException(status_code=403, detail="Permission denied.")
    return AssetService.add_student(req, user)

@app.post("/api/students/batch-transfer")
def batch_transfer(req: BatchTransferRequest, user: CurrentUser = Depends(get_session_user)):
    if user.role not in ["Admin", "Staff"]:
        raise HTTPException(status_code=403, detail="Permission denied.")
    return AssetService.batch_transfer(req, user)

@app.post("/api/students/update-email")
def update_student_email(req: UpdateStudentEmailRequest, user: CurrentUser = Depends(get_session_user)):
    """
    Dynamically link or update a student's Gmail.
    Email is NOT pre-set — it is added only when staff enters it during issuance.
    """
    if user.role not in ["Admin", "Staff"]:
        raise HTTPException(status_code=403, detail="Permission denied.")
    return AssetService.update_student_email(req.student_id, req.registered_gmail, user)

@app.get("/api/students/batches")
def get_all_batches(user: CurrentUser = Depends(get_session_user)):
    """Returns distinct batch names for filter dropdowns."""
    if user.role == "Student":
        raise HTTPException(status_code=403, detail="Access denied.")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT Batch_Name FROM Students_Master ORDER BY Batch_Name ASC")
    batches = [r[0] for r in cursor.fetchall() if r[0]]
    conn.close()
    return batches

# ======================== STAFF ========================

@app.get("/api/staff")
def get_staff(user: CurrentUser = Depends(get_session_user)):
    if user.role == "Student":
        raise HTTPException(status_code=403, detail="Access denied.")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Staff_Master ORDER BY Staff_ID ASC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

# ======================== FAST ISSUE / RETURN ========================

@app.post("/api/movement/issue")
def issue_asset(req: FastIssueRequest, user: CurrentUser = Depends(get_session_user)):
    if user.role != "Admin" and not (user.role == "Staff" and user.can_issue_return):
        raise HTTPException(status_code=403, detail="Access denied: 'Can_Issue_Return' privilege required.")
    return AssetService.fast_issue(req, user)

@app.post("/api/movement/return")
def return_asset(req: FastReturnRequest, user: CurrentUser = Depends(get_session_user)):
    if user.role != "Admin" and not (user.role == "Staff" and user.can_issue_return):
        raise HTTPException(status_code=403, detail="Access denied: 'Can_Issue_Return' privilege required.")
    return AssetService.fast_return(req, user)

@app.post("/api/movement/acknowledge")
def acknowledge_asset(req: StudentAckRequest, user: CurrentUser = Depends(get_session_user)):
    return AssetService.student_acknowledge(req.movement_id, user)

@app.get("/api/movement/logs")
def get_movement_logs(
    person_id: Optional[str] = None,
    asset_id: Optional[str] = None,
    action: Optional[str] = None,
    user: CurrentUser = Depends(get_session_user)
):
    conn = get_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM Movement_Log WHERE 1=1"
    params = []

    # If caller is Student, enforce privacy: return only records matching their registered email
    if user.role == "Student":
        query += " AND LOWER(Person_Email) = ?"
        params.append(user.email.lower().strip())
    else:
        if person_id:
            query += " AND Person_ID = ?"
            params.append(person_id)
        if asset_id:
            query += " AND Asset_ID = ?"
            params.append(asset_id)
        if action and action != "All":
            query += " AND Action = ?"
            params.append(action)

    query += " ORDER BY Event_Timestamp DESC LIMIT 200"
    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

# ======================== REPAIR MANAGEMENT ========================

@app.get("/api/repairs")
def get_repairs(
    status: Optional[str] = None,
    user: CurrentUser = Depends(get_session_user)
):
    if user.role == "Student":
        raise HTTPException(status_code=403, detail="Access denied.")
    conn = get_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM Repair_Log WHERE 1=1"
    params = []
    if status and status != "All":
        query += " AND Repair_Status = ?"
        params.append(status)
    query += " ORDER BY Out_Timestamp DESC"
    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

@app.post("/api/repairs")
def send_to_repair(req: SendToRepairRequest, user: CurrentUser = Depends(get_session_user)):
    if user.role != "Admin" and not (user.role == "Staff" and user.can_manage_repairs):
        raise HTTPException(status_code=403, detail="Access denied: 'Can_Manage_Repairs' privilege required.")
    return AssetService.send_to_repair(req, user)

@app.post("/api/repairs/return")
def return_from_repair(req: ReturnFromRepairRequest, user: CurrentUser = Depends(get_session_user)):
    if user.role != "Admin" and not (user.role == "Staff" and user.can_manage_repairs):
        raise HTTPException(status_code=403, detail="Access denied: 'Can_Manage_Repairs' privilege required.")
    return AssetService.return_from_repair(req, user)

# ======================== REPORTS & EXPORT ========================

@app.get("/api/reports/movement-csv")
def export_movement_csv(user: CurrentUser = Depends(get_session_user)):
    if user.role == "Student":
        raise HTTPException(status_code=403, detail="Access denied.")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Movement_Log ORDER BY Event_Timestamp DESC")
    rows = cursor.fetchall()

    cursor.execute("PRAGMA table_info(Movement_Log)")
    headers = [col[1] for col in cursor.fetchall()]
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for r in rows:
        writer.writerow(list(r))

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=Movement_Log_Audit.csv"}
    )

# ======================== STATIC & SPA HOSTING ========================

frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

@app.get("/")
def serve_index():
    index_file = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Institute Asset Manager API is running."}
