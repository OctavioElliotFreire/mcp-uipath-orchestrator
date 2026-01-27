import os
import httpx
from dotenv import load_dotenv

load_dotenv()

# -----------------------------------------------------------------------------
# Global configuration (shared across tenants)
# -----------------------------------------------------------------------------

ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
ACCOUNT_LOGICAL_NAME = os.getenv("ACCOUNT_LOGICAL_NAME")

TENANTS = [
    t.strip()
    for t in os.getenv("TENANTS", "").split(",")
    if t.strip()
]


def _require(value: str | None, name: str) -> str:
    """
    Fail fast with a clear error if a required value is missing.
    """
    if not value:
        raise RuntimeError(
            f"Required configuration '{name}' is not set. "
            "This may be expected in compliance/redacted environments."
        )
    return value


# -----------------------------------------------------------------------------
# Orchestrator Client
# -----------------------------------------------------------------------------

class OrchestratorClient:
    """
    UiPath Orchestrator client (multi-tenant, programmatic).

    - Tenants are passed directly (must be real UiPath tenant names)
    - OAuth token is shared across all tenants
    - Tenant switching is done via X-UIPATH-TenantName header
    """

    _access_token: str | None = None

    def __init__(self, tenant: str | None = None):
        self.base_url = _require(ORCHESTRATOR_URL, "ORCHESTRATOR_URL")
        self.account = _require(ACCOUNT_LOGICAL_NAME, "ACCOUNT_LOGICAL_NAME")

        if not TENANTS:
            raise RuntimeError(
                "No tenants configured. Set TENANTS in the environment."
            )

        if tenant:
            if tenant not in TENANTS:
                raise RuntimeError(
                    f"Unknown tenant '{tenant}'. "
                    f"Allowed tenants: {TENANTS}"
                )
            self.tenant = tenant
        else:
            # Default to the first configured tenant
            self.tenant = TENANTS[0]

        self.client = httpx.AsyncClient(timeout=30.0)

    # -------------------------------------------------------------------------
    # Authentication
    # -------------------------------------------------------------------------

    async def authenticate(self) -> str:
        """
        Authenticate once using client credentials.
        Token is reused across all tenants.
        """
        if OrchestratorClient._access_token:
            return OrchestratorClient._access_token

        auth_url = f"{self.base_url}identity_/connect/token"

        data = {
            "grant_type": "client_credentials",
            "client_id": _require(CLIENT_ID, "CLIENT_ID"),
            "client_secret": _require(CLIENT_SECRET, "CLIENT_SECRET"),
        }

        response = await self.client.post(auth_url, data=data)
        response.raise_for_status()

        token_data = response.json()
        OrchestratorClient._access_token = token_data["access_token"]
        return OrchestratorClient._access_token

    # -------------------------------------------------------------------------
    # Request helpers
    # -------------------------------------------------------------------------

    def get_headers(self, folder_id: int | None = None) -> dict:
        """
        Build request headers with tenant context.
        """
        if not OrchestratorClient._access_token:
            raise RuntimeError("Client is not authenticated")

        headers = {
            "Authorization": f"Bearer {OrchestratorClient._access_token}",
            "Content-Type": "application/json",
            "X-UIPATH-TenantName": self.tenant,
        }

        headers["X-UIPATH-OrganizationUnitId"] = (
            str(folder_id) if folder_id else self.account
        )

        return headers

    async def get(self, endpoint: str, folder_id: int | None = None):
        """
        Make a GET request to Orchestrator.
        """
        if not OrchestratorClient._access_token:
            await self.authenticate()

        url = f"{self.base_url}{self.account}/{self.tenant}/{endpoint}"
        response = await self.client.get(
            url, headers=self.get_headers(folder_id)
        )
        response.raise_for_status()
        return response.json()

    async def post(self, endpoint: str, data: dict):
        """
        Make a POST request to Orchestrator.
        """
        if not OrchestratorClient._access_token:
            await self.authenticate()

        url = f"{self.base_url}{self.account}/{self.tenant}/{endpoint}"
        response = await self.client.post(
            url, headers=self.get_headers(), json=data
        )
        response.raise_for_status()
        return response.json()

    # -------------------------------------------------------------------------
    # Domain methods
    # -------------------------------------------------------------------------

    async def get_folders(self):
        return await self.get("odata/Folders")

    async def get_assets(self, folder_id: int):
        return await self.get("odata/Assets", folder_id)

    async def get_queues(self, folder_id: int):
        return await self.get("odata/QueueDefinitions", folder_id)

    async def get_storage_buckets(self, folder_id: int):
        return await self.get("odata/Buckets", folder_id)

    async def get_triggers(self, folder_id: int):
        return await self.get("odata/ProcessSchedules", folder_id)

    async def get_processes(self, folder_id: int):
        return await self.get("odata/Releases", folder_id)

    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------

    async def close(self):
        await self.client.aclose()