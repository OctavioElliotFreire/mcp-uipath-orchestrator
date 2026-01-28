"""
Individual tests for UiPath Orchestrator Client (Multi-Tenant)
Uncomment the test you want to run at the bottom
"""

import asyncio
import os
from service import OrchestratorClient

TENANTS = [
    t.strip()
    for t in os.getenv("TENANTS", "").split(",")
    if t.strip()
]


# -----------------------------------------------------------------------------
# TEST 1: Authentication (shared token)
# -----------------------------------------------------------------------------

async def test_connection():
    """Test 1: Connection and Authentication (Shared Token)"""
    print("\n" + "=" * 60)
    print("TEST 1: Connection and Authentication (Shared Token)")
    print("=" * 60)

    client = OrchestratorClient()

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
# TEST 2: Get folders (multi-tenant)
# -----------------------------------------------------------------------------

async def test_get_folders_multi_tenant():
    print("\n" + "=" * 60)
    print("TEST 2: Get Folders (Multi-Tenant)")
    print("=" * 60)

    results = {}

    for tenant in TENANTS:
        print(f"\n▶ Tenant: {tenant}")
        client = OrchestratorClient(tenant=tenant)

        try:
            await client.authenticate()
            folders = await client.get_folders()

            count = len(folders.get("value", []))
            results[tenant] = count

            print(f"✓ {tenant}: {count} folders")

            if count > 0:
                sample = folders["value"][0]
                print(f"  Sample folder: {sample.get('DisplayName')} (ID: {sample.get('Id')})")

        except Exception as e:
            print(f"✗ {tenant}: {e}")
            return False

        finally:
            await client.close()

    print("\n▶ Summary:")
    for tenant, count in results.items():
        print(f"  {tenant}: {count} folders")

    return True


# -----------------------------------------------------------------------------
# TEST 3: Get assets (multi-tenant)
# -----------------------------------------------------------------------------

async def test_get_assets_multi_tenant():
    print("\n" + "=" * 60)
    print("TEST 3: Get Assets (Multi-Tenant)")
    print("=" * 60)

    for tenant in TENANTS:
        print(f"\n▶ Tenant: {tenant}")
        client = OrchestratorClient(tenant=tenant)

        try:
            await client.authenticate()
            folders = await client.get_folders()

            if not folders.get("value"):
                print(f"⚠ {tenant}: No folders found")
                continue

            folder = folders["value"][0]
            assets = await client.get_assets(folder["Id"])

            asset_count = len(assets.get("value", []))
            print(f"✓ {tenant}: {asset_count} assets in '{folder['DisplayName']}'")

            if asset_count > 0:
                sample = assets["value"][0]
                print(f"  Sample asset: {sample.get('Name')} ({sample.get('ValueType')})")

        except Exception as e:
            print(f"✗ {tenant}: {e}")
            return False

        finally:
            await client.close()

    return True


# -----------------------------------------------------------------------------
# TEST 4: Get queues (multi-tenant)
# -----------------------------------------------------------------------------

async def test_get_queues_multi_tenant():
    print("\n" + "=" * 60)
    print("TEST 4: Get Queues (Multi-Tenant)")
    print("=" * 60)

    for tenant in TENANTS:
        print(f"\n▶ Tenant: {tenant}")
        client = OrchestratorClient(tenant=tenant)

        try:
            await client.authenticate()
            folders = await client.get_folders()

            for folder in folders.get("value", [])[:3]:
                queues = await client.get_queues(folder["Id"])
                print(
                    f"✓ {tenant} | {folder['DisplayName']}: "
                    f"{len(queues.get('value', []))} queues"
                )

        except Exception as e:
            print(f"✗ {tenant}: {e}")
            return False

        finally:
            await client.close()

    return True


# -----------------------------------------------------------------------------
# TEST 5: Get triggers (multi-tenant)
# -----------------------------------------------------------------------------

async def test_get_triggers_multi_tenant():
    print("\n" + "=" * 60)
    print("TEST 5: Get Triggers (Multi-Tenant)")
    print("=" * 60)

    for tenant in TENANTS:
        print(f"\n▶ Tenant: {tenant}")
        client = OrchestratorClient(tenant=tenant)

        try:
            await client.authenticate()
            folders = await client.get_folders()

            for folder in folders.get("value", [])[:3]:
                triggers = await client.get_triggers(folder["Id"])
                print(
                    f"✓ {tenant} | {folder['DisplayName']}: "
                    f"{len(triggers.get('value', []))} triggers"
                )

        except Exception as e:
            print(f"✗ {tenant}: {e}")
            return False

        finally:
            await client.close()

    return True


