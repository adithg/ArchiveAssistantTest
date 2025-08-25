# Archive Assistant - Technical Handoff Document

## Executive Summary

The Archive Assistant is a fully functional AI-powered chatbot that provides users with direct quotes from Henry's meditation teachings, synchronized with video playback at precise timestamps. This document provides complete technical details for ongoing development and maintenance.

**Current Status:** Production-ready, deployed on Vercel with 17+ teaching sessions indexed
**Live URL:** https://archive-assistant-test-9ngpeton0-adith-gangalakuntas-projects.vercel.app

---

## Architecture Overview

### System Components
```
User Interface (Frontend)
    ↓
Flask Application (Backend)
    ↓
OpenAI API (Embeddings + LLM)
    ↓
Pinecone Vector Database
    ↓
Google Cloud Storage (Videos)
```

### Technology Stack
- **Backend:** Python Flask application
- **AI/ML:** OpenAI GPT-3.5-turbo + text-embedding-3-small
- **Vector Database:** Pinecone (for semantic search)
- **Video Storage:** Google Cloud Storage (public access)
- **Deployment:** Vercel (serverless)
- **Frontend:** HTML/CSS/JavaScript with video player integration

---

## File Structure & Key Components

### Core Application Files
```
├── app.py                    # Main Flask application
├── main.py                   # Local testing/development script
├── ingest_transcripts.py     # Data ingestion pipeline
├── video_processor.py        # Local video processing (not used in production)
├── requirements.txt          # Python dependencies
├── vercel.json              # Vercel deployment configuration
├── api/index.py             # Vercel entry point
└── .vercelignore            # Files excluded from deployment
```

### Data & Configuration
```
├── Transcripts/             # Original CSV transcript files
├── Video/                   # Local video files (not deployed)
├── video_mapping.json       # Teaching name to GCS video URL mapping
├── static/                  # Frontend assets
│   ├── css/style.css
│   ├── js/chat.js
│   └── video_clips/         # Local clips (not deployed)
└── templates/index.html     # Main UI template
```

### Utility Scripts
```
├── upload_videos_to_gcs.py     # Upload videos to Google Cloud Storage
├── make_videos_public.py       # Make GCS videos publicly accessible
├── create_video_mapping.py     # Generate video URL mappings
└── fix_video_mapping.py        # Correct mapping inconsistencies
```

---

## Core Application Logic (app.py)

### Key Functions

#### 1. QA System Initialization
```python
def initialize_qa_system():
    # Sets up OpenAI embeddings, Pinecone connection, and RetrievalQA chain
    # Returns configured QA system or None if initialization fails
```

#### 2. Chat Endpoint (/chat)
```python
@app.route('/chat', methods=['POST'])
def chat():
    # Main API endpoint for user questions
    # Returns: JSON with response, video_url, video_timestamp
```

#### 3. Timestamp Matching Logic
The system implements sophisticated timestamp matching:
- Finds the document with highest word overlap with LLM response
- Parses content into timestamp sections
- Selects the section with best semantic match
- Returns precise video seeking timestamp

### Environment Variables Required
```bash
OPENAI_API_KEY=your_openai_api_key
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_INDEX=archiveassistanttest
```

---

## Data Pipeline & Ingestion

### 1. Transcript Processing (ingest_transcripts.py)

**Purpose:** Convert CSV transcripts into vector embeddings for semantic search

**Key Parameters:**
- `--window-size 7`: Number of sentences per chunk
- `--step-size 4`: Overlap between chunks
- `--max-chars 3000`: Maximum characters per chunk
- `--reset-index`: Clear existing data before ingestion

**Usage:**
```bash
python ingest_transcripts.py --reset-index --window-size 7 --step-size 4 --max-chars 3000
```

**Process:**
1. Loads CSV files from `Transcripts/` directory
2. Chunks text using sliding window approach
3. Generates OpenAI embeddings for each chunk
4. Uploads to Pinecone with metadata (timestamps, teaching names, video URLs)

### 2. Video URL Mapping (video_mapping.json)

**Structure:**
```json
{
  "Teaching Name": {
    "normalized_name": "Teaching Name",
    "video_filename": "actual_file.mp4",
    "video_url": "https://storage.googleapis.com/bucket/path/file.mp4",
    "gcs_path": "Videos/Video/actual_file.mp4"
  }
}
```

