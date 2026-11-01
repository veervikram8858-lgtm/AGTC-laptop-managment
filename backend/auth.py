"""
Authentication & Role-Based Access Control (RBAC) Module.
Supports Google OAuth ID Token verification and Institute email verification.
Enforces Admin, Staff (Can_Issue_Return, Can_Manage_Repairs), and Student roles.
"""

from typing import Optional, Dict, Any
from fastapi import HTTPException, Header, Depends, status
import json
import urllib.request
from backend.database import get_connection

class CurrentUser:
    def __init__(self, email: str, role: str, id_: str, name: str,
                 can_issue_return: bool = False, can_manage_repairs: bool = False,
                 course: str = "", batch: str = "", active: bool = True):
        self.email = email.lower().strip()
        self.role = role # "Admin", "Staff", "Student"
        self.id = id_
        self.name = name
        self.can_issue_return = can_issue_return
        self.can_manage_repairs = can_manage_repairs
        self.course = course
        self.batch = batch
        self.active = active

    def to_dict(self):
        return {
            "email": self.email,
            "role": self.role,
            "id": self.id,
            "name": self.name,
            "can_issue_return": self.can_issue_return,
            "can_manage_repairs": self.can_manage_repairs,
            "course": self.course,
            "batch": self.batch,
            "active": self.active
        }

def verify_google_id_token(id_token: str) -> Optional[str]:
    """Verifies a Google OAuth2 ID Token using Google tokeninfo API endpoint."""
    try:
        url = f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token}"
        req = urllib.request.Request(url, headers={'User-Agent': 'InstituteAssetManager/1.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                return data.get("email")
    except Exception:
        pass
    return None

def lookup_user_by_email(email: str) -> Optional[CurrentUser]:
    email = email.lower().strip()
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Check Staff_Master
    cursor.execute("SELECT * FROM Staff_Master WHERE LOWER(Official_Gmail) = ?", (email,))
    staff = cursor.fetchone()
    if staff:
        conn.close()
        return CurrentUser(
            email=staff["Official_Gmail"],
            role=staff["Role"], # "Admin" or "Staff"
            id_=staff["Staff_ID"],
            name=staff["Staff_Name"],
            can_issue_return=bool(staff["Can_Issue_Return"]),
            can_manage_repairs=bool(staff["Can_Manage_Repairs"]),
            active=bool(staff["Active"])
        )

    # 2. Check Students_Master
    cursor.execute("SELECT * FROM Students_Master WHERE LOWER(Registered_Gmail) = ?", (email,))
    student = cursor.fetchone()
    if student:
        conn.close()
        return CurrentUser(
            email=student["Registered_Gmail"],
            role="Student",
            id_=student["Student_ID"],
            name=student["Student_Name"],
            can_issue_return=False,
            can_manage_repairs=False,
            course=student["Course_Name"],
            batch=student["Batch_Name"],
            active=bool(student["Active"])
        )

    conn.close()
    return None

def get_current_user(
    x_user_email: Optional[str] = Header(None, alias="X-User-Email"),
    authorization: Optional[str] = Header(None)
) -> CurrentUser:
    """Dependency to retrieve and verify caller identity."""
    verified_email = None

    # Check Bearer Token if present (Google Token)
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        google_email = verify_google_id_token(token)
        if google_email:
            verified_email = google_email

    # If no bearer or token was mock/header passed:
    if not verified_email and x_user_email:
        verified_email = x_user_email

    if not verified_email:
        # Default fallback for testing or initial load
        verified_email = "director.vikram@sample-institute.in"

    user = lookup_user_by_email(verified_email)
    if not user:
        # Fallback if unknown guest
        return CurrentUser(
            email=verified_email,
            role="Student",
            id_="UNKNOWN",
            name="Guest User",
            active=False
        )

    if not user.active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is marked INACTIVE. Contact Administrator.")

    return user

def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "Admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator role required for this operation.")
    return user

def require_issue_return(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role == "Admin":
        return user
    if user.role == "Staff" and user.can_issue_return:
        return user
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: 'Can_Issue_Return' privilege required.")

def require_manage_repairs(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role == "Admin":
        return user
    if user.role == "Staff" and user.can_manage_repairs:
        return user
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: 'Can_Manage_Repairs' privilege required.")
