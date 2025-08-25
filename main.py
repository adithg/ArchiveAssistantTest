from langchain_pinecone import PineconeVectorStore
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import ChatOpenAI
from langchain.chains import RetrievalQA
from langchain.schema import Document
from dotenv import load_dotenv
import os
import glob
import nltk
import ssl
from pinecone import Pinecone

# Load environment variables from .env file
load_dotenv()

# Set environment variables
os.environ["OPENAI_API_KEY"] = os.getenv('OPENAI_API_KEY')
os.environ["PINECONE_API_KEY"] = os.getenv('PINECONE_API_KEY')

def setup_nltk():
    try:
        # Try to create unverified HTTPS context to handle SSL issues
        try:
            _create_unverified_https_context = ssl._create_unverified_context
        except AttributeError:
            pass
        else:
            ssl._create_default_https_context = _create_unverified_https_context
        
        # Download required NLTK data
        nltk.download('punkt_tab', quiet=True)
        nltk.download('averaged_perceptron_tagger_eng', quiet=True)
        print("NLTK data downloaded successfully")
    except Exception as e:
        print(f"Warning: Could not download NLTK data: {e}")

def load_text_files(directory):
    """Load text files from directory and extract metadata from filenames"""
    documents = []
    txt_files = glob.glob(os.path.join(directory, "*.txt"))
    
    for file_path in txt_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Extract teaching name from filename
                filename = os.path.basename(file_path)
                teaching_name = filename.replace('.txt', '')
                
                # Create a Document object with enhanced metadata
                doc = Document(
                    page_content=content,
                    metadata={
                        "source": file_path,
                        "teaching_name": teaching_name,
                        "filename": filename
                    }
                )
                documents.append(doc)
                print(f"Loaded: {teaching_name}")
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
    
    return documents

def check_index_exists_and_has_data(index_name):
    """Check if Pinecone index exists and has data"""
    try:
        pc = Pinecone(api_key=os.getenv('PINECONE_API_KEY'))
        
        # Check if index exists
        if index_name not in pc.list_indexes().names():
            print(f"Index '{index_name}' does not exist.")
            return False
        
        # Check if index has data
        index = pc.Index(index_name)
        stats = index.describe_index_stats()
        vector_count = stats.get('total_vector_count', 0)
        
        print(f"Index '{index_name}' exists with {vector_count} vectors.")
        return vector_count > 0
        
    except Exception as e:
        print(f"Error checking index: {e}")
        return False

def get_user_choice(prompt, valid_choices):
    """Get user input with validation"""
    while True:
        choice = input(prompt).strip().lower()
        if choice in valid_choices:
            return choice
        print(f"Please enter one of: {', '.join(valid_choices)}")

def upload_documents(index_name, embeddings):
    """Upload documents to Pinecone"""
    # Load documents from local directory
    docs = load_text_files('Transcripts')
    
    if not docs:
        print("No documents loaded. Please check your HenryTranscripts directory.")
        return None
    
    print(f"Loaded {len(docs)} documents")
    
    # Set up text splitter with larger chunks to capture more context
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=300)
    split_docs = text_splitter.split_documents(docs)
    
    print(f"Split into {len(split_docs)} chunks")
    
    # Create vector store and upload documents
    print("Creating vector store and uploading documents...")
    vectorstore = PineconeVectorStore.from_documents(
        split_docs, 
        embeddings, 
        index_name=index_name
    )
    print("Documents uploaded successfully!")
    return vectorstore

def main():
    setup_nltk()
    
    index_name = "archiveassistanttest"
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    
    # Check if we need to upload documents
    has_existing_data = check_index_exists_and_has_data(index_name)
    
    if has_existing_data:
        print("Found existing data in Pinecone.")
        choice = get_user_choice(
            "Do you want to:\n"
            "1. Use existing data (u)\n"
            "2. Re-upload documents (r)\n"
            "3. Quit (q)\n"
            "Enter your choice: ", 
            ['u', 'r', 'q', 'use', 'reupload', 'quit']
        )
        
        if choice in ['q', 'quit']:
            print("Goodbye!")
            return
        elif choice in ['r', 'reupload']:
            print("Re-uploading documents...")
            vectorstore = upload_documents(index_name, embeddings)
            if vectorstore is None:
                return
        else:  # use existing
            print("Using existing data.")
            vectorstore = PineconeVectorStore(
                index_name=index_name,
                embedding=embeddings
            )
    else:
        print("No existing data found.")
        choice = get_user_choice(
            "Do you want to upload documents now? (y/n): ",
            ['y', 'n', 'yes', 'no']
        )
        
        if choice in ['n', 'no']:
            print("Cannot proceed without documents. Goodbye!")
            return
        
        print("Loading and processing documents...")
        vectorstore = upload_documents(index_name, embeddings)
        if vectorstore is None:
            return
    
    # Set up the QA chain with specific instructions for Henry quotes
    llm = ChatOpenAI(
        temperature=0.2,
        model_name="gpt-3.5-turbo"
    )
    
    # Custom prompt to ensure only Henry's direct quotes are returned
    from langchain.prompts import PromptTemplate
    
    prompt_template = """You are an assistant that helps people find one direct quote from Henry's teachings. 

IMPORTANT INSTRUCTIONS:
1. Find the MOST RELEVANT quote from Henry that answers the question
2. Once you find a relevant starting point, include the COMPLETE PASSAGE from that timestamp - continue reading the following sentences that come after the initial relevant quote to provide a fuller, more complete response
3. Provide EXTENDED PASSAGES (multiple sentences forming complete thoughts) rather than short fragments
4. Always include the exact timestamp if available in the source material
5. Always include the name/title of the specific teaching the quote comes from
6. If you cannot find a direct quote that answers the question, say "I could not find a direct quote from Henry addressing this topic."
7. Never add your own commentary or interpretation - only Henry's exact words from the transcript
8. The goal is to provide substantial, meaningful passages that give complete context and deeper insights

Use this context to find direct quotes from Henry:
{context}

Question: {question}

Response format:

Henry's Quote: "[Start with the most relevant sentence that answers the question, then continue with the following sentences from that same section to provide a complete, extended passage that gives fuller context and meaning]"

Answer:"""
    
    PROMPT = PromptTemplate(
        template=prompt_template,
        input_variables=["context", "question"]
    )
    
    # Create retriever with enhanced settings for longer context
    retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 3}  # Get more relevant chunks for better context
    )
    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        chain_type_kwargs={"prompt": PROMPT}
    )
    
    # Interactive query loop
    print("\nReady to find Henry's direct quotes!")
    print("Ask questions and I'll provide his exact words with timestamps and teaching names.")
    print("Type 'quit' to exit.\n")
    
    while True:
        query = input("What would you like to find from Henry's teachings? ")
        
        if query.lower() == 'quit':
            break
            
        try:
            result = qa_chain.invoke(query)
            print(f"\n{result['result']}\n")
            print("-" * 50)
        except Exception as e:
            print(f"Error: {e}\n")

if __name__ == "__main__":
    main()