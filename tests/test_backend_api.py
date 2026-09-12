#!/usr/bin/env python3
"""
Test Backend API Connectivity
Quick script to verify the hydra backend is working
"""

import requests
import json

API_URL = "http://localhost:8888"

def test_health():
    """Test health endpoint"""
    print("Testing backend health...")
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        print(f"✓ Backend is healthy: {response.json()}")
        return True
    except Exception as e:
        print(f"✗ Backend health check failed: {e}")
        return False


def test_system_info():
    """Test system info endpoint"""
    print("\nTesting system info...")
    try:
        response = requests.get(f"{API_URL}/api/v1/system/info", timeout=5)
        response.raise_for_status()
        info = response.json()
        print(f"✓ Garak version: {info.get('garak_version')}")
        print(f"  Python version: {info.get('python_version')}")
        print(f"  Garak installed: {info.get('garak_installed')}")
        return True
    except Exception as e:
        print(f"✗ System info failed: {e}")
        return False


def test_list_probes():
    """Test listing available probes"""
    print("\nTesting probe listing...")
    try:
        response = requests.get(f"{API_URL}/api/v1/plugins/probes", timeout=10)
        response.raise_for_status()
        data = response.json()
        total = data.get('total_count', 0)
        print(f"✓ Found {total} probes")

        # Show first few probes
        probes = data.get('plugins', [])[:5]
        for probe in probes:
            print(f"  - {probe.get('full_name')}")

        return True
    except Exception as e:
        print(f"✗ Probe listing failed: {e}")
        return False


def test_scan_request():
    """Test scan request with proper format"""
    print("\nTesting scan request format...")

    # Correct format based on ScanConfigRequest schema
    config = {
        "target_type": "huggingface",  # Standard generator type
        "target_name": "mistral:latest",  # Model name
        "probes": ["dan.Dan_11_0"],  # Single probe for quick test
        "generations": 2,  # Just 2 generations for testing
    }

    print(f"Request config:")
    print(json.dumps(config, indent=2))

    try:
        response = requests.post(
            f"{API_URL}/api/v1/scan/start",
            json=config,
            timeout=10
        )

        print(f"\nResponse status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")

        if response.status_code == 200:
            print("✓ Scan request accepted!")
            return True
        else:
            print(f"✗ Scan request failed with status {response.status_code}")
            return False

    except Exception as e:
        print(f"✗ Scan request failed: {e}")
        return False


def main():
    print("=" * 60)
    print("  AEGIS SECURITY BACKEND API TEST")
    print("=" * 60)

    results = {
        "Health Check": test_health(),
        "System Info": test_system_info(),
        "List Probes": test_list_probes(),
        "Scan Request": test_scan_request()
    }

    print("\n" + "=" * 60)
    print("  RESULTS")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{test_name:<20} {status}")

    all_passed = all(results.values())

    if all_passed:
        print("\n✓ All tests passed! Backend is ready.")
    else:
        print("\n✗ Some tests failed. Check backend configuration.")

    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted.")
