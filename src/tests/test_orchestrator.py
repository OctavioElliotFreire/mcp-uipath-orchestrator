"""
Test suite for UiPath Orchestrator Client
Run with: pytest src/tests/test_orchestrator.py -v
"""
import pytest
from src.service import OrchestratorClient


@pytest.fixture
async def client():
    """Fixture to create and cleanup OrchestratorClient"""
    client = OrchestratorClient()
    yield client
    await client.close()


@pytest.fixture
async def authenticated_client():
    """Fixture to create an authenticated client"""
    client = OrchestratorClient()
    await client.authenticate()
    yield client
    await client.close()


class TestAuthentication:
    """Test cases for authentication"""
    
    @pytest.mark.asyncio
    async def test_authenticate_returns_token(self, client):
        """Test that authentication returns a valid token"""
        token = await client.authenticate() 
        
        assert token is not None, "Token should not be None"
        assert isinstance(token, str), "Token should be a string"
        assert len(token) > 0, "Token should not be empty"
    
    @pytest.mark.asyncio
    async def test_authenticate_sets_access_token(self, client):
        """Test that authentication sets the access_token attribute"""
        await client.authenticate()
        
        assert client.access_token is not None, "access_token should be set"
        assert len(client.access_token) > 0, "access_token should not be empty"
    
    @pytest.mark.asyncio
    async def test_token_format(self, client):
        """Test that token has expected format (JWT-like)"""
        token = await client.authenticate()
        
        # JWT tokens typically have dots separating sections
        assert isinstance(token, str), "Token should be a string"
        # Token should be reasonably long (JWTs are typically 100+ chars)
        assert len(token) > 50, "Token seems too short to be valid"


class TestFolders:
    """Test cases for folder operations"""
    
    @pytest.mark.asyncio
    async def test_get_folders_returns_data(self, authenticated_client):
        """Test that get_folders returns data"""
        folders = await authenticated_client.get_folders()
        
        assert folders is not None, "Folders response should not be None"
        assert isinstance(folders, dict), "Folders should be a dictionary"
    
    @pytest.mark.asyncio
    async def test_get_folders_has_value_key(self, authenticated_client):
        """Test that folders response has 'value' key"""
        folders = await authenticated_client.get_folders()
        
        assert "value" in folders, "Response should have 'value' key"
        assert isinstance(folders["value"], list), "'value' should be a list"
    
    @pytest.mark.asyncio
    async def test_get_folders_returns_folders(self, authenticated_client):
        """Test that folders list is not empty"""
        folders = await authenticated_client.get_folders()
        
        assert len(folders["value"]) > 0, "Should have at least one folder"
    
    @pytest.mark.asyncio
    async def test_folder_structure(self, authenticated_client):
        """Test that folder objects have expected keys"""
        folders = await authenticated_client.get_folders()
        
        if len(folders["value"]) > 0:
            folder = folders["value"][0]
            
            assert "Id" in folder, "Folder should have 'Id'"
            assert "DisplayName" in folder, "Folder should have 'DisplayName'"
            assert "FullyQualifiedName" in folder, "Folder should have 'FullyQualifiedName'"
    
    @pytest.mark.asyncio
    async def test_folder_count_matches(self, authenticated_client):
        """Test that @odata.count matches value length"""
        folders = await authenticated_client.get_folders()
        
        if "@odata.count" in folders:
            assert folders["@odata.count"] >= len(folders["value"]), \
                "Count should be >= returned items"


class TestAssets:
    """Test cases for asset operations"""
    
    @pytest.mark.asyncio
    async def test_get_assets_requires_folder_id(self, authenticated_client):
        """Test that get_assets requires folder_id parameter"""
        # This should work without error when folder_id is provided
        folders = await authenticated_client.get_folders()
        folder_id = folders["value"][0]["Id"]
        
        # Should not raise an error
        assets = await authenticated_client.get_assets(folder_id=folder_id)
        assert assets is not None
    
    @pytest.mark.asyncio
    async def test_get_assets_returns_dict(self, authenticated_client):
        """Test that get_assets returns a dictionary"""
        folders = await authenticated_client.get_folders()
        folder_id = folders["value"][0]["Id"]
        
        try:
            assets = await authenticated_client.get_assets(folder_id=folder_id)
            assert isinstance(assets, dict), "Assets should be a dictionary"
        except Exception as e:
            if "403" in str(e):
                pytest.skip("Permission denied for assets - OAuth scope issue")
            raise
    
    @pytest.mark.asyncio
    async def test_get_assets_has_value_key(self, authenticated_client):
        """Test that assets response has 'value' key"""
        folders = await authenticated_client.get_folders()
        folder_id = folders["value"][0]["Id"]
        
        try:
            assets = await authenticated_client.get_assets(folder_id=folder_id)
            assert "value" in assets, "Response should have 'value' key"
            assert isinstance(assets["value"], list), "'value' should be a list"
        except Exception as e:
            if "403" in str(e):
                pytest.skip("Permission denied for assets - OAuth scope issue")
            raise
    
    @pytest.mark.asyncio
    async def test_asset_structure(self, authenticated_client):
        """Test that asset objects have expected keys (if any assets exist)"""
        folders = await authenticated_client.get_folders()
        
        # Try multiple folders to find one with assets
        for folder in folders["value"][:5]:
            folder_id = folder["Id"]
            
            try:
                assets = await authenticated_client.get_assets(folder_id=folder_id)
                
                if len(assets["value"]) > 0:
                    asset = assets["value"][0]
                    
                    assert "Name" in asset, "Asset should have 'Name'"
                    assert "ValueType" in asset, "Asset should have 'ValueType'"
                    assert "FolderId" in asset, "Asset should have 'FolderId'"
                    return  # Test passed
            except Exception as e:
                if "403" not in str(e):
                    raise
        
        pytest.skip("No accessible folders with assets found")


class TestHeaders:
    """Test cases for header generation"""
    
    @pytest.mark.asyncio
    async def test_headers_with_no_folder(self, authenticated_client):
        """Test headers without folder_id"""
        headers = authenticated_client.get_headers()
        
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer ")
        assert "X-UIPATH-TenantName" in headers
        assert "X-UIPATH-OrganizationUnitId" in headers
    
    @pytest.mark.asyncio
    async def test_headers_with_folder(self, authenticated_client):
        """Test headers with folder_id"""
        headers = authenticated_client.get_headers(folder_id=12345)
        
        assert headers["X-UIPATH-OrganizationUnitId"] == "12345"
    
    @pytest.mark.asyncio
    async def test_headers_content_type(self, authenticated_client):
        """Test that headers include correct content type"""
        headers = authenticated_client.get_headers()
        
        assert headers["Content-Type"] == "application/json"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])