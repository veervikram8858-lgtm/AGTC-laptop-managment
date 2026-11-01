/**
 * Google Apps Script - Institute Laptop & Asset Management Backend
 * Provides REST API endpoints (doGet/doPost) and business logic for
 * Laptop, Charger, Student, Staff, Issue/Return, and Repair Management.
 * Timezone: Asia/Kolkata
 */

const TIMEZONE = "Asia/Kolkata";

// Web App GET Router
function doGet(e) {
  try {
    const action = (e && e.parameter && e.parameter.action) || "dashboard";
    const userEmail = getUserEmail(e);
    const userRole = getUserRole(userEmail);

    let result;
    switch (action) {
      case "dashboard":
        result = getDashboardStats(userRole, userEmail);
        break;
      case "laptops":
        result = getLaptops(userRole, userEmail);
        break;
      case "accessories":
        result = getAccessories(userRole, userEmail);
        break;
      case "students":
        result = getStudents(userRole, userEmail);
        break;
      case "staff":
        result = getStaff(userRole, userEmail);
        break;
      case "movement_log":
        result = getMovementLog(userRole, userEmail);
        break;
      case "repair_log":
        result = getRepairLog(userRole, userEmail);
        break;
      case "student_my_assets":
        result = getStudentMyAssets(userEmail);
        break;
      case "whoami":
        result = { email: userEmail, role: userRole.role, permissions: userRole };
        break;
      default:
        result = { error: "Unknown action: " + action };
    }

    return createJsonResponse({ status: "success", data: result });
  } catch (err) {
    return createJsonResponse({ status: "error", message: err.toString() });
  }
}

// Web App POST Router
function doPost(e) {
  try {
    const payload = JSON.parse(e.postData.contents);
    const action = payload.action;
    const userEmail = getUserEmail(e, payload);
    const userRole = getUserRole(userEmail);

    let result;
    switch (action) {
      case "ISSUE":
        result = handleIssueAsset(payload, userEmail, userRole);
        break;
      case "RETURN":
        result = handleReturnAsset(payload, userEmail, userRole);
        break;
      case "SEND_TO_REPAIR":
        result = handleSendToRepair(payload, userEmail, userRole);
        break;
      case "RETURN_FROM_REPAIR":
        result = handleReturnFromRepair(payload, userEmail, userRole);
        break;
      case "STUDENT_ACKNOWLEDGE":
        result = handleStudentAcknowledge(payload, userEmail, userRole);
        break;
      case "BATCH_TRANSFER":
        result = handleBatchTransfer(payload, userEmail, userRole);
        break;
      case "ADD_STUDENT":
        result = handleAddStudent(payload, userEmail, userRole);
        break;
      case "ADD_LAPTOP":
        result = handleAddLaptop(payload, userEmail, userRole);
        break;
      case "ADD_ACCESSORY":
        result = handleAddAccessory(payload, userEmail, userRole);
        break;
      case "CORRECTION_LOG":
        result = handleCorrectionLog(payload, userEmail, userRole);
        break;
      default:
        throw new Error("Invalid action: " + action);
    }

    return createJsonResponse({ status: "success", data: result });
  } catch (err) {
    return createJsonResponse({ status: "error", message: err.toString() });
  }
}

// ======================== AUTHENTICATION & RBAC ========================

function getUserEmail(e, payload) {
  // If run in Google Apps Script authenticated context:
  let email = Session.getActiveUser().getEmail();
  // If running via client-token/payload in development or delegated mode:
  if (!email && payload && payload.operator_email) {
    email = payload.operator_email;
  }
  if (!email && e && e.parameter && e.parameter.email) {
    email = e.parameter.email;
  }
  return (email || "").toLowerCase().trim();
}

function getUserRole(email) {
  if (!email) {
    return { role: "Anonymous", can_issue_return: false, can_manage_repairs: false, active: false };
  }

  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const staffSheet = ss.getSheetByName("Staff_Master");
  if (staffSheet) {
    const data = staffSheet.getDataRange().getValues();
    for (let i = 1; i < data.length; i++) {
      const staffEmail = String(data[i][2]).toLowerCase().trim();
      if (staffEmail === email) {
        return {
          role: data[i][3], // Admin or Staff
          can_issue_return: Boolean(data[i][4]),
          can_manage_repairs: Boolean(data[i][5]),
          active: Boolean(data[i][6]),
          staff_id: data[i][0],
          staff_name: data[i][1]
        };
      }
    }
  }

  // Check if Student
  const stuSheet = ss.getSheetByName("Students_Master");
  if (stuSheet) {
    const data = stuSheet.getDataRange().getValues();
    for (let i = 1; i < data.length; i++) {
      const stuEmail = String(data[i][2]).toLowerCase().trim();
      if (stuEmail === email) {
        return {
          role: "Student",
          student_id: data[i][0],
          student_name: data[i][1],
          course: data[i][3],
          batch: data[i][4],
          active: Boolean(data[i][5]),
          can_issue_return: false,
          can_manage_repairs: false
        };
      }
    }
  }

  return { role: "Unknown", can_issue_return: false, can_manage_repairs: false, active: false };
}

