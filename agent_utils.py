"""Agent utilities for calling backend APIs securely."""
import httpx
import os
from typing import Optional, Dict, Any
from datetime import datetime

# Backend configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
REQUEST_TIMEOUT = 30


class BackendAPIClient:
    """Client for secure backend API calls."""

    def __init__(self, token: Optional[str] = None, base_url: str = BACKEND_URL):
        """Initialize backend API client."""
        self.base_url = base_url
        self.token = token
        self.timeout = httpx.Timeout(REQUEST_TIMEOUT)

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        headers = {
            "Content-Type": "application/json",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make GET request to backend."""
        url = f"{self.base_url}{endpoint}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url, headers=self._get_headers(), params=params)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                return {
                    "error": True,
                    "status_code": e.response.status_code,
                    "detail": e.response.text,
                }

    async def post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make POST request to backend."""
        url = f"{self.base_url}{endpoint}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, headers=self._get_headers(), json=data)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                return {
                    "error": True,
                    "status_code": e.response.status_code,
                    "detail": e.response.text,
                }

    async def put(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make PUT request to backend."""
        url = f"{self.base_url}{endpoint}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.put(url, headers=self._get_headers(), json=data)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                return {
                    "error": True,
                    "status_code": e.response.status_code,
                    "detail": e.response.text,
                }


class AgentContext:
    """Context for agent execution."""

    def __init__(self, user_id: str, session_id: str, token: Optional[str] = None):
        """Initialize agent context."""
        self.user_id = user_id
        self.session_id = session_id
        self.token = token
        self.client = BackendAPIClient(token=token)
        self.execution_log = []

    def log_step(self, step: Dict[str, Any]) -> None:
        """Log an execution step."""
        self.execution_log.append({
            **step,
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def request_token(self, system: str, scope: str, ttl_seconds: Optional[int] = None) -> Optional[str]:
        """Request a scoped token from the backend."""
        result = await self.client.post(
            "/api/agent/tokens",
            {
                "system": system,
                "scope": scope,
                "ttl_seconds": ttl_seconds or 3600,
            }
        )

        if result.get("error"):
            self.log_step({
                "action": "request_token",
                "status": "failed",
                "reason": result.get("detail"),
            })
            return None

        token = result.get("token")
        if token:
            self.token = token
            self.client.token = token
            self.log_step({
                "action": "request_token",
                "status": "success",
                "system": system,
                "scope": scope,
            })

        return token


def format_currency(amount_cents: int, currency: str = "USD") -> str:
    """Format currency for display."""
    if currency == "USD":
        return f"${amount_cents / 100:.2f}"
    return f"{amount_cents / 100:.2f} {currency}"


def format_date(date_str: str) -> str:
    """Format ISO date to readable format."""
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return date_str
