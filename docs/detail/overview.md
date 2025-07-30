# Cluster Storage Troubleshooting System Overview

## Introduction

The Cluster Storage Troubleshooting System is an intelligent, automated system for diagnosing and resolving Kubernetes cluster storage issues using Large Language Models (LLMs). It focuses on troubleshooting volume I/O errors in Kubernetes pods backed by local storage (HDD/SSD/NVMe disks) managed by the CSI Baremetal driver.

## Key Features

- **Automated Investigation**: Automatically investigates volume read/write errors in Kubernetes clusters
- **Knowledge Graph Integration**: Builds and utilizes a knowledge graph for context-aware troubleshooting
- **Multi-Provider LLM Support**: Supports multiple LLM providers (OpenAI, Google Gemini, Ollama)
- **Phase-Based Approach**: Structured troubleshooting in phases (planning, investigation, remediation)
- **Historical Experience**: Learns from past troubleshooting experiences
- **Interactive Mode**: Supports both automated and interactive troubleshooting

## System Goals

1. **Automated Troubleshooting**: Reduce the need for manual intervention in diagnosing and resolving storage issues
2. **Comprehensive Analysis**: Utilize knowledge graphs to organize diagnostic data for better root cause analysis
3. **Flexible Deployment**: Support various LLM providers and configuration options
4. **Safe Operation**: Ensure safety through command validation and interactive approval modes
5. **Learning Capability**: Improve over time by incorporating historical troubleshooting experiences

## High-Level Architecture

The system is structured around a 3-phase troubleshooting approach:

1. **Phase 0: Information Collection**
   - Pre-collects all diagnostic data upfront
   - Builds a knowledge graph of system entities and relationships

2. **Plan Phase: Investigation Planning**
   - Generates a structured investigation plan based on collected data
   - Utilizes historical experience and knowledge graph insights

3. **Phase 1: ReAct Investigation**
   - Executes the investigation plan using LangGraph ReAct agent
   - Performs comprehensive root cause analysis
   - Generates a fix plan

4. **Phase 2: Remediation**
   - Implements the fix plan to resolve identified issues
   - Validates fixes and provides a detailed report

The system integrates with Kubernetes through the Kubernetes API and can execute commands on worker nodes via SSH. It uses a knowledge graph to represent system entities (Pods, PVCs, PVs, Drives, etc.) and their relationships, enabling sophisticated analysis and troubleshooting.

## Target Use Cases

- Diagnosing volume I/O errors in Kubernetes pods
- Troubleshooting CSI Baremetal driver issues
- Identifying and resolving storage-related configuration problems
- Detecting and addressing hardware disk failures
- Resolving permission and access issues for volumes
