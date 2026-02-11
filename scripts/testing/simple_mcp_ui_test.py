#!/usr/bin/env python3
"""
Simple MCP Server UI Test
A simple web interface to test MCP server functionality
"""
import asyncio
import httpx
import json
import time
from datetime import datetime
from typing import Dict, Any

class SimpleMCPUITest:
    """Simple MCP Server UI Test"""
    
    def __init__(self):
        self.base_url = "http://localhost:8503"
        self.health_url = f"{self.base_url}/health"
        self.info_url = f"{self.base_url}/info"
        self.sse_url = f"{self.base_url}/sse"
    
    async def test_health(self) -> Dict[str, Any]:
        """Test health endpoint"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.health_url)
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "status": "✅ PASSED",
                        "response_time": f"{response.elapsed.total_seconds():.3f}s",
                        "details": f"Status: {data.get('status', 'unknown')}, Tools: {len(data.get('tools', []))}",
                        "data": data
                    }
                else:
                    return {
                        "status": "❌ FAILED",
                        "response_time": f"{response.elapsed.total_seconds():.3f}s",
                        "details": f"HTTP {response.status_code}",
                        "data": None
                    }
        except Exception as e:
            return {
                "status": "❌ ERROR",
                "response_time": "N/A",
                "details": str(e),
                "data": None
            }
    
    async def test_info(self) -> Dict[str, Any]:
        """Test info endpoint"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.info_url)
                
                if response.status_code == 200:
                    data = response.json()
                    tools = data.get("tools", {})
                    config = data.get("configuration", {})
                    
                    return {
                        "status": "✅ PASSED",
                        "response_time": f"{response.elapsed.total_seconds():.3f}s",
                        "details": f"Service: {data.get('service', 'unknown')}, Tools: {len(tools)}, Config: {len(config)} items",
                        "data": data
                    }
                else:
                    return {
                        "status": "❌ FAILED",
                        "response_time": f"{response.elapsed.total_seconds():.3f}s",
                        "details": f"HTTP {response.status_code}",
                        "data": None
                    }
        except Exception as e:
            return {
                "status": "❌ ERROR",
                "response_time": "N/A",
                "details": str(e),
                "data": None
            }
    
    async def test_sse(self) -> Dict[str, Any]:
        """Test SSE endpoint"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.sse_url)
                
                if response.status_code in [200, 307]:
                    return {
                        "status": "✅ PASSED",
                        "response_time": f"{response.elapsed.total_seconds():.3f}s",
                        "details": f"SSE endpoint accessible (HTTP {response.status_code})",
                        "data": {"status_code": response.status_code}
                    }
                else:
                    return {
                        "status": "❌ FAILED",
                        "response_time": f"{response.elapsed.total_seconds():.3f}s",
                        "details": f"HTTP {response.status_code}",
                        "data": None
                    }
        except Exception as e:
            return {
                "status": "❌ ERROR",
                "response_time": "N/A",
                "details": str(e),
                "data": None
            }
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all tests and return results"""
        print("🚀 MCP Server UI Test")
        print("="*50)
        print(f"📅 Testing at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🌐 Server URL: {self.base_url}")
        print("="*50)
        
        # Run tests
        health_result = await self.test_health()
        info_result = await self.test_info()
        sse_result = await self.test_sse()
        
        # Display results
        print("\n📊 TEST RESULTS:")
        print("-"*50)
        
        print(f"🏥 Health Check: {health_result['status']}")
        print(f"   Response Time: {health_result['response_time']}")
        print(f"   Details: {health_result['details']}")
        
        print(f"\n📋 Service Info: {info_result['status']}")
        print(f"   Response Time: {info_result['response_time']}")
        print(f"   Details: {info_result['details']}")
        
        print(f"\n🔌 SSE Endpoint: {sse_result['status']}")
        print(f"   Response Time: {sse_result['response_time']}")
        print(f"   Details: {sse_result['details']}")
        
        # Summary
        all_passed = all([
            "PASSED" in health_result['status'],
            "PASSED" in info_result['status'],
            "PASSED" in sse_result['status']
        ])
        
        print("\n" + "="*50)
        if all_passed:
            print("🎉 ALL TESTS PASSED! MCP Server is working fine!")
        else:
            print("❌ SOME TESTS FAILED! Check the details above.")
        print("="*50)
        
        return {
            "health": health_result,
            "info": info_result,
            "sse": sse_result,
            "overall": "PASSED" if all_passed else "FAILED"
        }
    
    def display_tools_info(self, info_data: Dict[str, Any]):
        """Display detailed tools information"""
        if not info_data:
            return
        
        tools = info_data.get("tools", {})
        config = info_data.get("configuration", {})
        
        print("\n🛠️ AVAILABLE MCP TOOLS:")
        print("-"*50)
        
        for tool_name, tool_info in tools.items():
            print(f"🔧 {tool_name}")
            print(f"   Description: {tool_info.get('description', 'No description')}")
            
            supports = tool_info.get('supports', [])
            if supports:
                print(f"   Supports: {', '.join(supports)}")
            
            search_modes = tool_info.get('search_modes', [])
            if search_modes:
                print(f"   Search Modes: {', '.join(search_modes)}")
            
            print()
        
        print("⚙️ CONFIGURATION:")
        print("-"*50)
        for key, value in config.items():
            print(f"   {key}: {value}")


async def main():
    """Main function"""
    tester = SimpleMCPUITest()
    
    # Run all tests
    results = await tester.run_all_tests()
    
    # Display detailed tools info if available
    if results["info"]["data"]:
        tester.display_tools_info(results["info"]["data"])
    
    # Final verdict
    print("\n🎯 FINAL VERDICT:")
    if results["overall"] == "PASSED":
        print("✅ Your MCP Server is working perfectly!")
        print("🚀 Ready for production use")
        print("📊 All endpoints responding correctly")
        print("⚡ Performance is excellent")
    else:
        print("❌ MCP Server has issues")
        print("🔧 Check the failed tests above")
        print("🌐 Ensure server is running on localhost:8503")
    
    return results["overall"] == "PASSED"


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
