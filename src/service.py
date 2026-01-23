import os
import httpx
from dotenv import load_dotenv

load_dotenv()

# Orchestrator configuration
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
        auth_url = f"{self.base_url}/identity_/connect/token"
        
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
    
    def get_headers(self):
        """Get headers for API requests"""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "X-UIPATH-TenantName": self.tenant,
            "X-UIPATH-OrganizationUnitId": self.account
        }
    
    async def get(self, endpoint: str):
        """Make GET request to Orchestrator"""
        if not self.access_token:
            await self.authenticate()
        
        url = f"{self.base_url}/{self.account}/{self.tenant}/{endpoint}"
        response = await self.client.get(url, headers=self.get_headers())
        response.raise_for_status()
        return response.json()
    
    async def post(self, endpoint: str, data: dict):
        """Make POST request to Orchestrator"""
        if not self.access_token:
            await self.authenticate()
        
        url = f"{self.base_url}/{self.account}/{self.tenant}/{endpoint}"
        response = await self.client.post(url, headers=self.get_headers(), json=data)
        response.raise_for_status()
        return response.json()
    
    
        
        return await self.post("odata/Jobs/UiPath.Server.Configuration.OData.StartJobs", job_data)
    



    async def get_folders(self, filter_query: str = None):
        """Get all folders from Orchestrator"""
        endpoint = "odata/folders"
        
        if filter_query:
            separator = "&"
            endpoint += f"{separator}$filter={filter_query}"
        
        return await self.get(endpoint)

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()