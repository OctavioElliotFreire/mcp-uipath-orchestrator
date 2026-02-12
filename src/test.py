"""
Individual tests for UiPath Orchestrator Client (Multi-Account, Multi-Tenant)
Uncomment the test you want to run at the bottom
"""

import asyncio
from service import (OrchestratorClient,CONFIG,get_available_accounts,get_available_tenants)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def get_all_account_tenant_pairs() -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for account in get_available_accounts(CONFIG):
        for tenant in get_available_tenants(CONFIG, account):
            pairs.append((account, tenant))
    return pairs


# -----------------------------------------------------------------------------
# TEST 1: Authentication
# -----------------------------------------------------------------------------

async def test_connection():
    print("\n" + "=" * 60)
    print("TEST 1: Connection and Authentication")
    print("=" * 60)

    pairs = get_all_account_tenant_pairs()
    if not pairs:
        print("✗ FAIL: No accounts/tenants configured")
        return False

    account, tenant = pairs[0]
    client = OrchestratorClient(account, tenant)

    try:
        token1 = await client.authenticate()
        token2 = await client.authenticate()

        assert token1 == token2
        print("✓ PASS: Token reused")
        return True

    except Exception as e:
        print(f"✗ FAIL: {e}")
        return False

    finally:
        await client.close()


# -----------------------------------------------------------------------------
# TEST 2: Get folders
# -----------------------------------------------------------------------------

async def test_get_folders_tree_multi_tenant():
    print("\n" + "=" * 60)
    print("TEST 2: Get Folder Tree (Multi-Account, Multi-Tenant)")
    print("=" * 60)

    def print_tree(nodes: list[dict], level: int = 0):
        """Recursively print folder tree."""
        indent = "  " * level
        for node in nodes:
            print(
                f"{indent}- {node.get('DisplayName')} "
                f"(ID: {node.get('Id')})"
            )
            children = node.get("children", [])
            if children:
                print_tree(children, level + 1)

    for account, tenant in get_all_account_tenant_pairs():
        key = f"{account}/{tenant}"
        client = OrchestratorClient(account, tenant)

        try:
            await client.authenticate()

           
            tree = await client.get_folders_tree()

            print(f"\n✓ {key}: {len(tree)} root folders")

            if tree:
                print_tree(tree)

        except Exception as e:
            print(f"✗ {key}: {e}")
            return False

        finally:
            await client.close()

    return True



async def test_get_folders_multi_tenant():
    print("\n" + "=" * 60)
    print("TEST 2: Get Folders (Multi-Account, Multi-Tenant)")
    print("=" * 60)

    for account, tenant in get_all_account_tenant_pairs():
        key = f"{account}/{tenant}"
        client = OrchestratorClient(account, tenant)

        try:
            await client.authenticate()
            folders = await client.get_folders()

            print(f"✓ {key}: {len(folders)} folders")

            if folders:
                sample = folders[0]
                print(
                    f"  Sample: {sample.get('DisplayName')} "
                    f"(ID: {sample.get('Id')})"
                )

        except Exception as e:
            print(f"✗ {key}: {e}")
            return False

        finally:
            await client.close()

    return True


# -----------------------------------------------------------------------------
# TEST 3: Get assets
# -----------------------------------------------------------------------------

async def test_get_assets_multi_tenant():
    print("\n" + "=" * 60)
    print("TEST 3: Get Assets")
    print("=" * 60)

    for account, tenant in get_all_account_tenant_pairs():
        key = f"{account}/{tenant}"
        client = OrchestratorClient(account, tenant)

        try:
            await client.authenticate()
            folders = await client.get_folders()

            if not folders:
                print(f"⚠ {key}: No folders")
                continue

            folder = folders[0]
            assets = await client.get_assets(folder["Id"])

            print(
                f"✓ {key}: {len(assets)} assets "
                f"in '{folder['DisplayName']}'"
            )

        except Exception as e:
            print(f"✗ {key}: {e}")
            return False

        finally:
            await client.close()

    return True