function requireStaffPermission(userRole, permissionType) {
  if (!userRole.active) {
    throw new Error("Access denied: Account is inactive or not found in Staff_Master.");
  }
  if (userRole.role === "Admin") {
    return true; // Admin has all permissions
  }
  if (permissionType === "ISSUE_RETURN" && !userRole.can_issue_return) {
    throw new Error("Access denied: Staff does not have 'Can_Issue_Return' privilege.");
  }
  if (permissionType === "REPAIR" && !userRole.can_manage_repairs) {
    throw new Error("Access denied: Staff does not have 'Can_Manage_Repairs' privilege.");
  }
  return true;
}

// ======================== CORE BUSINESS LOGIC ========================

/**
 * Fast Issue Workflow: Minimal typing, validated against masters.
 */
function handleIssueAsset(payload, userEmail, userRole) {
  requireStaffPermission(userRole, "ISSUE_RETURN");
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  const laptopId = (payload.laptop_id || "").trim();
  const personType = (payload.person_type || "Student").trim(); // Student or Staff
  const personId = (payload.person_id || "").trim();
  const includeCharger = Boolean(payload.include_charger);
  const chargerId = (payload.charger_id || "").trim();
  const purpose = payload.purpose || "Daily Lab Session";
  const conditionOut = payload.condition_out || "Good";
  const toLocation = payload.to_location || (personType === "Student" ? "Student Custody" : "Staff Custody");
  const notes = payload.notes || "";

  if (!laptopId || !personId) {
    throw new Error("Laptop ID and Person ID are required.");
  }

  // 1. Validate Person
  let personName = "";
  let personEmail = "";
  let courseAtTx = "";
  let batchAtTx = "";

  if (personType === "Student") {
    const stuSheet = ss.getSheetByName("Students_Master");
    const stuData = stuSheet.getDataRange().getValues();
    let found = false;
    for (let i = 1; i < stuData.length; i++) {
      if (String(stuData[i][0]).trim() === personId || String(stuData[i][6]).trim() === personId) {
        if (!stuData[i][5]) throw new Error("Student " + personId + " is marked INACTIVE.");
        personId = stuData[i][0];
        personName = stuData[i][1];
        personEmail = stuData[i][2];
        courseAtTx = stuData[i][3];
        batchAtTx = stuData[i][4];
        found = true;
        break;
      }
    }
    if (!found) throw new Error("Student ID or QR not found in Students_Master: " + personId);
  } else {
    const staffSheet = ss.getSheetByName("Staff_Master");
    const staffData = staffSheet.getDataRange().getValues();
    let found = false;
    for (let i = 1; i < staffData.length; i++) {
      if (String(staffData[i][0]).trim() === personId || String(staffData[i][7]).trim() === personId) {
        if (!staffData[i][6]) throw new Error("Staff " + personId + " is marked INACTIVE.");
        personId = staffData[i][0];
        personName = staffData[i][1];
        personEmail = staffData[i][2];
        courseAtTx = "Faculty / Administration";
        batchAtTx = "Staff";
        found = true;
        break;
      }
    }
    if (!found) throw new Error("Staff ID or QR not found in Staff_Master: " + personId);
  }

  // 2. Validate Laptop
  const laptopSheet = ss.getSheetByName("Laptop_Master");
  const lapData = laptopSheet.getDataRange().getValues();
  let lapRowIdx = -1;
  let fromLocation = "Institute Lab";

  for (let i = 1; i < lapData.length; i++) {
    if (String(lapData[i][0]).trim() === laptopId || String(lapData[i][12]).trim() === laptopId) {
      lapRowIdx = i + 1; // 1-indexed sheet row
      const currentStatus = String(lapData[i][7]).trim();
      if (currentStatus === "Issued") {
        throw new Error("Laptop " + laptopId + " is ALREADY ISSUED to " + lapData[i][8] + " (" + lapData[i][9] + ").");
      }
      if (currentStatus === "Under Repair") {
        throw new Error("Laptop " + laptopId + " is currently UNDER REPAIR and cannot be issued.");
      }
      if (currentStatus !== "Available") {
        throw new Error("Laptop " + laptopId + " is not Available (Current status: " + currentStatus + ").");
      }
      fromLocation = lapData[i][11] || "Institute Lab";
      break;
    }
  }
  if (lapRowIdx === -1) throw new Error("Laptop not found: " + laptopId);

  // 3. Validate Charger if requested
  let resolvedChargerId = chargerId;
  const accSheet = ss.getSheetByName("Accessories_Master");
  let accRowIdx = -1;
  if (includeCharger) {
    if (!resolvedChargerId) {
      // Auto-match paired charger
      const accData = accSheet.getDataRange().getValues();
      for (let i = 1; i < accData.length; i++) {
        if (accData[i][1] === "Charger" && accData[i][5] === "Available") {
          resolvedChargerId = accData[i][0];
          accRowIdx = i + 1;
          break;
        }
      }
    } else {
      const accData = accSheet.getDataRange().getValues();
      for (let i = 1; i < accData.length; i++) {
        if (accData[i][0] === resolvedChargerId || accData[i][9] === resolvedChargerId) {
          accRowIdx = i + 1;
          if (accData[i][5] === "Issued") {
            throw new Error("Charger " + resolvedChargerId + " is already issued.");
          }
          if (accData[i][5] === "Under Repair") {
            throw new Error("Charger " + resolvedChargerId + " is Under Repair.");
          }
          break;
        }
      }
    }
  }

  const nowTimestamp = getCurrentKolkataTimestamp();
  const movSheet = ss.getSheetByName("Movement_Log");

  // Determine Acknowledgement Status
  // If student is performing this action or staff confirms verbal/counter verification:
  const ackStatus = payload.immediate_student_ack ? "ACKNOWLEDGED" : "PENDING";
  const ackByEmail = payload.immediate_student_ack ? personEmail : "";
  const ackAt = payload.immediate_student_ack ? nowTimestamp : "";

  // 4. Update Laptop Master
  // Laptop columns: 7=Condition, 8=Status, 9=Holder_Type, 10=Holder_ID, 11=Holder_Email, 12=Current_Location
  laptopSheet.getRange(lapRowIdx, 8).setValue("Issued");
  laptopSheet.getRange(lapRowIdx, 9).setValue(personType);
  laptopSheet.getRange(lapRowIdx, 10).setValue(personId);
  laptopSheet.getRange(lapRowIdx, 11).setValue(personEmail);
  laptopSheet.getRange(lapRowIdx, 12).setValue(toLocation);

  // 5. Append Laptop Movement Log
  const laptopMovId = generateId("MOV");
  movSheet.appendRow([
    laptopMovId, personType, personId, personName,
    personEmail, courseAtTx, batchAtTx, "Laptop",
    laptopId, "ISSUE", userEmail, nowTimestamp,
    fromLocation, toLocation, purpose, conditionOut,
    "", ackStatus, ackByEmail, ackAt, "",
    (includeCharger ? "Issued with charger " + resolvedChargerId + ". " : "") + notes
  ]);

  // 6. Update and Append Charger if included
  if (includeCharger && resolvedChargerId && accRowIdx !== -1) {
    accSheet.getRange(accRowIdx, 6).setValue("Issued");
    accSheet.getRange(accRowIdx, 7).setValue(personType);
    accSheet.getRange(accRowIdx, 8).setValue(personId);
    accSheet.getRange(accRowIdx, 9).setValue(toLocation);

    const chargerMovId = generateId("MOV");
    movSheet.appendRow([
      chargerMovId, personType, personId, personName,
      personEmail, courseAtTx, batchAtTx, "Charger",
      resolvedChargerId, "ISSUE", userEmail, nowTimestamp,
      fromLocation, toLocation, purpose, conditionOut,
      "", ackStatus, ackByEmail, ackAt, "",
      "Issued bundled with Laptop " + laptopId + ". " + notes
    ]);
  }

  return {
    success: true,
    movement_id: laptopMovId,
    laptop_id: laptopId,
    charger_id: includeCharger ? resolvedChargerId : null,
    person_id: personId,
    person_name: personName,
    status: "Issued",
    acknowledgement_status: ackStatus,
    timestamp: nowTimestamp
  };
}

