# Institute Laptop, Charger, Student, Staff, Issue/Return & Repair Management System

Enterprise-ready inventory and issue/return tracking system tailored for computer training institutes in India. Built with a dual architecture:
1. **Google Sheets + Google Apps Script (GAS) Cloud Backend**: Central spreadsheet database with automated schema creation, role-based access control, and transaction logging.
2. **Responsive Web Application (FastAPI + HTML5/Tailwind + QR Camera Scanner)**: High-performance 2–3 second counter workflow, student self-service portal, camera QR scanner, and offline-capable data mirroring.

---

## 1. System Architecture & Features

### Core Modules & Masters
- **Students_Master**: Permanent `Student_ID` that never changes. Batch transfer preservation (`Batch_At_Transaction` logged in historical records). Search by ID, Name, Gmail, Course, and Batch. Prevents duplicate IDs.
- **Staff_Master**: Role-Based Access Control (`Admin`, `Staff`). Granular permissions (`Can_Issue_Return`, `Can_Manage_Repairs`).
- **Laptop_Master**: Tracks 6 initial pre-configured laptops (Lenovo ThinkPad, Dell Latitude, HP ProBook) with expandable capacity, condition rating, status (`Available`, `Issued`, `Under Repair`), and current holder.
- **Accessories_Master**: Complete power adapter/charger tracking. Auto-pairs with laptops or issues standalone.
- **Movement_Log**: Append-only audit trail. Supported actions: `ISSUE`, `RETURN`, `HANDOVER`, `REPAIR_OUT`, `REPAIR_RETURN`, `TRANSFER`. Timestamps strictly in `Asia/Kolkata` (+05:30).
- **Repair_Log**: Tracks service centre, technician, estimated and final cost (in INR), receipt/job sheet URLs, and condition before/after. Prevents devices marked `Under Repair` from being issued.
- **Fast 2–3 Second Counter Workflow**: Scan student QR code -> Scan laptop QR code -> Click Confirm. Auto-pairs charger and validates availability in real time.
- **Student Acknowledgement**: Separate confirmation workflow where students acknowledge receipt using their verified registered Gmail.

---

## 2. Project Files Overview

```
institute-laptop-manager/
├── backend/
│   ├── __init__.py
│   ├── main.py                   # FastAPI REST API, routing & static file serving
│   ├── models.py                 # Pydantic data schemas & request DTOs
│   ├── auth.py                   # RBAC & Google OAuth token verification
│   ├── database.py               # SQLite storage mirroring Google Sheets tabs
│   └── service.py                # Core business rules, fast issue/return, repairs
├── frontend/
│   ├── index.html                # Responsive web app (Tailwind, Lucide, QR Scanner)
│   └── printable_qr_tags.html    # Printable QR stickers for laptops, chargers, student cards
├── google_apps_script/
│   ├── Code.gs                   # Full Google Apps Script Web App (doGet/doPost)
│   ├── SetupSheet.gs             # One-click spreadsheet generator with master schema
│   └── appsscript.json           # GAS manifest with Asia/Kolkata timezone
├── tools/
│   ├── generate_sheets_excel.py  # Generates initial Excel template ready for Google Drive
│   └── generate_qr_codes.py      # QR label generator utility
├── tests/
│   ├── __init__.py
│   └── test_system.py            # Automated test suite (11 unit tests)
├── Institute_Asset_Management_Template.xlsx # Ready-to-import master workbook
└── README.md
```

---

## 3. Quick Start: Local Web Application

### Prerequisites
- Python 3.10+ (tested with Python 3.13)
- Required packages (FastAPI, Uvicorn, Openpyxl, Requests, Pydantic)

### Running the App
From the `institute-laptop-manager` directory:
```powershell
# Set Python path to current directory
$env:PYTHONPATH="."

# Run FastAPI server on port 8000
python -m uvicorn backend.main:app --reload --port 8000
```
Open your browser at:
`http://localhost:8000`

### Running the Automated Tests
```powershell
$env:PYTHONPATH="."
python -m unittest discover tests
```
*Result: 11 tests passed in ~0.9s.*

---

## 4. Google Sheets & Apps Script Setup Guide

