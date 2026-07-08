"""VNC WebSocket gateway — view-only enforcement, session validation, signed token.

vnc_gateway.py 핵심 계약: token 발급/검증, input frame 판별, WS close codes.
"""
from __future__ import annotations

import pytest

from backend.controlplane.vnc_gateway import (
    VncGateway,
    WS_CLOSE_VIEW_ONLY_FALSE, WS_CLOSE_SESSION_EXPIRED,
    WS_CLOSE_INVALID_TOKEN, WS_CLOSE_SESSION_NOT_FOUND,
    WS_CLOSE_VIEW_ONLY_VIOLATION,
)


@pytest.fixture
def gateway():
    return VncGateway(secret_key="test-secret-for-vnc-tokens")


def test_issue_and_validate_token_roundtrip(gateway):
    token = gateway.issue_token("r1", "vnc-1")
    assert gateway.validate_token(token, "r1", "vnc-1") is True


def test_validate_token_wrong_run_id(gateway):
    token = gateway.issue_token("r1", "vnc-1")
    assert gateway.validate_token(token, "r2", "vnc-1") is False


def test_validate_token_wrong_session_id(gateway):
    token = gateway.issue_token("r1", "vnc-1")
    assert gateway.validate_token(token, "r1", "vnc-other") is False


def test_validate_token_expired(gateway):
    token = gateway.issue_token("r1", "vnc-1", ttl_sec=-1)
    assert gateway.validate_token(token, "r1", "vnc-1") is False


def test_validate_token_wrong_secret():
    g1 = VncGateway(secret_key="secretA")
    g2 = VncGateway(secret_key="secretB")
    token = g1.issue_token("r1", "vnc-1")
    assert g2.validate_token(token, "r1", "vnc-1") is False


def test_validate_token_malformed(gateway):
    assert gateway.validate_token("not-a-valid-token", "r", "v") is False
    assert gateway.validate_token("", "r", "v") is False


def test_view_only_false_close_code_distinct():
    assert WS_CLOSE_VIEW_ONLY_FALSE not in (1000, 1001)
    assert 4000 <= WS_CLOSE_VIEW_ONLY_FALSE <= 4999


def test_session_expired_close_code_distinct():
    assert WS_CLOSE_SESSION_EXPIRED != 1000
    assert 4000 <= WS_CLOSE_SESSION_EXPIRED <= 4999


def test_invalid_token_close_code():
    assert WS_CLOSE_INVALID_TOKEN == 4401


def test_session_not_found_close_code():
    assert WS_CLOSE_SESSION_NOT_FOUND == 4404


def test_view_only_violation_close_code():
    assert WS_CLOSE_VIEW_ONLY_VIOLATION == 4403


def test_input_frame_keyboard_detected(gateway):
    assert gateway.is_input_frame({"type": "key", "key": "Enter"}) is True


def test_input_frame_mouse_detected(gateway):
    assert gateway.is_input_frame({"type": "mouse", "x": 10, "y": 20, "button": 1}) is True


def test_input_frame_clipboard_detected(gateway):
    assert gateway.is_input_frame({"type": "clipboard", "data": "secret"}) is True


def test_input_frame_paste_detected(gateway):
    assert gateway.is_input_frame({"type": "paste"}) is True


def test_screen_frame_not_input(gateway):
    assert gateway.is_input_frame({"type": "screen", "data": "raw-bytes"}) is False


def test_non_dict_message_not_input(gateway):
    assert gateway.is_input_frame("not a dict") is False
    assert gateway.is_input_frame(None) is False


def test_input_via_kind_fallback(gateway):
    assert gateway.is_input_frame({"kind": "mousedown"}) is True
