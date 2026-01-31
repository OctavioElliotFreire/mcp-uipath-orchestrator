"""
Individual tests for UiPath Orchestrator Client (Multi-Account, Multi-Tenant)
Uncomment the test you want to run at the bottom
"""

import asyncio
from service import OrchestratorClient, CONFIG


# Helper to get all account/tenant combinations from config
def get_all_account_tenant_pairs():
    """Returns list of (account, tenant) tuples from CONFIG"""
    pairs = []
    for account, account_config in CONFIG["accounts"].items():
        for tenant in account_config["tenants"].keys():
            pairs.append((account, tenant))
    return pairs


# -----------------------------------------------------------------------------
# TEST 1: Authentication (shared token)
# -----------------------------------------------------------------------------




async def test_connection():
    """Test 1: Connection and Authentication (Shared Token)"""
    print("\n" + "=" * 60)
    print("TEST 1: Connection and Authentication (Shared Token)")
    print("=" * 60)

    # Use first account/tenant from config
    pairs = get_all_account_tenant_pairs()
    if not pairs:
        print("✗ FAIL: No accounts/tenants configured")
        return False
    
    account, tenant = pairs[0]
    print(f"▶ Using: {account} / {tenant}")
    
    client = OrchestratorClient(account=account, tenant=tenant)

    try:
        print("\n▶ Authenticating first time...")
        token1 = await client.authenticate()

        print("▶ Authenticating second time...")
        token2 = await client.authenticate()

        if token1 == token2:
            print("✓ PASS: Token reused successfully")
            print(f"  Token preview: {token1[:30]}...")
            return True
        else:
            print("✗ FAIL: Token mismatch")
            return False

    except Exception as e:
        print(f"✗ FAIL: {e}")
        return False

    finally:
        await client.close()


# -----------------------------------------------------------------------------
# TEST 2: Get folders (multi-account, multi-tenant)
# -----------------------------------------------------------------------------


async def test_get_folders_multi_tenant():
    print("\n" + "=" * 60)
    print("TEST 2: Get Folders (Multi-Account, Multi-Tenant)")
    print("=" * 60)

    pairs = get_all_account_tenant_pairs()
    results = {}

    for account, tenant in pairs:
        key = f"{account}/{tenant}"
        print(f"\n▶ Account/Tenant: {key}")
        client = OrchestratorClient(account=account, tenant=tenant)

        try:
            await client.authenticate()
            folders = await client.get_folders()

            count = len(folders.get("value", []))
            results[key] = count

            print(f"✓ {key}: {count} folders")

            if count > 0:
                sample = folders["value"][0]
                print(f"  Sample folder: {sample.get('DisplayName')} (ID: {sample.get('Id')})")

        except Exception as e:
            print(f"✗ {key}: {e}")
            return False

        finally:
            await client.close()

    print("\n▶ Summary:")
    for key, count in results.items():
        print(f"  {key}: {count} folders")

    return True



# test_get_resources.py

async def test_get_resources_multi_tenant():
    print("\n" + "=" * 60)
    print("TEST: Get Resources (Multi-Account, Multi-Tenant)")
    print("=" * 60)

    pairs = get_all_account_tenant_pairs()

    for account, tenant in pairs:
        key = f"{account}/{tenant}"
        print(f"\n▶ Account/Tenant: {key}")
        client = OrchestratorClient(account=account, tenant=tenant)

        try:
            await client.authenticate()

            folders = await client.get_folders()
            if not folders.get("value"):
                print(f"⚠ {key}: No folders found")
                continue

            folder = folders["value"][0]
            folder_id = folder["Id"]
            folder_name = folder.get("DisplayName")

            print(f"• Using folder: {folder_name} (Id={folder_id})")

            # Single resource
            resources = ["assets"]
            print(f"\n• Fetching resources: {resources}")
            result = await client.get_resources(resources, folder_id=folder_id)

            asset_count = len(result.get("assets", []))
            print(f"✓ {key}: {asset_count} assets")

            if asset_count > 0:
                sample = result["assets"][0]
                print(
                    f"  Sample asset: {sample.get('Name')} "
                    f"({sample.get('ValueType')})"
                )

            # Multiple resources
            resources = ["assets", "queues", "processes"]
            print(f"\n• Fetching resources: {resources}")
            result = await client.get_resources(resources, folder_id=folder_id)

            for resource, values in result.items():
                count = len(values)
                print(f"✓ {key}: {count} {resource}")

                if count > 0:
                    sample = values[0]
                    name = sample.get("Name") or sample.get("DisplayName")
                    print(f"  Sample {resource[:-1]}: {name}")

        except Exception as e:
            print(f"✗ {key}: {e}")
            return False

        finally:
            await client.close()

    return True





