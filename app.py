# app.py
import datetime
from flask import Flask, request, render_template, redirect, url_for, session, jsonify
import mysql.connector, os, threading, time

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.urandom(24)

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "18January.",
    "database": "icu",   
    "autocommit": True
    
}

def get_db():
    return mysql.connector.connect(**DB_CONFIG)

# ---------- AUTH / LOGIN ----------

@app.route("/")
def index():
    return render_template("login.html", error=None)

#Login starts
@app.route("/login/staff", methods=["POST"])
def login_staff():
    staffid = request.form.get("staffid")
    password = request.form.get("password")
    role_btn = request.form.get("role")  # 'staff' or 'admin'
    db = get_db(); cur = db.cursor(dictionary=True, buffered=True)
    if role_btn == "admin":
        cur.execute("SELECT * FROM `Admin` WHERE AdminID = %s AND Password = %s", (staffid, password))
        admin = cur.fetchone()
        cur.close(); db.close()
        if admin:
            session["user_type"] = "admin"
            session["admin_id"] = admin["AdminID"]
            return redirect(url_for("admin_page"))
        else:
            return render_template("login.html", error="Invalid admin credentials")
    # Normal staff login
    cur.execute("SELECT * FROM Staff WHERE StaffID = %s AND Password = %s", (staffid, password))
    staff = cur.fetchone()
    cur.close(); db.close()
    if not staff:
        return render_template("login.html", error="Invalid staff credentials")
    session["user_type"] = "staff"
    session["staff_id"] = staff["StaffID"]
    return redirect(url_for("staff_page"))

