import os
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

# Load environment variables from config.env
load_dotenv('config.env')

def get_llm():
    # Get API key from environment variable
    api_key = os.getenv("GOOGLE_API_KEY")
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-preview-05-20")
    
    if not api_key:
        raise ValueError("Google API key not set. Please set GOOGLE_API_KEY in config.env file.")
    
    return ChatGoogleGenerativeAI(
        model=model_name,
        temperature=0,
        google_api_key=api_key,
        # Performance optimizations
        max_retries=2,
        # request_timeout=30,  # REMOVED TO PREVENT TIMEOUT ISSUES
        max_tokens=4000,  # Limit token usage for faster responses
        # Removed cache=True to fix LangChain cache error
        # Caching is handled by our custom enhanced_query_cache module
    )
