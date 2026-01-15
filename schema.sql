DROP TABLE IF EXISTS payslips;

CREATE TABLE payslips (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  filename TEXT NOT NULL,
  month INTEGER,
  year INTEGER,
  net_income REAL,
  meal_allowance REAL,
  worked_days INTEGER,
  uploaded_at TIMESTAMP NOT NULL
);
