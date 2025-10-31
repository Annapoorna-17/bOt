#!/usr/bin/env python3
"""
Test script to verify document preview endpoint
"""
import requests
import sys

# Configuration
BASE_URL = "http://localhost:8000"
SUPERADMIN_TOKEN = "B946C6F2747914D24C1F6C74F5AB5291"

def test_preview():
    """Test document preview endpoint"""

    # First, get list of documents
    print("🔍 Fetching list of documents...")
    response = requests.get(
        f"{BASE_URL}/documents/superadmin/all",
        headers={"Authorization": f"Bearer {SUPERADMIN_TOKEN}"}
    )

    if response.status_code != 200:
        print(f"❌ Failed to get documents: {response.status_code}")
        print(response.text)
        return False

    documents = response.json()

    if not documents:
        print("❌ No documents found in the database")
        return False

    print(f"✅ Found {len(documents)} documents")

    # Test preview for the first document
    doc = documents[0]
    doc_id = doc['id']
    filename = doc['filename']
    original_name = doc['original_name']

    print(f"\n📄 Testing preview for document:")
    print(f"   ID: {doc_id}")
    print(f"   Filename: {filename}")
    print(f"   Original: {original_name}")

    # Test superadmin preview endpoint
    print(f"\n🔐 Testing superadmin preview endpoint...")
    response = requests.get(
        f"{BASE_URL}/documents/superadmin/{doc_id}/preview",
        headers={"Authorization": f"Bearer {SUPERADMIN_TOKEN}"}
    )

    if response.status_code == 200:
        print(f"✅ Superadmin preview SUCCESS!")
        print(f"   Content-Type: {response.headers.get('content-type')}")
        print(f"   Content-Length: {len(response.content)} bytes")
        return True
    else:
        print(f"❌ Superadmin preview FAILED: {response.status_code}")
        print(f"   Response: {response.text}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Document Preview Test")
    print("=" * 60)

    success = test_preview()

    print("\n" + "=" * 60)
    if success:
        print("✅ TEST PASSED")
    else:
        print("❌ TEST FAILED")
    print("=" * 60)

    sys.exit(0 if success else 1)
