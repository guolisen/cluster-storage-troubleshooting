#!/usr/bin/env python3
"""
LLM Factory for Multiple Provider Support

This module provides a factory for initializing different LLM providers
(OpenAI, Google Gemini, Ollama) based on configuration.
"""

import logging
from typing import Dict, Any, Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

class LLMFactory:
    """
    Factory class for creating LLM instances based on provider configuration
    
    Supports multiple LLM providers:
    - OpenAI (ChatGPT)
    - Google (Gemini)
    - Ollama (Local models)
    """
    
    def __init__(self, config_data: Dict[str, Any] = None):
        """
        Initialize the LLM Factory
        
        Args:
            config_data: Configuration data for the LLM
        """
        self.config_data = config_data or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def create_llm(self, streaming=False, phase_name=None) -> Optional[BaseChatModel]:
        """
        Create an LLM instance based on the provider specified in config
        
        Args:
            streaming: Whether to enable streaming for the LLM
            phase_name: Name of the current phase for streaming callbacks
            
        Returns:
            BaseChatModel: Initialized LLM instance or None if initialization fails
        """
        try:
            # Get LLM configuration
            llm_config = self.config_data.get('llm', {})
            provider = llm_config.get('provider', 'openai').lower()
            
            # Check if streaming is enabled in config
            if streaming:
                # Check if streaming is enabled for this specific phase
                streaming_phases = llm_config.get('streaming_phases', {})
                if phase_name and not streaming_phases.get(phase_name, True):
                    # Streaming is disabled for this phase
                    streaming = False
            
            # Create LLM based on provider
            if provider == 'openai':
                return self._create_openai_llm(llm_config, streaming, phase_name)
            elif provider == 'google':
                return self._create_google_llm(llm_config, streaming, phase_name)
            elif provider == 'ollama':
                return self._create_ollama_llm(llm_config, streaming, phase_name)
            else:
                self.logger.error(f"Unsupported LLM provider: {provider}")
                return None
        except Exception as e:
            self.logger.error(f"Error creating LLM: {str(e)}")
            return None
    
    def _create_openai_llm(self, llm_config: Dict[str, Any], streaming=False, phase_name=None) -> Optional[BaseChatModel]:
        """
        Create an OpenAI LLM instance
        
        Args:
            llm_config: LLM configuration data
            streaming: Whether to enable streaming for the LLM
            phase_name: Name of the current phase for streaming callbacks
            
        Returns:
            BaseChatModel: Initialized OpenAI LLM instance or None if initialization fails
        """
        try:
            from langchain_openai import ChatOpenAI
            
            # Get OpenAI-specific configuration
            openai_config = llm_config.get('openai', {})
            if not openai_config:
                # If no specific OpenAI config is provided, use the top-level config
                # This maintains backward compatibility with the old config format
                if streaming:
                    from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
                    from .streaming_callbacks import StreamingCallbackHandler
                    
                    # Create streaming callback handler
                    callbacks = [StreamingCallbackHandler(phase_name)] if phase_name else [StreamingStdOutCallbackHandler()]
                    
                    return ChatOpenAI(
                        model=llm_config.get('model', 'gpt-4'),
                        api_key=llm_config.get('api_key', None),
                        base_url=llm_config.get('api_endpoint', None),
                        temperature=llm_config.get('temperature', 0.1),
                        max_tokens=llm_config.get('max_tokens', 4000),
                        streaming=True,
                        callbacks=callbacks
                    )
                else:
                    return ChatOpenAI(
                        model=llm_config.get('model', 'gpt-4'),
                        api_key=llm_config.get('api_key', None),
                        base_url=llm_config.get('api_endpoint', None),
                        temperature=llm_config.get('temperature', 0.1),
                        max_tokens=llm_config.get('max_tokens', 4000)
                    )
            
            # Use OpenAI-specific configuration
            if streaming:
                from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
                from .streaming_callbacks import StreamingCallbackHandler
                
                # Create streaming callback handler
                callbacks = [StreamingCallbackHandler(phase_name)] if phase_name else [StreamingStdOutCallbackHandler()]
                
                return ChatOpenAI(
                    model=openai_config.get('model', 'gpt-4'),
                    api_key=openai_config.get('api_key', None),
                    base_url=openai_config.get('api_endpoint', None),
                    temperature=openai_config.get('temperature', 0.1),
                    max_tokens=openai_config.get('max_tokens', 4000),
                    streaming=True,
                    callbacks=callbacks
                )
            else:
                return ChatOpenAI(
                    model=openai_config.get('model', 'gpt-4'),
                    api_key=openai_config.get('api_key', None),
                    base_url=openai_config.get('api_endpoint', None),
                    temperature=openai_config.get('temperature', 0.1),
                    max_tokens=openai_config.get('max_tokens', 4000)
                )
            
        except Exception as e:
            self.logger.error(f"Error creating OpenAI LLM: {str(e)}")
            return None
    
    def _create_google_llm(self, llm_config: Dict[str, Any], streaming=False, phase_name=None) -> Optional[BaseChatModel]:
        """
        Create a Google Gemini LLM instance
        
        Args:
            llm_config: LLM configuration data
            streaming: Whether to enable streaming for the LLM
            phase_name: Name of the current phase for streaming callbacks
            
        Returns:
            BaseChatModel: Initialized Google LLM instance or None if initialization fails
        """
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            
            # Get Google-specific configuration
            google_config = llm_config.get('google', {})
            
            # Use Google-specific configuration
            if streaming:
                from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
                from .streaming_callbacks import StreamingCallbackHandler
                
                # Create streaming callback handler
                callbacks = [StreamingCallbackHandler(phase_name)] if phase_name else [StreamingStdOutCallbackHandler()]
                
                return ChatGoogleGenerativeAI(
                    model=google_config.get('model', 'gemini-2.5-pro'),
                    google_api_key=google_config.get('api_key', None),
                    temperature=google_config.get('temperature', 0.1),
                    max_output_tokens=google_config.get('max_tokens', 4000),
                    streaming=True,
                    callbacks=callbacks
                )
            else:
                return ChatGoogleGenerativeAI(
                    model=google_config.get('model', 'gemini-2.5-pro'),
                    google_api_key=google_config.get('api_key', None),
                    temperature=google_config.get('temperature', 0.1),
                    max_output_tokens=google_config.get('max_tokens', 4000)
                )
            
        except Exception as e:
            self.logger.error(f"Error creating Google LLM: {str(e)}")
            return None
    
    def _create_ollama_llm(self, llm_config: Dict[str, Any], streaming=False, phase_name=None) -> Optional[BaseChatModel]:
        """
        Create an Ollama LLM instance
        
        Args:
            llm_config: LLM configuration data
            streaming: Whether to enable streaming for the LLM
            phase_name: Name of the current phase for streaming callbacks
            
        Returns:
            BaseChatModel: Initialized Ollama LLM instance or None if initialization fails
        """
        try:
            from langchain_ollama import ChatOllama
            
            # Get Ollama-specific configuration
            ollama_config = llm_config.get('ollama', {})
            
            # Use Ollama-specific configuration
            if streaming:
                from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
                from .streaming_callbacks import StreamingCallbackHandler
                
                # Create streaming callback handler
                callbacks = [StreamingCallbackHandler(phase_name)] if phase_name else [StreamingStdOutCallbackHandler()]
                
                return ChatOllama(
                    model=ollama_config.get('model', 'llama3'),
                    base_url=ollama_config.get('base_url', 'http://localhost:11434'),
                    temperature=ollama_config.get('temperature', 0.1),
                    num_predict=ollama_config.get('max_tokens', 4000),
                    streaming=True,
                    callbacks=callbacks
                )
            else:
                return ChatOllama(
                    model=ollama_config.get('model', 'llama3'),
                    base_url=ollama_config.get('base_url', 'http://localhost:11434'),
                    temperature=ollama_config.get('temperature', 0.1),
                    num_predict=ollama_config.get('max_tokens', 4000)
                )
            
        except Exception as e:
            self.logger.error(f"Error creating Ollama LLM: {str(e)}")
            return None
    
    def test_llm_connection(self, streaming=False) -> bool:
        """
        Test the LLM connection by sending a simple message
        
        Args:
            streaming: Whether to enable streaming for the test
            
        Returns:
            bool: True if the connection is successful, False otherwise
        """
        llm = self.create_llm(streaming=streaming)
        if not llm:
            return False
            
        try:
            # Simple test message
            messages = [
                SystemMessage(content="You are a helpful assistant."),
                HumanMessage(content="Hello, are you working?")
            ]
            
            # Test the LLM
            response = llm.invoke(messages)
            
            # If we get here, the connection is working
            return True
            
        except Exception as e:
            self.logger.error(f"Error testing LLM connection: {str(e)}")
            return False
