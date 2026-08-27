#!/usr/bin/env python3
"""Self-contained tests for the verify-message command.

Dependency-free (stdlib + the ``cryptography`` the tool already imports).
Run directly with::

    python tests/test_verify_message.py

Exits 0 when every check passes, 1 otherwise. Exercises the real signing
and verification paths through the tool's own ``sign_bytes``,
``verify_bytes``, ``message_payload`` and ``verify_message`` functions so
the wire format is covered end to end.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)

import technocore_agent as ta  # noqa: E402
from cryptography.exceptions import InvalidSignature  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: E402
    Ed25519PrivateKey,
)

PASSED = 0


def check(name: str, fn) -> None:
    """Run ``fn()``, failing loudly with a non-zero exit on assertion error."""
    global PASSED
    try:
        fn()
    except Exception as error:  # noqa: BLE001 - deliberate test harness
        print(f"FAIL {name}: {type(error).__name__}: {error}")
        raise SystemExit(1)
    PASSED += 1
    print(f"ok   {name}")


def new_key() -> tuple[Ed25519PrivateKey, str]:
    """Create a throwaway Ed25519 key and its canonical did:key."""
    key = Ed25519PrivateKey.generate()
    return key, ta.did_from_private_key(key)


def test_valid_message() -> None:
    key, did = new_key()
    normalized, payload = ta.message_payload("technocore", "1234567890", "  hi there  ")
    assert normalized == "hi there", "text should be normalized"
    sig = ta.sign_bytes(key, payload)
    assert ta.verify_message(did, "technocore", "1234567890", "hi there", sig) == "hi there"


def test_valid_message_requires_normalized_input() -> None:
    key, did = new_key()
    normalized, payload = ta.message_payload("lobby", "1", "hello world")
    sig = ta.sign_bytes(key, payload)
    # Leading/trailing whitespace must be stripped before signing; passing the
    # un-normalized text must still verify because verification normalizes too.
    assert ta.verify_message(did, "lobby", "1", "  hello world  ", sig) == "hello world"


def test_tampered_text_rejected() -> None:
    key, did = new_key()
    _, payload = ta.message_payload("technocore", "9876543210", "original")
    sig = ta.sign_bytes(key, payload)
    try:
        ta.verify_message(did, "technocore", "9876543210", "tampered", sig)
    except ta.IdentityError:
        return
    raise AssertionError("tampered text must not verify")


def test_wrong_room_rejected() -> None:
    key, did = new_key()
    _, payload = ta.message_payload("technocore", "55", "same text")
    sig = ta.sign_bytes(key, payload)
    try:
        ta.verify_message(did, "lobby", "55", "same text", sig)
    except ta.IdentityError:
        return
    raise AssertionError("signature bound to another room must not verify")


def test_wrong_nonce_rejected() -> None:
    key, did = new_key()
    _, payload = ta.message_payload("technocore", "111", "nonce bound")
    sig = ta.sign_bytes(key, payload)
    try:
        ta.verify_message(did, "technocore", "222", "nonce bound", sig)
    except ta.IdentityError:
        return
    raise AssertionError("signature bound to another nonce must not verify")


def test_wrong_did_rejected() -> None:
    signer_key, _ = new_key()
    other_key, other_did = new_key()
    _, payload = ta.message_payload("technocore", "42", "who signed this")
    sig = ta.sign_bytes(signer_key, payload)
    try:
        ta.verify_message(other_did, "technocore", "42", "who signed this", sig)
    except ta.IdentityError:
        return
    raise AssertionError("a signature must not verify against a different DID")


def test_bad_signature_format_rejected() -> None:
    _, did = new_key()
    try:
        ta.verify_message(did, "technocore", "7", "x", "not-a-signature")
    except ta.ProtocolError:
        return
    raise AssertionError("malformed signature must raise ProtocolError")


def test_low_level_signature_mismatch() -> None:
    key, did = new_key()
    payload = b"room|1|hello"
    sig = ta.sign_bytes(key, payload)
    tampered = bytearray(payload)
    tampered[-1] ^= 0x01
    try:
        ta.verify_bytes(did, sig, bytes(tampered))
    except ta.IdentityError:
        return
    raise AssertionError("verify_bytes must reject a changed payload")


def main() -> int:
    for name in (
        "test_valid_message",
        "test_valid_message_requires_normalized_input",
        "test_tampered_text_rejected",
        "test_wrong_room_rejected",
        "test_wrong_nonce_rejected",
        "test_wrong_did_rejected",
        "test_bad_signature_format_rejected",
        "test_low_level_signature_mismatch",
    ):
        check(name, globals()[name])
    print(f"\n{PASSED}/{PASSED} checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