# -----------------------------------------------------------------------------
# TEST 4–6: Queues / Triggers / Processes (pattern-based)
# -----------------------------------------------------------------------------

async def test_folder_collections(method_name: str, label: str):
    print("\n" + "=" * 60)
    print(f"TEST: {label}")
    print("=" * 60)

    for account, tenant in get_all_account_tenant_pairs():
        key = f"{account}/{tenant}"
        client = OrchestratorClient(account, tenant)

        try:
            await client.authenticate()
            folders = await client.get_folders()

            for folder in folders[:3]:
                method = getattr(client, method_name)
                items = await method(folder["Id"])
                print(
                    f"✓ {key} | {folder['DisplayName']}: "
                    f"{len(items)} {label.lower()}"
                )

        except Exception as e:
            print(f"✗ {key}: {e}")
            return False

        finally:
            await client.close()

    return True


# -----------------------------------------------------------------------------
# TEST 7: Libraries → Versions
# -----------------------------------------------------------------------------

async def test_list_library_versions_flow():
    print("\n" + "=" * 60)
    print("TEST: Libraries → Versions")
    print("=" * 60)

    for account, tenant in get_all_account_tenant_pairs():
        key = f"{account}/{tenant}"
        client = OrchestratorClient(account, tenant)

        try:
            await client.authenticate()
            libraries = await client.list_libraries()

            if not libraries:
                print(f"⚠ {key}: No libraries")
                continue

            package_id = libraries[0]
            versions = await client.list_library_versions(package_id)

            print(
                f"✓ {key}: {package_id} → "
                f"{len(versions)} versions"
            )

        except Exception as e:
            print(f"✗ {key}: {e}")
            return False

        finally:
            await client.close()

    return True


# -----------------------------------------------------------------------------
# TEST 8: Download library
# -----------------------------------------------------------------------------

async def test_download_library_version():
    print("\n" + "=" * 60)
    print("TEST: Download Library Version")
    print("=" * 60)

    for account, tenant in get_all_account_tenant_pairs():
        key = f"{account}/{tenant}"
        client = OrchestratorClient(account, tenant)

        try:
            await client.authenticate()
            libraries = await client.list_libraries()
            if not libraries:
                print(f"⚠ {key}: No libraries")
                continue

            package_id = libraries[0]
            versions = await client.list_library_versions(package_id)
            version = versions[-1]

            path = await client.download_library_version(package_id, version)
            assert path.exists()
            assert path.stat().st_size > 0

            print(f"✓ {key}: Downloaded {path.name}")

        except Exception as e:
            print(f"✗ {key}: {e}")
            return False

        finally:
            await client.close()

    return True


# -----------------------------------------------------------------------------
# TEST 9: get_resources
# -----------------------------------------------------------------------------

async def test_get_resources():
    print("\n" + "=" * 60)
    print("TEST: get_resources()")
    print("=" * 60)

    for account, tenant in get_all_account_tenant_pairs():
        key = f"{account}/{tenant}"
        client = OrchestratorClient(account, tenant)

        try:
            await client.authenticate()
            folders = await client.get_folders()

            if not folders:
                print(f"⚠ {key}: No folders")
                continue

            for folder in folders[:5]:
                print(f"\n📁 {folder['DisplayName']} ({folder['Id']})")

                result = await client.get_resources(
                    resource_types=["assets", "queues", "processes", "triggers"],
                    folder_id=folder["Id"],
                )

                for k, v in result.items():
                    if isinstance(v, dict) and "error" in v:
                        print(f"  ✗ {k}: {v['error']}")
                    else:
                        print(f"  ✓ {k}: {len(v)}")

        except Exception as e:
            print(f"✗ {key}: {e}")
            return False

        finally:
            await client.close()

    return True

# -----------------------------------------------------------------------------
# TEST 10: Ensure_folder_path
# -----------------------------------------------------------------------------

