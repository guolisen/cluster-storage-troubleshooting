#!/usr/bin/env python3
"""
Utility classes for Kubernetes Volume I/O Error Troubleshooting

This module contains utility classes for:
- Graph execution
- Error handling
- Message list management
- Output formatting
"""

import logging
import json
import re
import time
from typing import Dict, List, Any, Optional, Tuple, Callable
from langgraph.graph import StateGraph


class FallbackPlanGenerator:
    """
    Utility class for generating fallback investigation plans
    
    This class provides methods for generating fallback investigation plans
    when the primary plan generation fails.
    """
    
    @staticmethod
    def generate_basic_fallback_plan(pod_name: str, namespace: str, volume_path: str) -> str:
        """
        Generate a basic fallback investigation plan
        
        Args:
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            
        Returns:
            str: Basic fallback investigation plan
        """
        plan_lines = []
        plan_lines.append("Investigation Plan (Fallback):")
        plan_lines.append(f"Target: Pod {namespace}/{pod_name}, Volume Path: {volume_path}")
        plan_lines.append("Generated Steps: 5 fallback steps (primary plan generation failed)")
        plan_lines.append("")
        
        # Add basic Knowledge Graph exploration steps
        plan_lines.append("Step 1: Get all critical issues | Tool: kg_get_all_issues(severity='critical') | Expected: Critical issues in the system")
        plan_lines.append("Step 2: Analyze issue patterns | Tool: kg_analyze_issues() | Expected: Root cause analysis and patterns")
        plan_lines.append("Step 3: Get system overview | Tool: kg_get_summary() | Expected: Overall system health statistics")
        plan_lines.append("Step 4: Get pod details | Tool: kubectl_describe(resource_type='pod', name='" + pod_name + "', namespace='" + namespace + "') | Expected: Pod details including volume mounts")
        plan_lines.append("Step 5: Get PVC details | Tool: kubectl_get(resource_type='pvc', namespace='" + namespace + "', output_format='yaml') | Expected: PVC details including storage class and volume")
        
        # Add fallback steps
        plan_lines.append("")
        plan_lines.append("Fallback Steps (if main steps fail):")
        plan_lines.append("Step F1: Print Knowledge Graph | Tool: kg_print_graph(include_details=True, include_issues=True) | Expected: Complete system visualization | Trigger: plan_generation_failed")
        
        return "\n".join(plan_lines)
    
    @staticmethod
    def generate_comprehensive_fallback_plan(pod_name: str, namespace: str, volume_path: str, 
                                           error_context: str = "") -> str:
        """
        Generate a comprehensive fallback investigation plan with error context
        
        Args:
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            error_context: Error context from the primary plan generation
            
        Returns:
            str: Comprehensive fallback investigation plan
        """
        plan_lines = []
        plan_lines.append("Investigation Plan (Comprehensive Fallback):")
        plan_lines.append(f"Target: Pod {namespace}/{pod_name}, Volume Path: {volume_path}")
        plan_lines.append("Generated Steps: 10 fallback steps (primary plan generation failed)")
        if error_context:
            plan_lines.append(f"Error Context: {error_context}")
        plan_lines.append("")
        
        # Add comprehensive Knowledge Graph exploration steps
        plan_lines.append("Step 1: Get all critical issues | Tool: kg_get_all_issues(severity='critical') | Expected: Critical issues in the system")
        plan_lines.append("Step 2: Analyze issue patterns | Tool: kg_analyze_issues() | Expected: Root cause analysis and patterns")
        plan_lines.append("Step 3: Get system overview | Tool: kg_get_summary() | Expected: Overall system health statistics")
        
        # Add pod and volume investigation steps
        plan_lines.append("Step 4: Get pod details | Tool: kubectl_describe(resource_type='pod', name='" + pod_name + "', namespace='" + namespace + "') | Expected: Pod details including volume mounts")
        plan_lines.append("Step 5: Get pod logs | Tool: kubectl_logs(pod_name='" + pod_name + "', namespace='" + namespace + "') | Expected: Pod logs with potential error messages")
        plan_lines.append("Step 6: Get PVC details | Tool: kubectl_get(resource_type='pvc', namespace='" + namespace + "', output_format='yaml') | Expected: PVC details including storage class and volume")
        plan_lines.append("Step 7: Get PV details | Tool: kubectl_get(resource_type='pv', output_format='yaml') | Expected: PV details including storage class and volume source")
        
        # Add CSI driver investigation steps
        plan_lines.append("Step 8: Get storage class details | Tool: kubectl_get_storageclass() | Expected: Storage class details including provisioner")
        plan_lines.append("Step 9: Get CSI driver details | Tool: kubectl_get_csidrivers() | Expected: CSI driver details")
        plan_lines.append("Step 10: Get node details | Tool: kubectl_describe(resource_type='node') | Expected: Node details including disk pressure status")
        
        # Add fallback steps
        plan_lines.append("")
        plan_lines.append("Fallback Steps (if main steps fail):")
        plan_lines.append("Step F1: Print Knowledge Graph | Tool: kg_print_graph(include_details=True, include_issues=True) | Expected: Complete system visualization | Trigger: plan_generation_failed")
        plan_lines.append("Step F2: Check system logs | Tool: journalctl_command(filter_pattern='error|fail|volume|mount') | Expected: System logs with potential error messages | Trigger: kg_tools_failed")
        
        return "\n".join(plan_lines)


