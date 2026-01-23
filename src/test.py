import asyncio
from service import OrchestratorClient

async def test_connection():
    """Test connection, folders, and assets from UiPath Orchestrator"""
    
    print("Testing UiPath Orchestrator Connection...")
    print("=" * 50)
    
    client = OrchestratorClient()
    
    try:
        # Test authentication
        print("\n1. Attempting authentication...")
        token = await client.authenticate()
        
        if token:
            print(f"✓ Authentication successful!")
            print(f"   Token: {token[:30]}...")
            
            # Test get folders
            print("\n2. Fetching folders...")
            folders = await client.get_folders()
            
            if folders.get("value"):
                print(f"✓ Found {folders['@odata.count']} folder(s)")
                
                # Show first 3 folders for testing
                print("\nFirst 3 folders:")
                for folder in folders['value'][:3]:
                    display_name = folder.get('DisplayName', 'N/A')
                    folder_id = folder.get('Id', 'N/A')
                    print(f"   📁 {display_name} (ID: {folder_id})")
                
                # Try getting assets from multiple folders
                print(f"\n3. Testing asset access across folders...")
                
                folders_to_try = folders['value'][:5]  # Try first 5 folders
                assets_found = False
                
                for folder in folders_to_try:
                    folder_id = folder['Id']
                    folder_name = folder['DisplayName']
                    
                    try:
                        print(f"\n   Trying folder '{folder_name}' (ID: {folder_id})...")
                        assets = await client.get_assets(folder_id=folder_id)
                        
                        if assets.get("value"):
                            print(f"   ✓ Found {len(assets['value'])} asset(s):")
                            for asset in assets['value'][:3]:
                                asset_name = asset.get('Name', 'N/A')
                                asset_type = asset.get('ValueType', 'N/A')
                                print(f"      📦 {asset_name} (Type: {asset_type})")
                            assets_found = True
                            break
                        else:
                            print(f"      (no assets)")
                    except Exception as e:
                        error_msg = str(e)
                        if "403" in error_msg:
                            print(f"      ⚠ Permission denied")
                        elif "404" in error_msg:
                            print(f"      ⚠ Not found")
                        else:
                            print(f"      ✗ Error: {error_msg[:50]}")
                
                if not assets_found:
                    print("\n   ℹ No accessible assets found in any tested folder")
                    print("   This might be a permissions issue with your OAuth credentials")
                
            else:
                print("   No folders found or empty response")
            
            return True
        else:
            print("✗ Authentication failed - no token received")
            return False
            
    except Exception as e:
        print(f"✗ Test failed!")
        print(f"   Error: {str(e)}")
        print(f"   Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        await client.close()
        print("\n" + "=" * 50)
        print("Test complete")


if __name__ == "__main__":
    # Run the test
    result = asyncio.run(test_connection())
    
    if result:
        print("\n🎉 SUCCESS!")
    else:
        print("\n❌ FAILED - Check error messages above")