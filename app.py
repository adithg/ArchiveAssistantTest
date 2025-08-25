from flask import Flask, render_template, request, jsonify, send_from_directory
from langchain_pinecone import PineconeVectorStore
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv
import os
# Try to import video processor, but handle gracefully if not available
try:
    from video_processor import get_video_processor
    VIDEO_PROCESSING_AVAILABLE = True
except ImportError:
    VIDEO_PROCESSING_AVAILABLE = False
    get_video_processor = lambda: None

# Try to import Google Cloud Storage for video proxy
try:
    from google.cloud import storage
    GCS_AVAILABLE = True
except ImportError:
    GCS_AVAILABLE = False
    storage = None

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Initialize the components
def initialize_qa_system():
    """Initialize the QA system with Pinecone and OpenAI"""
    try:
        # Set up embeddings and vector store
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        vectorstore = PineconeVectorStore(
            index_name=os.getenv("PINECONE_INDEX", "archiveassistanttest"),
            embedding=embeddings
        )
        
        # Set up the LLM
        llm = ChatOpenAI(
            temperature=0.2,
            model_name="gpt-3.5-turbo",
            frequency_penalty=0.6,
            presence_penalty=0.1,
        )
        
        # Custom prompt template
        prompt_template = """You are an assistant that helps people find direct quotes from Henry's teachings. 

CRITICAL INSTRUCTIONS FOR SUBSTANTIAL QUOTES:
1. SCAN the provided context carefully to find the MOST RELEVANT section that directly addresses the question
2. EXTRACT the complete passage from that relevant section - aim for 3-6 full sentences minimum
3. FOCUS on the part that directly answers the question, even if the document contains other topics
4. INCLUDE the complete thought from start to finish - don't cut off mid-sentence or mid-idea
5. If the context contains mixed topics, ONLY extract the portion that addresses the specific question
6. Provide Henry's EXACT WORDS from the transcript - never paraphrase or add your own words
7. Timestamps: Convert seconds to HH:MM:SS format and round to nearest second (e.g., 64.4 → 00:01:04). Show as range if both start/end exist: HH:MM:SS–HH:MM:SS
8. Always include the teaching name/title from the context
9. If you cannot find a relevant quote that directly addresses the question, provide the most relevant content available and note that it may be related but not directly addressing the specific question.
10. NEVER add commentary - only Henry's exact words, but make sure they form a COMPLETE, MEANINGFUL passage

EXTRACTION STRATEGY:
- Look for the specific topic mentioned in the question
- Find where Henry directly addresses that topic
- Extract the complete discussion of that topic
- Ignore unrelated content in the same document

QUALITY CHECK: Before responding, ensure your quote is:
- Directly relevant to the question asked
- At least 3-6 complete sentences about the specific topic
- Forms a coherent, complete thought
- Doesn't include unrelated content from the same document

Use this context to find direct quotes from Henry:
{context}

Question: {question}

Response format:
Teaching: [Use the CSV filename shown in the context as the title]
Timestamp: [HH:MM:SS or HH:MM:SS–HH:MM:SS when computed from seconds; round seconds]
Henry's Quote: "[Start with the most relevant sentence that answers the question, then continue with the following sentences from that same section to provide a complete, extended passage that gives fuller context and meaning]"

Answer:"""
        
        PROMPT = PromptTemplate(
            template=prompt_template,
            input_variables=["context", "question"]
        )
        
        # Create QA chain with enhanced retrieval and a document prompt that exposes metadata
        retriever = vectorstore.as_retriever(
            search_type="mmr",
            search_kwargs={"k": 3, "fetch_k": 20, "lambda_mult": 0.3}
        )

        # Make each document include the teaching (CSV filename) and seconds when present
        from langchain.prompts import PromptTemplate as _DocPrompt
        document_prompt = _DocPrompt(
            input_variables=["page_content", "teaching_name", "start_seconds", "end_seconds"],
            template=(
                "Teaching: {teaching_name}\n"
                "StartSeconds: {start_seconds}\nEndSeconds: {end_seconds}\n"
                "{page_content}"
            ),
        )

        qa_chain = RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",
            retriever=retriever,
            chain_type_kwargs={
                "prompt": PROMPT,
                "document_prompt": document_prompt,
                "document_variable_name": "context",  # ensure docs render into {context}
            },
            return_source_documents=True,
        )
        
        return qa_chain
        
    except Exception as e:
        print(f"Error initializing QA system: {e}")
        print(f"Error type: {type(e).__name__}")
        print(f"OPENAI_API_KEY set: {'OPENAI_API_KEY' in os.environ}")
        print(f"PINECONE_API_KEY set: {'PINECONE_API_KEY' in os.environ}")
        print(f"PINECONE_INDEX set: {'PINECONE_INDEX' in os.environ}")
        import traceback
        traceback.print_exc()
        return None

# Initialize the QA system
qa_system = initialize_qa_system()

