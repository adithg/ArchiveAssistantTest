#!/usr/bin/env python3
"""
Fix the video mapping to use the correct GCS paths and create signed URLs.
"""

import json
from urllib.parse import quote

def create_corrected_mapping():
    """Create corrected video mapping with actual GCS paths"""
    
    # Base GCS URL for your videos (correct path)
    base_gcs_url = "https://storage.googleapis.com/archive-assistant/Videos/Video"
    
    # Mapping of transcript names to actual video filenames in GCS
    # Include variations with "Transcription" suffix
    video_mappings = {
        "DC Retreat Day 1": "Oct 2024 DC Retreat Day 1.mp4",
        "DC Retreat Day 2": "Oct 2024 DC Retreat Day 2.mp4", 
        "DC Retreat Day 3": "Oct 2024 DC Retreat Day 3.mp4",
        "One Day Retreat London": "One-Day Retreat London with Henry Shukman May 2024.mp4",
        "Original Love One-Year Session 1": "Original Love One-Year Session 1 Jan 21 2024.mp4",
        "Original Love One-Year Session 4": "Original Love One-Year Session 4.mp4",
        "Original Love One-Year Session 4 Transcription": "Original Love One-Year Session 4.mp4",
        "Original Love One-Year Session 5": "Original Love One-Year Session 5 Mar 24.mp4",
        "Original Love One-Year Session 6": "Original Love One-Year Session 6.mp4",
        "Original Love One-Year Session 6 Transcription": "Original Love One-Year Session 6.mp4",
        "Original Love One-Year Session 8": "Original Love One-Year Session 8 May 2024.mp4",
        "Original Love One-Year Session 10": "Original Love One-Year Session 10.mp4",
        "Original Love One-Year Session 10 Transcription": "Original Love One-Year Session 10.mp4",
        "Original Love One-Year Session 11": "Original Love One-Year Session 11.mp4",
        "Original Love One-Year Session 11 Transcription": "Original Love One-Year Session 11.mp4",
        "Original Love One-Year Session 12": "Original Love One-Year Session 12 July 2024.mp4",
        "Original Love One-Year Session 15": "2024-08-25 Original Love One-Year Sunday Session 15.mp4",
        "Original Love One-Year Session 16": "2024-09-01 Original Love One-Year Sunday Session 16.mp4",
        "Original Love Trailer Nov 2024": "Original Love Trailer Nov 2024.mp4",
        "Santa Fe Retreat Day 1": "Santa Fe Retreat Day 1 Oct 2024.mp4",
        "True Person of No Rank Koans": "True Person of No Rank Koans Dec 2024.mp4",
    }
    
    # Create the final mapping
    final_mapping = {}
    
    print("🔧 Creating corrected video mapping...")
    
    for transcript_name, video_filename in video_mappings.items():
        # URL encode the filename for the URL
        encoded_filename = quote(video_filename)
        video_url = f"{base_gcs_url}/{encoded_filename}"
        
        final_mapping[transcript_name] = {
            "normalized_name": transcript_name,
            "video_filename": video_filename,
            "video_url": video_url,
            "gcs_path": f"Videos/Video/{video_filename}"
        }
        print(f"✅ {transcript_name} -> {video_filename}")
    
    # Save the corrected mapping
    with open("video_mapping_corrected.json", 'w') as f:
        json.dump(final_mapping, f, indent=2)
    
    print(f"\n💾 Saved corrected mapping to video_mapping_corrected.json")
    print(f"📊 Mapped {len(final_mapping)} teachings")
    
    return final_mapping

if __name__ == "__main__":
    create_corrected_mapping()