# -----------------------------------------------------------------------------
# TEST 3: Get assets (multi-account, multi-tenant)
# -----------------------------------------------------------------------------


async def test_get_assets_multi_tenant():
    print("\n" + "=" * 60)
    print("TEST 3: Get Assets (Multi-Account, Multi-Tenant)")
    print("=" * 60)

    pairs = get_all_account_tenant_pairs()

    for account, tenant in pairs:
        key = f"{account}/{tenant}"
        print(f"\n▶ Account/Tenant: {key}")
        client = OrchestratorClient(account=account, tenant=tenant)

        try:
            await client.authenticate()
            folders = await client.get_folders()

            if not folders.get("value"):
                print(f"⚠ {key}: No folders found")
                continue

            folder = folders["value"][0]
            assets = await client.get_assets(folder["Id"])

            asset_count = len(assets.get("value", []))
            print(f"✓ {key}: {asset_count} assets in '{folder['DisplayName']}'")

            if asset_count > 0:
                sample = assets["value"][0]
                print(f"  Sample asset: {sample.get('Name')} ({sample.get('ValueType')})")

        except Exception as e:
            print(f"✗ {key}: {e}")
            return False

        finally:
            await client.close()

    return True


# -----------------------------------------------------------------------------
# TEST 4: Get queues (multi-account, multi-tenant)
# -----------------------------------------------------------------------------

async def test_get_queues_multi_tenant():
    print("\n" + "=" * 60)
    print("TEST 4: Get Queues (Multi-Account, Multi-Tenant)")
    print("=" * 60)

    pairs = get_all_account_tenant_pairs()

    for account, tenant in pairs:
        key = f"{account}/{tenant}"
        print(f"\n▶ Account/Tenant: {key}")
        client = OrchestratorClient(account=account, tenant=tenant)

        try:
            await client.authenticate()
            folders = await client.get_folders()

            for folder in folders.get("value", [])[:3]:
                queues = await client.get_queues(folder["Id"])
                print(
                    f"✓ {key} | {folder['DisplayName']}: "
                    f"{len(queues.get('value', []))} queues"
                )

        except Exception as e:
            print(f"✗ {key}: {e}")
            return False

        finally:
            await client.close()

    return True


# -----------------------------------------------------------------------------
# TEST 5: Get triggers (multi-account, multi-tenant)
# -----------------------------------------------------------------------------

async def test_get_triggers_multi_tenant():
    print("\n" + "=" * 60)
    print("TEST 5: Get Triggers (Multi-Account, Multi-Tenant)")
    print("=" * 60)

    pairs = get_all_account_tenant_pairs()

    for account, tenant in pairs:
        key = f"{account}/{tenant}"
        print(f"\n▶ Account/Tenant: {key}")
        client = OrchestratorClient(account=account, tenant=tenant)

        try:
            await client.authenticate()
            folders = await client.get_folders()

            for folder in folders.get("value", [])[:3]:
                triggers = await client.get_triggers(folder["Id"])
                print(
                    f"✓ {key} | {folder['DisplayName']}: "
                    f"{len(triggers.get('value', []))} triggers"
                )

        except Exception as e:
            print(f"✗ {key}: {e}")
            return False

        finally:
            await client.close()

    return True


# -----------------------------------------------------------------------------
# TEST 6: Get processes (multi-account, multi-tenant)
# -----------------------------------------------------------------------------

async def test_get_processes_multi_tenant():
    print("\n" + "=" * 60)
    print("TEST 6: Get Processes (Multi-Account, Multi-Tenant)")
    print("=" * 60)

    pairs = get_all_account_tenant_pairs()

    for account, tenant in pairs:
        key = f"{account}/{tenant}"
        print(f"\n▶ Account/Tenant: {key}")
        client = OrchestratorClient(account=account, tenant=tenant)

        try:
            await client.authenticate()
            folders = await client.get_folders()

            for folder in folders.get("value", [])[:3]:
                processes = await client.get_processes(folder["Id"])
                print(
                    f"✓ {key} | {folder['DisplayName']}: "
                    f"{len(processes.get('value', []))} processes"
                )

        except Exception as e:
            print(f"✗ {key}: {e}")
            return False

        finally:
            await client.close()

    return True


# -----------------------------------------------------------------------------
# TEST 7: List library versions (multi-account, multi-tenant)
# -----------------------------------------------------------------------------