class HistoricalExperienceFormatter:
    """
    Utility class for formatting historical experience data
    
    This class provides methods for formatting historical experience data
    for use in troubleshooting.
    """
    
    @staticmethod
    def format_historical_experiences(collected_info: Dict[str, Any]) -> str:
        """
        Format historical experience data from collected information
        
        Args:
            collected_info: Pre-collected diagnostic information
            
        Returns:
            str: Formatted historical experience data
        """
        if 'historical_experience' not in collected_info:
            return "No historical experience data available."
        
        historical_experience = collected_info['historical_experience']
        
        if not historical_experience:
            return "No historical experience data available."
        
        formatted_output = "Historical Experience Data:\n\n"
        
        # Format each historical experience entry
        for i, experience in enumerate(historical_experience, 1):
            formatted_output += f"Experience #{i}:\n"
            
            # Add issue description
            if 'issue_description' in experience:
                formatted_output += f"Issue: {experience['issue_description']}\n"
            
            # Add symptoms
            if 'symptoms' in experience:
                formatted_output += "Symptoms:\n"
                for symptom in experience['symptoms']:
                    formatted_output += f"- {symptom}\n"
            
            # Add root cause
            if 'root_cause' in experience:
                formatted_output += f"Root Cause: {experience['root_cause']}\n"
            
            # Add resolution
            if 'resolution' in experience:
                formatted_output += f"Resolution: {experience['resolution']}\n"
            
            # Add similarity score if available
            if 'similarity_score' in experience:
                formatted_output += f"Similarity Score: {experience['similarity_score']:.2f}\n"
            
            formatted_output += "\n"
        
        return formatted_output