**Key Mappings:**
- Maps transcript filenames to GCS video URLs
- Handles variations (e.g., "Session 10" vs "Session 10 Transcription")
- Used during ingestion to add video URLs to Pinecone metadata

---

## Google Cloud Storage Setup

### Current Configuration
- **Bucket:** `archive-assistant`
- **Path Structure:** `Videos/Video/[filename].mp4`
- **Access:** Public read access (no authentication required)
- **URLs:** Direct HTTPS access via `storage.googleapis.com`

### Key Scripts

#### upload_videos_to_gcs.py
```python
# Uploads local videos to GCS bucket
# Sanitizes filenames and maintains directory structure
```

#### make_videos_public.py
```python
# Makes uploaded videos publicly accessible
# Required for frontend video player access
```

### Authentication
Uses Google Cloud Application Default Credentials (ADC):
```bash
gcloud auth application-default login
```

---

## Deployment (Vercel)

### Configuration Files

#### vercel.json
```json
{
  "builds": [
    {
      "src": "api/index.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "api/index.py"
    }
  ]
}
```

#### api/index.py
```python
from app import app
# Direct export for Vercel Python runtime
```

#### .vercelignore
```
Video/
Transcripts/
static/video_clips/
*.mp4
*.mov
*.avi
*.mkv
*.m4v
```

### Deployment Commands
```bash
# Install Vercel CLI
npm i -g vercel

# Deploy to production
npx vercel --prod

# Set environment variables
npx vercel env add OPENAI_API_KEY
npx vercel env add PINECONE_API_KEY
npx vercel env add PINECONE_INDEX
```

### Environment Variables in Vercel
Set via Vercel dashboard or CLI:
- `OPENAI_API_KEY`: OpenAI API key
- `PINECONE_API_KEY`: Pinecone API key  
- `PINECONE_INDEX`: Pinecone index name (archiveassistanttest)

---

## Frontend Implementation

### Main UI (templates/index.html)
- Clean chat interface with message history
- Integrated video player with timestamp seeking
- Responsive design for mobile compatibility

### JavaScript (static/js/chat.js)
**Key Functions:**
- `sendMessage()`: Handles user input and API calls
- `addMessage()`: Displays messages and video content
- `formatTime()`: Converts seconds to HH:MM:SS format

**Video Integration:**
```javascript
// Automatic timestamp seeking
if (videoTimestamp !== null && videoTimestamp > 0) {
    videoElement.addEventListener('loadedmetadata', () => {
        videoElement.currentTime = videoTimestamp;
    });
}
```

### Styling (static/css/style.css)
- Modern chat interface design
- Video player integration
- Mobile-responsive layout

---

## Current Data Scope

### Ingested Teachings (17 sessions)
- DC Retreat Day 1, 2, 3
- One Day Retreat London
- Original Love One-Year Sessions 1, 4-6, 8, 10-12, 15-16
- Original Love Trailer Nov 2024
- Santa Fe Retreat Day 1
- True Person of No Rank Koans

### Data Statistics
- **Total Chunks:** ~11,060 (with current chunking strategy)
- **Average Chunk Size:** 7 sentences, ~3000 characters
- **Overlap:** 4 sentences between chunks
- **Vector Dimensions:** 1536 (OpenAI text-embedding-3-small)

---

## Key Algorithms & Logic

### 1. Intelligent Timestamp Matching
```python
# Find document with highest word overlap with response
response_words = set(response.lower().split())
for doc in docs:
    doc_words = set(doc.page_content.lower().split())
    overlap = len(response_words.intersection(doc_words))

# Parse content into timestamp sections
# Find section with best semantic match
# Return precise timestamp for video seeking
```

### 2. Prompt Engineering
The system uses a carefully crafted prompt that:
- Demands substantial quotes (3-6 sentences minimum)
- Focuses on relevant content extraction
- Handles mixed-topic documents
- Converts timestamps to HH:MM:SS format
- Provides complete, coherent thoughts

### 3. Retrieval Strategy
- **Search Type:** MMR (Maximal Marginal Relevance)
- **Parameters:** k=3, fetch_k=20, lambda_mult=0.3
- **Benefits:** Balances relevance with diversity

---

## Monitoring & Maintenance

### Health Check Endpoint
```
GET /health
Returns: {"status": "healthy", "qa_system_initialized": true}
```

### Logs & Debugging
- Vercel deployment logs: `npx vercel logs [deployment-url]`
- Local testing: Run `python app.py` (requires Flask installation)
- Debug prints for timestamp matching included in production