async def test_list_library_versions_flow():
    """
    Test (for ALL accounts/tenants):
    1. List libraries
    2. Pick the first library
    3. List all versions for that library
    """
    print("\n" + "=" * 60)
    print("TEST: List Libraries → List Library Versions (All Accounts/Tenants)")
    print("=" * 60)

    pairs = get_all_account_tenant_pairs()
    results = {}

    for account, tenant in pairs:
        key = f"{account}/{tenant}"
        print("\n" + "-" * 60)
        print(f"▶ Account/Tenant: {key}")
        print("-" * 60)

        client = OrchestratorClient(account=account, tenant=tenant)

        try:
            print("▶ Authenticating...")
            await client.authenticate()
            print("✓ Authenticated")

            # Step 1: List libraries
            print("▶ Fetching libraries...")
            libraries = await client.list_libraries()

            if not libraries:
                print(f"✗ FAIL: No libraries found in {key}")
                results[key] = False
                continue

            print(f"✓ Found {len(libraries)} libraries")

            # Show first 5 libraries
            print("  Sample libraries:")
            for i, lib in enumerate(libraries[:5], 1):
                print(f"    {i}. {lib}")

            # Step 2: Pick the first library
            package_id = libraries[0]
            print(f"▶ Testing versions for library: {package_id}")

            # Step 3: List versions
            versions = await client.list_library_versions(package_id)

            if not versions:
                print(f"✗ FAIL: No versions returned for {package_id}")
                results[key] = False
                continue

            print(f"✓ Found {len(versions)} versions for {package_id}")

            # Show versions
            print("  Versions:")
            for v in versions:
                print(f"    - {v}")

            print(f"✓ PASS: Library version enumeration works for {key}")
            results[key] = True

        except Exception as e:
            print(f"✗ FAIL for {key}: {e}")
            import traceback
            traceback.print_exc()
            results[key] = False

        finally:
            await client.close()



# -----------------------------------------------------------------------------
# TEST 8: Download library (all accounts/tenants)
# -----------------------------------------------------------------------------

async def test_download_library_version():
    """
    Test (for ALL accounts/tenants):
    1. Authenticate
    2. List libraries
    3. Pick first library
    4. List versions
    5. Download a specific version
    6. Verify file exists in download_dir
    """
    print("\n" + "=" * 60)
    print("TEST: Download Library Version (All Accounts/Tenants)")
    print("=" * 60)

    pairs = get_all_account_tenant_pairs()
    if not pairs:
        print("✗ FAIL: No accounts/tenants configured")
        return False
    
    results = {}

    for account, tenant in pairs:
        key = f"{account}/{tenant}"
        print("\n" + "-" * 60)
        print(f"▶ Account/Tenant: {key}")
        print("-" * 60)

        client = OrchestratorClient(account=account, tenant=tenant)

        try:
            print("▶ Authenticating...")
            await client.authenticate()
            print("✓ Authenticated")

            print("▶ Fetching libraries...")
            libraries = await client.list_libraries()
            if not libraries:
                print(f"⚠ {key}: No libraries found, skipping")
                results[key] = "skipped"
                continue

            package_id = libraries[0]
            print(f"▶ Selected library: {package_id}")

            print("▶ Fetching versions...")
            versions = await client.list_library_versions(package_id)
            if not versions:
                print(f"✗ FAIL: No versions found for {package_id}")
                results[key] = False
                continue

            # Pick latest version
            version = versions[-1]  # Last version (usually newest)
            print(f"▶ Downloading version: {version}")

            path = await client.download_library_version(
                package_id=package_id,
                version=version
            )

            print(f"✓ Downloaded to: {path}")

            if not path.exists():
                print(f"✗ FAIL: File does not exist on disk")
                results[key] = False
                continue

            size = path.stat().st_size
            print(f"✓ File size: {size:,} bytes")

            if size == 0:
                print(f"✗ FAIL: Downloaded file is empty")
                results[key] = False
                continue

            print(f"✓ PASS: Library download works for {key}")
            results[key] = True

        except Exception as e:
            print(f"✗ FAIL for {key}: {e}")
            import traceback
            traceback.print_exc()
            results[key] = False

        finally:
            await client.close()

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY: Download Library Test Results")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v == "skipped")
    
    for key, result in results.items():
        status = "✓ PASS" if result is True else "⚠ SKIP" if result == "skipped" else "✗ FAIL"
        print(f"  {status}: {key}")
    
    print(f"\nTotal: {len(results)} | Passed: {passed} | Failed: {failed} | Skipped: {skipped}")
    
    # Return True only if all tests passed (no failures)
    return failed == 0


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    # Uncomment ONE test at a time:

   # result = asyncio.run(test_connection())
    #result = asyncio.run(test_get_folders_multi_tenant())
    #result = asyncio.run(test_get_assets_multi_tenant())
    #result = asyncio.run(test_get_queues_multi_tenant())
    #result = asyncio.run(test_get_triggers_multi_tenant())
    #result = asyncio.run(test_get_processes_multi_tenant())
    #result = asyncio.run(test_list_library_versions_flow())
    #result = asyncio.run(test_download_library_version())
    result = asyncio.run(test_get_resources_multi_tenant())