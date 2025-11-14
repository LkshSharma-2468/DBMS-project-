# simulate_vitals.py
import mysql.connector, random, time

DB = dict(host="localhost", user="root", password="18January.", database="icu", autocommit=True)

# Ensure these PatientIDs exist in Patients table
PATIENTS = ["P101", "P102", "P103", "P104", "UNLUCKY"]
UNLUCKY_ID = "UNLUCKY"

def fetch_safe_ranges(pid):
    db = mysql.connector.connect(**DB)
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT SafeHeartRateMin, SafeHeartRateMax, SafeBPMin, SafeBPMax, SafeSpO2Min 
        FROM Patients WHERE PatientID = %s
    """, (pid,))
    row = cur.fetchone()
    cur.close(); db.close()
    return row

def insert_vitals(pid, hr, bp, spo2):
    db = mysql.connector.connect(**DB)
    cur = db.cursor()
    cur.execute("SELECT BedNo FROM Patients WHERE PatientID = %s", (pid,))
    bed = cur.fetchone()
    bedno = bed[0] if bed else None
    cur.execute("""
        INSERT INTO Vitals (PatientID, BedNo, HeartRate, BloodPressure, SpO2)
        VALUES (%s, %s, %s, %s, %s)
    """, (pid, bedno, hr, bp, spo2))
    db.commit()
    cur.close(); db.close()

def random_normal_value_for_vital(vital):
    if vital == "hr":
        return random.randint(60, 100)
    if vital == "bp":
        return random.randint(100, 130)
    if vital == "sp":
        return random.randint(95, 100)

def random_wide_value_for_vital(vital):
    if vital == "hr":
        return random.randint(40, 160)
    if vital == "bp":
        return random.randint(70, 180)
    if vital == "sp":
        return random.randint(80, 95)

if __name__ == "__main__":
    print("Simulator starting for our DBMS project. Press Ctrl+C to stop.")
    while True:
        for pid in PATIENTS:
            if pid == UNLUCKY_ID:
                safe = fetch_safe_ranges(pid)
                if safe:
                    hr = (safe['SafeHeartRateMax'] + random.randint(5, 30)
                          if random.random() < 0.5
                          else max(20, safe['SafeHeartRateMin'] - random.randint(5, 20)))
                    bp = (safe['SafeBPMax'] + random.randint(10, 60)
                          if random.random() < 0.5
                          else max(50, safe['SafeBPMin'] - random.randint(10, 30)))
                    spo2 = max(60, safe['SafeSpO2Min'] - random.randint(2, 10))
                else:
                    hr = random_wide_value_for_vital("hr")
                    bp = random_wide_value_for_vital("bp")
                    spo2 = random_wide_value_for_vital("sp")
            else:
                if random.random() < 0.15:  # occasional abnormal
                    hr = random_wide_value_for_vital("hr")
                    bp = random_wide_value_for_vital("bp")
                    spo2 = random_wide_value_for_vital("sp")
                else:
                    hr = random_normal_value_for_vital("hr")
                    bp = random_normal_value_for_vital("bp")
                    spo2 = random_normal_value_for_vital("sp")

            insert_vitals(pid, hr, bp, spo2)
            print(f"Inserted → {pid}: HR={hr}, BP={bp}, SpO2={spo2}")

        time.sleep(10)
