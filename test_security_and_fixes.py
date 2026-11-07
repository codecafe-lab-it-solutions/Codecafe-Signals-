"""TDD Security & Integration Test Suite.
Verifies all Phase 2 security, risk engine enforcement, multi-tenant isolation,
session revocation, rate limiting, and HTTP security headers.
"""
import asyncio
import os
import time
from starlette.testclient import TestClient

import auth
from broker import get_broker
import dashboard_server
import db
import paper
from risk_engine import RiskEngine

client = TestClient(dashboard_server.app)


def test_session_invalidation_on_password_change():
    """Verify that changing a password immediately revokes all prior session tokens."""
    username = "test_user_session"
    pw1 = "InitialPassword123"
    pw2 = "UpdatedPassword456"

    # Setup user
    if username in auth.users():
        auth.delete_user(username)
    auth.create_user(username, pw1, "client")

    # Issue token with initial password
    token1 = auth.make_token(username)
    assert auth.read_token(token1) == (username, "client"), "Initial token must be valid"

    # Sleep slightly to ensure monotonic timestamp advance
    time.sleep(1.05)

    # Change password
    auth.set_password(username, pw2)

    # Token 1 must now be revoked
    assert auth.read_token(token1) is None, "Token issued before password change MUST be rejected"

    # New token with new password must be valid
    token2 = auth.make_token(username)
    assert auth.read_token(token2) == (username, "client"), "Token issued after password change must be valid"

    # Cleanup
    auth.delete_user(username)
    print("  -> PASS: Session invalidation on password change verified")


def test_security_headers_present():
    """Verify that standard security headers are present on responses."""
    resp = client.get("/login")
    assert resp.status_code == 200
    headers = resp.headers
    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("x-frame-options") in ("DENY", "SAMEORIGIN")
    assert "content-security-policy" in headers
    assert "referrer-policy" in headers
    print("  -> PASS: Security headers (CSP, nosniff, frame-options) verified")


def test_login_rate_limiting():
    """Verify brute-force rate limiting returns 429 after repeated failed logins."""
    # Attempt 5 wrong logins
    for i in range(5):
        resp = client.post("/api/login", json={"username": f"baduser_{i}", "password": "wrongpassword"})
        assert resp.status_code in (401, 429)

    # 6th attempt from same client should hit 429
    resp6 = client.post("/api/login", json={"username": "baduser_exceed", "password": "wrongpassword"})
    assert resp6.status_code == 429, f"Expected 429 Too Many Requests, got {resp6.status_code}"
    print("  -> PASS: Rate limiting on /api/login verified")


def test_risk_validation_enforced_in_api_execute():
    """Verify that /api/execute checks mathematical risk limits before submitting order."""
    # Setup authenticated user session
    username = "test_trader"
    if username not in auth.users():
        auth.create_user(username, "TraderPassword123", "client")
    token = auth.make_token(username)
    cookies = {dashboard_server.COOKIE: token}

    # 1. Reject invalid SL (BUY with SL >= Entry)
    bad_sl_req = {"symbol": "XAUUSD", "side": "BUY", "qty": 0.01, "price": 4000.0, "sl": 4100.0, "tp": 4200.0}
    resp = client.post("/api/execute", json=bad_sl_req, cookies=cookies)
    assert resp.status_code == 400
    data = resp.json()
    assert data["ok"] is False
    assert "SL" in data["error"] or "below entry" in data["error"]

    # 2. Reject bad Risk/Reward ratio (< 1.5)
    bad_rr_req = {"symbol": "XAUUSD", "side": "BUY", "qty": 0.01, "price": 4000.0, "sl": 3950.0, "tp": 4020.0}
    resp = client.post("/api/execute", json=bad_rr_req, cookies=cookies)
    assert resp.status_code == 400
    data = resp.json()
    assert data["ok"] is False
    assert "Risk/Reward" in data["error"] or "Refused" in data["error"]

    # Cleanup
    auth.delete_user(username)
    print("  -> PASS: Risk engine validation enforced in /api/execute verified")


def test_multi_tenant_paper_ticket_isolation():
    """Verify that paper trade tickets for Alice and Bob do not overwrite each other in DB."""
    # User Alice
    paper.USER.set("alice")
    res_a = paper.open_trade("XAUUSD", "BUY", 0.01, sl=3900.0, tp=4200.0, price=4000.0)
    assert res_a["ok"] is True
    t_a = res_a["trade"]

    # User Bob
    paper.USER.set("bob")
    res_b = paper.open_trade("XAUUSD", "BUY", 0.01, sl=3900.0, tp=4200.0, price=4000.0)
    assert res_b["ok"] is True
    t_b = res_b["trade"]

    broker = get_broker("paper")

    # Record via broker
    paper.USER.set("alice")
    pos_a = broker.get_positions()
    ticket_a = pos_a[-1].ticket

    paper.USER.set("bob")
    pos_b = broker.get_positions()
    ticket_b = pos_b[-1].ticket

    # Tickets must be distinct to prevent database collision
    assert ticket_a != ticket_b or ("alice" in ticket_a and "bob" in ticket_b), f"Tickets collided: {ticket_a} vs {ticket_b}"
    print("  -> PASS: Multi-tenant ticket isolation verified")


if __name__ == "__main__":
    print("=" * 60)
    print("RUNNING TDD SECURITY & INTEGRATION TEST SUITE")
    print("=" * 60)
    test_security_headers_present()
    test_session_invalidation_on_password_change()
    test_login_rate_limiting()
    test_risk_validation_enforced_in_api_execute()
    test_multi_tenant_paper_ticket_isolation()
    print("=" * 60)
    print("ALL TDD TESTS PASSED")
    print("=" * 60)

