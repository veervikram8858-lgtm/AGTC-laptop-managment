/**
 * Google Apps Script - Initial Spreadsheet Setup & Schema Generator
 * Run this function once in your Google Sheet script editor to automatically create
 * and format all 6 master tabs, column headers, validations, and sample records.
 */

function setupSpreadsheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  
  const sheets = [
    {
      name: "Students_Master",
      headers: [
        "Student_ID", "Student_Name", "Registered_Gmail", "Course_Name",
        "Batch_Name", "Active", "Student_QR_Value", "Notes"
      ],
      data: [
        ["STU-1001", "Aarav Sharma [SAMPLE]", "aarav.sharma.sample@gmail.com", "Full Stack Web Dev", "BATCH-2026-MORNING-A", true, "QR-STU-1001", "Identity verified via Aadhaar copy"],
        ["STU-1002", "Priya Patel [SAMPLE]", "priya.patel.sample@gmail.com", "Data Science & Python", "BATCH-2026-MORNING-A", true, "QR-STU-1002", "Needs high RAM laptop for ML"],
        ["STU-1003", "Rohan Verma [SAMPLE]", "rohan.verma.sample@gmail.com", "Cloud Computing & DevOps", "BATCH-2026-WEEKEND-B", true, "QR-STU-1003", "Transferred from morning batch"],
        ["STU-1004", "Ananya Iyer [SAMPLE]", "ananya.iyer.sample@gmail.com", "Full Stack Web Dev", "BATCH-2026-EVENING-C", true, "QR-STU-1004", "Active student"],
        ["STU-1005", "Kabir Singh [SAMPLE]", "kabir.singh.sample@gmail.com", "UI/UX Design", "BATCH-2026-WEEKEND-B", true, "QR-STU-1005", "Has personal stylus"]
      ]
    },
    {
      name: "Staff_Master",
      headers: [
        "Staff_ID", "Staff_Name", "Official_Gmail", "Role",
        "Can_Issue_Return", "Can_Manage_Repairs", "Active", "Staff_QR_Value", "Notes"
      ],
      data: [
        ["STAFF-01", "Director Vikram Rao [SAMPLE]", "director.vikram@sample-institute.in", "Admin", true, true, true, "QR-STAFF-01", "Super Admin & Institute Head"],
        ["STAFF-02", "Sunita Nair (Lab Incharge) [SAMPLE]", "sunita.lab@sample-institute.in", "Staff", true, true, true, "QR-STAFF-02", "Authorized for inventory & repair dispatch"],
        ["STAFF-03", "Deepak Joshi (Lab Assistant) [SAMPLE]", "deepak.lab@sample-institute.in", "Staff", true, false, true, "QR-STAFF-03", "Daily counter issue/return assistant"],
        ["STAFF-04", "Neha Gupta (Trainer) [SAMPLE]", "neha.trainer@sample-institute.in", "Staff", false, false, true, "QR-STAFF-04", "Instructor only, no inventory issuance permission"]
      ]
    },
    {
      name: "Laptop_Master",
      headers: [
        "Laptop_ID", "Asset_Tag", "Serial_Number", "Brand", "Model",
        "Purchase_Date", "Condition", "Status", "Current_Holder_Type",
        "Current_Holder_ID", "Current_Holder_Email", "Current_Location", "QR_Value", "Notes"
      ],
      data: [
        ["LAP-001", "TAG-LEN-01", "PF2K9901", "Lenovo", "ThinkPad L14 Gen 3", "2024-03-15", "Good", "Available", "None", "", "", "Lab 1 Cabinet A", "QR-LAP-001", "Intel Core i5-1235U, 16GB RAM, 512GB SSD"],
        ["LAP-002", "TAG-LEN-02", "PF2K9902", "Lenovo", "ThinkPad L14 Gen 3", "2024-03-15", "Good", "Issued", "Student", "STU-1001", "aarav.sharma.sample@gmail.com", "Student Custody (Lab Session)", "QR-LAP-002", "Issued with paired charger CHG-002"],
        ["LAP-003", "TAG-DEL-01", "DL74001A", "Dell", "Latitude 3420", "2024-05-10", "Good", "Available", "None", "", "", "Lab 1 Cabinet A", "QR-LAP-003", "Intel Core i5-1135G7, 16GB RAM, 256GB SSD"],
        ["LAP-004", "TAG-DEL-02", "DL74002B", "Dell", "Latitude 3420", "2024-05-10", "Fair", "Under Repair", "Service_Centre", "REP-2026-001", "", "Authorized Dell Centre, Nehru Place", "QR-LAP-004", "Trackpad replacement pending"],
        ["LAP-005", "TAG-HP-01", "HPPB440G1", "HP", "ProBook 440 G8", "2024-07-01", "Good", "Available", "None", "", "", "Lab 2 Shelf B", "QR-LAP-005", "Intel Core i5, 16GB RAM"],
        ["LAP-006", "TAG-HP-02", "HPPB440G2", "HP", "ProBook 440 G8", "2024-07-01", "Good", "Issued", "Staff", "STAFF-02", "sunita.lab@sample-institute.in", "Instructor Desk Lab 2", "QR-LAP-006", "Assigned for Lab demonstration"]
      ]
    },
    {
      name: "Accessories_Master",
      headers: [
        "Accessory_ID", "Asset_Type", "Serial_Number", "Specification",
        "Condition", "Status", "Current_Holder_Type", "Current_Holder_ID",
        "Current_Location", "QR_Value", "Notes"
      ],
      data: [
        ["CHG-001", "Charger", "CHG-LN-65-01", "Lenovo 65W USB-C Original Adapter", "Good", "Available", "None", "", "Lab 1 Charger Rack", "QR-CHG-001", "Paired default for LAP-001"],
        ["CHG-002", "Charger", "CHG-LN-65-02", "Lenovo 65W USB-C Original Adapter", "Good", "Issued", "Student", "STU-1001", "With Student STU-1001", "QR-CHG-002", "Issued alongside LAP-002"],
        ["CHG-003", "Charger", "CHG-DL-65-01", "Dell 65W Barrel 4.5mm Adapter", "Good", "Available", "None", "", "Lab 1 Charger Rack", "QR-CHG-003", "Paired default for LAP-003"],
        ["CHG-004", "Charger", "CHG-DL-65-02", "Dell 65W Barrel 4.5mm Adapter", "Damaged", "Under Repair", "Service_Centre", "REP-2026-001", "Dell Service Nehru Place", "QR-CHG-004", "Cable frayed at connector"],
        ["CHG-005", "Charger", "CHG-HP-45-01", "HP 45W Smart Blue Pin Adapter", "Good", "Available", "None", "", "Lab 2 Shelf B", "QR-CHG-005", "Paired default for LAP-005"],
        ["CHG-006", "Charger", "CHG-HP-45-02", "HP 45W Smart Blue Pin Adapter", "Good", "Issued", "Staff", "STAFF-02", "Instructor Desk Lab 2", "QR-CHG-006", "Issued alongside LAP-006"]
      ]
    },
    {
      name: "Movement_Log",
      headers: [
        "Movement_ID", "Person_Type", "Person_ID", "Person_Name_At_Transaction",
        "Person_Email", "Course_At_Transaction", "Batch_At_Transaction",
        "Asset_Type", "Asset_ID", "Action", "Operator_Staff_Email",
        "Event_Timestamp", "From_Location", "To_Location", "Purpose",
        "Condition_Out", "Condition_In", "Acknowledgement_Status",
        "Acknowledged_By_Email", "Acknowledged_At", "Related_Repair_ID", "Notes"
      ],
      data: [
        [
          "MOV-2026-0001", "Student", "STU-1001", "Aarav Sharma [SAMPLE]",
          "aarav.sharma.sample@gmail.com", "Full Stack Web Dev", "BATCH-2026-MORNING-A",
          "Laptop", "LAP-002", "ISSUE", "sunita.lab@sample-institute.in",
          "2026-10-26T10:00:00+05:30", "Lab 1 Cabinet A", "Student Custody", "Daily Lab Session",
          "Good", "", "ACKNOWLEDGED", "aarav.sharma.sample@gmail.com", "2026-10-26T10:02:15+05:30",
          "", "Issued with paired charger CHG-002. Student acknowledged in lab."
        ],
        [
          "MOV-2026-0002", "Student", "STU-1001", "Aarav Sharma [SAMPLE]",
          "aarav.sharma.sample@gmail.com", "Full Stack Web Dev", "BATCH-2026-MORNING-A",
          "Charger", "CHG-002", "ISSUE", "sunita.lab@sample-institute.in",
          "2026-10-26T10:00:00+05:30", "Lab 1 Charger Rack", "Student Custody", "Daily Lab Session",
          "Good", "", "ACKNOWLEDGED", "aarav.sharma.sample@gmail.com", "2026-10-26T10:02:15+05:30",
          "", "Charger issued bundled with LAP-002."
        ],
        [
          "MOV-2026-0003", "Staff", "STAFF-02", "Sunita Nair [SAMPLE]",
          "sunita.lab@sample-institute.in", "Faculty / Administration", "Staff",
          "Laptop", "LAP-006", "ISSUE", "director.vikram@sample-institute.in",
          "2026-10-26T09:30:00+05:30", "Lab 2 Shelf B", "Instructor Desk Lab 2", "Lab Demonstration",
          "Good", "", "ACKNOWLEDGED", "sunita.lab@sample-institute.in", "2026-10-26T09:31:00+05:30",
          "", "Semester curriculum setup."
        ]
      ]
    },
    {
      name: "Repair_Log",
      headers: [
        "Repair_ID", "Asset_Type", "Asset_ID", "Taken_By_Staff_ID", "Taken_By_Staff_Email",
        "Repair_Reason", "Service_Centre", "Technician", "Out_Timestamp",
        "Expected_Return", "Actual_Return_Timestamp", "Repair_Status",
        "Estimated_Cost", "Final_Cost", "Receipt_or_JobSheet_Link",
        "Condition_Before", "Condition_After", "Acknowledgement_Status", "Notes"
      ],
      data: [
        [
          "REP-2026-001", "Laptop", "LAP-004", "STAFF-02", "sunita.lab@sample-institute.in",
          "Intermittent trackpad click failure and loose left hinge", "Authorized Dell Service Centre, Nehru Place, New Delhi", "Ramesh Kumar (Desk 4)",
          "2026-10-24T14:15:00+05:30", "2026-10-28", "", "SENT_TO_CENTRE",
          2200.0, 0.0, "https://drive.google.com/sample_jobsheet_dell_rep001.pdf",
          "Fair - trackpad sticky", "", "ACKNOWLEDGED", "Estimated turnaround time 4 days. Under warranty inspection."
        ]
      ]
    }
  ];

  sheets.forEach(config => {
    let sheet = ss.getSheetByName(config.name);
    if (!sheet) {
      sheet = ss.insertSheet(config.name);
    }
    
    // Clear and set headers
    sheet.clear();
    sheet.getRange(1, 1, 1, config.headers.length).setValues([config.headers]);
    
    // Style headers
    const headerRange = sheet.getRange(1, 1, 1, config.headers.length);
    headerRange.setBackground("#1F4E78");
    headerRange.setFontColor("#FFFFFF");
    headerRange.setFontWeight("bold");
    headerRange.setHorizontalAlignment("center");
    sheet.setFrozenRows(1);

    // Insert sample data
    if (config.data && config.data.length > 0) {
      sheet.getRange(2, 1, config.data.length, config.headers.length).setValues(config.data);
    }

    // Auto-fit column widths
    for (let c = 1; c <= config.headers.length; c++) {
      sheet.autoResizeColumn(c);
    }
  });

  // Set Sheet TimeZone to Asia/Kolkata
  ss.setSpreadsheetTimeZone("Asia/Kolkata");

  Logger.log("Institute Asset Management Spreadsheet initialized successfully with all 6 master tabs!");
}
