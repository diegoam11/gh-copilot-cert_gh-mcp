import tempfile
import unittest
from pathlib import Path

from src.app import (
    ActivityRepository,
    DuplicateEnrollmentError,
    EnrollmentNotFoundError,
)


class ActivityRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.database_path = Path(tempfile.mkdtemp()) / "activities.db"

    def test_seed_data_and_enrollments_survive_repository_restart(self):
        repository = ActivityRepository(self.database_path)
        repository.signup("Chess Club", "student@mergington.edu")

        restarted_repository = ActivityRepository(self.database_path)
        chess_club = restarted_repository.get_activities()["Chess Club"]

        self.assertIn("student@mergington.edu", chess_club["participants"])

    def test_duplicate_enrollment_is_rejected_without_duplicate_rows(self):
        repository = ActivityRepository(self.database_path)
        repository.signup("Chess Club", "student@mergington.edu")

        with self.assertRaises(DuplicateEnrollmentError):
            repository.signup("Chess Club", "student@mergington.edu")

        participants = repository.get_activities()["Chess Club"]["participants"]
        self.assertEqual(participants.count("student@mergington.edu"), 1)

    def test_unregister_is_persisted(self):
        repository = ActivityRepository(self.database_path)
        repository.signup("Chess Club", "student@mergington.edu")
        repository.unregister("Chess Club", "student@mergington.edu")

        restarted_repository = ActivityRepository(self.database_path)
        participants = restarted_repository.get_activities()["Chess Club"]["participants"]
        self.assertNotIn("student@mergington.edu", participants)

        with self.assertRaises(EnrollmentNotFoundError):
            restarted_repository.unregister("Chess Club", "student@mergington.edu")


if __name__ == "__main__":
    unittest.main()
