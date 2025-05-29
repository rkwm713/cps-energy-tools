#!/usr/bin/env python3
"""
Test script to verify the fixed API endpoints are working correctly.
Run this after deploying the fix to test locally or against Heroku.
"""

import requests
import sys
from pathlib import Path

def test_health_endpoint(base_url="http://localhost:8000"):
    """Test the health endpoint to see if routers are properly registered."""
    try:
        response = requests.get(f"{base_url}/health")
        response.raise_for_status()
        
        data = response.json()
        print(f"✅ Health check successful: {data['message']}")
        print(f"   Status: {data['status']}")
        print(f"   Registered routes: {len(data['routes'])}")
        
        # Check if our API endpoints are registered
        api_routes = [route for route in data['routes'] if route['path'].startswith('/api/')]
        print(f"   API routes found: {len(api_routes)}")
        
        for route in api_routes:
            print(f"   - {route['path']} ({', '.join(route['methods'])})")
        
        # Specifically check for our problematic endpoints
        cover_sheet_found = any(route['path'] == '/api/cover-sheet' for route in data['routes'])
        pole_comparison_found = any(route['path'] == '/api/pole-comparison' for route in data['routes'])
        
        if cover_sheet_found:
            print("✅ /api/cover-sheet endpoint is registered")
        else:
            print("❌ /api/cover-sheet endpoint NOT found")
            
        if pole_comparison_found:
            print("✅ /api/pole-comparison endpoint is registered")
        else:
            print("❌ /api/pole-comparison endpoint NOT found")
            
        return cover_sheet_found and pole_comparison_found
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Health check failed: {e}")
        return False

def test_endpoints_with_dummy_data(base_url="http://localhost:8000"):
    """Test the actual endpoints with dummy data to verify they respond correctly."""
    
    # Test cover-sheet endpoint
    print("\n📋 Testing /api/cover-sheet endpoint...")
    try:
        # We expect this to fail with validation error but not 404 or 405
        files = {'spida_file': ('test.json', '{"invalid": "json"}', 'application/json')}
        response = requests.post(f"{base_url}/api/cover-sheet", files=files)
        
        if response.status_code == 404:
            print("❌ /api/cover-sheet returns 404 (endpoint not found)")
        elif response.status_code == 405:
            print("❌ /api/cover-sheet returns 405 (method not allowed)")
        elif response.status_code in [400, 422, 500]:
            print(f"✅ /api/cover-sheet responds correctly (status {response.status_code})")
            print(f"   Response: {response.text[:100]}...")
        else:
            print(f"⚠️  /api/cover-sheet unexpected status: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Cover sheet test failed: {e}")
    
    # Test pole-comparison endpoint
    print("\n🏗️  Testing /api/pole-comparison endpoint...")
    try:
        # We expect this to fail with validation error but not 404 or 405
        files = {
            'katapult_file': ('test.xlsx', b'dummy', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            'spida_file': ('test.json', '{"invalid": "json"}', 'application/json')
        }
        data = {'threshold': '5.0'}
        response = requests.post(f"{base_url}/api/pole-comparison", files=files, data=data)
        
        if response.status_code == 404:
            print("❌ /api/pole-comparison returns 404 (endpoint not found)")
        elif response.status_code == 405:
            print("❌ /api/pole-comparison returns 405 (method not allowed)")
        elif response.status_code in [400, 422, 500]:
            print(f"✅ /api/pole-comparison responds correctly (status {response.status_code})")
            print(f"   Response: {response.text[:100]}...")
        else:
            print(f"⚠️  /api/pole-comparison unexpected status: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Pole comparison test failed: {e}")

if __name__ == "__main__":
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    
    print(f"🧪 Testing API endpoints at: {base_url}")
    print("=" * 50)
    
    # Test health endpoint first
    if test_health_endpoint(base_url):
        print("\n🎯 Testing actual endpoint functionality...")
        test_endpoints_with_dummy_data(base_url)
    else:
        print("\n❌ Health check failed - endpoints may not be properly registered")
        
    print("\n" + "=" * 50)
    print("✅ Test completed!")
    print("\nTo test against Heroku:")
    print(f"python {sys.argv[0]} https://cps-energy-tools-eca5b70fc3e3.herokuapp.com")