/**
 * Fast Return Workflow
 */
function handleReturnAsset(payload, userEmail, userRole) {
  requireStaffPermission(userRole, "ISSUE_RETURN");
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  const laptopId = (payload.laptop_id || "").trim();
  const conditionIn = payload.condition_in || "Good";
  const toLocation = payload.to_location || "Lab 1 Cabinet A";
  const notes = payload.notes || "";
  const includeCharger = payload.include_charger !== false; // default true if paired
  const chargerId = (payload.charger_id || "").trim();

  if (!laptopId) throw new Error("Laptop ID is required for return.");

  const laptopSheet = ss.getSheetByName("Laptop_Master");
  const lapData = laptopSheet.getDataRange().getValues();
  let lapRowIdx = -1;
  let previousHolderType = "";
  let previousHolderId = "";
  let previousHolderEmail = "";
  let currentFromLocation = "";

  for (let i = 1; i < lapData.length; i++) {
    if (String(lapData[i][0]).trim() === laptopId || String(lapData[i][12]).trim() === laptopId) {
      lapRowIdx = i + 1;
      const currentStatus = String(lapData[i][7]).trim();
      if (currentStatus !== "Issued") {
        throw new Error("Cannot return Laptop " + laptopId + ": Device is currently " + currentStatus + ", not Issued.");
      }
      previousHolderType = lapData[i][8];
      previousHolderId = lapData[i][9];
      previousHolderEmail = lapData[i][10];
      currentFromLocation = lapData[i][11];
      break;
    }
  }
  if (lapRowIdx === -1) throw new Error("Laptop not found: " + laptopId);

  // Get Person Details at Return
  let personName = "";
  let courseAtTx = "";
  let batchAtTx = "";

  if (previousHolderType === "Student") {
    const stuSheet = ss.getSheetByName("Students_Master");
    const stuData = stuSheet.getDataRange().getValues();
    for (let i = 1; i < stuData.length; i++) {
      if (String(stuData[i][0]).trim() === previousHolderId) {
        personName = stuData[i][1];
        courseAtTx = stuData[i][3];
        batchAtTx = stuData[i][4];
        break;
      }
    }
  } else {
    const staffSheet = ss.getSheetByName("Staff_Master");
    const staffData = staffSheet.getDataRange().getValues();
    for (let i = 1; i < staffData.length; i++) {
      if (String(staffData[i][0]).trim() === previousHolderId) {
        personName = staffData[i][1];
        courseAtTx = "Faculty / Administration";
        batchAtTx = "Staff";
        break;
      }
    }
  }

  const nowTimestamp = getCurrentKolkataTimestamp();
  const movSheet = ss.getSheetByName("Movement_Log");

  // 1. Reset Laptop Master
  laptopSheet.getRange(lapRowIdx, 7).setValue(conditionIn);
  laptopSheet.getRange(lapRowIdx, 8).setValue("Available");
  laptopSheet.getRange(lapRowIdx, 9).setValue("None");
  laptopSheet.getRange(lapRowIdx, 10).setValue("");
  laptopSheet.getRange(lapRowIdx, 11).setValue("");
  laptopSheet.getRange(lapRowIdx, 12).setValue(toLocation);

  // 2. Append Laptop Return Movement
  const laptopMovId = generateId("MOV");
  movSheet.appendRow([
    laptopMovId, previousHolderType, previousHolderId, personName,
    previousHolderEmail, courseAtTx, batchAtTx, "Laptop",
    laptopId, "RETURN", userEmail, nowTimestamp,
    currentFromLocation, toLocation, "Return to Inventory", "",
    conditionIn, "NOT_REQUIRED", "", "", "",
    notes
  ]);

  // 3. Return Charger if specified or assigned to same holder
  const accSheet = ss.getSheetByName("Accessories_Master");
  const accData = accSheet.getDataRange().getValues();
  let resolvedChargerId = chargerId;

  if (includeCharger) {
    for (let i = 1; i < accData.length; i++) {
      const matchSpecific = resolvedChargerId && (accData[i][0] === resolvedChargerId || accData[i][9] === resolvedChargerId);
      const matchHolder = !resolvedChargerId && accData[i][1] === "Charger" && accData[i][5] === "Issued" && accData[i][7] === previousHolderId;
      if (matchSpecific || matchHolder) {
        const accRow = i + 1;
        resolvedChargerId = accData[i][0];
        accSheet.getRange(accRow, 5).setValue(conditionIn);
        accSheet.getRange(accRow, 6).setValue("Available");
        accSheet.getRange(accRow, 7).setValue("None");
        accSheet.getRange(accRow, 8).setValue("");
        accSheet.getRange(accRow, 9).setValue(toLocation);

        const chgMovId = generateId("MOV");
        movSheet.appendRow([
          chgMovId, previousHolderType, previousHolderId, personName,
          previousHolderEmail, courseAtTx, batchAtTx, "Charger",
          resolvedChargerId, "RETURN", userEmail, nowTimestamp,
          currentFromLocation, toLocation, "Return to Inventory", "",
          conditionIn, "NOT_REQUIRED", "", "", "",
          "Charger returned with Laptop " + laptopId + ". " + notes
        ]);
        break;
      }
    }
  }

  return {
    success: true,
    movement_id: laptopMovId,
    laptop_id: laptopId,
    charger_id: resolvedChargerId,
    status: "Available",
    returned_by: previousHolderId,
    timestamp: nowTimestamp
  };
}

