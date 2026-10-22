from __future__ import annotations

from typing import Any

import httpx
from fastapi.testclient import TestClient

from humbee_sfa.core.conventions import generate_ulid
from humbee_sfa.modules.org.models import Employee
from tests.fixtures.seed import phone_of

OTP = "123456"


class Authed:
    def __init__(self, client: TestClient, token: str, employee: Employee) -> None:
        self.client = client
        self.token = token
        self.employee = employee

    def _headers(self, key: str | None, extra: dict[str, str] | None) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self.token}", "Idempotency-Key": key or generate_ulid()}
        headers.update(extra or {})
        return headers

    def get(self, path: str, **params: Any) -> httpx.Response:
        return self.client.get(path, params=params, headers={"Authorization": f"Bearer {self.token}"})

    def post(self, path: str, json: Any = None, *, key: str | None = None, headers: dict[str, str] | None = None) -> httpx.Response:
        return self.client.post(path, json=json, headers=self._headers(key, headers))

    def put(self, path: str, json: Any = None, *, key: str | None = None, headers: dict[str, str] | None = None) -> httpx.Response:
        return self.client.put(path, json=json, headers=self._headers(key, headers))

    def patch(self, path: str, json: Any = None, *, key: str | None = None, headers: dict[str, str] | None = None) -> httpx.Response:
        return self.client.patch(path, json=json, headers=self._headers(key, headers))

    def delete(self, path: str, *, key: str | None = None, headers: dict[str, str] | None = None) -> httpx.Response:
        return self.client.delete(path, headers=self._headers(key, headers))


def request_otp(client: TestClient, phone: str, *, device_id: str = "device-1", key: str | None = None) -> httpx.Response:
    return client.post(
        "/api/v1/auth/otp/request",
        headers={"Idempotency-Key": key or generate_ulid()},
        json={"phone_e164": phone, "purpose": "login", "client_device_id": device_id},
    )


def verify_otp(client: TestClient, challenge_id: str, *, code: str = OTP, device_id: str = "device-1") -> httpx.Response:
    return client.post(
        "/api/v1/auth/otp/verify",
        headers={"Idempotency-Key": generate_ulid()},
        json={
            "challenge_id": challenge_id,
            "code": code,
            "purpose": "login",
            "client_device_id": device_id,
            "platform": "web_pwa",
            "app_version": "test",
        },
    )


def login(client: TestClient, employee: Employee, *, device_id: str | None = None) -> Authed:
    device = device_id or f"device-{employee.id}"
    requested = request_otp(client, phone_of(employee), device_id=device)
    assert requested.status_code == 200, requested.text
    verified = verify_otp(client, requested.json()["challenge_id"], device_id=device)
    assert verified.status_code == 200, verified.text
    return Authed(client, verified.json()["access_token"], employee)
