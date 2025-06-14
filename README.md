# Cluster Storage Troubleshooting

An intelligent troubleshooting system for Kubernetes cluster storage issues using LLMs.

## Features

- **Automated Investigation**: Automatically investigates volume read/write errors in Kubernetes clusters
- **Knowledge Graph**: Builds and utilizes a knowledge graph for context-aware troubleshooting
- **Multi-Provider LLM Support**: Supports multiple LLM providers (OpenAI, Google Gemini, Ollama)
- **Phase-Based Approach**: Structured troubleshooting in phases (planning, investigation, remediation)
- **Historical Experience**: Learns from past troubleshooting experiences
- **Interactive Mode**: Supports both automated and interactive troubleshooting

## Getting Started

### Prerequisites

- Python 3.10+
- Kubernetes cluster access
- LLM API access (OpenAI, Google Gemini, or local Ollama setup)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/cluster-storage-troubleshooting.git
   cd cluster-storage-troubleshooting
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure your LLM provider in `config.yaml`:
   ```yaml
   llm:
     provider: "openai"  # Options: "openai", "google", "ollama"
     # Provider-specific configurations...
   ```

### Usage

Run the troubleshooter:

```bash
python -m troubleshooting.troubleshoot --pod mypod --namespace default --volume-path /data
```

## LLM Provider Support

This project now supports multiple LLM providers:

- **OpenAI (ChatGPT)** - Various GPT models
- **Google (Gemini)** - Gemini models
- **Ollama** - Local open-source models

For detailed configuration and usage instructions, see [LLM Providers Guide](docs/LLM_PROVIDERS_GUIDE.md).

## Documentation

- [LLM Providers Guide](docs/LLM_PROVIDERS_GUIDE.md)
- [Project Structure](docs/PROJECT_STRUCTURE.md)
- [Design Requirements](docs/design_requirement.md)

## Testing

Run the tests:

```bash
# Run all tests
./run_test.sh

# Test LLM providers
python tests/test_llm_providers.py
```

## License

This project is licensed under the terms of the LICENSE file included in the repository.
