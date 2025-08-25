import os
import re
from datetime import datetime, timedelta
import tempfile
import subprocess

# Try to import moviepy, fall back to placeholder if not available
try:
    from moviepy.video.io.VideoFileClip import VideoFileClip
    MOVIEPY_AVAILABLE = True
    print("✅ MoviePy successfully imported with VideoFileClip")
except ImportError as e:
    MOVIEPY_AVAILABLE = False
    print(f"MoviePy not available. Video processing will be disabled. Error: {e}")

class VideoProcessor:
    def __init__(self):
        # Default to any available MP4 under Video/Video; will be refined per response
        self.video_path = self._find_default_video()
        self.clips_dir = "static/video_clips"
        # Create clips directory if it doesn't exist
        os.makedirs(self.clips_dir, exist_ok=True)

    def _find_default_video(self):
        try:
            base_dir = "Video/Video"
            if os.path.isdir(base_dir):
                for name in os.listdir(base_dir):
                    if name.lower().endswith(".mp4"):
                        return os.path.join(base_dir, name)
        except Exception:
            pass
        return ""
    
    def parse_timestamp(self, timestamp_str):
        """Convert timestamp string to seconds (supports MM:SS, HH:MM:SS, and fractional seconds)."""
        try:
            ts = timestamp_str.strip()
            parts = ts.split(":")
            if len(parts) == 2:
                minutes = float(parts[0])
                seconds = float(parts[1])
                return float(minutes) * 60.0 + float(seconds)
            if len(parts) == 3:
                hours = float(parts[0])
                minutes = float(parts[1])
                seconds = float(parts[2])
                return float(hours) * 3600.0 + float(minutes) * 60.0 + float(seconds)
            raise ValueError(f"Invalid timestamp format: {timestamp_str}")
        except Exception as e:
            print(f"Error parsing timestamp '{timestamp_str}': {e}")
            return None
    
    def extract_timestamp_from_response(self, response_text):
        """Extract timestamp from the QA response"""
        # Look for ranges like HH:MM:SS(.s)–HH:MM:SS(.s) or with hyphen/dash
        range_match = re.search(r"(\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?)\s*[–-]\s*(\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?)", response_text)
        if range_match:
            start, end = range_match.group(1), range_match.group(2)
            # Normalize invalid mm >= 60 by carrying minutes to hours
            start = self._normalize_clock_time(start)
            end = self._normalize_clock_time(end)
            return start

        # Look for labeled or standalone HH:MM:SS(.s) or MM:SS(.s)
        ts_match = re.search(r"(?:Timestamp:\s*)?(\d{1,2}:\d{2}:\d{2}(?:\.\d+)?|\d{1,2}:\d{2}(?:\.\d+)?)", response_text)
        if ts_match:
            return self._normalize_clock_time(ts_match.group(1))

        # Look for seconds like "Timestamp: 93.5" or "Start time: 124 s"
        secs_match = re.search(r"(?:Timestamp:|Start\s*time:)\s*(\d+(?:\.\d+)?)\s*(?:s|sec|seconds)?", response_text, re.IGNORECASE)
        if secs_match:
            secs = float(secs_match.group(1))
            return self.seconds_to_hms(secs)

        return None

    def _normalize_clock_time(self, ts: str) -> str:
        try:
            parts = ts.split(":")
            if len(parts) == 2:
                m = int(parts[0])
                s = int(float(parts[1]))
                m2, s = divmod(s, 60)
                m += m2
                h, m = divmod(m, 60)
                return f"{h:02d}:{m:02d}:{s:02d}"
            if len(parts) == 3:
                h = int(parts[0])
                m = int(parts[1])
                s = int(float(parts[2]))
                m2, s = divmod(s, 60)
                m += m2
                h2, m = divmod(m, 60)
                h += h2
                return f"{h:02d}:{m:02d}:{s:02d}"
        except Exception:
            pass
        return ts

    def seconds_to_hms(self, total_seconds: float) -> str:
        total_seconds = max(0.0, float(total_seconds))
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(round(total_seconds % 60))
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def _choose_video_by_teaching(self, response_text: str) -> str:
        """Try to pick a video file that best matches the Teaching name in the response."""
        try:
            m = re.search(r"Teaching:\s*(.+)", response_text)
            teaching = m.group(1).strip() if m else ""
            base_dir = "Video/Video"
            if not os.path.isdir(base_dir):
                return self.video_path
            # Simple fuzzy match by token overlap
            tokens = set(re.findall(r"[a-z0-9]+", teaching.lower()))
            best = None
            best_score = -1
            for name in os.listdir(base_dir):
                if not name.lower().endswith(".mp4"):
                    continue
                v_tokens = set(re.findall(r"[a-z0-9]+", name.lower()))
                score = len(tokens & v_tokens)
                if score > best_score:
                    best = os.path.join(base_dir, name)
                    best_score = score
            return best or self.video_path
        except Exception:
            return self.video_path
    
    def create_video_clip(self, timestamp_str, duration_minutes=2):
        """Create a video clip starting from the given timestamp"""
        try:
            if not MOVIEPY_AVAILABLE:
                print(f"MoviePy not available. Cannot create video clip for timestamp {timestamp_str}")
                return None
                
            if not os.path.exists(self.video_path):
                # Try to find any default video now
                self.video_path = self._find_default_video()
                if not self.video_path or not os.path.exists(self.video_path):
                    print(f"Video file not found: {self.video_path}")
                    return None
            
            start_seconds = self.parse_timestamp(timestamp_str)
            if start_seconds is None:
                return None
            
            duration_seconds = duration_minutes * 60
            
            # Create a unique filename for the clip
            clip_filename = f"clip_{timestamp_str.replace(':', '-')}_{duration_minutes}min.mp4"
            clip_path = os.path.join(self.clips_dir, clip_filename)
            
            # Check if clip already exists
            if os.path.exists(clip_path):
                print(f"Using existing clip: {clip_filename}")
                return f"/static/video_clips/{clip_filename}"
            
            print(f"Creating video clip from {timestamp_str} for {duration_minutes} minutes...")

            # Try MoviePy first (using alternative method when subclip is unavailable)
            try:
                with VideoFileClip(self.video_path) as video:
                    video_duration = float(video.duration)
                    end_seconds = min(float(start_seconds) + float(duration_seconds), video_duration)
                    if float(start_seconds) >= video_duration:
                        print(f"Timestamp {timestamp_str} exceeds video duration")
                        return None
                    if hasattr(VideoFileClip, "subclip"):
                        clip = video.subclip(float(start_seconds), float(end_seconds))
                    else:
                        # Fallback: cut by setting start and end on the clip
                        clip = video.set_start(float(start_seconds)).set_end(float(end_seconds))
                    clip.write_videofile(clip_path, codec='libx264', audio_codec='aac')
                    clip.close()
                print(f"Video clip created: {clip_filename}")
                return f"/static/video_clips/{clip_filename}"
            except Exception as e_mp:
                print(f"MoviePy failed, falling back to ffmpeg: {e_mp}")

            # Fallback to ffmpeg CLI
            try:
                cmd = [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-ss", str(float(start_seconds)),
                    "-t", str(float(duration_seconds)),
                    "-i", self.video_path,
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                    "-c:a", "aac", "-b:a", "128k",
                    clip_path,
                ]
                subprocess.run(cmd, check=True)
                if os.path.exists(clip_path):
                    print(f"Video clip created (ffmpeg): {clip_filename}")
                    return f"/static/video_clips/{clip_filename}"
            except Exception as e_ff:
                print(f"FFmpeg fallback failed: {e_ff}")
                return None

        except Exception as e:
            print(f"Error creating video clip: {e}")
            return None
    
    def get_video_clip_url(self, response_text, duration_minutes=2):
        """Extract timestamp from response and create video clip"""
        # Choose the most relevant video for this response if possible
        chosen = self._choose_video_by_teaching(response_text)
        if chosen:
            self.video_path = chosen

        timestamp = self.extract_timestamp_from_response(response_text)
        if timestamp:
            return self.create_video_clip(timestamp, duration_minutes)
        return None
    
    def cleanup_old_clips(self, max_clips=20):
        """Remove old clips to prevent disk space issues"""
        try:
            if not os.path.exists(self.clips_dir):
                return
            
            clips = []
            for filename in os.listdir(self.clips_dir):
                if filename.endswith('.mp4'):
                    filepath = os.path.join(self.clips_dir, filename)
                    clips.append((filepath, os.path.getctime(filepath)))
            
            # Sort by creation time (oldest first)
            clips.sort(key=lambda x: x[1])
            
            # Remove oldest clips if we exceed max_clips
            while len(clips) > max_clips:
                old_clip_path, _ = clips.pop(0)
                try:
                    os.remove(old_clip_path)
                    print(f"Removed old clip: {os.path.basename(old_clip_path)}")
                except Exception as e:
                    print(f"Error removing old clip: {e}")
                    
        except Exception as e:
            print(f"Error during cleanup: {e}")

# Create a global instance only when needed
video_processor = None

def get_video_processor():
    """Get or create the video processor instance"""
    global video_processor
    if video_processor is None:
        try:
            video_processor = VideoProcessor()
        except Exception as e:
            print(f"Failed to create video processor: {e}")
            video_processor = False  # Mark as failed
    return video_processor if video_processor is not False else None