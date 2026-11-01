"""
Service layer containing core business rules, validation, fast issue/return workflows,
repair management, batch transfers, student acknowledgement, and dashboard reporting.
All timestamps formatted in Asia/Kolkata timezone.
"""

from datetime import datetime
import zoneinfo
import random
from typing import Dict, Any, List, Optional
from fastapi import HTTPException, status
from backend.database import get_connection, db_lock, sync_to_excel
from backend.models import (
    FastIssueRequest, FastReturnRequest, SendToRepairRequest,
    ReturnFromRepairRequest, BatchTransferRequest, StudentAckRequest,
    AddStudentRequest, AddLaptopRequest, AddAccessoryRequest
)
from backend.auth import CurrentUser

KOLKATA_TZ = zoneinfo.ZoneInfo("Asia/Kolkata")

def get_now_kolkata() -> str:
    """Returns current timestamp in Asia/Kolkata ISO 8601 format."""
    return datetime.now(KOLKATA_TZ).strftime("%Y-%m-%dT%H:%M:%S+05:30")

def get_today_kolkata() -> str:
    return datetime.now(KOLKATA_TZ).strftime("%Y-%m-%d")

def generate_id(prefix: str) -> str:
    now_str = datetime.now(KOLKATA_TZ).strftime("%Y%m%d-%H%M%S")
    rand = random.randint(1000, 9999)
    return f"{prefix}-{now_str}-{rand}"

