import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch


TEST_OTP = "123456"
_temporary_directory = tempfile.TemporaryDirectory()
_database_path = Path(_temporary_directory.name) / "email-verification.db"

with closing(sqlite3.connect(_database_path)) as connection:
    connection.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username VARCHAR(64) NOT NULL UNIQUE,
            email VARCHAR(120) NOT NULL UNIQUE,
            password_hash VARCHAR(128),
            subscription_type VARCHAR(20) NOT NULL DEFAULT 'free',
            subscription_expiry DATETIME,
            created_at DATETIME NOT NULL
        )
        """
    )
    connection.execute(
        """
        INSERT INTO users (
            username, email, subscription_type, created_at
        ) VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """,
        ("legacy-user", "legacy@example.com", "free"),
    )
    connection.commit()

os.environ["DATABASE_URL"] = f"sqlite:///{_database_path.as_posix()}"
os.environ["SECRET_KEY"] = "email-verification-test-secret"
os.environ["SMTP_HOST"] = "smtp.invalid"
os.environ["SMTP_PORT"] = "587"
os.environ["SMTP_USERNAME"] = "test-user"
os.environ["SMTP_PASSWORD"] = "test-password"
os.environ["MAIL_FROM"] = "no-reply@example.com"

import app as app_module
from models import User, db
from utils.email_verification import hash_otp


class EmailVerificationAuthTest(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        if app_module.scheduler.running:
            app_module.scheduler.shutdown(wait=False)

        with app_module.app.app_context():
            db.session.remove()
            db.engine.dispose()

        _temporary_directory.cleanup()

    def setUp(self):
        app_module.app.config.update(TESTING=True)
        self.client = app_module.app.test_client()

    def test_legacy_user_is_verified_when_email_column_is_added(self):
        # Given: a user created in the legacy schema before app import.
        with app_module.app.app_context():
            # When: the import-time compatibility migration has completed.
            legacy_user = User.query.filter_by(email="legacy@example.com").one()

            # Then: the added column preserves access for the existing user.
            self.assertTrue(legacy_user.email_verified)

    def test_registration_then_otp_verification_logs_user_in(self):
        # Given: deterministic OTP generation and a no-network email delivery seam.
        with (
            patch(
                "utils.email_verification.generate_otp",
                return_value=TEST_OTP,
            ),
            patch("utils.email_verification._send_email") as send_email,
        ):
            # When: a visitor registers through the public route.
            registration = self.client.post(
                "/register",
                data={
                    "username": "new-user",
                    "email": "new@example.com",
                    "password": "secret123",
                },
            )

            # Then: registration persists an unverified user and requests verification.
            self.assertEqual(registration.status_code, 302)
            self.assertEqual(registration.headers["Location"], "/verify-email")
            send_email.assert_called_once_with("new@example.com", TEST_OTP)

            with app_module.app.app_context():
                registered_user = User.query.filter_by(email="new@example.com").one()
                registered_user_id = registered_user.id
                self.assertFalse(registered_user.email_verified)
                self.assertEqual(
                    registered_user.otp_hash,
                    hash_otp(registered_user_id, TEST_OTP),
                )
                self.assertIsNotNone(registered_user.otp_expires_at)

            # When: the visitor submits the issued OTP.
            verification = self.client.post(
                "/verify-email",
                data={"otp": TEST_OTP},
            )

            # Then: verification logs the user in and consumes all OTP state.
            self.assertEqual(verification.status_code, 302)
            self.assertEqual(verification.headers["Location"], "/")

            with self.client.session_transaction() as session:
                self.assertEqual(session.get("_user_id"), str(registered_user_id))
                self.assertNotIn("pending_verification_user_id", session)
                self.assertNotIn("pending_verification_next", session)

            with app_module.app.app_context():
                verified_user = db.session.get(User, registered_user_id)
                self.assertTrue(verified_user.email_verified)
                self.assertIsNone(verified_user.otp_hash)
                self.assertIsNone(verified_user.otp_expires_at)
                self.assertEqual(verified_user.otp_attempts, 0)
                self.assertIsNone(verified_user.otp_last_sent_at)


if __name__ == "__main__":
    unittest.main()
