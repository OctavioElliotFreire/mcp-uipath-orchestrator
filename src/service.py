import os
import httpx
from dotenv import load_dotenv
from urllib.parse import urljoin
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

   
    def get_headers(
        self,
        folder_id: int | None = None,
        account_level: bool = False
    ) -> dict:
        """
        Build request headers.

        account_level=True:
        - NO OrganizationUnitId header
        """
        if not OrchestratorClient._access_token:
            raise RuntimeError("Client is not authenticated")

        headers = {
            "Authorization": f"Bearer {OrchestratorClient._access_token}",
            "Content-Type": "application/json",
            "X-UIPATH-TenantName": self.tenant,
        }

        if not account_level:
            headers["X-UIPATH-OrganizationUnitId"] = (
                str(folder_id) if folder_id else self.account
            )

        return headers


    async def get(self, endpoint: str, folder_id: int | None = None):
        if not OrchestratorClient._access_token:
            await self.authenticate()

        url = (
            f"{self.base_url}{self.account}/orchestrator_/"
            f"{self.tenant}/{endpoint}"
        )

        response = await self.client.get(
            url,
            headers=self.get_headers(folder_id=folder_id)
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

        

    def _nuget_headers(self) -> dict:
            """
            NuGet endpoints may accept either:
            - Bearer token (some setups)
            - X-NuGet-ApiKey (common for Orchestrator feeds)
            We send both when available.
            """
            headers = {
                "Accept": "application/json",
            }

            # Bearer (if you already authenticated)
            if OrchestratorClient._access_token:
                headers["Authorization"] = f"Bearer {OrchestratorClient._access_token}"

            # Tenant hint (safe to include; some gateways require it)
            if getattr(self, "tenant", None):
                headers["X-UIPATH-TenantName"] = self.tenant

            # Optional NuGet API Key (often required for Orchestrator-hosted feeds)
            nuget_key = os.getenv("NUGET_API_KEY")
            if nuget_key:
                headers["X-NuGet-ApiKey"] = nuget_key

            return headers

    def _candidate_nuget_index_urls(self) -> list[str]:
        """
        Try multiple known shapes *without* hardcoding a single one.
        You can optionally set LIBRARIES_FEED_ID if your Orchestrator feed uses a GUID/name.
        """
        base = (self.base_url or "").rstrip("/")
        org = (self.account or "").strip()
        tenant = (self.tenant or "").strip()

        # Optional: Orchestrator may expose a v3 feed by feed id/name (common on-prem & some cloud setups)
        feed_id = (os.getenv("LIBRARIES_FEED_ID") or "").strip()

        urls: list[str] = []

        # 1) Tenant-scoped "activities" feed (some cloud tenants)
        urls += [
            f"{base}/{org}/{tenant}/nuget/activities/v3/index.json",
            f"{base}/{org}/{tenant}/nuget/activities/api/v3/index.json",
        ]

        # 2) Org-level variants (sometimes exists, sometimes not)
        urls += [
            f"{base}/{org}/nuget/activities/v3/index.json",
            f"{base}/{org}/nuget/activities/api/v3/index.json",
        ]

        # 3) Feed-id based v3 (if you know it; very common in Orchestrator-hosted feeds)
        if feed_id:
            urls += [
                f"{base}/{org}/{tenant}/nuget/v3/{feed_id}/index.json",
                f"{base}/{org}/nuget/v3/{feed_id}/index.json",
            ]

        # 4) Generic org nuget index (rare, but cheap to test)
        urls += [
            f"{base}/{org}/{tenant}/nuget/v3/index.json",
            f"{base}/{org}/nuget/v3/index.json",
        ]

        # Remove dupes while preserving order
        seen = set()
        deduped = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                deduped.append(u)
        return deduped

    async def _get_first_working_json(self, urls: list[str]) -> tuple[str, dict]:
        """
        Try each URL until one returns 200 JSON.
        If all fail, raise with a very explicit debug summary.
        """
        attempts = []

        for url in urls:
            try:
                r = await self.client.get(
                    url,
                    headers=self._nuget_headers(),
                    follow_redirects=False,
                )

                # Record for debug
                attempts.append((url, r.status_code, r.headers.get("location")))

                if r.status_code == 200:
                    return url, r.json()

            except Exception as e:
                attempts.append((url, f"EXC:{type(e).__name__}", str(e)))

        # Build a compact error message
        lines = ["No working NuGet v3 index endpoint found. Attempts:"]
        for url, code, extra in attempts:
            if extra:
                lines.append(f"- {code} {url}  ({extra})")
            else:
                lines.append(f"- {code} {url}")

        lines.append(
            "Hints:\n"
            "1) If responses are 302 to portal_/unregistered, you are hitting the portal router.\n"
            "2) If responses are 404 Service Not Found, that feed path doesn’t exist for your org/tenant.\n"
            "3) Many Orchestrator feeds require NUGET_API_KEY and/or a LIBRARIES_FEED_ID.\n"
        )
        raise RuntimeError("\n".join(lines))

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
    
    async def list_libraries(self, search: str | None = None) -> list[str]:
        """
        List available UiPath library package names.

        Args:
            search: Optional substring to filter package names
        """
        data = await self.get("odata/Libraries")

        names = {
            lib.get("Id")
            for lib in data.get("value", [])
            if lib.get("Id")
        }

        if search:
            search_lower = search.lower()
            names = {
                name for name in names
                if search_lower in name.lower()
            }

        return sorted(names)

    async def list_library_versions(self, package_id: str) -> list[str]:
        """
        List all versions of a UiPath library using the tenant-scoped
        Orchestrator NuGet feed (Secure Deployment).
        """
        if not OrchestratorClient._access_token:
            await self.authenticate()

        feed_id = os.getenv("LIBRARIES_FEED_ID")
        if not feed_id:
            raise RuntimeError("LIBRARIES_FEED_ID is not set")
        print(feed_id)
        index_url = (
            f"{self.base_url}{self.account}/{self.tenant}"
            f"/orchestrator_/nuget/v3/{feed_id}/index.json"
        )

        headers = {
            "Authorization": f"Bearer {OrchestratorClient._access_token}",
            "Accept": "application/json",
        }

        # 1) Fetch NuGet service index
        r = await self.client.get(index_url, headers=headers)
        r.raise_for_status()
        index = r.json()

        # 2) Locate PackageBaseAddress
        base_addr = None
        for res in index.get("resources", []):
            t = res.get("@type")
            if t == "PackageBaseAddress/3.0.0" or (
                isinstance(t, list) and "PackageBaseAddress/3.0.0" in t
            ):
                base_addr = res["@id"]
                break

        if not base_addr:
            raise RuntimeError("PackageBaseAddress/3.0.0 not found in NuGet index")

        # 3) Fetch versions list
        pkg = package_id.lower()
        versions_url = f"{base_addr.rstrip('/')}/{pkg}/index.json"

        vr = await self.client.get(versions_url, headers=headers)
        vr.raise_for_status()
        data = vr.json()

        versions = data.get("versions", [])
        if not versions:
            raise RuntimeError(f"No versions found for library '{package_id}'")

        return sorted(versions)
    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------

    async def close(self):
        await self.client.aclose()