class GraphExecutor:
    """
    Utility class for executing LangGraph operations
    
    This class provides methods for executing LangGraph operations
    with proper error handling and logging.
    """
    
    @staticmethod
    async def execute_graph(graph: StateGraph, initial_state: Dict[str, Any], 
                          timeout_seconds: int = 600) -> Dict[str, Any]:
        """
        Execute a LangGraph with timeout
        
        Args:
            graph: LangGraph StateGraph to execute
            initial_state: Initial state for the graph
            timeout_seconds: Timeout in seconds
            
        Returns:
            Dict[str, Any]: Final state of the graph
            
        Raises:
            TimeoutError: If execution exceeds timeout
        """
        start_time = time.time()
        
        # Create initial state
        state = {"messages": []}
        if initial_state:
            state.update(initial_state)
        
        # Execute graph with timeout
        try:
            logging.info(f"Starting graph execution with timeout {timeout_seconds}s")
            
            # Create async iterator
            stream = graph.astream(state)
            
            # Track the latest state
            latest_state = None
            
            # Process stream with timeout check
            async for chunk in stream:
                latest_state = chunk
                
                # Check for timeout
                if time.time() - start_time > timeout_seconds:
                    logging.warning(f"Graph execution timed out after {timeout_seconds}s")
                    raise TimeoutError(f"Graph execution timed out after {timeout_seconds}s")
            
            # Return the final state
            if latest_state is not None:
                logging.info(f"Graph execution completed in {time.time() - start_time:.2f}s")
                return latest_state
            else:
                logging.error("Graph execution completed but no state was returned")
                return state
                
        except TimeoutError:
            # Re-raise timeout errors
            raise
        except Exception as e:
            # Log and re-raise other errors
            logging.error(f"Error during graph execution: {str(e)}")
            raise
    
    @staticmethod
    def extract_final_response(state: Dict[str, Any]) -> str:
        """
        Extract the final response from the graph state
        
        Args:
            state: Final state of the graph
            
        Returns:
            str: Final response text
        """
        try:
            # Get the last message from the state
            if "messages" in state and state["messages"]:
                last_message = state["messages"][-1]
                
                # Extract content from the message
                if hasattr(last_message, "content"):
                    return last_message.content
                elif isinstance(last_message, dict) and "content" in last_message:
                    return last_message["content"]
                else:
                    return str(last_message)
            else:
                return "No response generated"
        except Exception as e:
            logging.error(f"Error extracting final response: {str(e)}")
            return "Error extracting response"
    
    @staticmethod
    def should_skip_phase2(final_response: str) -> bool:
        """
        Determine if Phase 2 should be skipped based on the final response
        
        Args:
            final_response: Final response from Phase 1
            
        Returns:
            bool: True if Phase 2 should be skipped, False otherwise
        """
        # Check for explicit skip indicators
        skip_indicators = [
            "no issues detected",
            "no remediation needed",
            "manual intervention required",
            "skip phase 2",
            "skip remediation",
            "no action needed",
            "no problems found",
            "system is healthy",
            "no errors detected"
        ]
        
        # Check if any skip indicators are present in the final response
        for indicator in skip_indicators:
            if indicator.lower() in final_response.lower():
                logging.info(f"Skipping Phase 2 due to indicator: '{indicator}'")
                return True
        
        # Check if there's no fix plan section
        if "fix plan" not in final_response.lower():
            logging.info("Skipping Phase 2 due to missing Fix Plan section")
            return True
            
        # Check if the fix plan is empty or contains only "N/A" or similar
        fix_plan_pattern = r"fix plan:?\s*(.*?)(?:\n\s*\n|\Z)"
        fix_plan_match = re.search(fix_plan_pattern, final_response, re.IGNORECASE | re.DOTALL)
        
        if fix_plan_match:
            fix_plan_content = fix_plan_match.group(1).strip()
            if not fix_plan_content or fix_plan_content.lower() in ["n/a", "none", "no action needed"]:
                logging.info("Skipping Phase 2 due to empty or N/A Fix Plan")
                return True
        
        # Default to not skipping
        return False


class ErrorHandler:
    """
    Utility class for handling errors consistently
    
    This class provides methods for handling errors in a consistent way
    across the troubleshooting process.
    """
    
    @staticmethod
    def format_error(error: Exception, context: str = "") -> str:
        """
        Format an error message with context
        
        Args:
            error: Exception to format
            context: Additional context for the error
            
        Returns:
            str: Formatted error message
        """
        error_type = type(error).__name__
        error_message = str(error)
        
        if context:
            return f"{context}: {error_type} - {error_message}"
        else:
            return f"{error_type} - {error_message}"
    
    @staticmethod
    def handle_phase_error(phase_name: str, error: Exception, 
                         results: Dict[str, Any], start_time: float) -> None:
        """
        Handle an error in a phase
        
        Args:
            phase_name: Name of the phase where the error occurred
            error: Exception that occurred
            results: Results dictionary to update
            start_time: Start time of the phase
        """
        error_msg = ErrorHandler.format_error(error, f"Error in {phase_name}")
        logging.error(error_msg)
        
        # Update results with error information
        results["phases"][phase_name] = {
            "status": "failed",
            "error": error_msg,
            "duration": time.time() - start_time
        }
    
    @staticmethod
    def create_error_response(error: Exception, context: str = "") -> str:
        """
        Create a user-friendly error response
        
        Args:
            error: Exception to format
            context: Additional context for the error
            
        Returns:
            str: User-friendly error response
        """
        error_msg = ErrorHandler.format_error(error, context)
        
        return f"""
Error encountered during troubleshooting:
{error_msg}

This error prevented the troubleshooting process from completing successfully.
Please check the logs for more details and try again.

Possible solutions:
1. Check Kubernetes connectivity and permissions
2. Verify the pod and namespace exist
3. Ensure the volume path is correct
4. Check for any network or system issues
"""