/**
 * Send Device for Repair
 */
function handleSendToRepair(payload, userEmail, userRole) {
  requireStaffPermission(userRole, "REPAIR");
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  const assetType = payload.asset_type || "Laptop"; // Laptop or Charger
  const assetId = (payload.asset_id || "").trim();
  const repairReason = payload.repair_reason || "Hardware fault";
  const serviceCentre = payload.service_centre || "Authorized Service Centre";
  const technician = payload.technician || "Service Technician";
  const expectedReturn = payload.expected_return || "";
  const estimatedCost = Number(payload.estimated_cost) || 0.0;
  const jobSheetLink = payload.receipt_or_jobsheet_link || "";
  const conditionBefore = payload.condition_before || "Damaged";
  const notes = payload.notes || "";

  if (!assetId) throw new Error("Asset ID is required.");

  const nowTimestamp = getCurrentKolkataTimestamp();
  const repairId = generateId("REP");

  // Update Asset Master to Under Repair
  if (assetType === "Laptop") {
    const lapSheet = ss.getSheetByName("Laptop_Master");
    const data = lapSheet.getDataRange().getValues();
    let rowIdx = -1;
    for (let i = 1; i < data.length; i++) {
      if (String(data[i][0]).trim() === assetId) {
        rowIdx = i + 1;
        if (data[i][7] === "Issued") {
          throw new Error("Cannot send Laptop " + assetId + " for repair while it is currently Issued. Return it first.");
        }
        break;
      }
    }
    if (rowIdx === -1) throw new Error("Laptop " + assetId + " not found.");
    lapSheet.getRange(rowIdx, 7).setValue(conditionBefore);
    lapSheet.getRange(rowIdx, 8).setValue("Under Repair");
    lapSheet.getRange(rowIdx, 9).setValue("Service_Centre");
    lapSheet.getRange(rowIdx, 10).setValue(repairId);
    lapSheet.getRange(rowIdx, 12).setValue(serviceCentre);
  } else {
    const accSheet = ss.getSheetByName("Accessories_Master");
    const data = accSheet.getDataRange().getValues();
    let rowIdx = -1;
    for (let i = 1; i < data.length; i++) {
      if (String(data[i][0]).trim() === assetId) {
        rowIdx = i + 1;
        break;
      }
    }
    if (rowIdx === -1) throw new Error("Accessory " + assetId + " not found.");
    accSheet.getRange(rowIdx, 5).setValue(conditionBefore);
    accSheet.getRange(rowIdx, 6).setValue("Under Repair");
    accSheet.getRange(rowIdx, 7).setValue("Service_Centre");
    accSheet.getRange(rowIdx, 8).setValue(repairId);
    accSheet.getRange(rowIdx, 9).setValue(serviceCentre);
  }

  // Append to Repair_Log
  const repSheet = ss.getSheetByName("Repair_Log");
  repSheet.appendRow([
    repairId, assetType, assetId, userRole.staff_id || "STAFF", userEmail,
    repairReason, serviceCentre, technician, nowTimestamp,
    expectedReturn, "", "SENT_TO_CENTRE",
    estimatedCost, 0.0, jobSheetLink,
    conditionBefore, "", "ACKNOWLEDGED", notes
  ]);

  // Append to Movement_Log
  const movSheet = ss.getSheetByName("Movement_Log");
  const movId = generateId("MOV");
  movSheet.appendRow([
    movId, "Staff", userRole.staff_id || "STAFF", userRole.staff_name || "Staff",
    userEmail, "Administration", "Staff", assetType,
    assetId, "REPAIR_OUT", userEmail, nowTimestamp,
    "Institute Lab", serviceCentre, "Hardware Repair: " + repairReason, conditionBefore,
    "", "ACKNOWLEDGED", userEmail, nowTimestamp, repairId, notes
  ]);

  return {
    success: true,
    repair_id: repairId,
    movement_id: movId,
    asset_id: assetId,
    status: "Under Repair",
    service_centre: serviceCentre,
    timestamp: nowTimestamp
  };
}