# -----------------------------------------------------------------------------
# TEST 6: Get processes (multi-tenant)
# -----------------------------------------------------------------------------

async def test_get_processes_multi_tenant():
    print("\n" + "=" * 60)
    print("TEST 6: Get Processes (Multi-Tenant)")
    print("=" * 60)

    for tenant in TENANTS:
        print(f"\n▶ Tenant: {tenant}")
        client = OrchestratorClient(tenant=tenant)

        try:
            await client.authenticate()
            folders = await client.get_folders()

            for folder in folders.get("value", [])[:3]:
                processes = await client.get_processes(folder["Id"])
                print(
                    f"✓ {tenant} | {folder['DisplayName']}: "
                    f"{len(processes.get('value', []))} processes"
                )

        except Exception as e:
            print(f"✗ {tenant}: {e}")
            return False

        finally:
            await client.close()

    return True

# -----------------------------------------------------------------------------
# TEST 7: Get packages (multi-tenant)
# -----------------------------------------------------------------------------


async def test_list_library_versions_flow():
    """
    Test (for ALL tenants):
    1. List libraries
    2. Pick the first library
    3. List all versions for that library
    """
    print("\n" + "=" * 60)
    print("TEST: List Libraries → List Library Versions (All Tenants)")
    print("=" * 60)

    results = {}

    for tenant in TENANTS:
        print("\n" + "-" * 60)
        print(f"▶ Tenant: {tenant}")
        print("-" * 60)

        client = OrchestratorClient(tenant=tenant)

        try:
            print("▶ Authenticating...")
            await client.authenticate()
            print("✓ Authenticated")

            # Step 1: List libraries
            print("▶ Fetching libraries...")
            libraries = await client.list_libraries()

            if not libraries:
                print(f"✗ FAIL: No libraries found in tenant {tenant}")
                results[tenant] = False
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
                results[tenant] = False
                continue

            print(f"✓ Found {len(versions)} versions for {package_id}")

            # Show versions
            print("  Versions:")
            for v in versions:
                print(f"    - {v}")

            print(f"✓ PASS: Library version enumeration works for {tenant}")
            results[tenant] = True

        except Exception as e:
            print(f"✗ FAIL for tenant {tenant}: {e}")
            import traceback
            traceback.print_exc()
            results[tenant] = False

        finally:
            await client.close()

# -----------------------------------------------------------------------------
# TEST 8: Download library (multi-tenant)
# -----------------------------------------------------------------------------


async def test_download_library_version():
    """
    Test:
    1. Authenticate
    2. List libraries
    3. Pick first library
    4. List versions
    5. Download a specific version
    6. Verify file exists in DOWNLOAD_DIR
    """
    print("\n" + "=" * 60)
    print("TEST: Download Library Version")
    print("=" * 60)

    tenant = TENANTS[0]
    print(f"\n▶ Using tenant: {tenant}")

    client = OrchestratorClient(tenant=tenant)

    try:
        print("▶ Authenticating...")
        await client.authenticate()
        print("✓ Authenticated")

        print("▶ Fetching libraries...")
        libraries = await client.list_libraries()
        if not libraries:
            print("✗ FAIL: No libraries found")
            return False

        package_id =  libraries[0]
        print(f"▶ Selected library: {package_id}")

        print("▶ Fetching versions...")
        versions = await client.list_library_versions(package_id)
        if not versions:
            print("✗ FAIL: No versions found")
            return False

        # Pick latest version
        version = versions[0]
        print(f"▶ Downloading version: {version}")

        path = await client.download_library_version(
            package_id=package_id,
            version=version
        )

        print(f"✓ Downloaded to: {path}")

        if not path.exists():
            print("✗ FAIL: File does not exist on disk")
            return False

        size = path.stat().st_size
        print(f"✓ File size: {size} bytes")

        if size == 0:
            print("✗ FAIL: Downloaded file is empty")
            return False

        print("\n✓ PASS: Library download works")
        return True

    except Exception as e:
        print(f"\n✗ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        await client.close()





# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    # Uncomment ONE test at a time:

    #result = asyncio.run(test_connection())
    #result = asyncio.run(test_get_folders_multi_tenant())
    #result = asyncio.run(test_get_assets_multi_tenant())
    #result = asyncio.run(test_get_queues_multi_tenant())
    #result = asyncio.run(test_get_triggers_multi_tenant())
    #result = asyncio.run(test_get_processes_multi_tenant())
    #result = asyncio.run(test_list_library_versions_flow())
    result = asyncio.run(test_download_library_version())

