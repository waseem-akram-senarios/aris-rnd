import asyncio
import sys
import os
from pathlib import Path
import json

# Add project root to path
project_root = str(Path(__file__).resolve().parents[2])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from api.service import ServiceContainer
from services.gateway.service import GatewayService

async def test_mcp_integration():
    print("="*60)
    print("🧪 Testing UI -> Gateway -> MCP Integration")
    print("="*60)

    # 1. Initialize ServiceContainer (simulates UI startup)
    print("\n[1] Initializing ServiceContainer...")
    try:
        container = ServiceContainer()
        print("✅ ServiceContainer initialized")
    except Exception as e:
        print(f"❌ Failed to initialize ServiceContainer: {e}")
        return

    # 2. Test Get MCP Status
    print("\n[2] Testing get_mcp_status()...")
    try:
        status = container.get_mcp_status()
        print(f"Status Result: {json.dumps(status, indent=2)}")
        if status.get("status") == "healthy" or status.get("status") == "ok":
            print("✅ MCP Status: ONLINE")
        else:
            print("⚠️ MCP Status: OFFLINE/UNHEALTHY")
    except Exception as e:
        print(f"❌ Error getting status: {e}")

    # 3. Test Get MCP Tools
    print("\n[3] Testing get_mcp_tools()...")
    try:
        tools = container.get_mcp_tools()
        print(f"Tools Result Keys: {list(tools.keys())}")
        if "tools" in tools:
            print(f"✅ Found {len(tools['tools'])} tools")
            for t in tools['tools']:
                print(f"   - {t.get('name')}")
        else:
            print("⚠️ No tools returned or unexpected format")
    except Exception as e:
        print(f"❌ Error getting tools: {e}")

    # 4. Test Get MCP Stats
    print("\n[4] Testing get_mcp_stats()...")
    try:
        stats = container.get_mcp_stats()
        print(f"Stats Result: {json.dumps(stats, indent=2)}")
        if "documents" in stats or "stats" in stats:
             print("✅ Stats retrieved successfully")
        else:
             print("⚠️ Stats might be empty or error")
    except Exception as e:
        print(f"❌ Error getting stats: {e}")
    
    # 5. Test Sync Trigger (Dry Run)
    print("\n[5] Testing trigger_mcp_sync()...")
    try:
        # We won't assert success since sync might take time or fail if already syncing
        # But we check if the call completes
        sync_res = container.trigger_mcp_sync()
        print(f"Sync Result: {json.dumps(sync_res, indent=2)}")
        print("✅ Sync trigger call completed")
    except Exception as e:
        print(f"❌ Error triggering sync: {e}")

if __name__ == "__main__":
    # ServiceContainer methods are sync (wrappers), but they use asyncio.run internally 
    # if no loop is running. Since we are in main, no loop is running yet.
    # But wait, ServiceContainer methods use asyncio.run(). 
    # So we don't need to await them here?
    # Yes, the methods in ServiceContainer are `def` (sync).
    
    # Re-write test to be sync since ServiceContainer provides sync interface
    print("Running Sync Test Wrapper...")
    
    # 1. Initialize
    container = ServiceContainer()
    
    # 2. Status
    print("\n[Check 1] Status")
    print(container.get_mcp_status())
    
    # 3. Tools
    print("\n[Check 2] Tools")
    print(container.get_mcp_tools())
    
    # 4. Stats
    print("\n[Check 3] Stats")
    print(container.get_mcp_stats())
    
    print("\n✅ Test Complete")