async def test_ensure_folder_path():
    print("\n" + "=" * 60)
    print("TEST: Ensure Folder Path")
    print("=" * 60)

    account = "billiysusldx"
    tenant = "DefaultTenant"

    test_path = "Shared/MCP_Test/Level1/Level2"

    client = OrchestratorClient(account, tenant)

    try:
        await client.authenticate()

        # 1️⃣ First call (should create folders)
        leaf = await client.ensure_folder_path(test_path)

        print(f"✓ Created or ensured path: {test_path}")
        print(f"  Leaf Folder ID: {leaf.get('Id')}")

        # 2️⃣ Second call (should NOT create duplicates)
        leaf_again = await client.ensure_folder_path(test_path)

        print("✓ Called ensure_folder_path again (idempotency check)")

        if leaf["Id"] != leaf_again["Id"]:
            print("✗ Id mismatch — not idempotent!")
            return False

        print("✓ Idempotency confirmed (same folder ID)")

        # 3️⃣ Validate structure exists in tree
        tree = await client.get_folders_tree()

        def find_path(nodes, segments):
            if not segments:
                return True

            for node in nodes:
                if node["DisplayName"] == segments[0]:
                    return find_path(node.get("children", []), segments[1:])

            return False

        exists = find_path(tree, test_path.split("/"))

        if not exists:
            print("✗ Folder path not found in tree")
            return False

        print("✓ Folder structure verified in tree")

        return True

    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False

    finally:
        await client.close()

# -----------------------------------------------------------------------------
# TEST 11: Ensure_folder_path
# -----------------------------------------------------------------------------


    print("\n" + "=" * 60)
    print("TEST: Ensure Asset Local (CREATE-ONLY POLICY)")
    print("=" * 60)

    account = "billiysusldx"
    tenant = "DefaultTenant"

    folder_path = "Shared/MCP_Test/Level1/Level2"

    import os
    cred_password = os.getenv("MCP_TEST_CRED_PASSWORD", "").strip()

    client = OrchestratorClient(account, tenant)

    try:
        await client.authenticate()

        # Ensure folder exists once
        await client.ensure_folder_path(folder_path)

        test_cases = [
            {
                "label": "Text",
                "name": "MCP_TEST_ASSET_TEXT",
                "spec_create": {
                    "Name": "MCP_TEST_ASSET_TEXT",
                    "ValueType": "Text",
                    "Value": "initial_value",
                },
                "spec_update": {
                    "Name": "MCP_TEST_ASSET_TEXT",
                    "ValueType": "Text",
                    "Value": "should_not_update",
                },
                "field": "StringValue",
            },
            {
                "label": "Bool",
                "name": "MCP_TEST_ASSET_BOOL",
                "spec_create": {
                    "Name": "MCP_TEST_ASSET_BOOL",
                    "ValueType": "Bool",
                    "Value": False,
                },
                "spec_update": {
                    "Name": "MCP_TEST_ASSET_BOOL",
                    "ValueType": "Bool",
                    "Value": True,
                },
                "field": "BoolValue",
            },
            {
                "label": "Integer",
                "name": "MCP_TEST_ASSET_INT",
                "spec_create": {
                    "Name": "MCP_TEST_ASSET_INT",
                    "ValueType": "Integer",
                    "Value": 1,
                },
                "spec_update": {
                    "Name": "MCP_TEST_ASSET_INT",
                    "ValueType": "Integer",
                    "Value": 999,
                },
                "field": "IntValue",
            },
        ]

        # Add Credential case only if password provided
        if cred_password:
            test_cases.append(
                {
                    "label": "Credential",
                    "name": "MCP_TEST_ASSET_CRED",
                    "spec_create": {
                        "Name": "MCP_TEST_ASSET_CRED",
                        "ValueType": "Credential",
                        "Value": {
                            "username": "mcp_test_user",
                            "password": cred_password,
                        },
                    },
                    "spec_update": {
                        "Name": "MCP_TEST_ASSET_CRED",
                        "ValueType": "Credential",
                        "Value": {
                            "username": "mcp_test_user",
                            "password": "different_password_should_be_ignored",
                        },
                    },
                    "field": "CredentialUsername",  # password is never returned
                }
            )
        else:
            print("⚠ Skipping Credential test (MCP_TEST_CRED_PASSWORD not set)")

        # ----------------------------------------------------------
        # Execute test cases
        # ----------------------------------------------------------
        for case in test_cases:

            print("\n" + "-" * 60)
            print(f"CASE: {case['label']} ({case['name']})")
            print("-" * 60)

            # 1️⃣ Create
            asset1 = await client.ensure_asset_local(
                folder_path,
                case["spec_create"],
            )

            print(f"✓ Created or ensured — Asset ID: {asset1.get('Id')}")

            # 2️⃣ Call again with modified value (should NOT update)
            asset2 = await client.ensure_asset_local(
                folder_path,
                case["spec_update"],
            )

            if asset1.get("Id") != asset2.get("Id"):
                raise AssertionError("✗ Asset ID changed — not idempotent")

            print("✓ No update performed (create-only policy)")
            print("✓ Idempotency confirmed")

            # 3️⃣ Verify original value still stored
            folder = await client.ensure_folder_path(folder_path)
            assets = await client.get_assets(folder["Id"])

            stored = next(
                (a for a in assets if a["Name"] == case["name"]),
                None,
            )

            if not stored:
                raise AssertionError("✗ Asset not found after ensure")

            field = case["field"]

            if case["label"] == "Credential":
                expected = case["spec_create"]["Value"]["username"]
            else:
                expected = case["spec_create"]["Value"]

            if stored.get(field) != expected:
                raise AssertionError(
                    f"✗ Asset value was modified unexpectedly "
                    f"(expected={expected}, got={stored.get(field)})"
                )

            print("✓ Verified original value preserved")

        print("\n" + "=" * 60)
        print("✓ PASS: All create-only asset tests completed successfully")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"\n✗ FAIL: {e}")
        return False

    finally:
        await client.close()

