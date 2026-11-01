"""
Automated Test Suite for Institute Laptop, Charger, Student, Staff,
Issue/Return, and Repair Management System.
Tests: Issue, Return, Repair, RBAC, Duplicate ID prevention, Batch Transfer, and Student Ack.
"""

import unittest
import os
import sqlite3
from fastapi.testclient import TestClient

# Ensure test DB is isolated or reset for testing
os.environ["TESTING"] = "true"
from backend.main import app, active_demo_email
from backend.database import init_db, get_connection, DB_FILE
from backend.models import (
    FastIssueRequest, FastReturnRequest, SendToRepairRequest,
    ReturnFromRepairRequest, BatchTransferRequest, StudentAckRequest,
    AddStudentRequest
)
from backend.auth import CurrentUser
from backend.service import AssetService, get_now_kolkata

class TestInstituteAssetManager(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

    def setUp(self):
        # Set session user to Admin by default
        self.client.post("/api/auth/switch-demo-role?email=director.vikram@sample-institute.in")

    def test_01_kolkata_timezone_format(self):
        """Test timestamp is formatted in Asia/Kolkata +05:30 offset."""
        ts = get_now_kolkata()
        self.assertTrue(ts.endswith("+05:30"), f"Expected Asia/Kolkata offset +05:30, got {ts}")

    def test_02_duplicate_student_id_prevention(self):
        """Test that system strictly prevents duplicate Student_IDs."""
        admin = CurrentUser(email="director.vikram@sample-institute.in", role="Admin", id_="STAFF-01", name="Admin")
        
        # Add a student
        req1 = AddStudentRequest(
            student_id="STU-TEST-999",
            student_name="Test Student One",
            registered_gmail="test.student.999@gmail.com",
            course_name="Web Dev",
            batch_name="BATCH-A"
        )
        res1 = AssetService.add_student(req1, admin)
        self.assertTrue(res1["success"])

        # Try to add another student with same Student_ID -> Must fail
        req2 = AddStudentRequest(
            student_id="STU-TEST-999",
            student_name="Duplicate Student",
            registered_gmail="duplicate.student@gmail.com",
            course_name="Data Science",
            batch_name="BATCH-B"
        )
        with self.assertRaises(Exception) as cm:
            AssetService.add_student(req2, admin)
        self.assertIn("already exists", str(cm.exception.detail))

    def test_03_fast_issue_workflow(self):
        """Test fast staff-operated issue workflow for laptop + paired charger."""
        staff = CurrentUser(
            email="sunita.lab@sample-institute.in",
            role="Staff",
            id_="STAFF-02",
            name="Sunita Nair",
            can_issue_return=True
        )

        issue_req = FastIssueRequest(
            person_type="Student",
            person_id="STU-1002", # Priya Patel
            laptop_id="LAP-001",
            include_charger=True,
            charger_id="CHG-001",
            purpose="Daily Lab Session",
            condition_out="Good"
        )

        result = AssetService.fast_issue(issue_req, staff)
        self.assertTrue(result["success"])
        self.assertEqual(result["laptop_id"], "LAP-001")
        self.assertEqual(result["charger_id"], "CHG-001")
        self.assertEqual(result["status"], "Issued")
        self.assertEqual(result["acknowledgement_status"], "PENDING")

        # Verify in DB
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT Status, Current_Holder_ID FROM Laptop_Master WHERE Laptop_ID = 'LAP-001'")
        lap = c.fetchone()
        self.assertEqual(lap["Status"], "Issued")
        self.assertEqual(lap["Current_Holder_ID"], "STU-1002")

        c.execute("SELECT Status FROM Accessories_Master WHERE Accessory_ID = 'CHG-001'")
        chg = c.fetchone()
        self.assertEqual(chg["Status"], "Issued")
        conn.close()

    def test_04_prevent_issuing_already_issued_device(self):
        """Test cannot issue a device that is already issued."""
        staff = CurrentUser(email="sunita.lab@sample-institute.in", role="Staff", id_="STAFF-02", name="Sunita", can_issue_return=True)
        issue_req = FastIssueRequest(
            person_type="Student",
            person_id="STU-1003",
            laptop_id="LAP-001", # Already issued in test_03
            include_charger=False
        )
        with self.assertRaises(Exception) as cm:
            AssetService.fast_issue(issue_req, staff)
        self.assertIn("ALREADY ISSUED", str(cm.exception.detail))

    def test_05_fast_return_workflow(self):
        """Test returning an issued laptop + paired charger back to Available."""
        staff = CurrentUser(email="sunita.lab@sample-institute.in", role="Staff", id_="STAFF-02", name="Sunita", can_issue_return=True)
        return_req = FastReturnRequest(
            laptop_id="LAP-001",
            condition_in="Good",
            to_location="Lab 1 Cabinet A",
            include_charger=True,
            charger_id="CHG-001"
        )
        result = AssetService.fast_return(return_req, staff)
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "Available")

        # Verify DB
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT Status, Current_Holder_Type FROM Laptop_Master WHERE Laptop_ID = 'LAP-001'")
        lap = c.fetchone()
        self.assertEqual(lap["Status"], "Available")
        self.assertEqual(lap["Current_Holder_Type"], "None")

        c.execute("SELECT Status FROM Accessories_Master WHERE Accessory_ID = 'CHG-001'")
        chg = c.fetchone()
        self.assertEqual(chg["Status"], "Available")
        conn.close()

    def test_06_prevent_returning_unissued_device(self):
        """Test cannot return a device that is already Available."""
        staff = CurrentUser(email="sunita.lab@sample-institute.in", role="Staff", id_="STAFF-02", name="Sunita", can_issue_return=True)
        return_req = FastReturnRequest(laptop_id="LAP-001") # Now Available
        with self.assertRaises(Exception) as cm:
            AssetService.fast_return(return_req, staff)
        self.assertIn("Cannot return", str(cm.exception.detail))

    def test_07_repair_workflow_and_under_repair_protection(self):
        """Test sending device for repair, blocking issuance, and completing repair."""
        repair_mgr = CurrentUser(
            email="sunita.lab@sample-institute.in",
            role="Staff",
            id_="STAFF-02",
            name="Sunita",
            can_issue_return=True,
            can_manage_repairs=True
        )

        # 1. Send LAP-003 to repair
        send_req = SendToRepairRequest(
            asset_type="Laptop",
            asset_id="LAP-003",
            repair_reason="Screen flickering and battery health degraded",
            service_centre="Dell Authorized Service, Okhla",
            technician="Mr. Sharma",
            expected_return="2026-10-30",
            estimated_cost=3500.0,
            condition_before="Fair"
        )
        repair_res = AssetService.send_to_repair(send_req, repair_mgr)
        self.assertTrue(repair_res["success"])
        repair_id = repair_res["repair_id"]

        # 2. Verify status is Under Repair
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT Status FROM Laptop_Master WHERE Laptop_ID = 'LAP-003'")
        self.assertEqual(c.fetchone()["Status"], "Under Repair")
        conn.close()

        # 3. Verify that issuing LAP-003 is strictly blocked while Under Repair
        issue_req = FastIssueRequest(
            person_type="Student",
            person_id="STU-1002",
            laptop_id="LAP-003"
        )
        with self.assertRaises(Exception) as cm:
            AssetService.fast_issue(issue_req, repair_mgr)
        self.assertIn("UNDER REPAIR", str(cm.exception.detail))

        # 4. Return from Repair
        ret_req = ReturnFromRepairRequest(
            repair_id=repair_id,
            final_cost=3400.0,
            condition_after="Excellent",
            to_location="Lab 1 Cabinet A",
            receipt_or_jobsheet_link="https://drive.google.com/sample_dell_jobsheet_lap003.pdf",
            notes="Screen replaced and new genuine battery installed under warranty"
        )
        ret_res = AssetService.return_from_repair(ret_req, repair_mgr)
        self.assertTrue(ret_res["success"])
        self.assertEqual(ret_res["status"], "Available")
        self.assertEqual(ret_res["final_cost"], 3400.0)

        # Verify in DB that status returned to Available
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT Status, Condition FROM Laptop_Master WHERE Laptop_ID = 'LAP-003'")
        lap = c.fetchone()
        self.assertEqual(lap["Status"], "Available")
        self.assertEqual(lap["Condition"], "Excellent")
        conn.close()

    def test_08_rbac_privilege_enforcement(self):
        """Test that unauthorized staff cannot issue/return or manage repairs."""
        # Neha Gupta (Trainer): Can_Issue_Return = False, Can_Manage_Repairs = False
        self.client.post("/api/auth/switch-demo-role?email=neha.trainer@sample-institute.in")

        # Try to issue asset
        resp_issue = self.client.post("/api/movement/issue", json={
            "person_type": "Student",
            "person_id": "STU-1002",
            "laptop_id": "LAP-005"
        })
        self.assertEqual(resp_issue.status_code, 403)
        self.assertIn("Can_Issue_Return", resp_issue.json()["detail"])

        # Try to send repair
        resp_repair = self.client.post("/api/repairs", json={
            "asset_type": "Laptop",
            "asset_id": "LAP-005",
            "repair_reason": "Broken key",
            "service_centre": "HP Care"
        })
        self.assertEqual(resp_repair.status_code, 403)
        self.assertIn("Can_Manage_Repairs", resp_repair.json()["detail"])

    def test_09_student_privacy_protection(self):
        """Test that student cannot view all students' master list or personal emails."""
        # Switch to Student Aarav Sharma
        self.client.post("/api/auth/switch-demo-role?email=aarav.sharma.sample@gmail.com")

        # Student tries to fetch Students_Master
        resp = self.client.get("/api/students")
        self.assertEqual(resp.status_code, 403)
        self.assertIn("forbidden", resp.json()["detail"].lower())

    def test_10_student_batch_transfer(self):
        """Test batch transfer retains permanent Student_ID while updating current batch."""
        admin = CurrentUser(email="director.vikram@sample-institute.in", role="Admin", id_="STAFF-01", name="Admin")
        
        req = BatchTransferRequest(
            student_id="STU-1001",
            new_batch="BATCH-2026-SPECIAL-AI",
            reason="Promoted to Special AI Batch"
        )
        res = AssetService.batch_transfer(req, admin)
        self.assertTrue(res["success"])
        self.assertEqual(res["student_id"], "STU-1001")
        self.assertEqual(res["new_batch"], "BATCH-2026-SPECIAL-AI")

        # Verify Student_ID did not change, but current batch updated
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT Student_ID, Batch_Name FROM Students_Master WHERE Student_ID = 'STU-1001'")
        s = c.fetchone()
        self.assertEqual(s["Student_ID"], "STU-1001")
        self.assertEqual(s["Batch_Name"], "BATCH-2026-SPECIAL-AI")
        conn.close()

    def test_11_student_acknowledgement(self):
        """Test student acknowledging their assigned transaction."""
        # Find a movement log with PENDING status for Aarav Sharma
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT Movement_ID, Person_Email FROM Movement_Log WHERE Person_Email = 'aarav.sharma.sample@gmail.com' LIMIT 1")
        mov = c.fetchone()
        conn.close()

        if mov:
            mov_id = mov["Movement_ID"]
            # Other student tries to acknowledge -> Forbidden
            wrong_student = CurrentUser(email="priya.patel.sample@gmail.com", role="Student", id_="STU-1002", name="Priya")
            with self.assertRaises(Exception) as cm:
                AssetService.student_acknowledge(mov_id, wrong_student)
            self.assertIn("Unauthorized", str(cm.exception.detail))

            # Correct student acknowledges
            correct_student = CurrentUser(email="aarav.sharma.sample@gmail.com", role="Student", id_="STU-1001", name="Aarav")
            ack_res = AssetService.student_acknowledge(mov_id, correct_student)
            self.assertTrue(ack_res["success"])
            self.assertEqual(ack_res["status"], "ACKNOWLEDGED")

if __name__ == "__main__":
    unittest.main()