/**
 * Return Device from Repair
 */
function handleReturnFromRepair(payload, userEmail, userRole) {
  requireStaffPermission(userRole, "REPAIR");
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  const repairId = (payload.repair_id || "").trim();
  const finalCost = Number(payload.final_cost) || 0.0;
  const conditionAfter = payload.condition_after || "Good";
  const toLocation = payload.to_location || "Lab 1 Cabinet A";
  const receiptLink = payload.receipt_or_jobsheet_link || "";
  const notes = payload.notes || "";

  if (!repairId) throw new Error("Repair ID is required.");

  const repSheet = ss.getSheetByName("Repair_Log");
  const repData = repSheet.getDataRange().getValues();
  let repRowIdx = -1;
  let assetType = "Laptop";
  let assetId = "";
  let serviceCentre = "";

  for (let i = 1; i < repData.length; i++) {
    if (String(repData[i][0]).trim() === repairId) {
      repRowIdx = i + 1;
      assetType = repData[i][1];
      assetId = repData[i][2];
      serviceCentre = repData[i][6];
      break;
    }
  }
  if (repRowIdx === -1) throw new Error("Repair record not found: " + repairId);

  const nowTimestamp = getCurrentKolkataTimestamp();

  // Update Repair_Log
  repSheet.getRange(repRowIdx, 11).setValue(nowTimestamp); // Actual_Return_Timestamp
  repSheet.getRange(repRowIdx, 12).setValue("COMPLETED");
  repSheet.getRange(repRowIdx, 14).setValue(finalCost);
  if (receiptLink) repSheet.getRange(repRowIdx, 15).setValue(receiptLink);
  repSheet.getRange(repRowIdx, 17).setValue(conditionAfter);

  // Return Asset Master to Available
  if (assetType === "Laptop") {
    const lapSheet = ss.getSheetByName("Laptop_Master");
    const data = lapSheet.getDataRange().getValues();
    for (let i = 1; i < data.length; i++) {
      if (String(data[i][0]).trim() === assetId) {
        const r = i + 1;
        lapSheet.getRange(r, 7).setValue(conditionAfter);
        lapSheet.getRange(r, 8).setValue("Available");
        lapSheet.getRange(r, 9).setValue("None");
        lapSheet.getRange(r, 10).setValue("");
        lapSheet.getRange(r, 12).setValue(toLocation);
        break;
      }
    }
  } else {
    const accSheet = ss.getSheetByName("Accessories_Master");
    const data = accSheet.getDataRange().getValues();
    for (let i = 1; i < data.length; i++) {
      if (String(data[i][0]).trim() === assetId) {
        const r = i + 1;
        accSheet.getRange(r, 5).setValue(conditionAfter);
        accSheet.getRange(r, 6).setValue("Available");
        accSheet.getRange(r, 7).setValue("None");
        accSheet.getRange(r, 8).setValue("");
        accSheet.getRange(r, 9).setValue(toLocation);
        break;
      }
    }
  }

  // Append Movement_Log
  const movSheet = ss.getSheetByName("Movement_Log");
  const movId = generateId("MOV");
  movSheet.appendRow([
    movId, "Staff", userRole.staff_id || "STAFF", userRole.staff_name || "Staff",
    userEmail, "Administration", "Staff", assetType,
    assetId, "REPAIR_RETURN", userEmail, nowTimestamp,
    serviceCentre, toLocation, "Return from Repair (Cost: INR " + finalCost + ")", "",
    conditionAfter, "NOT_REQUIRED", "", "", repairId, notes
  ]);

  return {
    success: true,
    repair_id: repairId,
    movement_id: movId,
    asset_id: assetId,
    status: "Available",
    final_cost: finalCost,
    timestamp: nowTimestamp
  };
}

