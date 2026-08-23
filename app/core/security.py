"""Ed25519 cryptographic signing for mandates and intents."""

from __future__ import annotations

import json
import hashlib
from base64 import b64encode, b64decode

from nacl.signing import SigningKey, VerifyKey
from nacl.exceptions import BadSignatureError


class CryptoService:
    """Handles Ed25519 signing and verification for mandates and intents."""

    @staticmethod
    def generate_keypair() -> tuple[str, str]:
        """Generate a new Ed25519 keypair. Returns (private_key_b64, public_key_b64)."""
        signing_key = SigningKey.generate()
        verify_key = signing_key.verify_key
        return (
            b64encode(signing_key.encode()).decode(),
            b64encode(verify_key.encode()).decode(),
        )

    @staticmethod
    def canonicalize(payload: dict) -> str:
        """
        Create a canonical JSON string from a dict.
        Sorted keys, no whitespace — deterministic for signing.
        """
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def sign(canonical_payload: str, private_key_b64: str) -> str:
        """Sign a canonical payload string with Ed25519. Returns signature as base64."""
        private_key_bytes = b64decode(private_key_b64)
        signing_key = SigningKey(private_key_bytes)
        signed = signing_key.sign(canonical_payload.encode("utf-8"))
        return b64encode(signed.signature).decode()

    @staticmethod
    def verify(canonical_payload: str, signature_b64: str, public_key_b64: str) -> bool:
        """Verify an Ed25519 signature. Returns True if valid, False otherwise."""
        try:
            public_key_bytes = b64decode(public_key_b64)
            verify_key = VerifyKey(public_key_bytes)
            signature_bytes = b64decode(signature_b64)
            verify_key.verify(canonical_payload.encode("utf-8"), signature_bytes)
            return True
        except (BadSignatureError, Exception):
            return False

    @staticmethod
    def hash_intent(canonical_payload: str) -> str:
        """SHA-256 hash of a canonical intent for replay protection."""
        return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()

    @staticmethod
    def build_mandate_canonical(mandate_data: dict) -> str:
        """Build canonical form for mandate signing."""
        canonical = {
            "agent_id": mandate_data["agent_id"],
            "principal_id": mandate_data["principal_id"],
            "financial_ceiling_paise": mandate_data["financial_ceiling_paise"],
            "scope_values": mandate_data["scope_values"],
            "max_transactions": mandate_data["max_transactions"],
            "velocity_window_seconds": mandate_data["velocity_window_seconds"],
        }
        return CryptoService.canonicalize(canonical)

    @staticmethod
    def build_intent_canonical(intent_data: dict) -> str:
        """Build canonical form for purchase intent signing."""
        canonical = {
            "agent_id": intent_data["agent_id"],
            "mandate_id": intent_data["mandate_id"],
            "sku": intent_data["sku"],
            "quantity": intent_data["quantity"],
            "amount_paise": intent_data["amount_paise"],
            "currency": intent_data.get("currency", "INR"),
            "timestamp": intent_data["timestamp"],
            "nonce": intent_data["nonce"],
        }
        return CryptoService.canonicalize(canonical)