Follow these beginner-friendly steps to deploy the central database in Google Workspace:

### Step 1: Create the Google Sheet
1. Open [Google Drive](https://drive.google.com).
2. Drag and drop `Institute_Asset_Management_Template.xlsx` into Google Drive.
3. Double-click the uploaded file and click **File > Save as Google Sheets**.
4. You will see all 6 master tabs pre-created with formatting and headers:
   - `Students_Master`
   - `Staff_Master`
   - `Laptop_Master`
   - `Accessories_Master`
   - `Movement_Log`
   - `Repair_Log`

*(Alternatively, if creating a fresh blank Google Sheet: Click **Extensions > Apps Script**, paste `google_apps_script/SetupSheet.gs`, and run `setupSpreadsheet()`)*

### Step 2: Deploy Google Apps Script Web App
1. In your Google Sheet, click **Extensions > Apps Script**.
2. Delete any existing code in `Code.gs` and paste the contents of `google_apps_script/Code.gs`.
3. In the left panel, click **Project Settings** (gear icon) and check **"Show 'appsscript.json' manifest file in editor"**.
4. Switch back to the editor, open `appsscript.json`, and replace its content with `google_apps_script/appsscript.json` (sets timezone to `Asia/Kolkata`).
5. Click **Deploy > New Deployment**:
   - Select type: **Web app**
   - Description: `TechLab Asset Management API v1`
   - Execute as: **Me (your Google account)**
   - Who has access: **Anyone** (or "Anyone within your Google Workspace organisation")
6. Click **Deploy**, authorize permissions when prompted, and copy the **Web App URL**.

---

## 5. Security & Authentication Architecture

1. **Backend Enforced RBAC**:
   - `Admin`: Full permissions (add staff, edit masters, batch transfer, traceable corrections).
   - `Staff`: Validated against `Staff_Master`. Only staff with `Can_Issue_Return = True` can issue/return. Only staff with `Can_Manage_Repairs = True` can dispatch repairs.
   - `Student`: Read-only self-service access. Can view only their own assigned laptop/charger. Can submit receipt acknowledgements. **Cannot view other students' personal data or Gmail addresses.**
2. **No Hardcoded Secrets**:
   - No OAuth secrets or API keys are embedded in frontend code. Identity is validated via Google Sign-In ID tokens or Institute-authenticated email sessions.
3. **Traceable Audit Log**:
   - Every movement generates an immutable row in `Movement_Log`. No silent updates or overwrites. Historical batches are frozen in `Batch_At_Transaction`.

---

## 6. AppSheet Workflow Integration (Optional)

If your institute uses AppSheet on mobile devices:
1. In Google Sheets, click **Extensions > AppSheet > Create an App**.
2. AppSheet will automatically detect `Laptop_Master`, `Students_Master`, and `Movement_Log`.
3. In AppSheet Table Settings:
   - Set `Laptop_Master[Status]` as Enum: `Available`, `Issued`, `Under Repair`.
   - Set `Movement_Log[Event_Timestamp]` initial value to `=NOW()` with time zone `Asia/Kolkata`.
4. Create Actions:
   - **Quick Issue**: Sets `Status = Issued`, logs row in `Movement_Log`.
   - **Quick Return**: Sets `Status = Available`, logs row in `Movement_Log`.

---

## 7. Action Checklist for the Institute Admin

| Task | Status | Instructions |
|---|---|---|
| Upload Excel Template to Google Sheets | User Action | Upload `Institute_Asset_Management_Template.xlsx` to Google Drive and convert to Google Sheets. |
| Deploy Apps Script | User Action | Paste `Code.gs` and `appsscript.json` into Apps Script editor and click Deploy. |
| Add Real Institute Staff & Students | User Action | Replace sample names in `Staff_Master` with your institute's actual trainers and lab assistants. |
| Print Physical QR Stickers | Ready | Open `http://localhost:8000/static/printable_qr_tags.html` and print labels on sticker paper. |
| Stick QR Labels on Hardware | User Action | Stick Laptop QR stickers on laptop bottom chassis; stick Charger QR stickers on power adapter bricks. |
