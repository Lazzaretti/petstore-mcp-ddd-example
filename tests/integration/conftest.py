"""Integration fixtures: start what the tests need, or skip with a clear reason."""

import os
import shutil
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import httpx2
import pytest

ROOT = Path(__file__).resolve().parents[2]
KEYCLOAK_ISSUER = "http://localhost:8080/realms/petstore"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def port_in_use(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def wait_until_up(url: str, timeout: float = 30) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            httpx2.get(url, timeout=2)
            return
        except httpx2.TransportError:
            time.sleep(0.2)
    raise TimeoutError(f"{url} did not come up within {timeout} s")


@contextmanager
def running_app(port: int, **env: str) -> Iterator[str]:
    """`python -m petstore.app serve` in a subprocess; yields the base URL."""
    process = subprocess.Popen(
        [sys.executable, "-m", "petstore.app", "serve"],
        cwd=ROOT,
        env={**os.environ, "PORT": str(port), **env},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    base_url = f"http://localhost:{port}"
    try:
        wait_until_up(f"{base_url}/sales/stock")
        yield base_url
    finally:
        process.terminate()
        process.wait(timeout=10)


@pytest.fixture(scope="module")
def app_url() -> Iterator[str]:
    """The app with AUTH=off on a free port."""
    with running_app(free_port(), AUTH="off", PETSTORE_CUSTOMER="alice") as url:
        yield url


def docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    return subprocess.run(["docker", "info"], capture_output=True).returncode == 0


def keycloak_up() -> bool:
    try:
        return httpx2.get(f"{KEYCLOAK_ISSUER}/.well-known/openid-configuration", timeout=2).is_success
    except httpx2.TransportError:
        return False


@pytest.fixture(scope="session")
def keycloak() -> Iterator[str]:
    """Uses a running Keycloak, or starts one with scripts/keycloak.sh and stops it afterwards."""
    if keycloak_up():
        yield KEYCLOAK_ISSUER
        return
    if not docker_available():
        pytest.skip("Keycloak is not running and Docker is not available to start it")
    if port_in_use(8080):
        pytest.skip("port 8080 is taken by something that isn't Keycloak")
    subprocess.run([ROOT / "scripts/keycloak.sh", "start"], check=True, capture_output=True)
    try:
        yield KEYCLOAK_ISSUER
    finally:
        subprocess.run([ROOT / "scripts/keycloak.sh", "stop"], capture_output=True)


@pytest.fixture(scope="module")
def app_with_auth(keycloak: str) -> Iterator[str]:
    """The app with OAuth on port 8000: the token audience is http://localhost:8000/<context>/mcp."""
    if port_in_use(8000):
        pytest.skip("port 8000 is taken; the OAuth audience needs exactly http://localhost:8000")
    with running_app(8000, AUTH="on") as url:
        yield url


LOCAL_PETSTORE = "http://localhost:8081/api/v3"


@pytest.fixture(scope="module")
def local_petstore() -> Iterator[str]:
    """A fresh local Petstore seeded with the demo's pets (scripts/petstore-local.sh)."""
    if not docker_available():
        pytest.skip("Docker is not available to run the local Petstore")
    subprocess.run([ROOT / "scripts/petstore-local.sh", "start"], check=True, capture_output=True)
    try:
        yield LOCAL_PETSTORE
    finally:
        subprocess.run([ROOT / "scripts/petstore-local.sh", "stop"], capture_output=True)