@app.route('/')
def home():
    """Render the main chat interface"""
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    """Handle chat requests and generate video clips"""
    try:
        data = request.get_json()
        question = data.get('question', '')
        
        if not question:
            return jsonify({'error': 'No question provided'}), 400
        
        if not qa_system:
            return jsonify({'error': 'QA system not initialized. Please check your API keys and Pinecone setup.'}), 500
        
        # Get response from QA system
        result = qa_system.invoke(question)
        response = result['result']
        
        # Extract video information from source documents
        video_url = None
        video_timestamp = None
        
        try:
            docs = result.get('source_documents') or []
            if docs:
                # Find the document that most likely contains the quoted content
                best_doc = docs[0]
                best_match_score = 0
                
                # Check which document has the most overlap with the response
                response_words = set(response.lower().split())
                for doc in docs:
                    doc_words = set(doc.page_content.lower().split())
                    overlap = len(response_words.intersection(doc_words))
                    if overlap > best_match_score:
                        best_match_score = overlap
                        best_doc = doc
                
                md = getattr(best_doc, 'metadata', {}) or {}
                start_s = md.get('start_seconds')
                end_s = md.get('end_seconds')
                teaching = md.get('teaching_name')
                
                # Get video URL if available (now publicly accessible)
                video_url = md.get('video_url')
                
                # Try to find the most precise timestamp by analyzing the content structure
                content = best_doc.page_content
                import re
                
                # Parse content into timestamp sections
                sections = []
                lines = content.split('\n')
                current_section = {'timestamp': None, 'text': []}
                
                for line in lines:
                    if 'Timestamp:' in line:
                        # Save previous section if it exists
                        if current_section['timestamp'] and current_section['text']:
                            sections.append(current_section)
                        
                        # Start new section
                        ts_match = re.search(r'(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)', line)
                        if ts_match:
                            current_section = {
                                'timestamp': (float(ts_match.group(1)), float(ts_match.group(2))),
                                'text': []
                            }
                    else:
                        if line.strip():  # Only add non-empty lines
                            current_section['text'].append(line.strip())
                
                # Add final section
                if current_section['timestamp'] and current_section['text']:
                    sections.append(current_section)
                
                # Find the section with the highest overlap with the response
                if sections and response_words:
                    best_section = None
                    best_overlap = 0
                    
                    for section in sections:
                        section_text = ' '.join(section['text']).lower()
                        section_words = set(section_text.split())
                        overlap = len(response_words.intersection(section_words))
                        
                        if overlap > best_overlap:
                            best_overlap = overlap
                            best_section = section
                    
                    # Use the timestamp from the best matching section
                    if best_section and best_overlap > 2:  # Lower threshold for better matching
                        start_s = best_section['timestamp'][0]
                        end_s = best_section['timestamp'][1]
                        print(f"DEBUG: Using precise timestamp {start_s}-{end_s} with {best_overlap} word overlap")
                
                # Format timestamp for display and video seeking
                if start_s is not None or end_s is not None:
                    def fmt(s):
                        try:
                            s = float(s)
                            h = int(s // 3600)
                            m = int((s % 3600) // 60)
                            se = int(round(s % 60))
                            return f"{h:02d}:{m:02d}:{se:02d}"
                        except Exception:
                            return None
                    
                    start_str = fmt(start_s) if start_s is not None else None
                    end_str = fmt(end_s) if end_s is not None else None
                    
                    # For display
                    ts_display = None
                    if start_str and end_str:
                        ts_display = f"{start_str}-{end_str}"
                    elif start_str:
                        ts_display = start_str
                    
                    # For video seeking (use start time in seconds)
                    if start_s is not None and video_url:
                        video_timestamp = int(start_s)
                    
                    # Add timestamp to response if not already present
                    if ts_display and 'Timestamp:' not in response:
                        header = []
                        if teaching and 'Teaching:' not in response:
                            header.append(f"Teaching: {teaching}")
                        header.append(f"Timestamp: {ts_display}")
                        response = "\n".join(header + [response])
        except Exception as e:
            print(f"Error processing video metadata: {e}")
            pass
        
        # Return response with video information
        return jsonify({
            'response': response,
            'video_url': video_url,
            'video_timestamp': video_timestamp
        })
        
    except Exception as e:
        return jsonify({'error': f'Error processing question: {str(e)}'}), 500

@app.route('/health')
def health():
    """Health check endpoint"""
    video_available = False
    if VIDEO_PROCESSING_AVAILABLE:
        video_processor = get_video_processor()
        if video_processor:
            try:
                video_available = os.path.exists(video_processor.video_path)
            except:
                video_available = False
    
    return jsonify({
        'status': 'healthy',
        'qa_system_initialized': qa_system is not None,
        'video_processing_available': video_available
    })

@app.route('/static/video_clips/<filename>')
def serve_video_clip(filename):
    """Serve video clip files"""
    try:
        return send_from_directory('static/video_clips', filename)
    except Exception as e:
        return jsonify({'error': 'Video clip not found'}), 404

if __name__ == '__main__':
    print("Starting Henry's Teaching Archive Chatbot...")
    print("Visit http://localhost:5001 to use the chatbot")
    app.run(debug=True, host='0.0.0.0', port=5001)