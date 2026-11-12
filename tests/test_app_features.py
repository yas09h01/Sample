import sqlite3

import pandas as pd

import app as tracker


def set_up_test_db(tmp_path, monkeypatch):
    db_path = tmp_path / "placements.db"
    monkeypatch.setattr(tracker, "DATABASE_PATH", db_path)

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE applications (
                application_id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                job_role TEXT NOT NULL,
                application_date TEXT,
                interview_date TEXT,
                status TEXT
            )
            """
        )
        connection.execute(
            """
            INSERT INTO applications (company_name, job_role, application_date, interview_date, status)
            VALUES
                ('Acme Corp', 'Data Analyst', '2026-11-01', '2026-11-15', 'Interview Scheduled'),
                ('Beta Labs', 'Software Engineer', '2026-11-02', NULL, 'Applied'),
                ('Gamma Inc', 'Frontend Engineer', '2026-11-03', '2026-11-18', 'Interview Scheduled')
            """
        )
        connection.commit()


def test_search_and_status_filter(tmp_path, monkeypatch):
    set_up_test_db(tmp_path, monkeypatch)

    applications, _, _ = tracker.get_applications("acme", "Interview Scheduled")

    assert len(applications) == 1
    assert applications[0]["company_name"] == "Acme Corp"


def test_update_application_status_and_interview_date(tmp_path, monkeypatch):
    set_up_test_db(tmp_path, monkeypatch)

    tracker.update_application_status(2, "Rejected", "2026-11-12")
    applications, _, _ = tracker.get_applications()

    updated = next(item for item in applications if item["application_id"] == 2)
    assert updated["status"] == "Rejected"
    assert updated["interview_date"] == "2026-11-12"


def test_delete_application(tmp_path, monkeypatch):
    set_up_test_db(tmp_path, monkeypatch)

    tracker.delete_application(1)
    applications, _, _ = tracker.get_applications()

    assert all(item["application_id"] != 1 for item in applications)


def test_export_applications_csv(tmp_path, monkeypatch):
    set_up_test_db(tmp_path, monkeypatch)

    csv_data = tracker.export_applications_csv()
    dataframe = pd.read_csv(csv_data)

    assert list(dataframe.columns) == [
        "application_id",
        "company_name",
        "job_role",
        "application_date",
        "interview_date",
        "status",
    ]
    assert len(dataframe) == 3
