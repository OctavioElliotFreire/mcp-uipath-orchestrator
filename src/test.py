

"""
Individual tests for UiPath Orchestrator Client (Multi-Account, Multi-Tenant)
Uncomment the test you want to run at the bottom
"""
import json
import asyncio
from service import (OrchestratorClient,CONFIG,get_available_accounts,get_available_tenants)
import json
from service import OrchestratorClient, QueueItemStatus,ResourceTypes,LinkableResourceTypes
from pathlib import Path



# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def get_all_account_tenant_pairs() -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for account in get_available_accounts(CONFIG):
        for tenant in get_available_tenants(CONFIG, account):
            pairs.append((account, tenant))
    return pairs

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



async def test_get_resources():
    print("\n" + "=" * 60)
    print("TEST: get_resources() — FULL OUTPUT")
    print("=" * 60)

    pairs = get_all_account_tenant_pairs()

    if not pairs:
        print("No account/tenant configured.")
        return False

    # Only first tenant for faster execution
    account, tenant = pairs[0]
    key = f"{account}/{tenant}"
    print(f"Using: {key}")

    client = OrchestratorClient(account, tenant)

    try:
        await client.authenticate()
        folders = await client.get_folders()

        if not folders:
            print("No folders found.")
            return False

        # Test first 3 folders only for readability
        for folder in folders[:3]:
            print(f"\n📁 Folder: {folder['DisplayName']} ({folder['Id']})")

            result = await client.get_resources(
                 resource_types=[
                    ResourceTypes.assets,
                    ResourceTypes.queues,
                    ResourceTypes.processes,
                    ResourceTypes.triggers,
                    ResourceTypes.storage_buckets,
    ],
                folder_id=folder["Id"],
            )

            for resource_type, items in result.items():
                print("\n" + "-" * 50)
                print(f"RESOURCE TYPE: {resource_type}")
                print("-" * 50)

                if isinstance(items, dict) and "error" in items:
                    print(f"ERROR: {items['error']}")
                    continue

                if not items:
                    print("No items.")
                    continue

                for idx, item in enumerate(items, 1):
                    print(f"\nItem #{idx}:")
                    print(json.dumps(item, indent=4, default=str))

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        return False

    finally:
        await client.close()


async def test_get_queue_items():
    print("\n" + "=" * 60)
    print("TEST: get_queue_items() — ALL QUEUES")
    print("=" * 60)

    pairs = get_all_account_tenant_pairs()

    if not pairs:
        print("No account/tenant configured.")
        return False

    account, tenant = pairs[1]
    print(f"Using: {account}/{tenant}")

    client = OrchestratorClient(account, tenant)

    try:
        await client.authenticate()

        folders = await client.get_folders()

        if not folders:
            print("No folders found.")
            return False

        total_items_across_all_queues = 0

        # ----------------------------------------------------
        # Iterate all folders
        # ----------------------------------------------------
        for folder in folders:
            folder_id = folder["Id"]
            folder_name = folder["DisplayName"]

            print("\n" + "-" * 60)
            print(f"📁 Folder: {folder_name} ({folder_id})")
            print("-" * 60)

            queues = await client.get_queues(folder_id)

            if not queues:
                print("No queues in this folder.")
                continue

            # ------------------------------------------------
            # Iterate all queues in folder
            # ------------------------------------------------
            for queue in queues:
                queue_id = queue["Id"]
                queue_name = queue["Name"]

                print(f"\n🎯 Queue: {queue_name} ({queue_id})")

                try:
                    skip = 0
                    queue_total = 0

                    while True:
                        result = await client.get_queue_items(
                            queue_id=queue_id,
                            skip=skip
                        )

                        items = result["items"]
                        returned = result["returned"]

                        print(
                            f"   → Page returned {returned} items "
                            f"(skip={skip})"
                        )

                        queue_total += returned

                        if not result["has_more"]:
                            break

                        skip = result["next_skip"]

                    print(f"   ✓ Total fetched for queue: {queue_total}")

                    total_items_across_all_queues += queue_total

                except Exception as e:
                    print(f"   ✗ Failed to fetch items: {e}")

        print("\n" + "=" * 60)
        print(f"TOTAL ITEMS ACROSS ALL QUEUES: {total_items_across_all_queues}")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        await client.close()
