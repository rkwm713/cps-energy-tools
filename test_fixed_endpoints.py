#!/usr/bin/env python3
"""
Test script to verify fixed API endpoints.
This script will check all API endpoints to confirm they're properly registered
and responding with the correct status codes.

Usage:
    python test_fixed_endpoints.py
"""

import json
import requests
import sys
from pprint import pprint

# Base URL - change this to match your deployment
BASE_URL = "https://cps-energy-tools-eca5b70fc3e3.herokuapp.com"
# For local testing uncomment the line below
# BASE_URL = "http://localhost:8000"

# Test endpoints
def test_health():
    """Test the health endpoint."""
    print("\n=== Testing Health Endpoint ===")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print("Health check passed!")
        # Print some of the registered routes for verification
        data = response.json()
        print(f"Found {len(data.get('routes', []))} routes")
        return True
    else:
        print("Health check failed!")
        return False

def test_debug_routes():
    """Test the debug-all-routes endpoint."""
    print("\n=== Testing Debug Routes Endpoint ===")
    response = requests.get(f"{BASE_URL}/debug-all-routes")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print("Debug routes check passed!")
        data = response.json()
        print(f"Total routes: {data.get('total_routes', 0)}")
        
        # Print API routes
        if 'api' in data.get('grouped_by_prefix', {}):
            api_routes = data['grouped_by_prefix']['api']
            print("\nAPI Routes:")
            for route in api_routes:
                print(f"  {', '.join(route['methods'])} {route['path']}")
        return True
    else:
        print("Debug routes check failed!")
        return False

def test_debug_endpoints():
    """Test all debug endpoints."""
    print("\n=== Testing Individual Debug Endpoints ===")
    
    debug_endpoints = [
        "/api/mrr-debug",
        "/api/spida-debug",
        "/api/pole-compare-debug"
    ]
    
    all_passed = True
    
    for endpoint in debug_endpoints:
        url = f"{BASE_URL}{endpoint}"
        print(f"\nTesting: {url}")
        
        try:
            response = requests.get(url)
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                print(f"✅ {endpoint} - OK")
                try:
                    print(f"Response: {json.dumps(response.json(), indent=2)}")
                except:
                    print(f"Response: {response.text[:100]}...")
            else:
                print(f"❌ {endpoint} - Failed with status {response.status_code}")
                all_passed = False
                
        except Exception as e:
            print(f"❌ {endpoint} - Exception: {str(e)}")
            all_passed = False
    
    return all_passed

def test_routes_endpoints():
    """Test all routes listing endpoints."""
    print("\n=== Testing Routes Listing Endpoints ===")
    
    routes_endpoints = [
        "/api/mrr-routes",
        "/api/spida-routes",
        "/api/pole-compare-routes"
    ]
    
    all_passed = True
    
    for endpoint in routes_endpoints:
        url = f"{BASE_URL}{endpoint}"
        print(f"\nTesting: {url}")
        
        try:
            response = requests.get(url)
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                print(f"✅ {endpoint} - OK")
                data = response.json()
                if 'routes' in data:
                    print(f"Found {len(data['routes'])} routes in this router")
                    for route in data['routes']:
                        print(f"  {route['path']} - {', '.join(route['methods'])}")
            else:
                print(f"❌ {endpoint} - Failed with status {response.status_code}")
                all_passed = False
                
        except Exception as e:
            print(f"❌ {endpoint} - Exception: {str(e)}")
            all_passed = False
    
    return all_passed

def test_api_endpoints():
    """Test previously problematic API endpoints."""
    print("\n=== Testing Fixed API Endpoints ===")
    
    endpoints = [
        {"url": "/api/mrr-process", "method": "POST"},
        {"url": "/api/spida-import", "method": "POST"},
        {"url": "/api/pole-comparison", "method": "POST"}
    ]
    
    all_passed = True
    
    for endpoint in endpoints:
        url = f"{BASE_URL}{endpoint['url']}"
        method = endpoint['method']
        print(f"\nTesting: {method} {url}")
        
        try:
            # We're not sending valid data, so we expect 422 or 400 errors, but NOT 405
            if method == "POST":
                response = requests.post(url)
            else:
                response = requests.get(url)
            
            print(f"Status: {response.status_code}")
            
            if response.status_code != 405:  # Anything but Method Not Allowed is good
                print(f"✅ {method} {endpoint['url']} - Status {response.status_code} (not 405, which is good!)")
                # We expect validation errors (422) or bad request (400) since we're not sending proper data
                if response.status_code in [400, 422]:
                    print("  Got expected validation error (good!)")
                try:
                    print(f"Response: {json.dumps(response.json(), indent=2)}")
                except:
                    print(f"Response: {response.text[:100]}...")
            else:
                print(f"❌ {method} {endpoint['url']} - Still getting Method Not Allowed (405)")
                all_passed = False
                
        except Exception as e:
            print(f"❌ {method} {endpoint['url']} - Exception: {str(e)}")
            all_passed = False
    
    return all_passed

def main():
    """Run all tests."""
    print("=== CPS Energy Tools API Endpoint Tester ===")
    print(f"Testing against: {BASE_URL}")
    
    tests = [
        ("Health Check", test_health),
        ("Debug Routes", test_debug_routes),
        ("Debug Endpoints", test_debug_endpoints),
        ("Routes Endpoints", test_routes_endpoints),
        ("API Endpoints", test_api_endpoints)
    ]
    
    results = {}
    
    for name, test_func in tests:
        print(f"\n{'='*50}\nRunning: {name}\n{'='*50}")
        try:
            result = test_func()
            results[name] = result
        except Exception as e:
            print(f"Error in {name}: {str(e)}")
            results[name] = False
    
    # Print summary
    print("\n\n=== TEST SUMMARY ===")
    all_passed = True
    for name, result in results.items():
        status = "PASSED" if result else "FAILED"
        print(f"{name}: {status}")
        if not result:
            all_passed = False
    
    if all_passed:
        print("\n✅ ALL TESTS PASSED!")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
