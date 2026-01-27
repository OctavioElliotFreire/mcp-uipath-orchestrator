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
# MAIN
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    # Uncomment ONE test at a time:

    result = asyncio.run(test_connection())
    result = asyncio.run(test_get_folders_multi_tenant())
    result = asyncio.run(test_get_assets_multi_tenant())
    result = asyncio.run(test_get_queues_multi_tenant())
    result = asyncio.run(test_get_triggers_multi_tenant())
    result = asyncio.run(test_get_processes_multi_tenant())

    print("\n" + "=" * 60)
    print("RESULT:", "✓ PASSED" if result else "✗ FAILED")
    print("=" * 60)
