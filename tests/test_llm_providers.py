#!/usr/bin/env python3
"""
Test script for verifying multiple LLM providers

This script tests the LLMFactory with different providers (OpenAI, Google, Ollama)
to ensure that configuration switching works properly.
"""

import os
import sys
import logging
import argparse
from typing import Dict, Any

# Add parent directory to path to import project modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from phases.llm_factory import LLMFactory
from langchain_core.messages import SystemMessage, HumanMessage

# Setup logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_test_config(provider: str) -> Dict[str, Any]:
    """
    Create a test configuration for the specified provider
    
    Args:
        provider: Provider name ('openai', 'google', or 'ollama')
        
    Returns:
        Dict[str, Any]: Test configuration
    """
    # Base configuration
    config = {
        'llm': {
            'provider': provider,
            # Legacy config for backward compatibility testing
            'model': 'gpt-4',
            'api_key': 'test-key',
            'api_endpoint': 'https://api.example.com/v1',
            'temperature': 0.1,
            'max_tokens': 1000,
            
            # Provider-specific configurations
            'openai': {
                'model': 'gpt-4o',
                'api_key': os.environ.get('OPENAI_API_KEY', 'sk-openai-test-key'),
                'api_endpoint': os.environ.get('OPENAI_API_BASE', 'https://api.openai.com/v1'),
                'temperature': 0.1,
                'max_tokens': 1000
            },
            'google': {
                'model': 'gemini-2.5-pro',
                'api_key': os.environ.get('GOOGLE_API_KEY', 'google-test-key'),
                'temperature': 0.1,
                'max_tokens': 1000
            },
            'ollama': {
                'model': 'llama3',
                'base_url': os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434'),
                'temperature': 0.1,
                'max_tokens': 1000
            }
        }
    }
    
    return config

def test_llm_provider(provider: str, perform_call: bool = False) -> None:
    """
    Test a specific LLM provider
    
    Args:
        provider: Provider name ('openai', 'google', or 'ollama')
        perform_call: Whether to actually perform an API call
    """
    logger.info(f"Testing {provider.upper()} LLM provider...")
    
    # Get test configuration
    config = get_test_config(provider)
    
    try:
        # Create LLM using factory
        factory = LLMFactory(config)
        llm = factory.create_llm()
        
        # Check if LLM was created
        if llm is None:
            logger.error(f"Failed to create {provider} LLM")
            return
            
        logger.info(f"Successfully created {provider} LLM instance: {llm.__class__.__name__}")
        
        # Perform a test call if requested
        if perform_call:
            logger.info(f"Performing test call to {provider} API...")
            
            # Prepare test messages
            messages = [
                SystemMessage(content="You are a helpful assistant."),
                HumanMessage(content="Say 'Hello from LLM Provider test!'")
            ]
            
            # Perform the call
            response = llm.invoke(messages)
            
            # Log the response
            logger.info(f"Response: {response.content}")
            
            logger.info(f"Successfully tested {provider} API call")
    
    except Exception as e:
        logger.error(f"Error testing {provider} LLM: {str(e)}")

def main():
    """Main function to run the test script"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Test LLM providers')
    parser.add_argument('--provider', type=str, choices=['all', 'openai', 'google', 'ollama'],
                      default='all', help='LLM provider to test')
    parser.add_argument('--call', action='store_true', 
                      help='Perform actual API calls (requires valid API keys)')
    args = parser.parse_args()
    
    # Test the specified provider(s)
    if args.provider == 'all':
        test_llm_provider('openai', args.call)
        test_llm_provider('google', args.call)
        test_llm_provider('ollama', args.call)
    else:
        test_llm_provider(args.provider, args.call)

if __name__ == "__main__":
    main()
