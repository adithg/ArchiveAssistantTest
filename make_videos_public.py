#!/usr/bin/env python3
"""
Make uploaded videos in Google Cloud Storage publicly accessible.
"""

import os
import sys
from google.cloud import storage
import argparse

def make_videos_public(bucket_name, video_prefix="Videos/Video/"):
    """Make all videos in the bucket publicly accessible"""
    
    # Initialize the client
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    
    print(f"Making videos public in gs://{bucket_name}/{video_prefix}")
    
    # List all video files
    blobs = bucket.list_blobs(prefix=video_prefix)
    
    public_urls = []
    for blob in blobs:
        if blob.name.endswith('.mp4'):
            print(f"Making public: {blob.name}")
            try:
                # Make the blob publicly readable
                blob.make_public()
                public_url = blob.public_url
                public_urls.append((blob.name, public_url))
                print(f"✅ Now public: {public_url}")
            except Exception as e:
                print(f"❌ Failed to make {blob.name} public: {e}")
    
    print(f"\n🎉 Made {len(public_urls)} videos public!")
    
    # Test a few URLs
    if public_urls:
        print("\n🧪 Testing first few URLs...")
        import requests
        for name, url in public_urls[:3]:
            try:
                response = requests.head(url, timeout=10)
                if response.status_code == 200:
                    print(f"✅ {name}: Working ({response.headers.get('content-length', 'unknown')} bytes)")
                else:
                    print(f"❌ {name}: HTTP {response.status_code}")
            except Exception as e:
                print(f"❌ {name}: Error testing - {e}")

def main():
    parser = argparse.ArgumentParser(description='Make GCS videos publicly accessible')
    parser.add_argument('--bucket-name', required=True, help='GCS bucket name')
    parser.add_argument('--project-id', help='Google Cloud Project ID (optional)')
    
    args = parser.parse_args()
    
    if args.project_id:
        os.environ['GOOGLE_CLOUD_PROJECT'] = args.project_id
    
    make_videos_public(args.bucket_name)

if __name__ == "__main__":
    main()