/**
 * Student Acknowledgement
 */
function handleStudentAcknowledge(payload, userEmail, userRole) {
  const movementId = (payload.movement_id || "").trim();
  if (!movementId) throw new Error("Movement ID is required.");

  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const movSheet = ss.getSheetByName("Movement_Log");
  const data = movSheet.getDataRange().getValues();
  let rowIdx = -1;
  let targetEmail = "";

  for (let i = 1; i < data.length; i++) {
    if (String(data[i][0]).trim() === movementId) {
      rowIdx = i + 1;
      targetEmail = String(data[i][4]).toLowerCase().trim();
      break;
    }
  }
  if (rowIdx === -1) throw new Error("Movement record not found: " + movementId);

  // Security check: Either student's email matches, or Admin authorized
  if (userRole.role !== "Admin" && userEmail !== targetEmail) {
    throw new Error("Unauthorized: Only the assigned student (" + targetEmail + ") can acknowledge this transaction.");
  }

  const nowTimestamp = getCurrentKolkataTimestamp();
  movSheet.getRange(rowIdx, 18).setValue("ACKNOWLEDGED");
  movSheet.getRange(rowIdx, 19).setValue(userEmail);
  movSheet.getRange(rowIdx, 20).setValue(nowTimestamp);

  return {
    success: true,
    movement_id: movementId,
    acknowledged_by: userEmail,
    timestamp: nowTimestamp
  };
}

/**
 * Batch Transfer: Updates student's current batch without altering permanent Student_ID.
 * Preserves past batches in Movement_Log.
 */
function handleBatchTransfer(payload, userEmail, userRole) {
  requireStaffPermission(userRole, "ISSUE_RETURN");
  const studentId = (payload.student_id || "").trim();
  const newBatch = (payload.new_batch || "").trim();
  const reason = payload.reason || "Batch transfer request";

  if (!studentId || !newBatch) throw new Error("Student ID and New Batch are required.");

  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const stuSheet = ss.getSheetByName("Students_Master");
  const data = stuSheet.getDataRange().getValues();
  let rowIdx = -1;
  let oldBatch = "";
  let studentName = "";

  for (let i = 1; i < data.length; i++) {
    if (String(data[i][0]).trim() === studentId) {
      rowIdx = i + 1;
      studentName = data[i][1];
      oldBatch = data[i][4];
      break;
    }
  }
  if (rowIdx === -1) throw new Error("Student not found: " + studentId);

  stuSheet.getRange(rowIdx, 5).setValue(newBatch);
  const oldNotes = stuSheet.getRange(rowIdx, 8).getValue();
  const timestamp = getCurrentKolkataTimestamp();
  stuSheet.getRange(rowIdx, 8).setValue(
    (oldNotes ? oldNotes + " | " : "") +
    "[" + timestamp + "] Transferred from " + oldBatch + " to " + newBatch + " by " + userEmail + " (" + reason + ")"
  );

  return {
    success: true,
    student_id: studentId,
    student_name: studentName,
    old_batch: oldBatch,
    new_batch: newBatch,
    timestamp: timestamp
  };
}

/**
 * Add New Student (With Duplicate ID Prevention)
 */
