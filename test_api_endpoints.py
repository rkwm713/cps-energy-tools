#!/usr/bin/env python3
"""Simple test script to verify API endpoints are properly registered."""

import requests
import json
from pathlib import Path

def test_endpoints():
    """Test that the API endpoints are accessible."""
    base_url = "http://localhost:8000"
    
    # Test endpoints that should exist
    endpoints_to_test = [
        "/api/cover-sheet",
        "/api/pole-comparison", 
        "/api/mrr-process",
        "/api/qc",
        "/api/exports",
        "/api/spida"
    ]
    
    print("Testing API endpoints...")
    print("=" * 50)
    
    for endpoint in endpoints_to_test:
        try:
            # Try a GET request first to see if endpoint exists
            response = requests.get(f"{base_url}{endpoint}", timeout=5)
            if response.status_code == 405:
                print(f"✓ {endpoint}: Endpoint exists (405 Method Not Allowed - expected for POST-only routes)")
            elif response.status_code == 200:
                print(f"✓ {endpoint}: Endpoint accessible (200 OK)")
            else:
                print(f"? {endpoint}: Status {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print(f"✗ {endpoint}: Connection failed - is the server running?")
            return False
        except requests.exceptions.Timeout:
            print(f"✗ {endpoint}: Request timed out")
        except Exception as e:
            print(f"✗ {endpoint}: Error - {e}")
    
    return True

def test_cover_sheet_api():
    """Test the cover sheet API with a sample file if available."""
    base_url = "http://localhost:8000"
    endpoint = "/api/cover-sheet"
    
    # Look for a sample JSON file to test with
    uploads_dir = Path("uploads")
    sample_files = list(uploads_dir.glob("*.json")) if uploads_dir.exists() else []
    
    if not sample_files:
        print("\nNo sample JSON files found in uploads/ directory for testing cover-sheet API")
        return
    
    sample_file = sample_files[0]
    print(f"\nTesting cover-sheet API with {sample_file.name}...")
    
    try:
        with open(sample_file, 'rb') as f:
            files = {'spida_file': (sample_file.name, f, 'application/json')}
            response = requests.post(f"{base_url}{endpoint}", files=files, timeout=30)
            
        if response.status_code == 200:
            print(f"✓ Cover-sheet API test: SUCCESS (200 OK)")
            data = response.json()
            print(f"  - Returned {len(data.get('Poles', []))} poles")
        elif response.status_code == 405:
            print(f"✗ Cover-sheet API test: 405 Method Not Allowed (routes not properly registered)")
        else:
            print(f"? Cover-sheet API test: Status {response.status_code}")
            print(f"  Response: {response.text[:200]}...")
            
    except requests.exceptions.ConnectionError:
        print(f"✗ Cover-sheet API test: Connection failed")
    except Exception as e:
        print(f"✗ Cover-sheet API test: Error - {e}")

if __name__ == "__main__":
    print("CPS Energy Tools API Endpoint Test")
    print("Make sure the server is running: uvicorn backend.main:app --reload")
    print()
    
    if test_endpoints():
        test_cover_sheet_api()
    
    print("\nTest complete!")