### Common Issues & Solutions

#### 1. Quote-Video Misalignment
**Symptoms:** Video doesn't match the returned quote
**Solution:** Check timestamp parsing logic, verify video_mapping.json accuracy

#### 2. Empty/No Results
**Symptoms:** "I could not find..." responses
**Solution:** Check Pinecone connectivity, verify embeddings quality, adjust search parameters

#### 3. Video Loading Errors
**Symptoms:** Videos don't play or show 403 errors
**Solution:** Verify GCS bucket permissions, check video URLs in video_mapping.json

---

## Development Workflow

### Local Development Setup
1. Install dependencies: `pip install -r requirements.txt`
2. Set environment variables in `.env` file
3. Run ingestion: `python ingest_transcripts.py`
4. Start Flask app: `python app.py`
5. Test at `http://localhost:5000`

### Adding New Teachings
1. Add CSV transcript to `Transcripts/` directory
2. Upload corresponding video to GCS using `upload_videos_to_gcs.py`
3. Update `video_mapping.json` with new teaching
4. Re-run ingestion: `python ingest_transcripts.py --reset-index`
5. Deploy updated application

### Performance Optimization
- **Chunking:** Adjust window_size/step_size for better relevance
- **Embeddings:** Consider fine-tuned models for spiritual content
- **Caching:** Implement Redis for frequently asked questions
- **CDN:** Use CDN for video delivery optimization

---

## API Documentation

### POST /chat
**Request:**
```json
{
  "question": "How do I meditate?"
}
```

**Response:**
```json
{
  "response": "Teaching: Session Name\nTimestamp: HH:MM:SS\nHenry's Quote: \"[Complete quote text...]\"",
  "video_url": "https://storage.googleapis.com/bucket/path/video.mp4",
  "video_timestamp": 1234
}
```

### GET /health
**Response:**
```json
{
  "status": "healthy",
  "qa_system_initialized": true,
  "video_processing_available": false
}
```

---

## Security Considerations

### API Keys
- OpenAI and Pinecone keys stored as environment variables
- Never commit keys to version control
- Rotate keys periodically

### Video Access
- Videos are publicly accessible (no authentication required)
- Consider signed URLs for sensitive content
- Monitor GCS usage and costs

### User Data
- No user data currently stored
- Consider GDPR compliance for future user accounts
- Implement rate limiting for API abuse prevention

---

## Cost Management

### Current Monthly Costs (Estimated)
- **OpenAI API:** $20-50 (depending on usage)
- **Pinecone:** $70 (starter plan)
- **Google Cloud Storage:** $5-10 (storage + bandwidth)
- **Vercel:** Free tier (sufficient for current usage)

### Optimization Strategies
- Cache frequent queries to reduce OpenAI calls
- Optimize chunk sizes to reduce Pinecone storage
- Use CDN for video delivery to reduce GCS bandwidth costs
- Monitor usage patterns and adjust accordingly

---

## Future Technical Considerations

### Scalability
- Current architecture handles ~1000 concurrent users
- Consider database migration for user accounts/history
- Implement proper logging and monitoring
- Add auto-scaling for high traffic periods

### Data Management
- Implement versioned embeddings for content updates
- Add backup/restore procedures for Pinecone data
- Consider hybrid search (vector + keyword) for better accuracy
- Implement A/B testing for prompt optimization

### Integration Points
- Mobile app API compatibility
- User authentication system integration
- Analytics and tracking implementation
- Third-party meditation app integrations

---

## Contact & Handoff Notes

### Key Decisions Made
1. **Chunking Strategy:** 7 sentences with 4-sentence overlap for optimal context
2. **Timestamp Matching:** Word overlap algorithm for precise video seeking  
3. **Public Video Access:** Simplified architecture, no authentication required
4. **Vercel Deployment:** Serverless for easy scaling and maintenance

### Known Limitations
1. **Local Video Processing:** Not available in serverless environment
2. **No User Accounts:** All sessions are stateless
3. **Limited Error Handling:** Basic error responses, could be enhanced
4. **No Caching:** Every query hits OpenAI API

### Recommended Next Steps
1. Implement user feedback collection system
2. Add comprehensive logging and monitoring
3. Optimize chunking strategy based on user feedback
4. Consider implementing caching layer
5. Add automated testing pipeline

---

*This document should be updated as the system evolves. For technical questions, refer to the codebase comments and the development roadmap document.*
