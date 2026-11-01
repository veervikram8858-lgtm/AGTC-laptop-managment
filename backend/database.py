"""
Database layer for Institute Laptop Management System.
Uses SQLite for local reliable storage mirroring Google Sheets structure,
with automatic export to Excel/Google Sheets compatible format.
"""

import sqlite3
import os
import threading
from typing import Dict, Any, List, Optional
import openpyxl

DB_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "institute_assets.db")
EXCEL_TEMPLATE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Institute_Asset_Management_Template.xlsx")

db_lock = threading.Lock()

def get_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db_lock:
        conn = get_connection()
        cursor = conn.cursor()

        # 1. Students_Master
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Students_Master (
            Student_ID TEXT PRIMARY KEY,
            Student_Name TEXT NOT NULL,
            Registered_Gmail TEXT,
            Course_Name TEXT NOT NULL,
            Batch_Name TEXT NOT NULL,
            Active INTEGER DEFAULT 1,
            Student_QR_Value TEXT NOT NULL,
            Notes TEXT
        )
        """)

        # 2. Staff_Master
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Staff_Master (
            Staff_ID TEXT PRIMARY KEY,
            Staff_Name TEXT NOT NULL,
            Official_Gmail TEXT NOT NULL UNIQUE,
            Role TEXT NOT NULL,
            Can_Issue_Return INTEGER DEFAULT 1,
            Can_Manage_Repairs INTEGER DEFAULT 0,
            Active INTEGER DEFAULT 1,
            Staff_QR_Value TEXT NOT NULL,
            Notes TEXT
        )
        """)

        # 3. Laptop_Master
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Laptop_Master (
            Laptop_ID TEXT PRIMARY KEY,
            Asset_Tag TEXT NOT NULL UNIQUE,
            Serial_Number TEXT NOT NULL UNIQUE,
            Brand TEXT NOT NULL,
            Model TEXT NOT NULL,
            Purchase_Date TEXT NOT NULL,
            Condition TEXT DEFAULT 'Good',
            Status TEXT DEFAULT 'Available',
            Current_Holder_Type TEXT DEFAULT 'None',
            Current_Holder_ID TEXT DEFAULT '',
            Current_Holder_Email TEXT DEFAULT '',
            Current_Location TEXT DEFAULT 'Lab 1 Cabinet A',
            QR_Value TEXT NOT NULL,
            Notes TEXT
        )
        """)

        # 4. Accessories_Master
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Accessories_Master (
            Accessory_ID TEXT PRIMARY KEY,
            Asset_Type TEXT DEFAULT 'Charger',
            Serial_Number TEXT NOT NULL UNIQUE,
            Specification TEXT NOT NULL,
            Condition TEXT DEFAULT 'Good',
            Status TEXT DEFAULT 'Available',
            Current_Holder_Type TEXT DEFAULT 'None',
            Current_Holder_ID TEXT DEFAULT '',
            Current_Location TEXT DEFAULT 'Lab 1 Charger Rack',
            QR_Value TEXT NOT NULL,
            Notes TEXT
        )
        """)

        # 5. Movement_Log
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Movement_Log (
            Movement_ID TEXT PRIMARY KEY,
            Person_Type TEXT NOT NULL,
            Person_ID TEXT NOT NULL,
            Person_Name_At_Transaction TEXT NOT NULL,
            Person_Email TEXT NOT NULL,
            Course_At_Transaction TEXT NOT NULL,
            Batch_At_Transaction TEXT NOT NULL,
            Asset_Type TEXT NOT NULL,
            Asset_ID TEXT NOT NULL,
            Action TEXT NOT NULL,
            Operator_Staff_Email TEXT NOT NULL,
            Event_Timestamp TEXT NOT NULL,
            From_Location TEXT NOT NULL,
            To_Location TEXT NOT NULL,
            Purpose TEXT NOT NULL,
            Condition_Out TEXT,
            Condition_In TEXT,
            Acknowledgement_Status TEXT DEFAULT 'PENDING',
            Acknowledged_By_Email TEXT,
            Acknowledged_At TEXT,
            Related_Repair_ID TEXT,
            Notes TEXT
        )
        """)

        # 6. Repair_Log
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Repair_Log (
            Repair_ID TEXT PRIMARY KEY,
            Asset_Type TEXT NOT NULL,
            Asset_ID TEXT NOT NULL,
            Taken_By_Staff_ID TEXT NOT NULL,
            Taken_By_Staff_Email TEXT NOT NULL,
            Repair_Reason TEXT NOT NULL,
            Service_Centre TEXT NOT NULL,
            Technician TEXT NOT NULL,
            Out_Timestamp TEXT NOT NULL,
            Expected_Return TEXT,
            Actual_Return_Timestamp TEXT,
            Repair_Status TEXT DEFAULT 'SENT_TO_CENTRE',
            Estimated_Cost REAL DEFAULT 0.0,
            Final_Cost REAL DEFAULT 0.0,
            Receipt_or_JobSheet_Link TEXT,
            Condition_Before TEXT DEFAULT 'Damaged',
            Condition_After TEXT,
            Acknowledgement_Status TEXT DEFAULT 'ACKNOWLEDGED',
            Notes TEXT
        )
        """)

        conn.commit()

        # Seed sample data if empty
        cursor.execute("SELECT COUNT(*) FROM Laptop_Master")
        if cursor.fetchone()[0] == 0:
            seed_sample_data(conn)

        # Ensure all Morning & Evening batch students are seeded (email initially empty/pending)
        seed_batch_students(conn)

        conn.close()