# Family login
@app.route("/login/family", methods=["POST"])
def login_family():
    fname = request.form.get("fname")
    fid = request.form.get("familyid")
    password = request.form.get("fpassword")
    db = get_db(); cur = db.cursor(dictionary=True, buffered=True)
    cur.execute("""
        SELECT * FROM FamilyAccess 
        WHERE FamilyID = %s AND FamilyMemberName = %s AND Password = %s
    """, (fid, fname, password))
    fam = cur.fetchone()
    cur.close(); db.close()
    if not fam:
        return render_template("login.html", error="Invalid family credentials")
    session["user_type"] = "family"
    session["family_id"] = fam["FamilyID"]
    session["family_email"] = fam.get("Email")
    return redirect(url_for("family_page"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# ---------- PAGES ----------

@app.route("/admin")
def admin_page():
    if session.get("user_type") != "admin":
        return redirect(url_for("index"))
    return render_template("admin.html")

@app.route("/staff")
def staff_page():
    if session.get("user_type") != "staff":
        return redirect(url_for("index"))
    return render_template("staff.html")

@app.route("/family")
def family_page():
    if session.get("user_type") != "family":
        return redirect(url_for("index"))
    return render_template("family.html")

# ---------- API ENDPOINTS ----------

# 1) Active alerts for admin
@app.route("/api/active_alerts")
def api_active_alerts():
    if session.get("user_type") not in ("admin", "staff"):
        return jsonify([]), 403

    db = get_db()
    cur = db.cursor(dictionary=True, buffered=True)
    query = """
    SELECT a_latest.AlertID, a_latest.PatientID, CONCAT(p.FirstName,' ',p.LastName) AS PatientName,
           p.BedNo,
           v.HeartRate, v.BloodPressure, v.SpO2, v.TimeStamp AS VitalTime,
           a_latest.AlertMessage, a_latest.AlertTime
    FROM Patients p
    JOIN (
        SELECT a1.* FROM Alerts a1
        JOIN (
            SELECT PatientID, MAX(AlertID) AS maxAid
            FROM Alerts
            WHERE IsAcknowledged = 0
            GROUP BY PatientID
        ) t ON a1.PatientID = t.PatientID AND a1.AlertID = t.maxAid
    ) a_latest ON p.PatientID = a_latest.PatientID
    JOIN Vitals v ON a_latest.VitalID = v.VitalID
    ORDER BY a_latest.AlertTime DESC;
    """
    cur.execute(query)
    rows = cur.fetchall()
    for r in rows:
        for key in ("VitalTime", "AlertTime"):
            if key in r and r[key] is not None:
                if isinstance(r[key], (datetime.datetime, datetime.date)):
                    r[key] = r[key].isoformat()
                elif isinstance(r[key], datetime.timedelta):
                    r[key] = str(r[key])
    cur.close(); db.close()
    return jsonify(rows)

# 2) Acknowledge alert
@app.route("/api/ack_patient", methods=["POST"])
def api_ack_patient():
    if session.get("user_type") not in ("admin","staff"):
        return jsonify({"status":"error"}), 403
    patient_id = request.json.get("patient_id")
    db = get_db(); cur = db.cursor()
    cur.execute("UPDATE Alerts SET IsAcknowledged = 1 WHERE PatientID = %s", (patient_id,))
    db.commit(); cur.close(); db.close()
    return jsonify({"status":"ok"})

# 3) Staff: fetch assigned patients
@app.route("/api/staff/patients")
def api_staff_patients():
    if session.get("user_type") != "staff":
        return jsonify([]), 403
    sid = session.get("staff_id")
    db = get_db(); cur = db.cursor(dictionary=True, buffered=True)
    cur.execute("SELECT AssignedPatientID FROM Staff WHERE StaffID = %s", (sid,))
    assigned = [r["AssignedPatientID"] for r in cur.fetchall()]
    if not assigned:
        cur.close(); db.close()
        return jsonify([])
    format_ids = ",".join(["%s"]*len(assigned))
    query = f"""
    SELECT p.PatientID, CONCAT(p.FirstName,' ',p.LastName) AS PatientName, p.BedNo,
           v.HeartRate, v.BloodPressure, v.SpO2, v.TimeStamp AS LastUpdated,
           CASE WHEN EXISTS (SELECT 1 FROM Alerts a WHERE a.PatientID = p.PatientID AND a.IsAcknowledged = 0) THEN 1 ELSE 0 END AS HasActiveAlert
    FROM Patients p
    LEFT JOIN Vitals v ON v.PatientID = p.PatientID
    WHERE p.PatientID IN ({format_ids})
      AND v.TimeStamp = (SELECT MAX(v2.TimeStamp) FROM Vitals v2 WHERE v2.PatientID = p.PatientID)
    """
    cur.execute(query, assigned)
    rows = cur.fetchall()
    cur.close(); db.close()
    return jsonify(rows)

# 4) Insert vitals
@app.route("/api/insert_vitals", methods=["POST"])
def api_insert_vitals():
    if session.get("user_type") not in ("staff","admin") and request.remote_addr != "127.0.0.1":
        return jsonify({"status":"error","msg":"not authorized"}), 403
    data = request.get_json()
    patient_id = data.get("patientID")
    heartRate = data.get("heartRate")
    bloodPressure = data.get("bloodPressure")
    spo2 = data.get("spo2")
    db = get_db(); cur = db.cursor()
    cur.execute("INSERT INTO Vitals (PatientID, BedNo, HeartRate, BloodPressure, SpO2) VALUES (%s,%s,%s,%s,%s)",
                (patient_id, get_bedno(patient_id), heartRate, bloodPressure, spo2))
    db.commit(); cur.close(); db.close()
    return jsonify({"status":"ok"})

def get_bedno(pid):
    db = get_db(); cur = db.cursor()
    cur.execute("SELECT BedNo FROM Patients WHERE PatientID = %s", (pid,))
    r = cur.fetchone()
    cur.close(); db.close()
    return r[0] if r else None

# 5) Family: fetch latest 5 patient vitals + alerts
@app.route("/api/family/patient_details")
def api_family_patient_details():
    if session.get("user_type") != "family":
        return jsonify({"status":"error"}), 403
    fid = session.get("family_id")
    db = get_db(); cur = db.cursor(dictionary=True, buffered=True)
    cur.execute("""
        SELECT * 
        FROM FamilyPortal 
        WHERE FamilyID = %s 
        ORDER BY LastUpdated DESC
        LIMIT 5
    """, (fid,))
    rows = cur.fetchall()
    for r in rows:
        for key in ("LastUpdated", "AlertTime"):
            if key in r and r[key] is not None:
                r[key] = r[key].isoformat() if isinstance(r[key], (datetime.datetime, datetime.date)) else str(r[key])
    cur.close(); db.close()
    return jsonify(rows)


if __name__ == "__main__":
    app.run(debug=True)
