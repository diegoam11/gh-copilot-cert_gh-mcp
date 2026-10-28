"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles


SAMPLE_ACTIVITIES = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"],
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"],
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"],
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"],
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"],
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"],
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"],
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"],
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"],
    },
}


class ActivityNotFoundError(Exception):
    """Raised when an activity name is not in the database."""


class EnrollmentNotFoundError(Exception):
    """Raised when a student is not enrolled in an activity."""


class DuplicateEnrollmentError(Exception):
    """Raised when a student is already enrolled in an activity."""


class ActivityRepository:
    """SQLite-backed storage for activities and student enrollments."""

    def __init__(self, database_path: Path):
        self.database_path = database_path
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS activities (
                    name TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    schedule TEXT NOT NULL,
                    max_participants INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS enrollments (
                    activity_name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    PRIMARY KEY (activity_name, email),
                    FOREIGN KEY (activity_name) REFERENCES activities(name)
                        ON DELETE CASCADE
                );
                """
            )
            if connection.execute("SELECT 1 FROM activities LIMIT 1").fetchone() is None:
                for name, activity in SAMPLE_ACTIVITIES.items():
                    connection.execute(
                        """
                        INSERT INTO activities
                            (name, description, schedule, max_participants)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            name,
                            activity["description"],
                            activity["schedule"],
                            activity["max_participants"],
                        ),
                    )
                    connection.executemany(
                        "INSERT INTO enrollments (activity_name, email) VALUES (?, ?)",
                        [(name, email) for email in activity["participants"]],
                    )

    def get_activities(self) -> dict[str, dict[str, Any]]:
        with self._connection() as connection:
            activities = connection.execute(
                "SELECT name, description, schedule, max_participants "
                "FROM activities ORDER BY rowid"
            ).fetchall()
            enrollments = connection.execute(
                "SELECT activity_name, email FROM enrollments ORDER BY rowid"
            ).fetchall()

        participants_by_activity: dict[str, list[str]] = {
            activity["name"]: [] for activity in activities
        }
        for enrollment in enrollments:
            participants_by_activity[enrollment["activity_name"]].append(
                enrollment["email"]
            )

        return {
            activity["name"]: {
                "description": activity["description"],
                "schedule": activity["schedule"],
                "max_participants": activity["max_participants"],
                "participants": participants_by_activity[activity["name"]],
            }
            for activity in activities
        }

    def signup(self, activity_name: str, email: str) -> None:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if not self._activity_exists(connection, activity_name):
                raise ActivityNotFoundError
            if connection.execute(
                """
                SELECT 1 FROM enrollments
                WHERE activity_name = ? AND email = ?
                """,
                (activity_name, email),
            ).fetchone():
                raise DuplicateEnrollmentError
            connection.execute(
                "INSERT INTO enrollments (activity_name, email) VALUES (?, ?)",
                (activity_name, email),
            )

    def unregister(self, activity_name: str, email: str) -> None:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if not self._activity_exists(connection, activity_name):
                raise ActivityNotFoundError
            result = connection.execute(
                "DELETE FROM enrollments WHERE activity_name = ? AND email = ?",
                (activity_name, email),
            )
            if result.rowcount == 0:
                raise EnrollmentNotFoundError

    @staticmethod
    def _activity_exists(connection: sqlite3.Connection, activity_name: str) -> bool:
        return connection.execute(
            "SELECT 1 FROM activities WHERE name = ?", (activity_name,)
        ).fetchone() is not None


def create_app(database_path: Path | None = None) -> FastAPI:
    if database_path is None:
        database_path = Path(
            os.getenv("ACTIVITY_DATABASE_PATH", str(Path(__file__).with_name("activities.db")))
        )
    repository = ActivityRepository(database_path)
    application = FastAPI(
        title="Mergington High School API",
        description="API for viewing and signing up for extracurricular activities",
    )
    application.mount(
        "/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static"
    )

    @application.get("/")
    def root():
        return RedirectResponse(url="/static/index.html")

    @application.get("/activities")
    def get_activities():
        return repository.get_activities()

    @application.post("/activities/{activity_name}/signup")
    def signup_for_activity(activity_name: str, email: str):
        try:
            repository.signup(activity_name, email)
        except ActivityNotFoundError:
            raise HTTPException(status_code=404, detail="Activity not found")
        except DuplicateEnrollmentError:
            raise HTTPException(status_code=400, detail="Student is already signed up")
        return {"message": f"Signed up {email} for {activity_name}"}

    @application.delete("/activities/{activity_name}/unregister")
    def unregister_from_activity(activity_name: str, email: str):
        try:
            repository.unregister(activity_name, email)
        except ActivityNotFoundError:
            raise HTTPException(status_code=404, detail="Activity not found")
        except EnrollmentNotFoundError:
            raise HTTPException(
                status_code=400,
                detail="Student is not signed up for this activity",
            )
        return {"message": f"Unregistered {email} from {activity_name}"}

    return application


app = create_app()
