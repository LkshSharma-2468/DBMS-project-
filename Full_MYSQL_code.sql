create database icu;
use icu;
create table Patients (
	PatientID varchar(20) PRIMARY KEY, 
    FirstName varchar(50),
	MiddleName varchar(50),
	LastName varchar(50),
    Age int,
	BedNo int UNIQUE,
    Gender varchar(10), 
    SafeHeartRateMin int,
    SafeHeartRateMax int,
    SafeBPMin int,
    SafeBPMax int, 
    SafeSpO2Min int);
create table Vitals(
	VitalID int AUTO_INCREMENT PRIMARY KEY,
    PatientID varchar(20),
	BedNo int,
    HeartRate int CHECK (HeartRate>0), 
    BloodPressure int CHECK (BloodPressure>0), 
    SpO2 int CHECK (SpO2 BETWEEN 0 and 100),
    TimeStamp datetime DEFAULT NOW(),
    FOREIGN KEY (PatientID) REFERENCES Patients(PatientID) ON DELETE CASCADE);
create table Alerts (
	AlertID int AUTO_INCREMENT PRIMARY KEY,
    PatientID varchar(20),
    VitalID int,
    AlertMessage varchar(255),
    AlertTime time,							-- Have to set alert time = TIME(Timestamp of vital table of that record which was abnormal)
    IsAcknowledged int DEFAULT 0,
    FOREIGN KEY (PatientID) REFERENCES Patients(PatientID) ON DELETE CASCADE,
    FOREIGN KEY (VitalID) REFERENCES Vitals(VitalID) ON DELETE CASCADE);
CREATE TABLE `Admin` (
    AdminID VARCHAR(20) PRIMARY KEY,
    Email VARCHAR(50) UNIQUE,
    Password VARCHAR(255)
);
CREATE TABLE Staff (
	SNo int AUTO_INCREMENT PRIMARY KEY,
    StaffID VARCHAR(20),
    FirstName VARCHAR(20),
    LastName VARCHAR(20),
    Email VARCHAR(50),
    Password VARCHAR(255),                         
    Phone VARCHAR(10),
    AssignedPatientID VARCHAR(20),
    FOREIGN KEY (AssignedPatientID) REFERENCES Patients(PatientID) ON DELETE CASCADE
);
-- comment for arush
/* For limited viewing --> Families = see their own patient's vitals 
  AccessID = SerialNo for table
  FamilyID = Assigned to a member but wrt the particular case. Will change for the same person with different cases. UNIQUE. Also will help in joins for views
  Multiple family members can be there for same patient- diff FamilyID- same patientID.
*/
CREATE TABLE FamilyAccess (
    AccessID INT AUTO_INCREMENT PRIMARY KEY,
    FamilyID VARCHAR(20) UNIQUE,
    FamilyMemberName VARCHAR(50),
    Email VARCHAR(50),
    Password VARCHAR(255),
    PatientID VARCHAR(20),
    FOREIGN KEY (PatientID) REFERENCES Patients(PatientID) ON DELETE CASCADE
);

-- Display linked vitals + alerts per family
CREATE VIEW FamilyPortal AS
SELECT 
    f.FamilyID,
    f.FamilyMemberName,
    f.Email,
    p.PatientID,
    CONCAT(p.FirstName, ' ', p.LastName) AS PatientName,
    p.BedNo,
    v.HeartRate,
    v.BloodPressure,
    v.SpO2,
    v.TimeStamp AS LastUpdated,
    a.AlertMessage,
    a.AlertTime
FROM FamilyAccess f
JOIN Patients p ON f.PatientID = p.PatientID
LEFT JOIN Vitals v ON p.PatientID = v.PatientID
LEFT JOIN Alerts a ON v.VitalID = a.VitalID
ORDER BY v.TimeStamp DESC;

-- Procedure
delimiter //

CREATE PROCEDURE chkAndInsert (
	IN v_patientID varchar(20),
	IN v_bedno int,
    IN v_vitalID int,
    IN v_heartRate int,
    IN v_bloodPressure int,
    IN v_spO2 int,
    IN v_timestamp datetime 
    )
BEGIN
	DECLARE hrMin, hrMax, bpMin, bpMax, spo2Min int;
    -- Safe limits
	SELECT SafeHeartRateMin, SafeHeartRateMax, SafeBPMin, SafeBPMax, SafeSpO2Min
    INTO hrMin, hrMax, bpMin, bpMax, spo2Min
    FROM Patients
    WHERE PatientID = v_patientID;
    -- Heart Rate checkup
    IF (v_heartRate < hrMin OR v_heartRate > hrMax) THEN
        INSERT INTO Alerts (PatientID, VitalID, AlertMessage, AlertTime)
        VALUES (v_patientID, v_vitalID, CONCAT('Abnormal Heart Rate: ', v_heartRate, '#',hrMin,'#',hrMax,' BedNo: ', v_bedno), TIME(v_timeStamp));		-- Time function ka use because timestamp is datetime
    END IF;
    -- Blood Pressure checkup
    IF (v_bloodPressure < bpMin OR v_bloodPressure > bpMax) THEN
        INSERT INTO Alerts (PatientID, VitalID, AlertMessage, AlertTime)
        VALUES (v_patientID, v_vitalID, CONCAT('Abnormal Blood Pressure: ', v_bloodPressure,'#',bpMin,'#',bpMax, ' BedNo: ', v_bedno), TIME(v_timeStamp));
    END IF;
    -- SpO2 checkup
    IF (v_spo2 < spo2Min) THEN
        INSERT INTO Alerts (PatientID, VitalID, AlertMessage, AlertTime)
        VALUES (v_patientID, v_vitalID, CONCAT('Low SpO2 level: ', v_spo2,'#',spo2Min,'%',' BedNo: ', v_bedno), TIME(v_timeStamp));
    END IF;
END //
delimiter ;

-- Trigger
delimiter //
create trigger check_vitals
after insert on vitals
for each row
begin 
	call chkAndInsert (
		new.PatientID, new.BedNo, new.VitalID, new.HeartRate, new.BloodPressure, new.SpO2, new.TimeStamp);
end //
delimiter ;

delimiter //
CREATE PROCEDURE family_fetch_details(IN famEmail VARCHAR(50))
BEGIN
    SELECT 
        PatientName,
        BedNo,
        HeartRate,
        BloodPressure,
        SpO2,
        AlertMessage,
        AlertTime
    FROM FamilyPortal
    WHERE Email = famEmail
    ORDER BY LastUpdated DESC
    LIMIT 5;
END;
//
delimiter ;

-- Vital Readings store for the last 2 minutes per patient in our project.
delimiter //
CREATE TRIGGER limit_vitals_perPatient
AFTER INSERT ON Vitals
FOR EACH ROW
BEGIN
	DECLARE counter INT;
    SELECT COUNT(*) INTO counter FROM Vitals WHERE PatientID = NEW.PatientID;
    IF counter > 120 THEN
        DELETE FROM Vitals
        WHERE PatientID = NEW.PatientID
        ORDER BY TimeStamp ASC
        LIMIT 1;
    END IF;
END;
//
delimiter ;
