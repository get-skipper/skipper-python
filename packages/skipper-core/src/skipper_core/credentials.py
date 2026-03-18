from __future__ import annotations

import base64
import dataclasses
import json
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class Credentials(Protocol):
    def resolve(self) -> bytes: ...


@dataclasses.dataclass(frozen=True)
class FileCredentials:
    path: str

    def resolve(self) -> bytes:
        return Path(self.path).read_bytes()


@dataclasses.dataclass(frozen=True)
class Base64Credentials:
    encoded: str

    def resolve(self) -> bytes:
        return base64.b64decode(self.encoded)


@dataclasses.dataclass(frozen=True)
class ServiceAccountCredentials:
    type: str
    project_id: str
    private_key_id: str
    private_key: str
    client_email: str
    client_id: str
    auth_uri: str
    token_uri: str
    auth_provider_x509_cert_url: str
    client_x509_cert_url: str

    def resolve(self) -> bytes:
        return json.dumps(dataclasses.asdict(self)).encode()
