"""
Individual tests for UiPath Orchestrator Client
Uncomment the test you want to run at the bottom
"""
import asyncio
from service import OrchestratorClient


async def test_connection():
    """Test 1: Connection and Authentication"""
    print("\n" + "=" * 60)
    print("TEST 1: Connection and Authentication")
    print("=" * 60)
    
    client = OrchestratorClient()
    
    try:
        print("\n▶ Attempting authentication...")
        token = await client.authenticate()
        
        if token and len(token) > 0:
            print(f"✓ PASS: Authentication successful")
            print(f"  Token preview: {token[:30]}...")
            print(f"  Token length: {len(token)} characters")
            return True
        else:
            print(f"✗ FAIL: No token received")
            return False
            
    except Exception as e:
        print(f"✗ FAIL: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        await client.close()


async def test_get_folders():
    """Test 2: Get Folders"""
    print("\n" + "=" * 60)
    print("TEST 2: Get Folders")
    print("=" * 60)
    
    client = OrchestratorClient()
    
    try:
        print("\n▶ Authenticating...")
        await client.authenticate()
        print("✓ Authenticated")
        
        print("\n▶ Fetching folders...")
        folders = await client.get_folders()
        
        if not folders or "value" not in folders:
            print("✗ FAIL: Invalid response")
            return False
        
        folder_count = len(folders['value'])
        total_count = folders.get('@odata.count', folder_count)
        
        print(f"✓ PASS: Retrieved {folder_count} folders")
        print(f"  Total count: {total_count}")
        
        # Show first 5 folders
        if folder_count > 0:
            print(f"\n  First 5 folders:")
            for i, folder in enumerate(folders['value'][:5], 1):
                name = folder.get('DisplayName', 'N/A')
                folder_id = folder.get('Id', 'N/A')
                path = folder.get('FullyQualifiedName', 'N/A')
                print(f"    {i}. {name} (ID: {folder_id})")
                print(f"       Path: {path}")
        
        return True
            
    except Exception as e:
        print(f"✗ FAIL: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        await client.close()


async def test_get_queues():
    """Test 3: Get Queues"""
    print("\n" + "=" * 60)
    print("TEST 3: Get Queues")
    print("=" * 60)
    
    client = OrchestratorClient()
    
    try:
        print("\n▶ Authenticating...")
        await client.authenticate()
        print("✓ Authenticated")
        
        print("\n▶ Fetching folders...")
        folders = await client.get_folders()
        print(f"✓ Found {len(folders['value'])} folders")
        
        print(f"\n▶ Testing queue access across folders...")
        
        tested = 0
        accessible = 0
        with_queues = 0
        
        for folder in folders['value'][:10]:  # Test first 10
            folder_id = folder['Id']
            folder_name = folder['DisplayName']
            tested += 1
            
            try:
                queues = await client.get_queues(folder_id=folder_id)
                accessible += 1
                
                queue_count = len(queues.get('value', []))
                
                if queue_count > 0:
                    with_queues += 1
                    print(f"  ✓ {folder_name}: {queue_count} queue(s)")
                    
                    # Show details for first folder with queues
                    if with_queues == 1:
                        print(f"\n  Sample queues from '{folder_name}':")
                        for i, queue in enumerate(queues['value'][:3], 1):
                            name = queue.get('Name', 'N/A')
                            queue_id = queue.get('Id', 'N/A')
                            max_retries = queue.get('MaxNumberOfRetries', 'N/A')
                            print(f"    {i}. {name}")
                            print(f"       ID: {queue_id}, Max Retries: {max_retries}")
                else:
                    print(f"  - {folder_name}: (no queues)")
                    
            except Exception as e:
                error_msg = str(e)
                if "403" in error_msg:
                    print(f"  ⚠ {folder_name}: Permission denied")
                elif "404" in error_msg:
                    print(f"  ⚠ {folder_name}: Not found")
                else:
                    print(f"  ✗ {folder_name}: {error_msg[:40]}")
        
        # Summary
        print(f"\n▶ Summary:")
        print(f"  Folders tested: {tested}")
        print(f"  Accessible: {accessible}")
        print(f"  With queues: {with_queues}")
        
        if accessible == 0:
            print("\n✗ FAIL: No folders accessible (permission issue)")
            return False
        elif with_queues == 0:
            print("\n⚠ WARNING: Queue retrieval works, but no queues found")
            return True
        else:
            print(f"\n✓ PASS: Successfully retrieved queues")
            return True
            
    except Exception as e:
        print(f"✗ FAIL: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        await client.close()


async def test_get_assets():
    """Test 4: Get Assets"""
    print("\n" + "=" * 60)
    print("TEST 4: Get Assets")
    print("=" * 60)
    
    client = OrchestratorClient()
    
    try:
        print("\n▶ Authenticating...")
        await client.authenticate()
        print("✓ Authenticated")
        
        print("\n▶ Fetching folders...")
        folders = await client.get_folders()
        print(f"✓ Found {len(folders['value'])} folders")
        
        print(f"\n▶ Testing asset access across folders...")
        
        tested = 0
        accessible = 0
        with_assets = 0
        
        for folder in folders['value'][:10]:  # Test first 10
            folder_id = folder['Id']
            folder_name = folder['DisplayName']
            tested += 1
            
            try:
                assets = await client.get_assets(folder_id=folder_id)
                accessible += 1
                
                asset_count = len(assets.get('value', []))
                
                if asset_count > 0:
                    with_assets += 1
                    print(f"  ✓ {folder_name}: {asset_count} asset(s)")
                    
                    # Show details for first folder with assets
                    if with_assets == 1:
                        print(f"\n  Sample assets from '{folder_name}':")
                        for i, asset in enumerate(assets['value'][:3], 1):
                            name = asset.get('Name', 'N/A')
                            value_type = asset.get('ValueType', 'N/A')
                            print(f"    {i}. {name} (Type: {value_type})")
                else:
                    print(f"  - {folder_name}: (no assets)")
                    
            except Exception as e:
                error_msg = str(e)
                if "403" in error_msg:
                    print(f"  ⚠ {folder_name}: Permission denied")
                elif "404" in error_msg:
                    print(f"  ⚠ {folder_name}: Not found")
                else:
                    print(f"  ✗ {folder_name}: {error_msg[:40]}")
        
        # Summary
        print(f"\n▶ Summary:")
        print(f"  Folders tested: {tested}")
        print(f"  Accessible: {accessible}")
        print(f"  With assets: {with_assets}")
        
        if accessible == 0:
            print("\n✗ FAIL: No folders accessible (permission issue)")
            return False
        elif with_assets == 0:
            print("\n⚠ WARNING: Asset retrieval works, but no assets found")
            return True
        else:
            print(f"\n✓ PASS: Successfully retrieved assets")
            return True
            
    except Exception as e:
        print(f"✗ FAIL: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        await client.close()

async def test_get_storage_buckets():
    """Test 5: Get Storage Buckets"""
    print("\n" + "=" * 60)
    print("TEST 5: Get Storage Buckets")
    print("=" * 60)
    
    client = OrchestratorClient()
    
    try:
        print("\n▶ Authenticating...")
        await client.authenticate()
        print("✓ Authenticated")
        
        print("\n▶ Fetching folders...")
        folders = await client.get_folders()
        print(f"✓ Found {len(folders['value'])} folders")
        
        print(f"\n▶ Testing storage bucket access across folders...")
        
        tested = 0
        accessible = 0
        with_buckets = 0
        
        for folder in folders['value'][:10]:  # Test first 10
            folder_id = folder['Id']
            folder_name = folder['DisplayName']
            tested += 1
            
            try:
                buckets = await client.get_storage_buckets(folder_id=folder_id)
                accessible += 1
                
                bucket_count = len(buckets.get('value', []))
                
                if bucket_count > 0:
                    with_buckets += 1
                    print(f"  ✓ {folder_name}: {bucket_count} bucket(s)")
                    
                    # Show details for first folder with buckets
                    if with_buckets == 1:
                        print(f"\n  Sample buckets from '{folder_name}':")
                        for i, bucket in enumerate(buckets['value'][:3], 1):
                            name = bucket.get('Name', 'N/A')
                            bucket_id = bucket.get('Id', 'N/A')
                            description = bucket.get('Description', 'N/A')
                            print(f"    {i}. {name}")
                            print(f"       ID: {bucket_id}, Description: {description}")
                else:
                    print(f"  - {folder_name}: (no buckets)")
                    
            except Exception as e:
                error_msg = str(e)
                if "403" in error_msg:
                    print(f"  ⚠ {folder_name}: Permission denied")
                elif "404" in error_msg:
                    print(f"  ⚠ {folder_name}: Not found")
                else:
                    print(f"  ✗ {folder_name}: {error_msg[:40]}")
        
        # Summary
        print(f"\n▶ Summary:")
        print(f"  Folders tested: {tested}")
        print(f"  Accessible: {accessible}")
        print(f"  With buckets: {with_buckets}")
        
        if accessible == 0:
            print("\n✗ FAIL: No folders accessible (permission issue)")
            return False
        elif with_buckets == 0:
            print("\n⚠ WARNING: Bucket retrieval works, but no buckets found")
            return True
        else:
            print(f"\n✓ PASS: Successfully retrieved storage buckets")
            return True
            
    except Exception as e:
        print(f"✗ FAIL: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        await client.close()

async def test_get_triggers():
    """Test 6: Get Triggers (Time and Queue)"""
    print("\n" + "=" * 60)
    print("TEST 6: Get Triggers")
    print("=" * 60)
    
    client = OrchestratorClient()
    
    try:
        print("\n▶ Authenticating...")
        await client.authenticate()
        print("✓ Authenticated")
        
        print("\n▶ Fetching folders...")
        folders = await client.get_folders()
        print(f"✓ Found {len(folders['value'])} folders")
        
        print(f"\n▶ Testing trigger access across folders...")
        
        tested = 0
        accessible = 0
        with_triggers = 0
        time_triggers_total = 0
        queue_triggers_total = 0
        
        for folder in folders['value'][:10]:  # Test first 10
            folder_id = folder['Id']
            folder_name = folder['DisplayName']
            tested += 1
            
            try:
                triggers = await client.get_triggers(folder_id=folder_id)
                accessible += 1
                
                trigger_count = len(triggers.get('value', []))
                
                if trigger_count > 0:
                    with_triggers += 1
                    
                    # Count trigger types
                    time_count = sum(1 for t in triggers['value'] if t.get('ScheduleType') == 'Cron')
                    queue_count = sum(1 for t in triggers['value'] if t.get('ScheduleType') == 'QueueTrigger')
                    
                    time_triggers_total += time_count
                    queue_triggers_total += queue_count
                    
                    print(f"  ✓ {folder_name}: {trigger_count} trigger(s) (Time: {time_count}, Queue: {queue_count})")
                    
                    # Show details for first folder with triggers
                    if with_triggers == 1:
                        print(f"\n  Sample triggers from '{folder_name}':")
                        for i, trigger in enumerate(triggers['value'][:3], 1):
                            name = trigger.get('Name', 'N/A')
                            schedule_type = trigger.get('ScheduleType', 'N/A')
                            enabled = trigger.get('Enabled', False)
                            print(f"    {i}. {name}")
                            print(f"       Type: {schedule_type}, Enabled: {enabled}")
                else:
                    print(f"  - {folder_name}: (no triggers)")
                    
            except Exception as e:
                error_msg = str(e)
                if "403" in error_msg:
                    print(f"  ⚠ {folder_name}: Permission denied")
                else:
                    print(f"  ✗ {folder_name}: {error_msg[:40]}")
        
        # Summary
        print(f"\n▶ Summary:")
        print(f"  Folders tested: {tested}")
        print(f"  Accessible: {accessible}")
        print(f"  Folders with triggers: {with_triggers}")
        print(f"  Total time triggers: {time_triggers_total}")
        print(f"  Total queue triggers: {queue_triggers_total}")
        
        if accessible == 0:
            print("\n✗ FAIL: No folders accessible (permission issue)")
            return False
        elif with_triggers == 0:
            print("\n⚠ WARNING: Trigger retrieval works, but no triggers found")
            return True
        else:
            print(f"\n✓ PASS: Successfully retrieved triggers")
            return True
            
    except Exception as e:
        print(f"✗ FAIL: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        await client.close()


# ============================================================================
# Main - Uncomment the test you want to run
# ============================================================================

if __name__ == "__main__":
    # Uncomment ONE test at a time:
    
    #result = asyncio.run(test_connection())
    #result = asyncio.run(test_get_folders())
    #result = asyncio.run(test_get_queues())
    #result = asyncio.run(test_get_assets())
    #result = asyncio.run(test_get_storage_buckets())
    result = asyncio.run(test_get_triggers())
    
    print("\n" + "=" * 60)
    if result:
        print("RESULT: ✓ PASSED")
    else:
        print("RESULT: ✗ FAILED")
    print("=" * 60)