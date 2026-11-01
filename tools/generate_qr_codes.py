"""
QR Code Generator & Printable Sheet Utility
Generates printable QR asset tags and ID cards for Laptops, Chargers, Students, and Staff.
Creates a self-contained printable HTML sheet that renders high-resolution QR codes.
"""

import os
from backend.database import get_connection

OUTPUT_HTML = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "printable_qr_tags.html")

def generate_printable_sheet():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT Laptop_ID, Asset_Tag, Brand, Model, Serial_Number, QR_Value FROM Laptop_Master")
    laptops = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT Accessory_ID, Asset_Type, Specification, Serial_Number, QR_Value FROM Accessories_Master")
    accessories = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT Student_ID, Student_Name, Course_Name, Batch_Name, Student_QR_Value FROM Students_Master WHERE Active = 1")
    students = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT Staff_ID, Staff_Name, Role, Official_Gmail, Staff_QR_Value FROM Staff_Master WHERE Active = 1")
    staff = [dict(r) for r in cursor.fetchall()]

    conn.close()

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Printable Asset & Identity QR Tags - Institute Management</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
    <style>
        @media print {{
            .no-print {{ display: none !important; }}
            .page-break {{ page-break-after: always; }}
            body {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
        }}
        .tag-card {{
            width: 280px;
            height: 180px;
            border: 2px dashed #94a3b8;
            page-break-inside: avoid;
        }}
    </style>
</head>
<body class="bg-gray-100 p-6 font-sans">
    <div class="max-w-6xl mx-auto no-print mb-6 flex justify-between items-center bg-white p-4 rounded-xl shadow-sm border border-gray-200">
        <div>
            <h1 class="text-xl font-bold text-gray-800">Institute QR Label & Card Printing Centre</h1>
            <p class="text-sm text-gray-500">Print durable sticker labels for Laptops, Chargers, and Student / Staff ID Cards</p>
        </div>
        <div class="flex gap-3">
            <button onclick="window.print()" class="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium shadow flex items-center gap-2">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z"></path></svg>
                Print All Labels (Ctrl + P)
            </button>
            <a href="/" class="px-4 py-2.5 bg-gray-200 hover:bg-gray-300 text-gray-700 rounded-lg font-medium">Back to App</a>
        </div>
    </div>

    <div class="max-w-6xl mx-auto bg-white p-8 rounded-xl shadow border border-gray-200">
        <!-- Section 1: Laptops -->
        <div class="mb-10">
            <h2 class="text-lg font-bold text-blue-900 border-b pb-2 mb-4 uppercase tracking-wider flex items-center justify-between">
                <span>Laptop Asset Tags (Stick on Laptop Bottom Chassis)</span>
                <span class="text-xs bg-blue-100 text-blue-800 px-2.5 py-1 rounded-full">{len(laptops)} Devices</span>
            </h2>
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {"".join([f'''
                <div class="tag-card bg-slate-50 rounded-xl p-3 flex flex-col justify-between border-2 border-slate-300 relative overflow-hidden">
                    <div class="flex justify-between items-start border-b border-slate-200 pb-2">
                        <div>
                            <span class="text-[10px] uppercase font-bold tracking-widest text-blue-600">INSTITUTE ASSET</span>
                            <h3 class="font-bold text-gray-900 text-sm">{lap["Brand"]} {lap["Model"]}</h3>
                        </div>
                        <span class="bg-blue-600 text-white font-mono text-xs px-2 py-0.5 rounded font-bold">{lap["Laptop_ID"]}</span>
                    </div>
                    <div class="flex items-center gap-3 my-1">
                        <div id="qr-lap-{lap['Laptop_ID']}" class="w-20 h-20 bg-white p-1 rounded border"></div>
                        <div class="text-[11px] text-gray-600 space-y-0.5 font-mono">
                            <div>Tag: <b class="text-gray-900">{lap["Asset_Tag"]}</b></div>
                            <div>S/N: <b class="text-gray-900">{lap["Serial_Number"]}</b></div>
                            <div class="text-[9px] text-gray-400 mt-1">Scan for Fast Issue / Return</div>
                        </div>
                    </div>
                    <div class="text-[9px] text-center text-gray-500 border-t border-slate-200 pt-1 font-mono">
                        Property of Computer Training Institute, India
                    </div>
                </div>
                ''' for lap in laptops])}
            </div>
        </div>

        <div class="page-break"></div>

        <!-- Section 2: Chargers -->
        <div class="mb-10">
            <h2 class="text-lg font-bold text-blue-900 border-b pb-2 mb-4 uppercase tracking-wider flex items-center justify-between">
                <span>Charger & Accessory Tags (Stick on Power Adapter Brick)</span>
                <span class="text-xs bg-blue-100 text-blue-800 px-2.5 py-1 rounded-full">{len(accessories)} Chargers</span>
            </h2>
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {"".join([f'''
                <div class="tag-card bg-amber-50/50 rounded-xl p-3 flex flex-col justify-between border-2 border-amber-200 relative">
                    <div class="flex justify-between items-start border-b border-amber-200 pb-2">
                        <div>
                            <span class="text-[10px] uppercase font-bold tracking-widest text-amber-700">CHARGER ASSET</span>
                            <h3 class="font-bold text-gray-900 text-xs truncate max-w-[170px]">{acc["Specification"]}</h3>
                        </div>
                        <span class="bg-amber-600 text-white font-mono text-xs px-2 py-0.5 rounded font-bold">{acc["Accessory_ID"]}</span>
                    </div>
                    <div class="flex items-center gap-3 my-1">
                        <div id="qr-acc-{acc['Accessory_ID']}" class="w-20 h-20 bg-white p-1 rounded border"></div>
                        <div class="text-[11px] text-gray-600 space-y-0.5 font-mono">
                            <div>Type: <b class="text-gray-900">{acc["Asset_Type"]}</b></div>
                            <div>S/N: <b class="text-gray-900">{acc["Serial_Number"]}</b></div>
                            <div class="text-[9px] text-amber-600 font-bold mt-1">Bundle with Laptop</div>
                        </div>
                    </div>
                    <div class="text-[9px] text-center text-gray-500 border-t border-amber-200 pt-1 font-mono">
                        Return with Laptop at counter
                    </div>
                </div>
                ''' for acc in accessories])}
            </div>
        </div>

        <div class="page-break"></div>

        <!-- Section 3: Student Cards -->
        <div class="mb-10">
            <h2 class="text-lg font-bold text-blue-900 border-b pb-2 mb-4 uppercase tracking-wider flex items-center justify-between">
                <span>Student Identity Cards (Counter Quick-Scan)</span>
                <span class="text-xs bg-emerald-100 text-emerald-800 px-2.5 py-1 rounded-full">{len(students)} Students</span>
            </h2>
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {"".join([f'''
                <div class="tag-card bg-emerald-50/40 rounded-xl p-3 flex flex-col justify-between border-2 border-emerald-300 relative">
                    <div class="flex justify-between items-start border-b border-emerald-200 pb-2">
                        <div>
                            <span class="text-[10px] uppercase font-bold tracking-widest text-emerald-700">STUDENT PASS</span>
                            <h3 class="font-bold text-gray-900 text-sm">{stu["Student_Name"]}</h3>
                        </div>
                        <span class="bg-emerald-600 text-white font-mono text-xs px-2 py-0.5 rounded font-bold">{stu["Student_ID"]}</span>
                    </div>
                    <div class="flex items-center gap-3 my-1">
                        <div id="qr-stu-{stu['Student_ID']}" class="w-20 h-20 bg-white p-1 rounded border"></div>
                        <div class="text-[11px] text-gray-600 space-y-0.5">
                            <div class="text-xs font-semibold text-gray-800">{stu["Course_Name"]}</div>
                            <div class="text-[10px] text-emerald-800 font-mono bg-emerald-100 px-1.5 py-0.5 rounded inline-block">{stu["Batch_Name"]}</div>
                        </div>
                    </div>
                    <div class="text-[9px] text-center text-gray-500 border-t border-emerald-200 pt-1">
                        Present this pass at counter for Laptop issuance
                    </div>
                </div>
                ''' for stu in students])}
            </div>
        </div>
    </div>

    <script>
        window.addEventListener('DOMContentLoaded', () => {{
            // Render Laptop QRs
            {";".join([f'new QRCode(document.getElementById("qr-lap-{lap["Laptop_ID"]}"), {{ text: "{lap["QR_Value"]}", width: 80, height: 80 }})' for lap in laptops])};
            
            // Render Charger QRs
            {";".join([f'new QRCode(document.getElementById("qr-acc-{acc["Accessory_ID"]}"), {{ text: "{acc["QR_Value"]}", width: 80, height: 80 }})' for acc in accessories])};

            // Render Student QRs
            {";".join([f'new QRCode(document.getElementById("qr-stu-{stu["Student_ID"]}"), {{ text: "{stu["Student_QR_Value"]}", width: 80, height: 80 }})' for stu in students])};
        }});
    </script>
</body>
</html>
"""
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Printable QR tag sheet created at: {OUTPUT_HTML}")

if __name__ == "__main__":
    generate_printable_sheet()