async def test_ensure_asset_local():
    print("\n" + "=" * 60)
    print("TEST: Ensure Asset Local (CREATE-ONLY POLICY)")
    print("=" * 60)

    account = "billiysusldx"
    tenant = "DefaultTenant"
    folder_path = "Shared/MCP_Test/Level1/Level2"

    TEST_PASSWORD = "TestPassword123!"

    client = OrchestratorClient(account, tenant)

    try:
        await client.authenticate()
        await client.ensure_folder_path(folder_path)

        test_cases = [
            {
                "label": "Text",
                "name": "MCP_TEST_ASSET_TEXT",
                "spec_create": {
                    "Name": "MCP_TEST_ASSET_TEXT",
                    "ValueType": "Text",
                    "Value": "initial_value",
                },
                "spec_update": {
                    "Name": "MCP_TEST_ASSET_TEXT",
                    "ValueType": "Text",
                    "Value": "should_not_update",
                },
                "field": "StringValue",
            },
            {
                "label": "Bool",
                "name": "MCP_TEST_ASSET_BOOL",
                "spec_create": {
                    "Name": "MCP_TEST_ASSET_BOOL",
                    "ValueType": "Bool",
                    "Value": False,
                },
                "spec_update": {
                    "Name": "MCP_TEST_ASSET_BOOL",
                    "ValueType": "Bool",
                    "Value": True,
                },
                "field": "BoolValue",
            },
            {
                "label": "Integer",
                "name": "MCP_TEST_ASSET_INT",
                "spec_create": {
                    "Name": "MCP_TEST_ASSET_INT",
                    "ValueType": "Integer",
                    "Value": 1,
                },
                "spec_update": {
                    "Name": "MCP_TEST_ASSET_INT",
                    "ValueType": "Integer",
                    "Value": 999,
                },
                "field": "IntValue",
            },
            {
                "label": "Credential",
                "name": "MCP_TEST_ASSET_CRED",
                "spec_create": {
                    "Name": "MCP_TEST_ASSET_CRED",
                    "ValueType": "Credential",
                    "Value": None,  # ignored
                },
                "spec_update": {
                    "Name": "MCP_TEST_ASSET_CRED",
                    "ValueType": "Credential",
                    "Value": None,  # ignored
                },
                "field": None,
            },
        ]

        # ----------------------------------------------------------
        # Execute test cases
        # ----------------------------------------------------------
        for case in test_cases:

            print("\n" + "-" * 60)
            print(f"CASE: {case['label']} ({case['name']})")
            print("-" * 60)

            # 1️⃣ Create
            asset1 = await client.ensure_asset_local(
                folder_path,
                case["spec_create"],
            )

            print(f"✓ Created or ensured — Asset ID: {asset1.get('Id')}")

            # 2️⃣ Call again with modified value (should NOT update)
            asset2 = await client.ensure_asset_local(
                folder_path,
                case["spec_update"],
            )

            if asset1.get("Id") != asset2.get("Id"):
                raise AssertionError("✗ Asset ID changed — not idempotent")

            print("✓ No update performed (create-only policy)")
            print("✓ Idempotency confirmed")

            # 3️⃣ For non-credential types, verify original value preserved
            if case["field"]:

                folder = await client.ensure_folder_path(folder_path)
                assets = await client.get_assets(folder["Id"])

                stored = next(
                    (a for a in assets if a["Name"] == case["name"]),
                    None,
                )

                if not stored:
                    raise AssertionError("✗ Asset not found after ensure")

                expected = case["spec_create"]["Value"]

                if stored.get(case["field"]) != expected:
                    raise AssertionError(
                        f"✗ Asset value was modified unexpectedly "
                        f"(expected={expected}, got={stored.get(case['field'])})"
                    )

                print("✓ Verified original value preserved")

            else:
                print("✓ Credential created and idempotent (value not validated)")

        print("\n" + "=" * 60)
        print("✓ PASS: All create-only asset tests completed successfully")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"\n✗ FAIL: {e}")
        return False

    finally:
        await client.close()