function handleAddStudent(payload, userEmail, userRole) {
  requireStaffPermission(userRole, "ISSUE_RETURN");
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const stuSheet = ss.getSheetByName("Students_Master");
  const data = stuSheet.getDataRange().getValues();

  const studentId = (payload.student_id || "").trim();
  const name = (payload.student_name || "").trim();
  const gmail = (payload.registered_gmail || "").trim().toLowerCase();
  const course = (payload.course_name || "").trim();
  const batch = (payload.batch_name || "").trim();
  const notes = payload.notes || "";

  if (!studentId || !name || !gmail) throw new Error("Student ID, Name, and Registered Gmail are required.");

  // Check duplicate Student_ID
  for (let i = 1; i < data.length; i++) {
    if (String(data[i][0]).trim().toUpperCase() === studentId.toUpperCase()) {
      throw new Error("Student_ID " + studentId + " already exists. Duplicate Student_IDs are strictly prevented.");
    }
  }

  const qrValue = "QR-" + studentId;
  stuSheet.appendRow([studentId, name, gmail, course, batch, true, qrValue, notes]);

  return { success: true, student_id: studentId, student_name: name, qr_value: qrValue };
}

/**
 * Add New Laptop
 */
function handleAddLaptop(payload, userEmail, userRole) {
  requireStaffPermission(userRole, "ISSUE_RETURN");
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const lapSheet = ss.getSheetByName("Laptop_Master");
  const data = lapSheet.getDataRange().getValues();

  const laptopId = (payload.laptop_id || "").trim();
  const assetTag = (payload.asset_tag || "").trim();
  const serialNo = (payload.serial_number || "").trim();
  const brand = (payload.brand || "").trim();
  const model = (payload.model || "").trim();
  const location = payload.current_location || "Lab 1 Cabinet A";

  if (!laptopId || !serialNo) throw new Error("Laptop ID and Serial Number are required.");

  for (let i = 1; i < data.length; i++) {
    if (String(data[i][0]).trim().toUpperCase() === laptopId.toUpperCase()) {
      throw new Error("Laptop_ID " + laptopId + " already exists.");
    }
  }

  const qrValue = "QR-" + laptopId;
  lapSheet.appendRow([
    laptopId, assetTag, serialNo, brand, model,
    payload.purchase_date || getCurrentKolkataDate(),
    "Good", "Available", "None", "", "", location, qrValue, payload.notes || ""
  ]);

  return { success: true, laptop_id: laptopId, qr_value: qrValue };
}

/**
 * Traceable Correction Log
 */
function handleCorrectionLog(payload, userEmail, userRole) {
  if (userRole.role !== "Admin") throw new Error("Only Admin can record traceable corrections.");
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const movSheet = ss.getSheetByName("Movement_Log");
  const movId = generateId("CORR");
  const nowTimestamp = getCurrentKolkataTimestamp();

  movSheet.appendRow([
    movId, "Staff", userRole.staff_id || "ADMIN", userRole.staff_name || "Admin",
    userEmail, "Administration", "Admin", payload.asset_type || "Laptop",
    payload.asset_id, "TRANSFER", userEmail, nowTimestamp,
    payload.from_location || "Correction", payload.to_location || "Correction",
    "ADMIN CORRECTION: " + (payload.reason || "Manual adjustment"),
    "", "", "ACKNOWLEDGED", userEmail, nowTimestamp, "",
    "Correction details: " + (payload.notes || "")
  ]);

  return { success: true, correction_id: movId, timestamp: nowTimestamp };
}

// ======================== QUERY / READ OPERATIONS ========================

function getDashboardStats(userRole, userEmail) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const lapData = ss.getSheetByName("Laptop_Master").getDataRange().getValues();
  const accData = ss.getSheetByName("Accessories_Master").getDataRange().getValues();
  const movData = ss.getSheetByName("Movement_Log").getDataRange().getValues();
  const repData = ss.getSheetByName("Repair_Log").getDataRange().getValues();

  let totalLaptops = lapData.length - 1;
  let availableLaptops = 0;
  let issuedLaptops = 0;
  let repairLaptops = 0;

  for (let i = 1; i < lapData.length; i++) {
    const s = lapData[i][7];
    if (s === "Available") availableLaptops++;
    else if (s === "Issued") issuedLaptops++;
    else if (s === "Under Repair") repairLaptops++;
  }

  let totalChargers = 0;
  let availableChargers = 0;
  let issuedChargers = 0;
  let repairChargers = 0;

  for (let i = 1; i < accData.length; i++) {
    if (accData[i][1] === "Charger") {
      totalChargers++;
      const s = accData[i][5];
      if (s === "Available") availableChargers++;
      else if (s === "Issued") issuedChargers++;
      else if (s === "Under Repair") repairChargers++;
    }
  }

  let totalRepairSpend = 0;
  for (let i = 1; i < repData.length; i++) {
    totalRepairSpend += Number(repData[i][13]) || 0;
  }

  let pendingStudentAcks = 0;
  for (let i = 1; i < movData.length; i++) {
    if (movData[i][17] === "PENDING") pendingStudentAcks++;
  }

  return {
    total_laptops: totalLaptops,
    available_laptops: availableLaptops,
    issued_laptops: issuedLaptops,
    under_repair_laptops: repairLaptops,
    total_chargers: totalChargers,
    available_chargers: availableChargers,
    issued_chargers: issuedChargers,
    under_repair_chargers: repairChargers,
    total_repair_spend_inr: totalRepairSpend,
    pending_student_acknowledgements: pendingStudentAcks,
    server_time: getCurrentKolkataTimestamp()
  };
}