async def test_ensure_folder_path():
    print("\n" + "=" * 60)
    print("TEST: Ensure + Resolve Folder Path")
    print("=" * 60)

    account = "billiysusldx"
    tenant = "DefaultTenant"

    test_path = "Shared/MCP_Test/Level1/Level2"
    non_existing_path = "Shared/MCP_Test/Level1/DoesNotExistXYZ"

    client = OrchestratorClient(account, tenant)

    try:
        await client.authenticate()

        # ----------------------------------------------------------
        # 1️⃣ Ensure path (create if missing)
        # ----------------------------------------------------------
        leaf = await client.ensure_folder_path(test_path)

        print(f"✓ Ensured path: {test_path}")
        print(f"  Leaf Folder ID: {leaf.get('Id')}")

        if not leaf.get("Id"):
            print("✗ Leaf folder has no ID")
            return False

        # ----------------------------------------------------------
        # 2️⃣ Idempotency check
        # ----------------------------------------------------------
        leaf_again = await client.ensure_folder_path(test_path)

        if leaf["Id"] != leaf_again["Id"]:
            print("✗ Id mismatch — ensure_folder_path not idempotent")
            return False

        print("✓ Idempotency confirmed")

        # ----------------------------------------------------------
        # 3️⃣ Resolve existing path
        # ----------------------------------------------------------
        resolved = await client.resolve_folder_path(test_path)

        if resolved["Id"] != leaf["Id"]:
            print("✗ resolve_folder_path returned different folder")
            return False

        print("✓ resolve_folder_path works")

        # ----------------------------------------------------------
        # 4️⃣ Resolve non-existing path
        # ----------------------------------------------------------
        try:
            await client.resolve_folder_path(non_existing_path)
            print("✗ resolve_folder_path should have failed")
            return False
        except RuntimeError:
            print("✓ resolve_folder_path correctly failed")

        # ----------------------------------------------------------
        # 5️⃣ Validate tree structure
        # ----------------------------------------------------------
        tree = await client.get_folders_tree()

        segments = test_path.split("/")

        def find_path(nodes, segments):
            if not segments:
                return True

            for node in nodes:
                if node["DisplayName"] == segments[0]:
                    return find_path(
                        node.get("children", []),
                        segments[1:]
                    )

            return False

        exists = find_path(tree, segments)

        if not exists:
            print("✗ Folder path not found in tree structure")
            return False

        print("✓ Folder structure verified in tree")

        print("\n" + "=" * 60)
        print("✓ FOLDER TEST PASSED")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False

    finally:
        await client.close()

