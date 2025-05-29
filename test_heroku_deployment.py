"""Test script to verify Heroku deployment fixes"""
import requests

# Replace with your actual Heroku app URL
BASE_URL = "https://cps-energy-tools-eca5b70fc3e3.herokuapp.com"

def test_health_endpoint():
    """Test the health check endpoint"""
    print("Testing health endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Health check passed: {data['message']}")
            print(f"  Registered routes: {len(data['routes'])}")
            for route in data['routes']:
                if 'api' in route['path']:
                    print(f"  - {route['path']}: {route['methods']}")
        else:
            print(f"✗ Health check failed with status: {response.status_code}")
    except Exception as e:
        print(f"✗ Health check error: {e}")

def test_pole_comparison_options():
    """Test if pole-comparison endpoint accepts POST"""
    print("\nTesting pole-comparison endpoint methods...")
    try:
        # OPTIONS request to check allowed methods
        response = requests.options(f"{BASE_URL}/api/pole-comparison")
        if response.status_code == 200:
            allow_header = response.headers.get('Allow', '')
            print(f"✓ Allowed methods for /api/pole-comparison: {allow_header}")
        else:
            print(f"  OPTIONS request returned: {response.status_code}")
            
        # Try a POST request (will fail without files, but should not be 405)
        response = requests.post(f"{BASE_URL}/api/pole-comparison")
        if response.status_code == 405:
            print(f"✗ POST method not allowed - endpoint not properly registered")
        else:
            print(f"✓ POST method allowed (status: {response.status_code})")
    except Exception as e:
        print(f"✗ Error testing pole-comparison: {e}")

if __name__ == "__main__":
    print(f"Testing Heroku deployment at: {BASE_URL}\n")
    test_health_endpoint()
    test_pole_comparison_options()
