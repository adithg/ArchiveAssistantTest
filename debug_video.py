#!/usr/bin/env python3
"""
Debug script to check video URL retrieval from Pinecone
"""

import os
from dotenv import load_dotenv
from langchain_pinecone import PineconeVectorStore
from langchain_openai import OpenAIEmbeddings
from langchain.chains import RetrievalQA
from langchain_openai import ChatOpenAI

load_dotenv()

def test_video_retrieval():
    """Test if video URLs are being retrieved correctly"""
    
    print("🔍 Testing video URL retrieval...")
    
    # Set up embeddings and vector store
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vectorstore = PineconeVectorStore(
        index_name="archiveassistanttest",
        embedding=embeddings
    )
    
    # Test query
    test_query = "What does Henry say about meditation?"
    
    # Get similar documents
    docs = vectorstore.similarity_search(test_query, k=3)
    
    print(f"\n📄 Found {len(docs)} documents:")
    
    for i, doc in enumerate(docs):
        print(f"\n--- Document {i+1} ---")
        print(f"Content preview: {doc.page_content[:100]}...")
        print(f"Metadata: {doc.metadata}")
        
        # Check for video URL
        video_url = doc.metadata.get('video_url')
        teaching_name = doc.metadata.get('teaching_name')
        
        print(f"Teaching name: {teaching_name}")
        print(f"Video URL: {video_url}")
        
        if video_url:
            print(f"✅ Video URL found!")
        else:
            print(f"❌ No video URL in metadata")
    
    print("\n" + "="*50)
    
    # Test with RetrievalQA to see what gets returned
    print("🤖 Testing with RetrievalQA...")
    
    llm = ChatOpenAI(temperature=0.2, model_name="gpt-3.5-turbo")
    retriever = vectorstore.as_retriever(search_type="mmr", search_kwargs={"k": 3})
    
    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        return_source_documents=True
    )
    
    result = qa_chain.invoke(test_query)
    
    print(f"Response: {result['result'][:200]}...")
    
    source_docs = result.get('source_documents', [])
    print(f"\n📄 Source documents returned: {len(source_docs)}")
    
    for i, doc in enumerate(source_docs):
        print(f"\n--- Source Doc {i+1} ---")
        teaching = doc.metadata.get('teaching_name')
        video_url = doc.metadata.get('video_url')
        print(f"Teaching: {teaching}")
        print(f"Video URL: {video_url}")

if __name__ == "__main__":
    test_video_retrieval()