async def test_ensure_resources_local():
    print("\n" + "=" * 60)
    print("TEST: Ensure Resources Local (CREATE-ONLY POLICY)")
    print("=" * 60)

    account = "billiysusldx"
    tenant = "DefaultTenant"
    folder_path = "Shared/MCP_Test/Level1/Level2"

    client = OrchestratorClient(account, tenant)

    try:
        await client.authenticate()
        await client.ensure_folder_path(folder_path)

        # ==========================================================
        # ASSET TEST CASES
        # ==========================================================

        asset_cases = [
            {
                "label": "Text",
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

        for case in asset_cases:

            print("\n" + "-" * 60)
            print(f"ASSET CASE: {case['label']}")
            print("-" * 60)

            asset1 = await client.ensure_resource_in_folder(
                linkable_resource_type=LinkableResourceTypes.assets,
                folder_path=folder_path,
                resource_spec=case["spec_create"],
            )

            asset2 = await client.ensure_resource_in_folder(
                linkable_resource_type=LinkableResourceTypes.assets,
                folder_path=folder_path,
                resource_spec=case["spec_update"],
            )

            if asset1["Id"] != asset2["Id"]:
                raise AssertionError("✗ Asset ID changed — not idempotent")

            print("✓ Idempotent creation confirmed")

            folder = await client.ensure_folder_path(folder_path)
            assets = await client.get_assets(folder["Id"])

            stored = next(
                (a for a in assets if a["Name"] == case["spec_create"]["Name"]),
                None,
            )

            expected = case["spec_create"]["Value"]

            if stored.get(case["field"]) != expected:
                raise AssertionError(
                    f"✗ Asset value modified (expected={expected}, got={stored.get(case['field'])})"
                )

            print("✓ Original value preserved")

        # ==========================================================
        # QUEUE TEST
        # ==========================================================

        print("\n" + "-" * 60)
        print("QUEUE CASE")
        print("-" * 60)

        queue_create = {
            "Name": "MCP_TEST_QUEUE",
            "Description": "Initial Description",
            "MaxNumberOfRetries": 1,
            "AcceptAutomaticallyRetry": False,
        }

        queue_update = {
            "Name": "MCP_TEST_QUEUE",
            "Description": "Should Not Update",
            "MaxNumberOfRetries": 99,
            "AcceptAutomaticallyRetry": True,
        }

        q1 = await client.ensure_resource_in_folder(
            linkable_resource_type=LinkableResourceTypes.queues,
            folder_path=folder_path,
            resource_spec=queue_create,
        )

        q2 = await client.ensure_resource_in_folder(
            linkable_resource_type=LinkableResourceTypes.queues,
            folder_path=folder_path,
            resource_spec=queue_update,
        )

        if q1["Id"] != q2["Id"]:
            raise AssertionError("✗ Queue ID changed — not idempotent")

        print("✓ Queue idempotency confirmed")

        folder = await client.ensure_folder_path(folder_path)
        queues = await client.get_queues(folder["Id"])

        stored_queue = next(
            (q for q in queues if q["Name"] == queue_create["Name"]),
            None,
        )

        if stored_queue["Description"] != queue_create["Description"]:
            raise AssertionError("✗ Queue was unexpectedly updated")

        print("✓ Queue original values preserved")

        # ==========================================================
        # STORAGE BUCKET TEST
        # ==========================================================

        print("\n" + "-" * 60)
        print("STORAGE BUCKET CASE")
        print("-" * 60)

        bucket_create = {
            "Name": "MCP_TEST_BUCKET",
            "Description": "Initial Bucket",
        }

        bucket_update = {
            "Name": "MCP_TEST_BUCKET",
            "Description": "Should Not Update",
        }

        b1 = await client.ensure_resource_in_folder(
            linkable_resource_type=LinkableResourceTypes.storage_buckets,
            folder_path=folder_path,
            resource_spec=bucket_create,
        )

        b2 = await client.ensure_resource_in_folder(
            linkable_resource_type=LinkableResourceTypes.storage_buckets,
            folder_path=folder_path,
            resource_spec=bucket_update,
        )

        if b1["Id"] != b2["Id"]:
            raise AssertionError("✗ Bucket ID changed — not idempotent")

        print("✓ Bucket idempotency confirmed")

        buckets = await client.get_storage_buckets(folder["Id"])

        stored_bucket = next(
            (b for b in buckets if b["Name"] == bucket_create["Name"]),
            None,
        )

        if stored_bucket["Description"] != bucket_create["Description"]:
            raise AssertionError("✗ Bucket was unexpectedly updated")

        print("✓ Bucket original values preserved")

        print("\n" + "=" * 60)
        print("✓ PASS: All resource ensure tests completed successfully")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"\n✗ FAIL: {e}")
        return False

    finally:
        await client.close()

async def test_link_resources_to_first_valid_folder():
    print("\n" + "=" * 60)
    print("TEST: link_resource_to_first_valid_folder() — Name-based Search")
    print("=" * 60)

    account = "billiysusldx"
    tenant = "DefaultTenant"

    base_folder = "Shared/MCP_Test/Level1/ValidCandidate"
    target_folder = "Shared/MCP_Test/Level1/Target"

    candidate_folders = [
        "Shared/MCP_Test/InvalidCandidate",
        base_folder,
    ]

    client = OrchestratorClient(account, tenant)

    try:
        await client.authenticate()

        # Ensure folders exist
        await client.ensure_folder_path(base_folder)
        await client.ensure_folder_path(target_folder)

        # ==========================================================
        # ASSET LINK TEST
        # ==========================================================
        print("\n" + "-" * 60)
        print("ASSET LINK CASE")
        print("-" * 60)

        asset_spec = {
            "Name": "MCP_TEST_LINK_ASSET",
            "ValueType": "Text",
            "Value": "LINK_TEST",
        }

        await client.ensure_resource_in_folder(
            linkable_resource_type=LinkableResourceTypes.assets,
            folder_path=base_folder,
            resource_spec=asset_spec,
        )

        result = await client.link_resource_to_folder(
            linkable_resource_type=LinkableResourceTypes.assets,
            resource_name=asset_spec["Name"],
            candidate_folder_paths=candidate_folders,
            target_folder_path=target_folder,
            expected_value_type=asset_spec["ValueType"],
        )

        if result["status"] != "linked":
            raise AssertionError("✗ Asset link failed")

        target = await client.ensure_folder_path(target_folder)
        assets = await client.get_assets(target["Id"])

        if not any(a["Name"] == asset_spec["Name"] for a in assets):
            raise AssertionError("✗ Asset not found in target after linking")

        print("✓ Asset linked and verified")

        # ==========================================================
        # QUEUE LINK TEST
        # ==========================================================
        print("\n" + "-" * 60)
        print("QUEUE LINK CASE")
        print("-" * 60)

        queue_spec = {
            "Name": "MCP_TEST_LINK_QUEUE",
            "Description": "Queue for linking test",
        }

        await client.ensure_resource_in_folder(
            linkable_resource_type=LinkableResourceTypes.queues,
            folder_path=base_folder,
            resource_spec=queue_spec,
        )

        result = await client.link_resource_to_folder(
            linkable_resource_type=LinkableResourceTypes.queues,
            resource_name=queue_spec["Name"],
            candidate_folder_paths=candidate_folders,
            target_folder_path=target_folder,
        )

        if result["status"] != "linked":
            raise AssertionError("✗ Queue link failed")

        queues = await client.get_queues(target["Id"])

        if not any(q["Name"] == queue_spec["Name"] for q in queues):
            raise AssertionError("✗ Queue not found in target after linking")

        print("✓ Queue linked and verified")

        # ==========================================================
        # BUCKET LINK TEST
        # ==========================================================
        print("\n" + "-" * 60)
        print("STORAGE BUCKET LINK CASE")
        print("-" * 60)

        bucket_spec = {
            "Name": "MCP_TEST_LINK_BUCKET",
            "Description": "Bucket for linking test",
        }

        await client.ensure_resource_in_folder(
            linkable_resource_type=LinkableResourceTypes.storage_buckets,
            folder_path=base_folder,
            resource_spec=bucket_spec,
        )

        result = await client.link_resource_to_folder(
            linkable_resource_type=LinkableResourceTypes.storage_buckets,
            resource_name=bucket_spec["Name"],
            candidate_folder_paths=candidate_folders,
            target_folder_path=target_folder,
        )

        if result["status"] != "linked":
            raise AssertionError("✗ Bucket link failed")

        buckets = await client.get_storage_buckets(target["Id"])

        if not any(b["Name"] == bucket_spec["Name"] for b in buckets):
            raise AssertionError("✗ Bucket not found in target after linking")

        print("✓ Storage bucket linked and verified")

        # ==========================================================
        # NOT FOUND CASE
        # ==========================================================
        print("\n" + "-" * 60)
        print("NOT LINKED CASE")
        print("-" * 60)

        result = await client.link_resource_to_folder(
            linkable_resource_type=LinkableResourceTypes.assets,
            resource_name="NON_EXISTENT_RESOURCE",
            candidate_folder_paths=candidate_folders,
            target_folder_path=target_folder,
            expected_value_type="Text",
        )

        if result["status"] != "not_linked":
            raise AssertionError("✗ Expected not_linked result")

        print("✓ not_linked case validated")

        print("\n" + "=" * 60)
        print("✓ ALL LINK TESTS PASSED")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"\n✗ FAIL: {e}")
        return False

    finally:
        await client.close()