class AssetService:

    @staticmethod
    def fast_issue(req: FastIssueRequest, operator: CurrentUser) -> Dict[str, Any]:
        """
        Fast staff-operated issue workflow (Target: 2-3 seconds).
        Validates person, laptop, optional charger, updates masters, logs transaction.
        """
        laptop_id = req.laptop_id.strip()
        person_id = req.person_id.strip()

        if not laptop_id or not person_id:
            raise HTTPException(status_code=400, detail="Both Laptop ID and Person ID are required.")

        with db_lock:
            conn = get_connection()
            cursor = conn.cursor()

            # 1. Validate Person (Student or Staff)
            person_name = ""
            person_email = ""
            course_at_tx = ""
            batch_at_tx = ""

            if req.person_type == "Student":
                cursor.execute(
                    "SELECT * FROM Students_Master WHERE Student_ID = ? OR Student_QR_Value = ?",
                    (person_id, person_id)
                )
                student = cursor.fetchone()
                if not student:
                    conn.close()
                    raise HTTPException(status_code=404, detail=f"Student ID / QR '{person_id}' not found.")
                if not student["Active"]:
                    conn.close()
                    raise HTTPException(status_code=400, detail=f"Student '{student['Student_Name']}' is INACTIVE.")

                person_id = student["Student_ID"]
                person_name = student["Student_Name"]
                person_email = student["Registered_Gmail"] or ""
                course_at_tx = student["Course_Name"]
                batch_at_tx = student["Batch_Name"]

                # Dynamically update student's Gmail if provided during issue
                if req.student_email and req.student_email.strip():
                    clean_email = req.student_email.strip().lower()
                    cursor.execute("UPDATE Students_Master SET Registered_Gmail = ? WHERE Student_ID = ?", (clean_email, person_id))
                    person_email = clean_email
            else:
                cursor.execute(
                    "SELECT * FROM Staff_Master WHERE Staff_ID = ? OR Staff_QR_Value = ?",
                    (person_id, person_id)
                )
                staff = cursor.fetchone()
                if not staff:
                    conn.close()
                    raise HTTPException(status_code=404, detail=f"Staff ID / QR '{person_id}' not found.")
                if not staff["Active"]:
                    conn.close()
                    raise HTTPException(status_code=400, detail=f"Staff '{staff['Staff_Name']}' is INACTIVE.")

                person_id = staff["Staff_ID"]
                person_name = staff["Staff_Name"]
                person_email = staff["Official_Gmail"]
                course_at_tx = "Faculty / Administration"
                batch_at_tx = "Staff"

            # 2. Validate Laptop
            cursor.execute(
                "SELECT * FROM Laptop_Master WHERE Laptop_ID = ? OR QR_Value = ?",
                (laptop_id, laptop_id)
            )
            laptop = cursor.fetchone()
            if not laptop:
                conn.close()
                raise HTTPException(status_code=404, detail=f"Laptop ID / QR '{laptop_id}' not found.")

            real_laptop_id = laptop["Laptop_ID"]
            current_status = laptop["Status"]

            if current_status == "Issued":
                conn.close()
                raise HTTPException(
                    status_code=400,
                    detail=f"Laptop '{real_laptop_id}' is ALREADY ISSUED to {laptop['Current_Holder_Type']} {laptop['Current_Holder_ID']}."
                )
            if current_status == "Under Repair":
                conn.close()
                raise HTTPException(
                    status_code=400,
                    detail=f"Laptop '{real_laptop_id}' is currently UNDER REPAIR and cannot be issued."
                )
            if current_status != "Available":
                conn.close()
                raise HTTPException(
                    status_code=400,
                    detail=f"Laptop '{real_laptop_id}' status is '{current_status}', must be 'Available' to issue."
                )

            from_location = laptop["Current_Location"]
            to_location = req.to_location or (f"Student Custody ({person_name})" if req.person_type == "Student" else f"Staff Custody ({person_name})")

            # 3. Resolve Charger if included
            charger_to_issue = None
            if req.include_charger:
                if req.charger_id:
                    cursor.execute(
                        "SELECT * FROM Accessories_Master WHERE (Accessory_ID = ? OR QR_Value = ?) AND Asset_Type = 'Charger'",
                        (req.charger_id.strip(), req.charger_id.strip())
                    )
                    charger_to_issue = cursor.fetchone()
                    if not charger_to_issue:
                        conn.close()
                        raise HTTPException(status_code=404, detail=f"Specified Charger '{req.charger_id}' not found.")
                    if charger_to_issue["Status"] != "Available":
                        conn.close()
                        raise HTTPException(status_code=400, detail=f"Charger '{charger_to_issue['Accessory_ID']}' is {charger_to_issue['Status']}, not Available.")
                else:
                    # Auto-pick available charger (prefer paired notes or any available)
                    cursor.execute(
                        "SELECT * FROM Accessories_Master WHERE Asset_Type = 'Charger' AND Status = 'Available' ORDER BY Accessory_ID ASC LIMIT 1"
                    )
                    charger_to_issue = cursor.fetchone()

            timestamp = get_now_kolkata()

            # Acknowledgement status determination
            if req.immediate_student_ack:
                ack_status = "ACKNOWLEDGED"
                ack_email = person_email
                ack_at = timestamp
            else:
                ack_status = "PENDING"
                ack_email = ""
                ack_at = ""

            # 4. Update Laptop_Master
            cursor.execute("""
                UPDATE Laptop_Master
                SET Status = 'Issued',
                    Condition = ?,
                    Current_Holder_Type = ?,
                    Current_Holder_ID = ?,
                    Current_Holder_Email = ?,
                    Current_Location = ?
                WHERE Laptop_ID = ?
            """, (req.condition_out, req.person_type, person_id, person_email, to_location, real_laptop_id))

            # 5. Insert Laptop Movement Log
            laptop_mov_id = generate_id("MOV")
            charger_info_note = f" Issued with charger {charger_to_issue['Accessory_ID']}." if charger_to_issue else ""
            cursor.execute("""
                INSERT INTO Movement_Log (
                    Movement_ID, Person_Type, Person_ID, Person_Name_At_Transaction,
                    Person_Email, Course_At_Transaction, Batch_At_Transaction,
                    Asset_Type, Asset_ID, Action, Operator_Staff_Email,
                    Event_Timestamp, From_Location, To_Location, Purpose,
                    Condition_Out, Condition_In, Acknowledgement_Status,
                    Acknowledged_By_Email, Acknowledged_At, Related_Repair_ID, Notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                laptop_mov_id, req.person_type, person_id, person_name,
                person_email, course_at_tx, batch_at_tx, "Laptop",
                real_laptop_id, "ISSUE", operator.email,
                timestamp, from_location, to_location, req.purpose,
                req.condition_out, "", ack_status,
                ack_email, ack_at, "", (req.notes + charger_info_note).strip()
            ))

            # 6. Update and Insert Charger if included
            charger_mov_id = None
            if charger_to_issue:
                chg_id = charger_to_issue["Accessory_ID"]
                cursor.execute("""
                    UPDATE Accessories_Master
                    SET Status = 'Issued',
                        Current_Holder_Type = ?,
                        Current_Holder_ID = ?,
                        Current_Location = ?
                    WHERE Accessory_ID = ?
                """, (req.person_type, person_id, to_location, chg_id))

                charger_mov_id = generate_id("MOV")
                cursor.execute("""
                    INSERT INTO Movement_Log (
                        Movement_ID, Person_Type, Person_ID, Person_Name_At_Transaction,
                        Person_Email, Course_At_Transaction, Batch_At_Transaction,
                        Asset_Type, Asset_ID, Action, Operator_Staff_Email,
                        Event_Timestamp, From_Location, To_Location, Purpose,
                        Condition_Out, Condition_In, Acknowledgement_Status,
                        Acknowledged_By_Email, Acknowledged_At, Related_Repair_ID, Notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    charger_mov_id, req.person_type, person_id, person_name,
                    person_email, course_at_tx, batch_at_tx, "Charger",
                    chg_id, "ISSUE", operator.email,
                    timestamp, charger_to_issue["Current_Location"], to_location, req.purpose,
                    req.condition_out, "", ack_status,
                    ack_email, ack_at, "", f"Issued bundled with Laptop {real_laptop_id}. {req.notes}".strip()
                ))

            conn.commit()
            conn.close()
            sync_to_excel()

            return {
                "success": True,
                "movement_id": laptop_mov_id,
                "laptop_id": real_laptop_id,
                "charger_id": charger_to_issue["Accessory_ID"] if charger_to_issue else None,
                "person_id": person_id,
                "person_name": person_name,
                "status": "Issued",
                "acknowledgement_status": ack_status,
                "timestamp": timestamp
            }

    @staticmethod
    def fast_return(req: FastReturnRequest, operator: CurrentUser) -> Dict[str, Any]:
        """
        Fast staff-operated return workflow.
        Validates laptop is currently Issued, returns laptop and paired charger to Available.
        """
        laptop_id = req.laptop_id.strip()
        if not laptop_id:
            raise HTTPException(status_code=400, detail="Laptop ID is required.")

        with db_lock:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM Laptop_Master WHERE Laptop_ID = ? OR QR_Value = ?",
                (laptop_id, laptop_id)
            )
            laptop = cursor.fetchone()
            if not laptop:
                conn.close()
                raise HTTPException(status_code=404, detail=f"Laptop '{laptop_id}' not found.")

            real_laptop_id = laptop["Laptop_ID"]
            if laptop["Status"] != "Issued":
                conn.close()
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot return Laptop '{real_laptop_id}': Device is currently '{laptop['Status']}', not 'Issued'."
                )

            prev_holder_type = laptop["Current_Holder_Type"]
            prev_holder_id = laptop["Current_Holder_ID"]
            prev_holder_email = laptop["Current_Holder_Email"]
            current_location = laptop["Current_Location"]

            # Lookup person info at return
            person_name = ""
            course_at_tx = ""
            batch_at_tx = ""

            if prev_holder_type == "Student":
                cursor.execute("SELECT * FROM Students_Master WHERE Student_ID = ?", (prev_holder_id,))
                s = cursor.fetchone()
                if s:
                    person_name = s["Student_Name"]
                    course_at_tx = s["Course_Name"]
                    batch_at_tx = s["Batch_Name"]
            elif prev_holder_type == "Staff":
                cursor.execute("SELECT * FROM Staff_Master WHERE Staff_ID = ?", (prev_holder_id,))
                st = cursor.fetchone()
                if st:
                    person_name = st["Staff_Name"]
                    course_at_tx = "Faculty / Administration"
                    batch_at_tx = "Staff"

            timestamp = get_now_kolkata()

            # 1. Update Laptop_Master to Available
            cursor.execute("""
                UPDATE Laptop_Master
                SET Status = 'Available',
                    Condition = ?,
                    Current_Holder_Type = 'None',
                    Current_Holder_ID = '',
                    Current_Holder_Email = '',
                    Current_Location = ?
                WHERE Laptop_ID = ?
            """, (req.condition_in, req.to_location, real_laptop_id))

            # 2. Append Laptop RETURN movement
            lap_mov_id = generate_id("MOV")
            cursor.execute("""
                INSERT INTO Movement_Log (
                    Movement_ID, Person_Type, Person_ID, Person_Name_At_Transaction,
                    Person_Email, Course_At_Transaction, Batch_At_Transaction,
                    Asset_Type, Asset_ID, Action, Operator_Staff_Email,
                    Event_Timestamp, From_Location, To_Location, Purpose,
                    Condition_Out, Condition_In, Acknowledgement_Status,
                    Acknowledged_By_Email, Acknowledged_At, Related_Repair_ID, Notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                lap_mov_id, prev_holder_type, prev_holder_id, person_name,
                prev_holder_email, course_at_tx, batch_at_tx, "Laptop",
                real_laptop_id, "RETURN", operator.email,
                timestamp, current_location, req.to_location, "Inventory Return",
                "", req.condition_in, "NOT_REQUIRED",
                "", "", "", req.notes
            ))

            # 3. Return Charger if requested or assigned to holder
            returned_charger_id = None
            if req.include_charger:
                if req.charger_id:
                    cursor.execute(
                        "SELECT * FROM Accessories_Master WHERE Accessory_ID = ? OR QR_Value = ?",
                        (req.charger_id.strip(), req.charger_id.strip())
                    )
                else:
                    cursor.execute(
                        "SELECT * FROM Accessories_Master WHERE Asset_Type = 'Charger' AND Status = 'Issued' AND Current_Holder_ID = ?",
                        (prev_holder_id,)
                    )
                charger = cursor.fetchone()
                if charger:
                    returned_charger_id = charger["Accessory_ID"]
                    cursor.execute("""
                        UPDATE Accessories_Master
                        SET Status = 'Available',
                            Condition = ?,
                            Current_Holder_Type = 'None',
                            Current_Holder_ID = '',
                            Current_Location = 'Lab 1 Charger Rack'
                        WHERE Accessory_ID = ?
                    """, (req.condition_in, returned_charger_id))

                    chg_mov_id = generate_id("MOV")
                    cursor.execute("""
                        INSERT INTO Movement_Log (
                            Movement_ID, Person_Type, Person_ID, Person_Name_At_Transaction,
                            Person_Email, Course_At_Transaction, Batch_At_Transaction,
                            Asset_Type, Asset_ID, Action, Operator_Staff_Email,
                            Event_Timestamp, From_Location, To_Location, Purpose,
                            Condition_Out, Condition_In, Acknowledgement_Status,
                            Acknowledged_By_Email, Acknowledged_At, Related_Repair_ID, Notes
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        chg_mov_id, prev_holder_type, prev_holder_id, person_name,
                        prev_holder_email, course_at_tx, batch_at_tx, "Charger",
                        returned_charger_id, "RETURN", operator.email,
                        timestamp, current_location, "Lab 1 Charger Rack", "Inventory Return",
                        "", req.condition_in, "NOT_REQUIRED",
                        "", "", "", f"Charger returned with Laptop {real_laptop_id}. {req.notes}".strip()
                    ))

            conn.commit()
            conn.close()
            sync_to_excel()

            return {
                "success": True,
                "movement_id": lap_mov_id,
                "laptop_id": real_laptop_id,
                "charger_id": returned_charger_id,
                "status": "Available",
                "timestamp": timestamp
            }

    @staticmethod
    def send_to_repair(req: SendToRepairRequest, operator: CurrentUser) -> Dict[str, Any]:
        """
        Sends a device for repair. Marks status as 'Under Repair' and records repair ticket.
        Prevents device from being issued while Under Repair.
        """
        asset_id = req.asset_id.strip()
        if not asset_id:
            raise HTTPException(status_code=400, detail="Asset ID is required.")

        with db_lock:
            conn = get_connection()
            cursor = conn.cursor()

            if req.asset_type == "Laptop":
                cursor.execute("SELECT * FROM Laptop_Master WHERE Laptop_ID = ?", (asset_id,))
                asset = cursor.fetchone()
                if not asset:
                    conn.close()
                    raise HTTPException(status_code=404, detail=f"Laptop '{asset_id}' not found.")
                if asset["Status"] == "Issued":
                    conn.close()
                    raise HTTPException(status_code=400, detail=f"Cannot send Laptop '{asset_id}' for repair while Issued. Return it first.")

                repair_id = generate_id("REP")
                cursor.execute("""
                    UPDATE Laptop_Master
                    SET Status = 'Under Repair',
                        Condition = ?,
                        Current_Holder_Type = 'Service_Centre',
                        Current_Holder_ID = ?,
                        Current_Holder_Email = '',
                        Current_Location = ?
                    WHERE Laptop_ID = ?
                """, (req.condition_before, repair_id, req.service_centre, asset_id))
            else:
                cursor.execute("SELECT * FROM Accessories_Master WHERE Accessory_ID = ?", (asset_id,))
                asset = cursor.fetchone()
                if not asset:
                    conn.close()
                    raise HTTPException(status_code=404, detail=f"Accessory '{asset_id}' not found.")

                repair_id = generate_id("REP")
                cursor.execute("""
                    UPDATE Accessories_Master
                    SET Status = 'Under Repair',
                        Condition = ?,
                        Current_Holder_Type = 'Service_Centre',
                        Current_Holder_ID = ?,
                        Current_Location = ?
                    WHERE Accessory_ID = ?
                """, (req.condition_before, repair_id, req.service_centre, asset_id))

            timestamp = get_now_kolkata()

            # Insert into Repair_Log
            cursor.execute("""
                INSERT INTO Repair_Log (
                    Repair_ID, Asset_Type, Asset_ID, Taken_By_Staff_ID, Taken_By_Staff_Email,
                    Repair_Reason, Service_Centre, Technician, Out_Timestamp,
                    Expected_Return, Actual_Return_Timestamp, Repair_Status,
                    Estimated_Cost, Final_Cost, Receipt_or_JobSheet_Link,
                    Condition_Before, Condition_After, Acknowledgement_Status, Notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                repair_id, req.asset_type, asset_id, operator.id, operator.email,
                req.repair_reason, req.service_centre, req.technician, timestamp,
                req.expected_return or "", "", "SENT_TO_CENTRE",
                req.estimated_cost, 0.0, req.receipt_or_jobsheet_link or "",
                req.condition_before, "", "ACKNOWLEDGED", req.notes or ""
            ))

            # Insert Movement_Log (REPAIR_OUT)
            mov_id = generate_id("MOV")
            cursor.execute("""
                INSERT INTO Movement_Log (
                    Movement_ID, Person_Type, Person_ID, Person_Name_At_Transaction,
                    Person_Email, Course_At_Transaction, Batch_At_Transaction,
                    Asset_Type, Asset_ID, Action, Operator_Staff_Email,
                    Event_Timestamp, From_Location, To_Location, Purpose,
                    Condition_Out, Condition_In, Acknowledgement_Status,
                    Acknowledged_By_Email, Acknowledged_At, Related_Repair_ID, Notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                mov_id, "Staff", operator.id, operator.name,
                operator.email, "Administration", "Staff", req.asset_type,
                asset_id, "REPAIR_OUT", operator.email,
                timestamp, "Institute Lab", req.service_centre, f"Repair: {req.repair_reason}",
                req.condition_before, "", "ACKNOWLEDGED",
                operator.email, timestamp, repair_id, req.notes or ""
            ))

            conn.commit()
            conn.close()
            sync_to_excel()

            return {
                "success": True,
                "repair_id": repair_id,
                "movement_id": mov_id,
                "asset_id": asset_id,
                "status": "Under Repair",
                "timestamp": timestamp
            }

    @staticmethod
    def return_from_repair(req: ReturnFromRepairRequest, operator: CurrentUser) -> Dict[str, Any]:
        """
        Receives repaired device back into Available inventory.
        Records final cost, condition after repair, receipt link, and marks ticket COMPLETED.
        """
        repair_id = req.repair_id.strip()
        with db_lock:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM Repair_Log WHERE Repair_ID = ?", (repair_id,))
            rep = cursor.fetchone()
            if not rep:
                conn.close()
                raise HTTPException(status_code=404, detail=f"Repair ticket '{repair_id}' not found.")

            asset_type = rep["Asset_Type"]
            asset_id = rep["Asset_ID"]
            service_centre = rep["Service_Centre"]
            timestamp = get_now_kolkata()

            # Update Repair_Log
            cursor.execute("""
                UPDATE Repair_Log
                SET Repair_Status = 'COMPLETED',
                    Actual_Return_Timestamp = ?,
                    Final_Cost = ?,
                    Condition_After = ?,
                    Receipt_or_JobSheet_Link = COALESCE(NULLIF(?, ''), Receipt_or_JobSheet_Link),
                    Notes = Notes || ?
                WHERE Repair_ID = ?
            """, (timestamp, req.final_cost, req.condition_after, req.receipt_or_jobsheet_link, f" [Returned: {req.notes}]", repair_id))

            # Return Asset to Available
            if asset_type == "Laptop":
                cursor.execute("""
                    UPDATE Laptop_Master
                    SET Status = 'Available',
                        Condition = ?,
                        Current_Holder_Type = 'None',
                        Current_Holder_ID = '',
                        Current_Holder_Email = '',
                        Current_Location = ?
                    WHERE Laptop_ID = ?
                """, (req.condition_after, req.to_location, asset_id))
            else:
                cursor.execute("""
                    UPDATE Accessories_Master
                    SET Status = 'Available',
                        Condition = ?,
                        Current_Holder_Type = 'None',
                        Current_Holder_ID = '',
                        Current_Location = ?
                    WHERE Accessory_ID = ?
                """, (req.condition_after, req.to_location, asset_id))

            # Append Movement_Log (REPAIR_RETURN)
            mov_id = generate_id("MOV")
            cursor.execute("""
                INSERT INTO Movement_Log (
                    Movement_ID, Person_Type, Person_ID, Person_Name_At_Transaction,
                    Person_Email, Course_At_Transaction, Batch_At_Transaction,
                    Asset_Type, Asset_ID, Action, Operator_Staff_Email,
                    Event_Timestamp, From_Location, To_Location, Purpose,
                    Condition_Out, Condition_In, Acknowledgement_Status,
                    Acknowledged_By_Email, Acknowledged_At, Related_Repair_ID, Notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                mov_id, "Staff", operator.id, operator.name,
                operator.email, "Administration", "Staff", asset_type,
                asset_id, "REPAIR_RETURN", operator.email,
                timestamp, service_centre, req.to_location, f"Return from Repair (Final Cost: INR {req.final_cost})",
                "", req.condition_after, "NOT_REQUIRED",
                "", "", repair_id, req.notes or ""
            ))

            conn.commit()
            conn.close()
            sync_to_excel()

            return {
                "success": True,
                "repair_id": repair_id,
                "movement_id": mov_id,
                "asset_id": asset_id,
                "status": "Available",
                "final_cost": req.final_cost,
                "timestamp": timestamp
            }

    @staticmethod
    def batch_transfer(req: BatchTransferRequest, operator: CurrentUser) -> Dict[str, Any]:
        """
        Updates student's current Batch_Name in Students_Master without modifying
        the permanent Student_ID. Historical transactions retain their Batch_At_Transaction.
        """
        student_id = req.student_id.strip()
        new_batch = req.new_batch.strip()
        if not student_id or not new_batch:
            raise HTTPException(status_code=400, detail="Student ID and New Batch are required.")

        with db_lock:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM Students_Master WHERE Student_ID = ?", (student_id,))
            student = cursor.fetchone()
            if not student:
                conn.close()
                raise HTTPException(status_code=404, detail=f"Student '{student_id}' not found.")

            old_batch = student["Batch_Name"]
            timestamp = get_now_kolkata()
            transfer_note = f"[{timestamp}] Transferred from {old_batch} to {new_batch} by {operator.email} ({req.reason})"

            cursor.execute("""
                UPDATE Students_Master
                SET Batch_Name = ?,
                    Notes = CASE WHEN Notes IS NULL OR Notes = '' THEN ? ELSE Notes || ' | ' || ? END
                WHERE Student_ID = ?
            """, (new_batch, transfer_note, transfer_note, student_id))

            conn.commit()
            conn.close()
            sync_to_excel()

            return {
                "success": True,
                "student_id": student_id,
                "old_batch": old_batch,
                "new_batch": new_batch,
                "timestamp": timestamp
            }

    @staticmethod
    def student_acknowledge(movement_id: str, caller: CurrentUser) -> Dict[str, Any]:
        """
        A student confirms receipt of their issued asset.
        Verifies caller's registered email against the Movement_Log Person_Email.
        """
        with db_lock:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM Movement_Log WHERE Movement_ID = ?", (movement_id.strip(),))
            mov = cursor.fetchone()
            if not mov:
                conn.close()
                raise HTTPException(status_code=404, detail=f"Movement log '{movement_id}' not found.")

            target_email = mov["Person_Email"].lower().strip()
            if caller.role != "Admin" and caller.email.lower().strip() != target_email:
                conn.close()
                raise HTTPException(
                    status_code=403,
                    detail=f"Unauthorized: Only the assigned recipient ({target_email}) can acknowledge this record."
                )

            timestamp = get_now_kolkata()
            cursor.execute("""
                UPDATE Movement_Log
                SET Acknowledgement_Status = 'ACKNOWLEDGED',
                    Acknowledged_By_Email = ?,
                    Acknowledged_At = ?
                WHERE Movement_ID = ?
            """, (caller.email, timestamp, movement_id.strip()))

            conn.commit()
            conn.close()
            sync_to_excel()

            return {
                "success": True,
                "movement_id": movement_id,
                "status": "ACKNOWLEDGED",
                "acknowledged_by": caller.email,
                "timestamp": timestamp
            }

    @staticmethod
    def add_student(req: AddStudentRequest, operator: CurrentUser) -> Dict[str, Any]:
        """
        Creates new Student record with duplicate Student_ID prevention.
        """
        student_id = req.student_id.strip().upper()
        if not student_id or not req.student_name.strip() or not req.registered_gmail.strip():
            raise HTTPException(status_code=400, detail="Student ID, Name, and Gmail are required.")

        with db_lock:
            conn = get_connection()
            cursor = conn.cursor()

            # Prevent duplicate Student_ID
            cursor.execute("SELECT Student_ID FROM Students_Master WHERE UPPER(Student_ID) = ?", (student_id,))
            if cursor.fetchone():
                conn.close()
                raise HTTPException(status_code=400, detail=f"Duplicate error: Student_ID '{student_id}' already exists.")

            # Prevent duplicate Gmail
            cursor.execute("SELECT Student_ID FROM Students_Master WHERE LOWER(Registered_Gmail) = ?", (req.registered_gmail.lower().strip(),))
            if cursor.fetchone():
                conn.close()
                raise HTTPException(status_code=400, detail=f"Student with email '{req.registered_gmail}' already exists.")

            qr_value = f"QR-{student_id}"
            cursor.execute("""
                INSERT INTO Students_Master (
                    Student_ID, Student_Name, Registered_Gmail, Course_Name,
                    Batch_Name, Active, Student_QR_Value, Notes
                ) VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            """, (
                student_id, req.student_name.strip(), req.registered_gmail.lower().strip(),
                req.course_name.strip(), req.batch_name.strip(), qr_value, req.notes or ""
            ))

            conn.commit()
            conn.close()
            sync_to_excel()

            return {"success": True, "student_id": student_id, "qr_value": qr_value}

    @staticmethod
    def add_laptop(req: AddLaptopRequest, operator: CurrentUser) -> Dict[str, Any]:
        """Admin or Staff adding a new laptop."""
        laptop_id = req.laptop_id.strip().upper()
        with db_lock:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT Laptop_ID FROM Laptop_Master WHERE UPPER(Laptop_ID) = ?", (laptop_id,))
            if cursor.fetchone():
                conn.close()
                raise HTTPException(status_code=400, detail=f"Laptop_ID '{laptop_id}' already exists.")

            qr_value = f"QR-{laptop_id}"
            purchase_date = req.purchase_date or get_today_kolkata()

            cursor.execute("""
                INSERT INTO Laptop_Master (
                    Laptop_ID, Asset_Tag, Serial_Number, Brand, Model,
                    Purchase_Date, Condition, Status, Current_Holder_Type,
                    Current_Holder_ID, Current_Holder_Email, Current_Location,
                    QR_Value, Notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Available', 'None', '', '', ?, ?, ?)
            """, (
                laptop_id, req.asset_tag.strip(), req.serial_number.strip(),
                req.brand.strip(), req.model.strip(), purchase_date,
                req.condition, req.current_location, qr_value, req.notes or ""
            ))

            conn.commit()
            conn.close()
            sync_to_excel()

            return {"success": True, "laptop_id": laptop_id, "qr_value": qr_value}

    @staticmethod
    def update_student_email(student_id: str, email: str, operator: CurrentUser) -> Dict[str, Any]:
        """Dynamically link or update a student's Gmail."""
        student_id = student_id.strip()
        email = email.strip().lower()
        if not student_id:
            raise HTTPException(status_code=400, detail="Student ID is required.")

        with db_lock:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT Student_Name FROM Students_Master WHERE Student_ID = ?", (student_id,))
            stu = cursor.fetchone()
            if not stu:
                conn.close()
                raise HTTPException(status_code=404, detail=f"Student '{student_id}' not found.")

            cursor.execute("UPDATE Students_Master SET Registered_Gmail = ? WHERE Student_ID = ?", (email, student_id))
            conn.commit()
            conn.close()
            sync_to_excel()

            return {
                "success": True,
                "student_id": student_id,
                "student_name": stu["Student_Name"],
                "registered_gmail": email
            }

    @staticmethod
    def get_dashboard_stats() -> Dict[str, Any]:
        """Calculates institute metrics and summaries."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*), Status FROM Laptop_Master GROUP BY Status")
        laptop_counts = {row[1]: row[0] for row in cursor.fetchall()}

        cursor.execute("SELECT COUNT(*), Status FROM Accessories_Master WHERE Asset_Type = 'Charger' GROUP BY Status")
        charger_counts = {row[1]: row[0] for row in cursor.fetchall()}

        cursor.execute("SELECT SUM(Final_Cost) FROM Repair_Log WHERE Repair_Status = 'COMPLETED'")
        repair_cost_row = cursor.fetchone()
        total_repair_cost = float(repair_cost_row[0] or 0.0)

        cursor.execute("SELECT COUNT(*) FROM Movement_Log WHERE Acknowledgement_Status = 'PENDING'")
        pending_acks = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM Students_Master WHERE Active = 1")
        active_students = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM Laptop_Master WHERE Condition IN ('Fair', 'Damaged')")
        damaged_laptops = cursor.fetchone()[0]

        conn.close()

        total_laptops = sum(laptop_counts.values())
        total_chargers = sum(charger_counts.values())

        return {
            "total_laptops": total_laptops,
            "available_laptops": laptop_counts.get("Available", 0),
            "issued_laptops": laptop_counts.get("Issued", 0),
            "under_repair_laptops": laptop_counts.get("Under Repair", 0),
            "total_chargers": total_chargers,
            "available_chargers": charger_counts.get("Available", 0),
            "issued_chargers": charger_counts.get("Issued", 0),
            "under_repair_chargers": charger_counts.get("Under Repair", 0),
            "damaged_or_fair_laptops": damaged_laptops,
            "total_repair_spend_inr": total_repair_cost,
            "pending_student_acknowledgements": pending_acks,
            "active_students": active_students,
            "timestamp": get_now_kolkata()
        }
