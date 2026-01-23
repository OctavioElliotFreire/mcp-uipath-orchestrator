import asyncio
from service import OrchestratorClient

async def test_connection():
    """Test connection and get folders from UiPath Orchestrator"""
    
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
                print(f"✓ Found {folders['@odata.count']} folder(s):\n")
                
                # Group folders by hierarchy
                root_folders = []
               
                
                for folder in folders['value']:
                    full_path = folder.get('FullyQualifiedName', '')
                    display_name = folder.get('DisplayName', 'N/A')
                    folder_id = folder.get('Id', 'N/A')
                    parent_id = folder.get('ParentId')
                    
                    if parent_id is None:
                        # Root folder
                        root_folders.append({
                            'name': display_name,
                            'id': folder_id,
                            'path': full_path
                        })
                    else:
                        # Child folder - show with indentation based on path depth
                        depth = full_path.count('/')
                        indent = "  " * depth
                        print(f"{indent}📁 {display_name} (ID: {folder_id})")
                
                # Show root folders
                print("\nRoot Folders:")
                for folder in root_folders:
                    print(f"📂 {folder['name']} (ID: {folder['id']})")
                
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
        return False
        
    finally:
        await client.close()
        print("\n" + "=" * 50)
        print("Test complete")


if __name__ == "__main__":
    # Run the test
    result = asyncio.run(test_connection())
    
    if result:
        print("\n🎉 SUCCESS - Connection is working!")
    else:
        print("\n❌ FAILED - Check your credentials and URL")