async def test_download_storage_file():
    print("\n" + "=" * 60)
    print("TEST: Download Storage File")
    print("=" * 60)

    for account, tenant in get_all_account_tenant_pairs():
        key = f"{account}/{tenant}"
        client = OrchestratorClient(account, tenant)

        try:
            await client.authenticate()

            folders = await client.get_folders()
            if not folders:
                print(f"⚠ {key}: No folders found")
                continue

            file_downloaded = False

            for folder in folders:
                folder_id = folder["Id"]

                buckets = await client.get_storage_buckets(folder_id)
                if not buckets:
                    continue

                for bucket in buckets:
                    bucket_id = bucket["Id"]

                    files = await client.get_storage_files(folder_id, bucket_id)
                    if not files:
                        continue

                    file = files[0]
                    print(file)
                    path = await client.download_storage_file(
                        folder_id=folder_id,
                        bucket_id=bucket_id,
                        file_path=file["FullPath"],
                    )



                    assert path.exists()
                    assert path.stat().st_size > 0

                    print(
                        f"✓ {key}: Downloaded '{file['FullPath']}' "
                        f"from bucket '{bucket['Name']}'"
                    )

                    file_downloaded = True
                    break

                if file_downloaded:
                    break

            if not file_downloaded:
                print(f"⚠ {key}: No storage files found in any bucket")

        except Exception as e:
            print(f"✗ {key}: {e}")
            return False

        finally:
            await client.close()

    return True