function getLaptops(userRole, userEmail) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const rows = ss.getSheetByName("Laptop_Master").getDataRange().getValues();
  const headers = rows[0];
  const list = [];
  for (let i = 1; i < rows.length; i++) {
    const obj = {};
    headers.forEach((h, col) => { obj[h] = rows[i][col]; });
    list.push(obj);
  }
  return list;
}

function getAccessories(userRole, userEmail) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const rows = ss.getSheetByName("Accessories_Master").getDataRange().getValues();
  const headers = rows[0];
  const list = [];
  for (let i = 1; i < rows.length; i++) {
    const obj = {};
    headers.forEach((h, col) => { obj[h] = rows[i][col]; });
    list.push(obj);
  }
  return list;
}

function getStudents(userRole, userEmail) {
  // Students cannot access other students' personal records
  if (userRole.role === "Student") {
    throw new Error("Access denied: Students cannot browse Student_Master list.");
  }
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const rows = ss.getSheetByName("Students_Master").getDataRange().getValues();
  const headers = rows[0];
  const list = [];
  for (let i = 1; i < rows.length; i++) {
    const obj = {};
    headers.forEach((h, col) => { obj[h] = rows[i][col]; });
    list.push(obj);
  }
  return list;
}

function getStaff(userRole, userEmail) {
  if (userRole.role === "Student") {
    throw new Error("Access denied.");
  }
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const rows = ss.getSheetByName("Staff_Master").getDataRange().getValues();
  const headers = rows[0];
  const list = [];
  for (let i = 1; i < rows.length; i++) {
    const obj = {};
    headers.forEach((h, col) => { obj[h] = rows[i][col]; });
    list.push(obj);
  }
  return list;
}

function getMovementLog(userRole, userEmail) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const rows = ss.getSheetByName("Movement_Log").getDataRange().getValues();
  const headers = rows[0];
  const list = [];

  for (let i = 1; i < rows.length; i++) {
    // If student, filter only their own movements
    if (userRole.role === "Student") {
      const rowEmail = String(rows[i][4]).toLowerCase().trim();
      if (rowEmail !== userEmail) continue;
    }
    const obj = {};
    headers.forEach((h, col) => { obj[h] = rows[i][col]; });
    list.push(obj);
  }
  return list.reverse(); // Latest first
}

function getRepairLog(userRole, userEmail) {
  if (userRole.role === "Student") {
    throw new Error("Access denied.");
  }
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const rows = ss.getSheetByName("Repair_Log").getDataRange().getValues();
  const headers = rows[0];
  const list = [];
  for (let i = 1; i < rows.length; i++) {
    const obj = {};
    headers.forEach((h, col) => { obj[h] = rows[i][col]; });
    list.push(obj);
  }
  return list.reverse();
}

function getStudentMyAssets(userEmail) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const lapData = ss.getSheetByName("Laptop_Master").getDataRange().getValues();
  const movData = ss.getSheetByName("Movement_Log").getDataRange().getValues();

  const myLaptops = [];
  for (let i = 1; i < lapData.length; i++) {
    if (String(lapData[i][10]).toLowerCase().trim() === userEmail && lapData[i][7] === "Issued") {
      myLaptops.push({
        laptop_id: lapData[i][0],
        brand: lapData[i][3],
        model: lapData[i][4],
        condition: lapData[i][6],
        status: lapData[i][7],
        location: lapData[i][11]
      });
    }
  }

  const pendingAcks = [];
  for (let i = 1; i < movData.length; i++) {
    if (String(movData[i][4]).toLowerCase().trim() === userEmail && movData[i][17] === "PENDING") {
      pendingAcks.push({
        movement_id: movData[i][0],
        asset_type: movData[i][7],
        asset_id: movData[i][8],
        action: movData[i][9],
        timestamp: movData[i][11],
        operator_email: movData[i][10]
      });
    }
  }

  return { assigned_assets: myLaptops, pending_acknowledgements: pendingAcks };
}

// ======================== HELPERS ========================

function getCurrentKolkataTimestamp() {
  return Utilities.formatDate(new Date(), TIMEZONE, "yyyy-MM-dd'T'HH:mm:ssXXX");
}

function getCurrentKolkataDate() {
  return Utilities.formatDate(new Date(), TIMEZONE, "yyyy-MM-dd");
}

function generateId(prefix) {
  const rand = Math.floor(1000 + Math.random() * 9000);
  const now = Utilities.formatDate(new Date(), TIMEZONE, "yyyyMMdd-HHmmss");
  return prefix + "-" + now + "-" + rand;
}

function createJsonResponse(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
