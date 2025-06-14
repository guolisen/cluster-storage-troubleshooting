# LLM Providers Guide

This guide explains how to configure and use multiple LLM providers in your cluster storage troubleshooting project.

## Supported Providers

The system now supports three LLM providers:

1. **OpenAI (ChatGPT)** - Various GPT models like GPT-4, GPT-4o, etc.
2. **Google (Gemini)** - Gemini models like gemini-2.5-pro
3. **Ollama** - Local LLM models like Llama, Mistral, etc.

## Configuration

LLM configuration is done in the `config.yaml` file. Here's an example configuration with all three providers:

```yaml
# LLM Configuration
llm:
  # Provider selection: "openai", "google", or "ollama"
  provider: "openai"  # <- Set this to the provider you want to use
  
  # OpenAI Configuration
  openai:
    model: "gpt-4o"
    api_key: "your-openai-api-key"
    api_endpoint: "https://api.openai.com/v1"  # Or alternative endpoint
    temperature: 0
    max_tokens: 8192
  
  # Google Gemini Configuration
  google:
    model: "gemini-2.5-pro"
    api_key: "your-google-api-key"
    temperature: 0
    max_tokens: 8192
  
  # Ollama Configuration (for local LLMs)
  ollama:
    model: "llama3"
    base_url: "http://localhost:11434"  # Default Ollama server URL
    temperature: 0
    max_tokens: 8192
```

### Setting Environment Variables

You can also use environment variables for API keys instead of hardcoding them in the config file:

```bash
# For OpenAI
export OPENAI_API_KEY="your-openai-api-key"
export OPENAI_API_BASE="https://api.openai.com/v1"  # Optional

# For Google
export GOOGLE_API_KEY="your-google-api-key"

# For Ollama
export OLLAMA_BASE_URL="http://localhost:11434"  # Optional, if not default
```

Then in your config.yaml:

```yaml
openai:
  model: "gpt-4o"
  # api_key and api_endpoint will be read from environment variables
  temperature: 0
  max_tokens: 8192
```

## Testing LLM Providers

You can test your LLM configuration using the provided test script:

```bash
# Test all providers (no API calls)
python tests/test_llm_providers.py

# Test a specific provider
python tests/test_llm_providers.py --provider openai

# Test with actual API calls (requires valid API keys)
python tests/test_llm_providers.py --provider google --call
```

## Provider-Specific Notes

### OpenAI (ChatGPT)

- Supports various models including gpt-4, gpt-4o, gpt-3.5-turbo
- Requires an OpenAI API key
- Can use alternative endpoints for services like Azure OpenAI

### Google (Gemini)

- Supports Gemini models like gemini-2.5-pro
- Requires a Google API key
- Different parameter names (e.g., `max_output_tokens` instead of `max_tokens`)

### Ollama

- Runs models locally (no API key needed)
- Must have Ollama server running
- Default URL is http://localhost:11434
- Supports many open-source models (llama3, mistral, etc.)
- Different parameter names (e.g., `num_predict` instead of `max_tokens`)

## Troubleshooting

### API Key Issues

If you're seeing authentication errors:

1. Verify your API keys are correct
2. Check that environment variables are properly set
3. For Ollama, ensure the Ollama server is running

### Model Not Available

- For OpenAI and Google, check that you have access to the specified model
- For Ollama, ensure you've pulled the model (`ollama pull modelname`)

### Connection Issues

- For OpenAI and Google, check your internet connection
- For Ollama, verify the Ollama server is running and accessible at the configured URL

### Backward Compatibility

For backward compatibility, the system will fall back to the legacy configuration format if provider-specific configuration is not found:

```yaml
llm:
  model: "gpt-4"
  api_key: "your-api-key" 
  api_endpoint: "https://api.openai.com/v1"
  temperature: 0
  max_tokens: 8192
```
