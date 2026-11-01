"""
Data models and schemas for Institute Laptop, Charger, Student, Staff,
Issue/Return, and Repair Management System.
"""

from typing import Optional, List, Literal
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime

# Enums as Literals
PersonType = Literal["Student", "Staff"]
MovementAction = Literal["ISSUE", "RETURN", "HANDOVER", "REPAIR_OUT", "REPAIR_RETURN", "TRANSFER"]
AssetStatus = Literal["Available", "Issued", "Under Repair", "Retired", "Lost"]
AssetCondition = Literal["Excellent", "Good", "Fair", "Damaged"]
RepairStatus = Literal["SENT_TO_CENTRE", "IN_PROGRESS", "READY_FOR_PICKUP", "COMPLETED", "CANCELLED"]
AcknowledgementStatus = Literal["PENDING", "ACKNOWLEDGED", "REJECTED", "NOT_REQUIRED"]
UserRole = Literal["Admin", "Staff", "Student"]

class StudentModel(BaseModel):
    Student_ID: str = Field(..., description="Unique permanent Student ID")
    Student_Name: str
    Registered_Gmail: Optional[str] = ""
    Course_Name: str
    Batch_Name: str
    Active: bool = True
    Student_QR_Value: str
    Notes: Optional[str] = ""

class StaffModel(BaseModel):
    Staff_ID: str
    Staff_Name: str
    Official_Gmail: str
    Role: Literal["Admin", "Staff"]
    Can_Issue_Return: bool = True
    Can_Manage_Repairs: bool = False
    Active: bool = True
    Staff_QR_Value: str
    Notes: Optional[str] = ""

class LaptopModel(BaseModel):
    Laptop_ID: str
    Asset_Tag: str
    Serial_Number: str
    Brand: str
    Model: str
    Purchase_Date: str
    Condition: AssetCondition = "Good"
    Status: AssetStatus = "Available"
    Current_Holder_Type: Literal["Student", "Staff", "None", "Service_Centre"] = "None"
    Current_Holder_ID: Optional[str] = ""
    Current_Holder_Email: Optional[str] = ""
    Current_Location: str = "Lab 1 Cabinet A"
    QR_Value: str
    Notes: Optional[str] = ""

class AccessoryModel(BaseModel):
    Accessory_ID: str
    Asset_Type: Literal["Charger", "Mouse", "Bag", "Lock", "Adapter"] = "Charger"
    Serial_Number: str
    Specification: str
    Condition: AssetCondition = "Good"
    Status: AssetStatus = "Available"
    Current_Holder_Type: Literal["Student", "Staff", "None", "Service_Centre"] = "None"
    Current_Holder_ID: Optional[str] = ""
    Current_Location: str = "Lab 1 Charger Rack"
    QR_Value: str
    Notes: Optional[str] = ""

class MovementLogModel(BaseModel):
    Movement_ID: str
    Person_Type: PersonType
    Person_ID: str
    Person_Name_At_Transaction: str
    Person_Email: str
    Course_At_Transaction: str
    Batch_At_Transaction: str
    Asset_Type: Literal["Laptop", "Charger", "Accessory", "Bundle"]
    Asset_ID: str
    Action: MovementAction
    Operator_Staff_Email: str
    Event_Timestamp: str
    From_Location: str
    To_Location: str
    Purpose: str = "Daily Lab Session"
    Condition_Out: Optional[str] = ""
    Condition_In: Optional[str] = ""
    Acknowledgement_Status: AcknowledgementStatus = "PENDING"
    Acknowledged_By_Email: Optional[str] = ""
    Acknowledged_At: Optional[str] = ""
    Related_Repair_ID: Optional[str] = ""
    Notes: Optional[str] = ""

class RepairLogModel(BaseModel):
    Repair_ID: str
    Asset_Type: Literal["Laptop", "Charger", "Accessory"] = "Laptop"
    Asset_ID: str
    Taken_By_Staff_ID: str
    Taken_By_Staff_Email: str
    Repair_Reason: str
    Service_Centre: str
    Technician: str
    Out_Timestamp: str
    Expected_Return: Optional[str] = ""
    Actual_Return_Timestamp: Optional[str] = ""
    Repair_Status: RepairStatus = "SENT_TO_CENTRE"
    Estimated_Cost: float = 0.0
    Final_Cost: float = 0.0
    Receipt_or_JobSheet_Link: Optional[str] = ""
    Condition_Before: str = "Damaged"
    Condition_After: Optional[str] = ""
    Acknowledgement_Status: AcknowledgementStatus = "ACKNOWLEDGED"
    Notes: Optional[str] = ""

# Request DTOs
class FastIssueRequest(BaseModel):
    person_type: PersonType = "Student"
    person_id: str
    laptop_id: str
    include_charger: bool = True
    charger_id: Optional[str] = None
    purpose: str = "Daily Lab Session"
    condition_out: AssetCondition = "Good"
    to_location: Optional[str] = None
    notes: Optional[str] = ""
    immediate_student_ack: bool = False
    student_email: Optional[str] = None

class UpdateStudentEmailRequest(BaseModel):
    student_id: str
    registered_gmail: str

class FastReturnRequest(BaseModel):
    laptop_id: str
    condition_in: AssetCondition = "Good"
    to_location: str = "Lab 1 Cabinet A"
    include_charger: bool = True
    charger_id: Optional[str] = None
    notes: Optional[str] = ""

class SendToRepairRequest(BaseModel):
    asset_type: Literal["Laptop", "Charger"] = "Laptop"
    asset_id: str
    repair_reason: str
    service_centre: str
    technician: str = "Authorized Technician"
    expected_return: Optional[str] = None
    estimated_cost: float = 0.0
    receipt_or_jobsheet_link: Optional[str] = ""
    condition_before: str = "Damaged"
    notes: Optional[str] = ""

class ReturnFromRepairRequest(BaseModel):
    repair_id: str
    final_cost: float = 0.0
    condition_after: AssetCondition = "Good"
    to_location: str = "Lab 1 Cabinet A"
    receipt_or_jobsheet_link: Optional[str] = ""
    notes: Optional[str] = ""

class BatchTransferRequest(BaseModel):
    student_id: str
    new_batch: str
    reason: Optional[str] = "Batch transfer schedule update"

class StudentAckRequest(BaseModel):
    movement_id: str

class AddStudentRequest(BaseModel):
    student_id: str
    student_name: str
    registered_gmail: str
    course_name: str
    batch_name: str
    notes: Optional[str] = ""

class AddLaptopRequest(BaseModel):
    laptop_id: str
    asset_tag: str
    serial_number: str
    brand: str
    model: str
    purchase_date: Optional[str] = None
    condition: AssetCondition = "Good"
    current_location: str = "Lab 1 Cabinet A"
    notes: Optional[str] = ""

class AddAccessoryRequest(BaseModel):
    accessory_id: str
    asset_type: Literal["Charger", "Mouse", "Bag", "Lock", "Adapter"] = "Charger"
    serial_number: str
    specification: str
    condition: AssetCondition = "Good"
    current_location: str = "Lab 1 Charger Rack"
    notes: Optional[str] = ""

class AuthLoginRequest(BaseModel):
    email: str
    google_token: Optional[str] = None
