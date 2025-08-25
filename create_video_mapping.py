#!/usr/bin/env python3
"""
Create a mapping between transcript names and Google Cloud Storage video URLs.
This will be used to associate video URLs with Pinecone metadata.
"""

import os
import re
from pathlib import Path
import json

def normalize_name(name):
    """Normalize names for matching by removing common variations"""
    # Remove file extensions
    name = re.sub(r'\.(csv|mp4)$', '', name, flags=re.IGNORECASE)
    
    # Remove common suffixes
    name = re.sub(r'\s+(Transcription|Transcript)$', '', name, flags=re.IGNORECASE)
    
    # Normalize spacing and punctuation
    name = re.sub(r'\s+', ' ', name.strip())
    name = re.sub(r'\s*\(\s*\d+\s*\)\s*$', '', name)  # Remove (1), (2) etc at end
    
    # Remove trailing periods and spaces
    name = name.rstrip('. ')
    
    return name

def create_video_mapping():
    """Create mapping between transcript files and GCS video URLs"""
    
    # Base GCS URL for your videos
    base_gcs_url = "https://storage.googleapis.com/archive-assistant/videos"
    
    # Get transcript files
    transcript_dir = Path("Transcripts")
    transcript_files = list(transcript_dir.glob("*.csv"))
    
    # Define video mappings based on your uploaded files
    # Format: normalized_transcript_name -> gcs_video_filename
    video_mappings = {
        "DC Retreat Day 1": "Oct_2024_DC_Retreat_Day_1.mp4",
        "DC Retreat Day 2": "Oct_2024_DC_Retreat_Day_2.mp4", 
        "DC Retreat Day 3": "Oct_2024_DC_Retreat_Day_3.mp4",
        "One Day Retreat London": "One-Day_Retreat_London_with_Henry_Shukman_May_2024.mp4",
        "Original Love One-Year Session 1": "Original_Love_One-Year_Session_1_Jan_21_2024.mp4",
        "Original Love One-Year Session 4": "Original_Love_One-Year_Session_4.mp4",
        "Original Love One-Year Session 5": "Original_Love_One-Year_Session_5_Mar_24.mp4",
        "Original Love One-Year Session 6": "Original_Love_One-Year_Session_6.mp4",
        "Original Love One-Year Session 8": "Original_Love_One-Year_Session_8_May_2024.mp4",
        "Original Love One-Year Session 10": "Original_Love_One-Year_Session_10.mp4",
        "Original Love One-Year Session 11": "Original_Love_One-Year_Session_11.mp4",
        "Original Love One-Year Session 12": "Original_Love_One-Year_Session_12_July_2024.mp4",
        "Original Love One-Year Session 15": "2024-08-25_Original_Love_One-Year_Sunday_Session_15.mp4",
        "Original Love One-Year Session 16": "2024-09-01_Original_Love_One-Year_Sunday_Session_16.mp4",
        "Original Love Trailer Nov 2024": "Original_Love_Trailer_Nov_2024.mp4",
        "Santa Fe Retreat Day 1": "Santa_Fe_Retreat_Day_1_Oct_2024.mp4",
        "True Person of No Rank Koans": "True_Person_of_No_Rank_Koans_Dec_2024.mp4",
    }
    
    # Create the final mapping
    final_mapping = {}
    
    print("🎥 Creating video mapping...")
    print(f"Found {len(transcript_files)} transcript files")
    
    for transcript_file in transcript_files:
        transcript_name = transcript_file.stem
        normalized_name = normalize_name(transcript_name)
        
        print(f"📄 Transcript: {transcript_name}")
        print(f"   Normalized: {normalized_name}")
        
        if normalized_name in video_mappings:
            video_filename = video_mappings[normalized_name]
            video_url = f"{base_gcs_url}/{video_filename}"
            final_mapping[transcript_name] = {
                "normalized_name": normalized_name,
                "video_filename": video_filename,
                "video_url": video_url
            }
            print(f"   ✅ Mapped to: {video_url}")
        else:
            print(f"   ❌ No video mapping found")
        
        print()
    
    # Save the mapping to a JSON file
    mapping_file = "video_mapping.json"
    with open(mapping_file, 'w') as f:
        json.dump(final_mapping, f, indent=2)
    
    print(f"💾 Saved video mapping to {mapping_file}")
    print(f"📊 Mapped {len(final_mapping)} out of {len(transcript_files)} transcripts")
    
    return final_mapping

if __name__ == "__main__":
    create_video_mapping()
