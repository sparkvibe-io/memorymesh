"""Tests for the privacy guard module."""

from __future__ import annotations

from memorymesh.privacy import check_for_secrets, redact_secrets


class TestCheckForSecrets:
    """Tests for check_for_secrets()."""

    def test_detect_api_key(self) -> None:
        text = "Use this key: sk-abc12345678901234567890"
        result = check_for_secrets(text)
        assert "API key" in result

    def test_detect_pk_key(self) -> None:
        text = "pk_live_abcdefghij1234567890"
        result = check_for_secrets(text)
        assert "API key" in result

    def test_detect_github_token(self) -> None:
        text = "My token is ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijkl"
        result = check_for_secrets(text)
        assert "GitHub token" in result

    def test_detect_github_gho_token(self) -> None:
        text = "Token: gho_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijkl"
        result = check_for_secrets(text)
        assert "GitHub token" in result

    def test_detect_password(self) -> None:
        text = "password: mysecretpassword123"
        result = check_for_secrets(text)
        assert "password" in result

    def test_detect_password_equals(self) -> None:
        text = "PASSWORD=supersecret"
        result = check_for_secrets(text)
        assert "password" in result

    def test_detect_private_key(self) -> None:
        text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEow..."
        result = check_for_secrets(text)
        assert "private key" in result

    def test_detect_ec_private_key(self) -> None:
        text = "-----BEGIN EC PRIVATE KEY-----\nMIIEow..."
        result = check_for_secrets(text)
        assert "private key" in result

    def test_detect_jwt(self) -> None:
        text = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abc"
        result = check_for_secrets(text)
        assert "JWT token" in result

    def test_detect_aws_key(self) -> None:
        text = "AWS key: AKIAIOSFODNN7EXAMPLE"
        result = check_for_secrets(text)
        assert "AWS access key" in result

    def test_detect_slack_token(self) -> None:
        text = "Slack: xoxb-123456789-abcdefghij"
        result = check_for_secrets(text)
        assert "Slack token" in result

    def test_no_false_positive_normal_text(self) -> None:
        text = "The user prefers dark mode and uses Python 3.11."
        result = check_for_secrets(text)
        assert result == []

    def test_no_false_positive_short_strings(self) -> None:
        text = "key = x"
        result = check_for_secrets(text)
        assert result == []

    def test_check_returns_empty_for_safe_text(self) -> None:
        text = "This is a perfectly safe memory about coding patterns."
        result = check_for_secrets(text)
        assert result == []

    def test_multiple_secret_types_detected(self) -> None:
        text = (
            "sk-abcdefghijklmnopqrstuvwxyz "
            "password: secret123 "
            "AKIAIOSFODNN7EXAMPLE"
        )
        result = check_for_secrets(text)
        assert len(result) >= 3
        assert "API key" in result
        assert "password" in result
        assert "AWS access key" in result

    def test_deduplicates_same_type(self) -> None:
        text = "sk-aaaaaaaaaaaaaaaaaaaa1234 and sk-bbbbbbbbbbbbbbbbbbbb5678"
        result = check_for_secrets(text)
        assert result.count("API key") == 1


class TestRedactSecrets:
    """Tests for redact_secrets()."""

    def test_redact_api_key(self) -> None:
        text = "Use sk-abc12345678901234567890 here"
        result = redact_secrets(text)
        assert "sk-abc" not in result
        assert "[REDACTED]" in result

    def test_redact_multiple_secrets(self) -> None:
        text = "key sk-abcdefghijklmnopqrstuvwxyz and pw password: secret123"
        result = redact_secrets(text)
        assert "sk-abcdefghijklmnopqrstuvwxyz" not in result
        assert "[REDACTED]" in result

    def test_redact_preserves_normal_text(self) -> None:
        text = "The user prefers dark mode."
        result = redact_secrets(text)
        assert result == text

    def test_redact_github_token(self) -> None:
        text = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijkl"
        result = redact_secrets(text)
        assert "ghp_" not in result
        assert "[REDACTED]" in result

    def test_redact_aws_key(self) -> None:
        text = "AKIAIOSFODNN7EXAMPLE"
        result = redact_secrets(text)
        assert "AKIA" not in result
        assert "[REDACTED]" in result