class MessageListManager:
    """
    Utility class for managing message lists in chat mode
    
    This class provides methods for managing message lists used in chat mode
    for interactive troubleshooting.
    """
    
    @staticmethod
    def create_initial_message_list() -> List[Dict[str, str]]:
        """
        Create an initial message list for chat mode
        
        Returns:
            List[Dict[str, str]]: Initial message list
        """
        return []
    
    @staticmethod
    def add_to_message_list(message_list: List[Dict[str, str]], content: str, 
                          role: str = "assistant") -> List[Dict[str, str]]:
        """
        Add a message to the message list
        
        Args:
            message_list: Existing message list
            content: Content of the message
            role: Role of the message (assistant or user)
            
        Returns:
            List[Dict[str, str]]: Updated message list
        """
        if message_list is None:
            message_list = MessageListManager.create_initial_message_list()
        
        message_list.append({
            "role": role,
            "content": content
        })
        
        return message_list
    
    @staticmethod
    def extract_last_assistant_message(message_list: List[Dict[str, str]]) -> Optional[str]:
        """
        Extract the last assistant message from the message list
        
        Args:
            message_list: Message list to extract from
            
        Returns:
            Optional[str]: Last assistant message content, or None if not found
        """
        if not message_list:
            return None
        
        # Iterate backwards through the message list
        for message in reversed(message_list):
            if message.get("role") == "assistant":
                return message.get("content")
        
        return None
    
    @staticmethod
    def extract_last_user_message(message_list: List[Dict[str, str]]) -> Optional[str]:
        """
        Extract the last user message from the message list
        
        Args:
            message_list: Message list to extract from
            
        Returns:
            Optional[str]: Last user message content, or None if not found
        """
        if not message_list:
            return None
        
        # Iterate backwards through the message list
        for message in reversed(message_list):
            if message.get("role") == "user":
                return message.get("content")
        
        return None
    
    @staticmethod
    def truncate_message_list(message_list: List[Dict[str, str]], 
                            max_messages: int = 10) -> List[Dict[str, str]]:
        """
        Truncate a message list to a maximum number of messages
        
        Args:
            message_list: Message list to truncate
            max_messages: Maximum number of messages to keep
            
        Returns:
            List[Dict[str, str]]: Truncated message list
        """
        if not message_list or len(message_list) <= max_messages:
            return message_list
        
        # Keep the first message (system message) and the last max_messages-1 messages
        return [message_list[0]] + message_list[-(max_messages-1):]


class OutputFormatter:
    """
    Utility class for formatting output consistently
    
    This class provides methods for formatting output in a consistent way
    across the troubleshooting process.
    """
    
    @staticmethod
    def truncate_long_text(text: str, max_length: int = 1000) -> str:
        """
        Truncate long text to a maximum length
        
        Args:
            text: Text to truncate
            max_length: Maximum length of the truncated text
            
        Returns:
            str: Truncated text
        """
        if not text or len(text) <= max_length:
            return text
        
        # Truncate to max_length and add ellipsis
        return text[:max_length] + "... [truncated]"
    
    @staticmethod
    def format_json_for_display(data: Any) -> str:
        """
        Format JSON data for display
        
        Args:
            data: JSON data to format
            
        Returns:
            str: Formatted JSON string
        """
        try:
            if isinstance(data, str):
                # Try to parse as JSON if it's a string
                data = json.loads(data)
            
            # Format with indentation
            return json.dumps(data, indent=2)
        except:
            # Return as-is if not valid JSON
            return str(data)
    
    @staticmethod
    def format_duration(seconds: float) -> str:
        """
        Format a duration in seconds to a human-readable string
        
        Args:
            seconds: Duration in seconds
            
        Returns:
            str: Formatted duration string
        """
        if seconds < 60:
            return f"{seconds:.2f} seconds"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.2f} minutes"
        else:
            hours = seconds / 3600
            return f"{hours:.2f} hours"
    
    @staticmethod
    def extract_section_from_text(text: str, section_name: str) -> Optional[str]:
        """
        Extract a section from text by section name
        
        Args:
            text: Text to extract from
            section_name: Name of the section to extract
            
        Returns:
            Optional[str]: Extracted section, or None if not found
        """
        # Create a pattern to match the section
        # This handles various formats like "Section Name:", "# Section Name", etc.
        patterns = [
            rf"{section_name}:?\s*(.*?)(?:\n\s*\n|\n\s*[#\d]|\Z)",  # Section Name: content
            rf"#{1,6}\s*{section_name}:?\s*(.*?)(?:\n\s*\n|\n\s*[#\d]|\Z)",  # # Section Name: content
            rf"\d+\.\s*{section_name}:?\s*(.*?)(?:\n\s*\n|\n\s*[#\d]|\Z)",  # 1. Section Name: content
        ]
        
        # Try each pattern
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()
        
        return None
