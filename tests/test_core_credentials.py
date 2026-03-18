"""Tests for skipper_core credential types."""

from __future__ import annotations

import base64
import json
import os
import tempfile

import pytest

from skipper_core import Base64Credentials, Credentials, FileCredentials, ServiceAccountCredentials


class TestFileCredentials:
    def test_resolves_file_contents(self) -> None:
        payload = b'{"type": "service_account"}'
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as f:
            f.write(payload)
            path = f.name
        try:
            creds = FileCredentials(path=path)
            assert creds.resolve() == payload
        finally:
            os.unlink(path)

    def test_missing_file_raises(self) -> None:
        creds = FileCredentials(path="/nonexistent/path/creds.json")
        with pytest.raises(FileNotFoundError):
            creds.resolve()

    def test_satisfies_credentials_protocol(self) -> None:
        creds = FileCredentials(path="./service-account.json")
        assert isinstance(creds, Credentials)


class TestBase64Credentials:
    def test_resolves_base64_encoded_json(self) -> None:
        payload = b'{"type": "service_account"}'
        encoded = base64.b64encode(payload).decode()
        creds = Base64Credentials(encoded=encoded)
        assert creds.resolve() == payload

    def test_satisfies_credentials_protocol(self) -> None:
        creds = Base64Credentials(encoded="dGVzdA==")
        assert isinstance(creds, Credentials)


class TestServiceAccountCredentials:
    def _make(self) -> ServiceAccountCredentials:
        return ServiceAccountCredentials(
            type="service_account",
            project_id="my-project",
            private_key_id="key-id",
            private_key="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n",
            client_email="bot@my-project.iam.gserviceaccount.com",
            client_id="123456789",
            auth_uri="https://accounts.google.com/o/oauth2/auth",
            token_uri="https://oauth2.googleapis.com/token",
            auth_provider_x509_cert_url="https://www.googleapis.com/oauth2/v1/certs",
            client_x509_cert_url="https://www.googleapis.com/robot/v1/metadata/x509/bot",
        )

    def test_resolves_to_json_bytes(self) -> None:
        creds = self._make()
        data = json.loads(creds.resolve())
        assert data["type"] == "service_account"
        assert data["project_id"] == "my-project"
        assert data["client_email"] == "bot@my-project.iam.gserviceaccount.com"

    def test_satisfies_credentials_protocol(self) -> None:
        creds = self._make()
        assert isinstance(creds, Credentials)

    def test_is_frozen(self) -> None:
        creds = self._make()
        with pytest.raises(Exception):
            creds.project_id = "other-project"  # type: ignore[misc]
