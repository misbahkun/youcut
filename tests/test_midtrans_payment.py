import hashlib
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch


_temporary_directory = tempfile.TemporaryDirectory()
_database_path = Path(_temporary_directory.name) / "midtrans-payment.db"

os.environ.setdefault("DATABASE_URL", f"sqlite:///{_database_path.as_posix()}")
os.environ.setdefault("SECRET_KEY", "midtrans-payment-test-secret")
os.environ.setdefault("MIDTRANS_MERCHANT_ID", "G123456789")
os.environ.setdefault("MIDTRANS_CLIENT_KEY", "SB-Mid-client-test")
os.environ.setdefault("MIDTRANS_SERVER_KEY", "SB-Mid-server-test")

import app as app_module
from models import Payment, User, db


SERVER_KEY = "SB-Mid-server-test"


class MidtransPaymentTest(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        if app_module.scheduler.running:
            app_module.scheduler.shutdown(wait=False)

        with app_module.app.app_context():
            db.session.remove()
            db.engine.dispose()

        _temporary_directory.cleanup()

    def setUp(self):
        app_module.app.config.update(
            TESTING=True,
            MIDTRANS_MERCHANT_ID="G123456789",
            MIDTRANS_CLIENT_KEY="SB-Mid-client-test",
            MIDTRANS_SERVER_KEY=SERVER_KEY,
            APP_BASE_URL="https://youcut.example",
        )
        self.client = app_module.app.test_client()

        with app_module.app.app_context():
            Path(db.engine.url.database).parent.mkdir(parents=True, exist_ok=True)
            db.create_all()
            Payment.query.delete()
            User.query.filter(User.email.like("midtrans-%@example.com")).delete(
                synchronize_session=False
            )
            user = User(
                username=f"midtrans-{id(self)}",
                email=f"midtrans-{id(self)}@example.com",
                email_verified=True,
            )
            db.session.add(user)
            db.session.commit()
            self.user_id = user.id

        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.user_id)
            session["_fresh"] = True

    def _snap_response(self, token="snap-token"):
        response = Mock()
        response.ok = True
        response.status_code = 201
        response.json.return_value = {"token": token}
        return response

    def _create_payment(self, plan="basic"):
        with patch("app.requests.post", return_value=self._snap_response()) as post:
            response = self.client.post("/api/create-payment", json={"plan": plan})
        return response, post

    def _notification(self, payment, status="settlement", **overrides):
        payload = {
            "order_id": payment.order_id,
            "status_code": "200",
            "gross_amount": f"{payment.gross_amount:.2f}",
            "transaction_status": status,
            "transaction_id": "midtrans-transaction-1",
            "fraud_status": "accept",
        }
        payload.update(overrides)
        payload["signature_key"] = hashlib.sha512(
            (
                payload["order_id"]
                + payload["status_code"]
                + payload["gross_amount"]
                + SERVER_KEY
            ).encode()
        ).hexdigest()
        return payload

    def _status_response(self, payload, **overrides):
        response = Mock()
        response.ok = True
        response.status_code = 200
        response.json.return_value = {**payload, **overrides}
        return response

    def test_checkout_success_persists_pending_payment_after_snap_token(self):
        response, post = self._create_payment("basic")

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["snap_token"], "snap-token")
        self.assertTrue(body["success"])

        with app_module.app.app_context():
            payment = Payment.query.filter_by(order_id=body["order_id"]).one()
            self.assertEqual(payment.user_id, self.user_id)
            self.assertEqual(payment.plan, "basic")
            self.assertEqual(payment.gross_amount, 29000)
            self.assertEqual(payment.status, "pending")

        request_kwargs = post.call_args.kwargs
        self.assertEqual(request_kwargs["auth"], (SERVER_KEY, ""))
        self.assertEqual(request_kwargs["timeout"], 15)
        payload = request_kwargs["json"]
        self.assertEqual(payload["transaction_details"]["gross_amount"], 29000)
        self.assertEqual(len(payload["item_details"]), 1)
        self.assertEqual(payload["customer_details"]["email"], f"midtrans-{id(self)}@example.com")
        self.assertEqual(
            payload["callbacks"]["finish"],
            "https://youcut.example/pricing?payment=finish",
        )

    def test_checkout_rejects_invalid_plan(self):
        with patch("app.requests.post") as post:
            response = self.client.post("/api/create-payment", json={"plan": "gold"})

        self.assertEqual(response.status_code, 400)
        post.assert_not_called()

    def test_checkout_rejects_active_paid_plan(self):
        with app_module.app.app_context():
            user = db.session.get(User, self.user_id)
            user.subscription_type = "pro"
            user.subscription_expiry = datetime.utcnow() + timedelta(days=1)
            db.session.commit()

        with patch("app.requests.post") as post:
            response = self.client.post("/api/create-payment", json={"plan": "basic"})

        self.assertEqual(response.status_code, 409)
        post.assert_not_called()

    def test_webhook_rejects_invalid_signature_without_status_lookup(self):
        self._create_payment()
        with app_module.app.app_context():
            payment = Payment.query.one()
            payload = self._notification(payment)
        payload["signature_key"] = "invalid"

        with patch("app.requests.get") as get:
            response = self.client.post("/webhooks/midtrans", json=payload)

        self.assertEqual(response.status_code, 401)
        get.assert_not_called()

    def test_settlement_activates_plan_for_30_days(self):
        self._create_payment("pro")
        with app_module.app.app_context():
            payment = Payment.query.one()
            payload = self._notification(payment)
            order_id = payment.order_id

        with patch(
            "app.requests.get",
            return_value=self._status_response(payload),
        ) as get:
            response = self.client.post("/webhooks/midtrans", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertIn(order_id, get.call_args.args[0])
        self.assertEqual(get.call_args.kwargs["auth"], (SERVER_KEY, ""))

        with app_module.app.app_context():
            payment = Payment.query.one()
            user = db.session.get(User, self.user_id)
            self.assertEqual(payment.status, "settlement")
            self.assertEqual(payment.midtrans_id, "midtrans-transaction-1")
            self.assertEqual(user.subscription_type, "pro")
            remaining = user.subscription_expiry - datetime.utcnow()
            self.assertGreater(remaining, timedelta(days=29, hours=23))
            self.assertLessEqual(remaining, timedelta(days=30))

    def test_settlement_replay_does_not_extend_expiry(self):
        self._create_payment()
        with app_module.app.app_context():
            payload = self._notification(Payment.query.one())

        status_response = self._status_response(payload)
        with patch("app.requests.get", return_value=status_response):
            first = self.client.post("/webhooks/midtrans", json=payload)
            with app_module.app.app_context():
                first_expiry = db.session.get(User, self.user_id).subscription_expiry
            replay = self.client.post("/webhooks/midtrans", json=payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(replay.status_code, 200)
        with app_module.app.app_context():
            self.assertEqual(
                db.session.get(User, self.user_id).subscription_expiry,
                first_expiry,
            )

    def test_terminal_status_updates_payment_without_activation(self):
        self._create_payment()
        for terminal_status in ("deny", "cancel", "expire", "failure"):
            with self.subTest(terminal_status=terminal_status):
                with app_module.app.app_context():
                    payload = self._notification(
                        Payment.query.one(),
                        status=terminal_status,
                    )

                with patch(
                    "app.requests.get",
                    return_value=self._status_response(payload),
                ):
                    response = self.client.post("/webhooks/midtrans", json=payload)

                self.assertEqual(response.status_code, 200)
                with app_module.app.app_context():
                    self.assertEqual(Payment.query.one().status, terminal_status)
                    self.assertEqual(
                        db.session.get(User, self.user_id).subscription_type,
                        "free",
                    )

    def test_terminal_notification_does_not_downgrade_settled_payment(self):
        self._create_payment()
        with app_module.app.app_context():
            payment = Payment.query.one()
            settled_payload = self._notification(payment)
            terminal_payload = self._notification(payment, status="cancel")

        with patch(
            "app.requests.get",
            side_effect=(
                self._status_response(settled_payload),
                self._status_response(terminal_payload),
            ),
        ):
            self.client.post("/webhooks/midtrans", json=settled_payload)
            with app_module.app.app_context():
                settled_expiry = db.session.get(User, self.user_id).subscription_expiry
            response = self.client.post("/webhooks/midtrans", json=terminal_payload)

        self.assertEqual(response.status_code, 200)
        with app_module.app.app_context():
            self.assertEqual(Payment.query.one().status, "settlement")
            self.assertEqual(
                db.session.get(User, self.user_id).subscription_expiry,
                settled_expiry,
            )

    def test_webhook_rejects_confirmed_amount_or_order_mismatch(self):
        self._create_payment()
        with app_module.app.app_context():
            payload = self._notification(Payment.query.one())

        mismatches = (
            {"gross_amount": "59000.00"},
            {"order_id": "YC-999-basic-other"},
        )
        for mismatch in mismatches:
            with self.subTest(mismatch=mismatch):
                with patch(
                    "app.requests.get",
                    return_value=self._status_response(payload, **mismatch),
                ):
                    response = self.client.post("/webhooks/midtrans", json=payload)
                self.assertEqual(response.status_code, 400)

        with app_module.app.app_context():
            self.assertEqual(Payment.query.one().status, "pending")
            self.assertEqual(db.session.get(User, self.user_id).subscription_type, "free")


if __name__ == "__main__":
    unittest.main()
