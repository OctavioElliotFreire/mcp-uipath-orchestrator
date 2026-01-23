import os
import httpx
from dotenv import load_dotenv

load_dotenv()

# Orchestrator configuration - loaded from .env file
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL")
TENANT_NAME = os.getenv("TENANT_NAME")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
ACCOUNT_LOGICAL_NAME = os.getenv("ACCOUNT_LOGICAL_NAME")


class OrchestratorClient:
    def __init__(self):
        self.base_url = ORCHESTRATOR_URL
        self.tenant = TENANT_NAME
        self.account = ACCOUNT_LOGICAL_NAME
        self.access_token = None
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def authenticate(self):
        """Authenticate with UiPath Orchestrator using OAuth2"""
        auth_url = f"{self.base_url}identity_/connect/token"
        
        data = {
            "grant_type": "client_credentials",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "scope": "OR.Execution OR.Folders OR.Jobs OR.Machines OR.Monitoring OR.Robots OR.Settings OR.Tasks OR.Users"
        }
        
        response = await self.client.post(auth_url, data=data)
        response.raise_for_status()
        
        token_data = response.json()
        self.access_token = token_data["access_token"]
        return self.access_token
    
    def get_headers(self, folder_id: int = None):
        """Get headers for API requests"""
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "X-UIPATH-TenantName": self.tenant,
        }
        
        # Add folder context if provided
        if folder_id:
            headers["X-UIPATH-OrganizationUnitId"] = str(folder_id)
        else:
            headers["X-UIPATH-OrganizationUnitId"] = self.account
            
        return headers
    
    async def get(self, endpoint: str, folder_id: int = None):
        """Make GET request to Orchestrator"""
        if not self.access_token:
            await self.authenticate()
        
        url = f"{self.base_url}{self.account}/{self.tenant}/{endpoint}"
        response = await self.client.get(url, headers=self.get_headers(folder_id=folder_id))
        response.raise_for_status()
        return response.json()
    
    async def post(self, endpoint: str, data: dict):
        """Make POST request to Orchestrator"""
        if not self.access_token:
            await self.authenticate()
        
        url = f"{self.base_url}{self.account}/{self.tenant}/{endpoint}"
        response = await self.client.post(url, headers=self.get_headers(), json=data)
        response.raise_for_status()
        return response.json()
    
    async def get_folders(self):
        """Get all folders from Orchestrator"""
        endpoint = "odata/folders"
        return await self.get(endpoint)
        
    async def get_assets(self, folder_id: int):
        """Get assets from Orchestrator for a specific folder"""
        endpoint = "odata/Assets"
        return await self.get(endpoint, folder_id=folder_id)
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()