# -----------------------------------------------------------------------------
# TEST: attach_asset_linked_folders
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# TEST: attach_asset_linked_folders (DISPLAY ONLY)
# -----------------------------------------------------------------------------

async def test_attach_asset_linked_folders():
    print("\n" + "=" * 60)
    print("TEST: attach_asset_linked_folders() — DISPLAY OUTPUT (FIRST TENANT)")
    print("=" * 60)

    pairs = get_all_account_tenant_pairs()

    if not pairs:
        print("No account/tenant configured.")
        return False

    account, tenant = pairs[0]
    print(f"Using: {account}/{tenant}")

    client = OrchestratorClient(account, tenant)

    try:
        await client.authenticate()

        folders = await client.get_folders()
        if not folders:
            print("No folders found.")
            return False

        # Pick first folder that contains assets
        for folder in folders:
            raw_assets = await client.get_assets(folder["Id"])

            if raw_assets:
                print(f"\nFolder: {folder['DisplayName']}")

                enhanced = await client.attach_asset_linked_folders(raw_assets)
                print(enhanced)
                for asset in enhanced:
                    print("\n-----------------------------------")
                    print(f"Asset Name : {asset.get('Name')}")
                    print(f"Asset ID   : {asset.get('Id')}")
                    print(f"Type       : {asset.get('ValueType')}")
                    print("LinkedFolders:")

                    for lf in asset.get("LinkedFolders", []):
                        print(f"   - {lf}")

                return True

        print("No assets found in any folder.")
        return False

    except Exception as e:
        print(f"✗ Error: {e}")
        return False

    finally:
        await client.close()



# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    # Uncomment ONE test at a time

     #asyncio.run(test_connection())
     #asyncio.run(test_get_folders_tree_multi_tenant())
     #asyncio.run(test_get_folders_multi_tenant())
     #asyncio.run(test_get_assets_multi_tenant())
     #asyncio.run(test_folder_collections("get_queues", "Queues"))
     #asyncio.run(test_folder_collections("get_triggers", "Triggers"))
     #asyncio.run(test_folder_collections("get_processes", "Processes"))
     #asyncio.run(test_list_library_versions_flow())
     #asyncio.run(test_download_library_version())
     #asyncio.run(test_get_resources())
     #asyncio.run(test_ensure_folder_path())
     #asyncio.run(test_ensure_asset_local())
     asyncio.run(test_attach_asset_linked_folders())