async def test_resolve_folder_from_queue():
    print("\n" + "=" * 60)
    print("TEST: _resolve_folder_from_queue()")
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

        # ------------------------------------------------
        # STEP 1: Get real folder + queue
        # ------------------------------------------------
        folders = await client.get_folders()

        if not folders:
            print("No folders found.")
            return False

        folder = folders[0]
        folder_id = folder["Id"]

        print(f"\n📁 Folder: {folder['DisplayName']} ({folder_id})")

        queues = await client.get_queues(folder_id)

        if not queues:
            print("No queues found.")
            return False

        queue = queues[0]
        queue_id = queue["Id"]

        print(f"🎯 Queue: {queue['Name']} ({queue_id})")

        # ------------------------------------------------
        # STEP 2: Resolve folder from queue_id
        # ------------------------------------------------
        resolved_folder_id = await client._resolve_folder_from_queue(queue_id)

        print(f"\nResolved folder_id: {resolved_folder_id}")

        # ------------------------------------------------
        # STEP 3: Validate correctness
        # ------------------------------------------------
        if resolved_folder_id == folder_id:
            print("✓ Folder resolution correct")
        else:
            print("✗ Folder resolution incorrect")
            print(f"Expected: {folder_id}")
            print(f"Got: {resolved_folder_id}")
            return False

        # ------------------------------------------------
        # STEP 4: Negative test (invalid queue)
        # ------------------------------------------------
        print("\nTesting invalid queue_id...")

        try:
            await client._resolve_folder_from_queue(999999999)
            print("✗ Expected failure but succeeded")
            return False
        except RuntimeError as e:
            print(f"✓ Expected error: {e}")

        return True

    except Exception as e:
        print(f"✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        await client.close()

async def test_download_process_via_odata():
    print("\n" + "=" * 60)
    print("TEST: Download Process via OData DownloadPackage")
    print("=" * 60)

    pairs = get_all_account_tenant_pairs()

    if not pairs:
        print("No account/tenant configured.")
        return False

    account, tenant = pairs[0]
    key = f"{account}/{tenant}"

    client = OrchestratorClient(account, tenant)

    # ---- Your Process ----
    process_name = "UHCPendingClaims_Dispatcher"
    version = "1.0.16"
    folder_id = 278023

    try:
        await client.authenticate()

        print(f"Downloading {process_name} v{version}")
        print(f"FolderId: {folder_id}")

        path = await client.download_package_odata(
            package_name=process_name,
            version=version,
            folder_id=folder_id,
        )

        assert path.exists()
        assert path.stat().st_size > 0

        print(f"✓ {key}: Downloaded {path.name}")
        print(f"   Size: {path.stat().st_size} bytes")

        return True

    except Exception as e:
        print(f"✗ {key}: {e}")
        return False

    finally:
        await client.close()

async def test_upload_package_odata():
    print("\n" + "=" * 60)
    print("TEST: Upload Package via OData")
    print("=" * 60)

    account = "billiysusldx"
    tenant = "DefaultTenant"
    folder_id = 733555
    client = OrchestratorClient(account, tenant)

    package_path = Path(client.download_dir) / "1password_API_Library.1.0.1.nupkg"
   

    try:
        await client.authenticate()

        if not package_path.exists():
            print(f"✗ Package not found at {package_path}")
            print("  Run test_download_package_odata() first")
            return False

        print(f"Uploading: {package_path.name} ({package_path.stat().st_size} bytes)")
        print(f"FolderId:  {folder_id}")

        result = await client.upload_package_odata(package_path, folder_id)
        print(result)
        if result.get("status") == "already_exists":
            print(f"⚠ Package already exists in Orchestrator — skipped")
        else:
            print(f"✓ Upload successful")
            if result:
                print(f"  Response: {result}")

        return True

    except Exception as e:
        print(f"✗ {e}")
        return False

    finally:
        await client.close()

async def test_get_process_dependencies_api():
    print("\n" + "=" * 60)
    print("TEST: Get Process Dependencies via API only")
    print("=" * 60)

    account = "billiysusldx"
    tenant = "DEV"
    folder_id = 278023
    package_name = "UHCPendingClaims_Dispatcher"
    version = "1.0.16"

    client = OrchestratorClient(account, tenant)

    try:
        await client.authenticate()
        headers = {"Authorization": f"Bearer {client._access_token}"}
        base = f"https://cloud.uipath.com/{account}/{tenant}/orchestrator_"
        feed_id = "284fdd4a-d3e7-4b56-af20-30e1e786711b"

        # Step 1: Read the NuGet index to see what resources are available
        index_url = f"{base}/nuget/v3/{feed_id}/index.json"
        r = await client.client.get(index_url, headers=headers)
        print(f"\n[{r.status_code}] {index_url}")

        if r.status_code != 200:
            print("✗ Cannot reach NuGet index")
            return False

        resources = r.json().get("resources", [])
        print(f"\nAvailable NuGet resources ({len(resources)}):")
        for res in resources:
            print(f"  {res.get('@type'):60s} {res.get('@id')}")

        # Step 2: Find registration and flatcontainer base URLs from the index
        def find_resource(rtype):
            return next(
                (res["@id"] for res in resources if rtype in res.get("@type", "")),
                None,
            )

        registration_url = find_resource("RegistrationsBaseUrl")
        flatcontainer_url = find_resource("PackageBaseAddress")

        print(f"\nRegistrationsBaseUrl: {registration_url}")
        print(f"PackageBaseAddress:   {flatcontainer_url}")

        # Step 3: Try the actual endpoints using the URLs from the index
        pkg = package_name.lower()
        candidates = []

        if registration_url:
            candidates += [
                f"{registration_url.rstrip('/')}/{pkg}/{version}.json",
                f"{registration_url.rstrip('/')}/{pkg}/index.json",
            ]

        if flatcontainer_url:
            candidates += [
                f"{flatcontainer_url.rstrip('/')}/{pkg}/{version}/{pkg}.nuspec",
            ]

        for url in candidates:
            r = await client.client.get(url, headers=headers)
            print(f"\n[{r.status_code}] {url}")
            if r.status_code == 200:
                ct = r.headers.get("content-type", "")
                if "json" in ct:
                    print(f"  → {str(r.json())[:500]}")
                else:
                    print(f"  → {r.text[:500]}")

    except Exception as e:
        print(f"✗ {e}")
        return False

    finally:
        await client.close()
async def debug_nuspec():
    account = "billiysusldx"
    tenant = "DEV"
    client = OrchestratorClient(account, tenant)

    try:
        await client.authenticate()
        headers = {"Authorization": f"Bearer {client._access_token}"}

        url = (
            "https://cloud.uipath.com/billiysusldx/DEV/orchestrator_"
            "/nuget/v3/284fdd4ad3e74b56af2030e1e786711b"
            "/packages/uhcpendingclaims_dispatcher/1.0.16"
            "/uhcpendingclaims_dispatcher.nuspec"
        )

        r = await client.client.get(url, headers=headers)
        r.raise_for_status()
        print(r.text)  # full XML, no truncation

    finally:
        await client.close()

async def test_get_dependencies_from_file():
    print("\n" + "=" * 60)
    print("TEST: Get Dependencies from .nupkg file")
    print("=" * 60)

    pairs = get_all_account_tenant_pairs()
    account, tenant = pairs[0]
    client = OrchestratorClient(account, tenant)

    path = Path(client.download_dir) / "UHCPendingClaims_Dispatcher.1.0.16.nupkg"

    print(f"File: {path}")

    if not path.exists():
        print("✗ File not found — run test_download_package_odata() first")
        return False

    try:
        result = OrchestratorClient.get_dependencies_from_file(path)

        if not result:
            print("✗ No data returned")
            return False

        # Package info
        print(f"\n📦 Package Info")
        print(f"  ID:          {result['id']}")
        print(f"  Version:     {result['version']}")
        print(f"  Type:        {result['packageType'].upper()}")
        print(f"  Authors:     {result['authors']}")
        print(f"  Description: {result['description']}")

        # Dependencies
        deps = result["dependencies"]
        if not deps:
            print("\n  No dependencies found")
            return True

        internal = [d for d in deps if d["source"] == "internal"]
        official = [d for d in deps if d["source"] == "uipath_official"]

        print(f"\n📋 Dependencies ({len(deps)} total)")

        if internal:
            print(f"\n  Internal ({len(internal)}):")
            for d in sorted(internal, key=lambda x: x["id"].lower()):
                constraint = "==" if d["versionConstraint"] == "exact" else ">="
                print(f"    ✦ {d['id']:<40} {constraint} {d['version']}")

        if official:
            print(f"\n  UiPath Official ({len(official)}):")
            for d in sorted(official, key=lambda x: x["id"].lower()):
                constraint = "==" if d["versionConstraint"] == "exact" else ">="
                print(f"    · {d['id']:<40} {constraint} {d['version']}")

        return True

    except Exception as e:
        print(f"✗ {e}")
        return False


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    # Uncomment ONE test at a time

     #asyncio.run(test_connection())
     #asyncio.run(test_get_folders_tree_multi_tenant())
     #asyncio.run(test_folder_collections("get_queues", "Queues"))
     #asyncio.run(test_folder_collections("get_triggers", "Triggers"))
     #asyncio.run(test_folder_collections("get_processes", "Processes"))
     #asyncio.run(test_list_library_versions_flow())
     #asyncio.run(test_download_library_version())
     #asyncio.run(test_get_resources())
     #asyncio.run(test_ensure_folder_path())
     #asyncio.run(test_ensure_resources_local())
     #asyncio.run(test_link_resources_to_first_valid_folder())
     #asyncio.run(test_download_storage_file())
     #asyncio.run(test_get_queue_items())
     #asyncio.run(test_resolve_folder_from_queue())
     #asyncio.run(test_download_process_via_odata())
     #asyncio.run(test_upload_package_odata())
     #asyncio.run(test_get_process_dependencies_api())
     #asyncio.run(debug_nuspec())
     asyncio.run(test_get_dependencies_from_file())


  
