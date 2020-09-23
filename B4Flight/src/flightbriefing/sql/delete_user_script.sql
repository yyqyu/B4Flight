SELECT Users.UserID, Username, Email, COUNT(*) as Flight_Plans
FROM Users LEFT JOIN FlightPlans ON Users.UserID = FlightPlans.UserID
GROUP BY Users.UserID, Username, Email;

SET @userid = xxxx;

START TRANSACTION;

DELETE FROM UserSettings WHERE UserID = @userid;
DELETE FROM UserHiddenNotams WHERE UserID = @userid;
DELETE FROM UserHiddenNotams WHERE UserID = @userid;
DELETE FROM FlightPlanPoints WHERE FlightplanID IN (SELECT FlightplanID FROM FlightPlans WHERE UserID = @userid);
DELETE FROM FlightPlans WHERE UserID = @userid;
DELETE FROM Users WHERE UserID = @userid;

SELECT Users.UserID, Username, Email, COUNT(*) as Flight_Plans
FROM Users LEFT JOIN FlightPlans ON Users.UserID = FlightPlans.UserID
WHERE Users.UserID = @userid
GROUP BY Users.UserID, Username, Email;

--COMMIT