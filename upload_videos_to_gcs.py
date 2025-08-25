#!/usr/bin/env python3
"""
Upload video files to Google Cloud Storage and make them publicly accessible.
This will allow the Vercel app to reference videos by URL with timestamp parameters.
"""

import os
import sys
from pathlib import Path
from google.cloud import storage
from urllib.parse import quote
import argparse

def upload_video_to_gcs(bucket_name, source_file_path, destination_blob_name, make_public=True):
    """Upload a file to the bucket and optionally make it public."""
    
    # Initialize the client
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    
    print(f"Uploading {source_file_path} to gs://{bucket_name}/{destination_blob_name}")
    
    # Upload the file
    blob.upload_from_filename(source_file_path)
    
    if make_public:
        # Make the blob publicly viewable
        blob.make_public()
        print(f"✅ Uploaded and made public: {blob.public_url}")
    else:
        print(f"✅ Uploaded: gs://{bucket_name}/{destination_blob_name}")
    
    return blob.public_url if make_public else f"gs://{bucket_name}/{destination_blob_name}"

def sanitize_filename(filename):
    """Sanitize filename for GCS (remove spaces, special chars, etc.)"""
    # Replace spaces with underscores and remove problematic characters
    sanitized = filename.replace(' ', '_').replace('(', '').replace(')', '')
    # URL encode any remaining special characters
    return quote(sanitized, safe='-_.~')

def main():
    parser = argparse.ArgumentParser(description='Upload videos to Google Cloud Storage')
    parser.add_argument('--bucket-name', required=True, help='GCS bucket name')
    parser.add_argument('--video-dir', default='Video/Video', help='Directory containing video files')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be uploaded without actually uploading')
    parser.add_argument('--project-id', help='Google Cloud Project ID (optional)')
    
    args = parser.parse_args()
    
    if args.project_id:
        os.environ['GOOGLE_CLOUD_PROJECT'] = args.project_id
    
    video_dir = Path(args.video_dir)
    if not video_dir.exists():
        print(f"❌ Video directory {video_dir} does not exist")
        sys.exit(1)
    
    # Find all video files
    video_extensions = {'.mp4', '.mov', '.mkv', '.avi', '.m4v'}
    video_files = []
    
    for ext in video_extensions:
        video_files.extend(video_dir.glob(f'*{ext}'))
        video_files.extend(video_dir.glob(f'*{ext.upper()}'))
    
    if not video_files:
        print(f"❌ No video files found in {video_dir}")
        sys.exit(1)
    
    print(f"Found {len(video_files)} video files:")
    
    uploaded_videos = []
    
    for video_file in sorted(video_files):
        # Sanitize the filename for GCS
        sanitized_name = sanitize_filename(video_file.name)
        destination_path = f"videos/{sanitized_name}"
        
        if args.dry_run:
            print(f"Would upload: {video_file.name} -> gs://{args.bucket_name}/{destination_path}")
        else:
            try:
                public_url = upload_video_to_gcs(
                    bucket_name=args.bucket_name,
                    source_file_path=str(video_file),
                    destination_blob_name=destination_path,
                    make_public=True
                )
                
                uploaded_videos.append({
                    'original_name': video_file.name,
                    'sanitized_name': sanitized_name,
                    'gcs_path': destination_path,
                    'public_url': public_url
                })
                
            except Exception as e:
                print(f"❌ Failed to upload {video_file.name}: {e}")
    
    if not args.dry_run and uploaded_videos:
        # Save the mapping for later use
        mapping_file = Path('video_urls_mapping.txt')
        with open(mapping_file, 'w') as f:
            f.write("# Video URL Mapping\n")
            f.write("# Original Name -> Public URL\n\n")
            for video in uploaded_videos:
                f.write(f"{video['original_name']}\n")
                f.write(f"  URL: {video['public_url']}\n")
                f.write(f"  GCS: gs://{args.bucket_name}/{video['gcs_path']}\n\n")
        
        print(f"\n✅ Upload complete! Video URL mapping saved to {mapping_file}")
        print(f"📊 Uploaded {len(uploaded_videos)} videos successfully")

if __name__ == "__main__":
    main()
