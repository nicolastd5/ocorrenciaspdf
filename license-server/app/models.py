from dataclasses import dataclass
from typing import Optional

@dataclass
class License:
    id: int
    key: str
    client_name: str
    notes: Optional[str]
    revoked: bool
    created_at: str
    revoked_at: Optional[str]

@dataclass
class ValidationLog:
    id: int
    license_id: int
    validated_at: str
    ip: str
    app_version: Optional[str]