def seed_batch_students(conn):
    cursor = conn.cursor()
    # 18 Morning Batch students
    morning_students = [
        ("STU-MOR-01", "Akhil", "", "Computer Training", "Morning Batch", 1, "QR-STU-MOR-01", "Morning Batch"),
        ("STU-MOR-02", "Harsh", "", "Computer Training", "Morning Batch", 1, "QR-STU-MOR-02", "Morning Batch"),
        ("STU-MOR-03", "Nikita", "", "Computer Training", "Morning Batch", 1, "QR-STU-MOR-03", "Morning Batch"),
        ("STU-MOR-04", "Osama", "", "Computer Training", "Morning Batch", 1, "QR-STU-MOR-04", "Morning Batch"),
        ("STU-MOR-05", "Harshit (Morning)", "", "Computer Training", "Morning Batch", 1, "QR-STU-MOR-05", "Morning Batch"),
        ("STU-MOR-06", "Omprakash", "", "Computer Training", "Morning Batch", 1, "QR-STU-MOR-06", "Morning Batch"),
        ("STU-MOR-07", "Anushtha", "", "Computer Training", "Morning Batch", 1, "QR-STU-MOR-07", "Morning Batch"),
        ("STU-MOR-08", "Deepika", "", "Computer Training", "Morning Batch", 1, "QR-STU-MOR-08", "Morning Batch"),
        ("STU-MOR-09", "Aryan", "", "Computer Training", "Morning Batch", 1, "QR-STU-MOR-09", "Morning Batch"),
        ("STU-MOR-10", "Ankit", "", "Computer Training", "Morning Batch", 1, "QR-STU-MOR-10", "Morning Batch"),
        ("STU-MOR-11", "Adarsh", "", "Computer Training", "Morning Batch", 1, "QR-STU-MOR-11", "Morning Batch"),
        ("STU-MOR-12", "Tanisha", "", "Computer Training", "Morning Batch", 1, "QR-STU-MOR-12", "Morning Batch"),
        ("STU-MOR-13", "Abhijeet", "", "Computer Training", "Morning Batch", 1, "QR-STU-MOR-13", "Morning Batch"),
        ("STU-MOR-14", "Roshni", "", "Computer Training", "Morning Batch", 1, "QR-STU-MOR-14", "Morning Batch"),
        ("STU-MOR-15", "Mustafa", "", "Computer Training", "Morning Batch", 1, "QR-STU-MOR-15", "Morning Batch"),
        ("STU-MOR-16", "Ambuj", "", "Computer Training", "Morning Batch", 1, "QR-STU-MOR-16", "Morning Batch"),
        ("STU-MOR-17", "Vibhor", "", "Computer Training", "Morning Batch", 1, "QR-STU-MOR-17", "Morning Batch"),
        ("STU-MOR-18", "Saurabh", "", "Computer Training", "Morning Batch", 1, "QR-STU-MOR-18", "Morning Batch"),
    ]

    # 12 Evening Batch students
    evening_students = [
        ("STU-EVE-01", "Nidhi", "", "Computer Training", "Evening Batch", 1, "QR-STU-EVE-01", "Evening Batch"),
        ("STU-EVE-02", "Neha", "", "Computer Training", "Evening Batch", 1, "QR-STU-EVE-02", "Evening Batch"),
        ("STU-EVE-03", "Juhi", "", "Computer Training", "Evening Batch", 1, "QR-STU-EVE-03", "Evening Batch"),
        ("STU-EVE-04", "Warisha", "", "Computer Training", "Evening Batch", 1, "QR-STU-EVE-04", "Evening Batch"),
        ("STU-EVE-05", "Arushi", "", "Computer Training", "Evening Batch", 1, "QR-STU-EVE-05", "Evening Batch"),
        ("STU-EVE-06", "Ayush", "", "Computer Training", "Evening Batch", 1, "QR-STU-EVE-06", "Evening Batch"),
        ("STU-EVE-07", "Anshu", "", "Computer Training", "Evening Batch", 1, "QR-STU-EVE-07", "Evening Batch"),
        ("STU-EVE-08", "Himanshu", "", "Computer Training", "Evening Batch", 1, "QR-STU-EVE-08", "Evening Batch"),
        ("STU-EVE-09", "Abhishek", "", "Computer Training", "Evening Batch", 1, "QR-STU-EVE-09", "Evening Batch"),
        ("STU-EVE-10", "Anmol", "", "Computer Training", "Evening Batch", 1, "QR-STU-EVE-10", "Evening Batch"),
        ("STU-EVE-11", "Pankaj", "", "Computer Training", "Evening Batch", 1, "QR-STU-EVE-11", "Evening Batch"),
        ("STU-EVE-12", "Harshit (Evening)", "", "Computer Training", "Evening Batch", 1, "QR-STU-EVE-12", "Evening Batch"),
    ]

    for s in morning_students + evening_students:
        cursor.execute("""
            INSERT OR IGNORE INTO Students_Master (
                Student_ID, Student_Name, Registered_Gmail, Course_Name, Batch_Name, Active, Student_QR_Value, Notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, s)
    conn.commit()

def seed_sample_data(conn):
    cursor = conn.cursor()

    # Students
    students = [
        ("STU-1001", "Aarav Sharma [SAMPLE]", "aarav.sharma.sample@gmail.com", "Full Stack Web Dev", "Morning Batch", 1, "QR-STU-1001", "Identity verified via Aadhaar copy"),
        ("STU-1002", "Priya Patel [SAMPLE]", "priya.patel.sample@gmail.com", "Data Science & Python", "Morning Batch", 1, "QR-STU-1002", "Needs high RAM laptop for ML"),
        ("STU-1003", "Rohan Verma [SAMPLE]", "rohan.verma.sample@gmail.com", "Cloud Computing & DevOps", "Weekend Batch", 1, "QR-STU-1003", "Transferred from morning batch"),
        ("STU-1004", "Ananya Iyer [SAMPLE]", "ananya.iyer.sample@gmail.com", "Full Stack Web Dev", "Evening Batch", 1, "QR-STU-1004", "Active student"),
        ("STU-1005", "Kabir Singh [SAMPLE]", "kabir.singh.sample@gmail.com", "UI/UX Design", "Weekend Batch", 1, "QR-STU-1005", "Has personal stylus")
    ]
    cursor.executemany("INSERT OR IGNORE INTO Students_Master VALUES (?, ?, ?, ?, ?, ?, ?, ?)", students)

    # Staff
    staff = [
        ("STAFF-01", "Director Vikram Rao [SAMPLE]", "director.vikram@sample-institute.in", "Admin", 1, 1, 1, "QR-STAFF-01", "Super Admin & Institute Head"),
        ("STAFF-02", "Sunita Nair (Lab Incharge) [SAMPLE]", "sunita.lab@sample-institute.in", "Staff", 1, 1, 1, "QR-STAFF-02", "Authorized for inventory & repair dispatch"),
        ("STAFF-03", "Deepak Joshi (Lab Assistant) [SAMPLE]", "deepak.lab@sample-institute.in", "Staff", 1, 0, 1, "QR-STAFF-03", "Daily counter issue/return assistant"),
        ("STAFF-04", "Neha Gupta (Trainer) [SAMPLE]", "neha.trainer@sample-institute.in", "Staff", 0, 0, 1, "QR-STAFF-04", "Instructor only, no inventory issuance permission")
    ]
    cursor.executemany("INSERT INTO Staff_Master VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", staff)

    # Laptops (6 initial laptops)
    laptops = [
        ("LAP-001", "TAG-LEN-01", "PF2K9901", "Lenovo", "ThinkPad L14 Gen 3", "2024-03-15", "Good", "Available", "None", "", "", "Lab 1 Cabinet A", "QR-LAP-001", "Intel Core i5-1235U, 16GB RAM, 512GB SSD"),
        ("LAP-002", "TAG-LEN-02", "PF2K9902", "Lenovo", "ThinkPad L14 Gen 3", "2024-03-15", "Good", "Issued", "Student", "STU-1001", "aarav.sharma.sample@gmail.com", "Student Custody (Lab Session)", "QR-LAP-002", "Issued with paired charger CHG-002"),
        ("LAP-003", "TAG-DEL-01", "DL74001A", "Dell", "Latitude 3420", "2024-05-10", "Good", "Available", "None", "", "", "Lab 1 Cabinet A", "QR-LAP-003", "Intel Core i5-1135G7, 16GB RAM, 256GB SSD"),
        ("LAP-004", "TAG-DEL-02", "DL74002B", "Dell", "Latitude 3420", "2024-05-10", "Fair", "Under Repair", "Service_Centre", "REP-2026-001", "", "Authorized Dell Centre, Nehru Place", "QR-LAP-004", "Trackpad replacement pending"),
        ("LAP-005", "TAG-HP-01", "HPPB440G1", "HP", "ProBook 440 G8", "2024-07-01", "Good", "Available", "None", "", "", "Lab 2 Shelf B", "QR-LAP-005", "Intel Core i5, 16GB RAM"),
        ("LAP-006", "TAG-HP-02", "HPPB440G2", "HP", "ProBook 440 G8", "2024-07-01", "Good", "Issued", "Staff", "STAFF-02", "sunita.lab@sample-institute.in", "Instructor Desk Lab 2", "QR-LAP-006", "Assigned for Lab demonstration")
    ]
    cursor.executemany("INSERT INTO Laptop_Master VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", laptops)

    # Accessories
    accessories = [
        ("CHG-001", "Charger", "CHG-LN-65-01", "Lenovo 65W USB-C Original Adapter", "Good", "Available", "None", "", "Lab 1 Charger Rack", "QR-CHG-001", "Paired default for LAP-001"),
        ("CHG-002", "Charger", "CHG-LN-65-02", "Lenovo 65W USB-C Original Adapter", "Good", "Issued", "Student", "STU-1001", "With Student STU-1001", "QR-CHG-002", "Issued alongside LAP-002"),
        ("CHG-003", "Charger", "CHG-DL-65-01", "Dell 65W Barrel 4.5mm Adapter", "Good", "Available", "None", "", "Lab 1 Charger Rack", "QR-CHG-003", "Paired default for LAP-003"),
        ("CHG-004", "Charger", "CHG-DL-65-02", "Dell 65W Barrel 4.5mm Adapter", "Damaged", "Under Repair", "Service_Centre", "REP-2026-001", "Dell Service Nehru Place", "QR-CHG-004", "Cable frayed at connector"),
        ("CHG-005", "Charger", "CHG-HP-45-01", "HP 45W Smart Blue Pin Adapter", "Good", "Available", "None", "", "Lab 2 Shelf B", "QR-CHG-005", "Paired default for LAP-005"),
        ("CHG-006", "Charger", "CHG-HP-45-02", "HP 45W Smart Blue Pin Adapter", "Good", "Issued", "Staff", "STAFF-02", "Instructor Desk Lab 2", "QR-CHG-006", "Issued alongside LAP-006")
    ]
    cursor.executemany("INSERT INTO Accessories_Master VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", accessories)

    # Movement Log
    movements = [
        (
            "MOV-2026-0001", "Student", "STU-1001", "Aarav Sharma [SAMPLE]",
            "aarav.sharma.sample@gmail.com", "Full Stack Web Dev", "BATCH-2026-MORNING-A",
            "Laptop", "LAP-002", "ISSUE", "sunita.lab@sample-institute.in",
            "2026-10-26T10:00:00+05:30", "Lab 1 Cabinet A", "Student Custody", "Daily Lab Session",
            "Good", "", "ACKNOWLEDGED", "aarav.sharma.sample@gmail.com", "2026-10-26T10:02:15+05:30",
            "", "Issued with paired charger CHG-002. Student acknowledged in lab."
        ),
        (
            "MOV-2026-0002", "Student", "STU-1001", "Aarav Sharma [SAMPLE]",
            "aarav.sharma.sample@gmail.com", "Full Stack Web Dev", "BATCH-2026-MORNING-A",
            "Charger", "CHG-002", "ISSUE", "sunita.lab@sample-institute.in",
            "2026-10-26T10:00:00+05:30", "Lab 1 Charger Rack", "Student Custody", "Daily Lab Session",
            "Good", "", "ACKNOWLEDGED", "aarav.sharma.sample@gmail.com", "2026-10-26T10:02:15+05:30",
            "", "Charger issued bundled with LAP-002."
        ),
        (
            "MOV-2026-0003", "Staff", "STAFF-02", "Sunita Nair [SAMPLE]",
            "sunita.lab@sample-institute.in", "Faculty / Administration", "Staff",
            "Laptop", "LAP-006", "ISSUE", "director.vikram@sample-institute.in",
            "2026-10-26T09:30:00+05:30", "Lab 2 Shelf B", "Instructor Desk Lab 2", "Lab Demonstration",
            "Good", "", "ACKNOWLEDGED", "sunita.lab@sample-institute.in", "2026-10-26T09:31:00+05:30",
            "", "Semester curriculum setup."
        )
    ]
    cursor.executemany("INSERT INTO Movement_Log VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", movements)

    # Repairs
    repairs = [
        (
            "REP-2026-001", "Laptop", "LAP-004", "STAFF-02", "sunita.lab@sample-institute.in",
            "Intermittent trackpad click failure and loose left hinge", "Authorized Dell Service Centre, Nehru Place, New Delhi", "Ramesh Kumar (Desk 4)",
            "2026-10-24T14:15:00+05:30", "2026-10-28", "", "SENT_TO_CENTRE",
            2200.0, 0.0, "https://drive.google.com/sample_jobsheet_dell_rep001.pdf",
            "Fair - trackpad sticky", "", "ACKNOWLEDGED", "Estimated turnaround time 4 days. Under warranty inspection."
        )
    ]
    cursor.executemany("INSERT INTO Repair_Log VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", repairs)

    conn.commit()

def sync_to_excel():
    """Exports SQLite tables to Excel format matching Google Sheets tabs."""
    try:
        from tools.generate_sheets_excel import create_template
        # The template generator can refresh directly or we can export current SQLite data
        conn = get_connection()
        wb = openpyxl.Workbook()
        wb.remove(wb.active)

        tables = ["Students_Master", "Staff_Master", "Laptop_Master", "Accessories_Master", "Movement_Log", "Repair_Log"]
        for tbl in tables:
            ws = wb.create_sheet(title=tbl)
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({tbl})")
            headers = [col[1] for col in cursor.fetchall()]
            ws.append(headers)

            cursor.execute(f"SELECT * FROM {tbl}")
            for row in cursor.fetchall():
                ws.append(list(row))

        wb.save(EXCEL_TEMPLATE)
        conn.close()
    except Exception as e:
        print(f"Excel sync notice: {e}")
