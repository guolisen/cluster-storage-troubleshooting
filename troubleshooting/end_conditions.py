"""
End Condition Checker for Kubernetes Volume I/O Error Troubleshooting

This module defines classes for checking graph termination conditions.
It implements the Strategy Pattern for different end condition checks.
"""

import logging
import re
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage

# Configure logging
logger = logging.getLogger('end_conditions')
logger.setLevel(logging.INFO)

class EndConditionChecker(ABC):
    """Abstract base class for end condition checkers."""
    
    @abstractmethod
    def check_conditions(self, state: Dict[str, Any]) -> Dict[str, str]:
        """Check if specific end conditions are met.
        
        Args:
            state: The current state of the graph
            
        Returns:
            Dict with "result" key set to "end" or "continue"
        """
        pass

class LLMBasedEndConditionChecker(EndConditionChecker):
    """End condition checker that uses LLM to determine when to end graph execution."""
    
    def __init__(self, model, phase: str, max_iterations: int = 30):
        """Initialize the LLM-based end condition checker.
        
        Args:
            model: The LLM model to use for checking
            phase: Current phase (phase1 or phase2)
            max_iterations: Maximum number of iterations before forcing end
        """
        self.model = model
        self.phase = phase
        self.max_iterations = max_iterations
    
    def check_conditions(self, state: Dict[str, Any]) -> Dict[str, str]:
        """Check if specific end conditions are met using LLM assistance when available.
        
        Args:
            state: The current state of the graph
            
        Returns:
            Dict with "result" key set to "end" or "continue"
        """
        messages = state.get("messages", [])
        if not messages:
            return {"result": "continue"}
            
        last_message = messages[-1]
        
        # Situation 1: Check if the last message is a tool response
        # Check if we've reached max iterations
        ai_messages = [m for m in messages if getattr(m, "type", "") == "ai"]
        if len(ai_messages) > self.max_iterations:
            logger.info(f"Ending graph: reached max iterations ({self.max_iterations})")
            return {"result": "end"}
            
        # Skip content checks if the last message isn't from the AI
        if getattr(last_message, "type", "") != "ai":
            return {"result": "continue"}
            
        content = getattr(last_message, "content", "")
        if not content:
            return {"result": "continue"}

        # Situation 2: Check if has explicit end markers in the content using LLM
        if self._check_explicit_end_markers(content):
            logger.info("Ending graph: LLM detected explicit end markers")
            return {"result": "end"}
        
        # Situation 3: Check for specific phrases indicating completion using LLM
        if self._check_completion_indicators(content):
            logger.info("Ending graph: LLM detected completion indicators")
            return {"result": "end"}
        
        # Situation 4: Check for convergence (model repeating itself)
        if len(ai_messages) > 3:
            # Compare the last message with the third-to-last message (skipping the tool response in between)
            last_content = content
            third_to_last_content = getattr(ai_messages[-3], "content", "")
            
            # Simple similarity check - if they start with the same paragraph
            if last_content and third_to_last_content:
                # Get first 100 chars of each message
                last_start = last_content[:100] if len(last_content) > 100 else last_content
                third_start = third_to_last_content[:100] if len(third_to_last_content) > 100 else third_to_last_content
                
                if last_start == third_start:
                    logger.info("Ending graph: detected convergence (model repeating itself)")
                    return {"result": "end"}
        
        # Default: continue execution
        return {"result": "continue"}
    
    def _check_explicit_end_markers(self, content: str) -> bool:
        """Use LLM to check if content contains explicit or implicit end markers.
        
        Args:
            content: The content to check for end markers
            
        Returns:
            bool: True if end markers detected, False otherwise
        """
        # Create a focused prompt for the LLM
        system_prompt = """
        You are an AI assistant tasked with determining if a text contains explicit or implicit markers 
        indicating the end of a process or conversation. Your task is to analyze the given text and 
        determine if it contains phrases or markers that suggest completion or termination.
        
        Examples of explicit end markers include:
        - "[END_GRAPH]", "[END]", "End of graph", "GRAPH END"
        - "This concludes the analysis"
        - "Final report"
        - "Investigation complete"
        - "FIX PLAN", "Fix Plan"
        - " Would you like to"
        - A question from AI that indicates the end of the process, such as " Would you like to proceed with planning the disk replacement or further investigate filesystem integrity?"
        - If just a call tools result, then return 'NO'

        Examples of implicit end markers include:
        - A summary followed by recommendations with no further questions
        - A conclusion paragraph that wraps up all findings
        - A complete analysis with all required sections present
        - A question from AI that indicates the end of the process, such as "Is there anything else I can help you with?" or "Do you have any further questions?"
        
        Respond with "YES" if you detect end markers, or "NO" if you don't.
        """
        
        user_prompt = f"""
        Analyze the following text and determine if it contains explicit or implicit end markers:
        
        {content}  # Limit content length to avoid token limits
        
        Does this text contain markers indicating it's the end of the process? Respond with only YES or NO.
        """
        
        try:
            # Create messages for the LLM
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            # Call the LLM
            response = self.model.invoke(messages)
            
            # Check if the response indicates end markers
            response_text = response.content.strip().upper()
            
            # Log the LLM's response
            logger.info(f"LLM end marker detection response: {response_text}")
            
            # Return True if the LLM detected end markers
            return "YES" in response_text
        except Exception as e:
            # Log any errors and fall back to the original behavior
            logger.error(f"Error in LLM end marker detection: {e}")
            
            # Fall back to simple string matching
            return any(marker in content for marker in ["[END_GRAPH]", "[END]", "End of graph", "GRAPH END", "Fix Plan", "FIX PLAN"])
    
    def _check_completion_indicators(self, content: str) -> bool:
        """Use LLM to check if content indicates task completion based on phase requirements.
        
        Args:
            content: The content to check for completion indicators
            
        Returns:
            bool: True if completion indicators detected, False otherwise
        """
        # Define phase-specific required sections
        phase1_sections = [
            "Summary of Findings:",
            "Special Case Detected",
            "Detailed Analysis:",
            "Relationship Analysis:",
            "Investigation Process:",
            "Potential Root Causes:",
            "Root Cause:",
            "Fix Plan:",
            "Summary",
            "Recommendations"
        ]
        
        phase2_sections = [
            "Actions Taken:",
            "Test Results:",
            "Resolution Status:",
            "Remaining Issues:",
            "Recommendations:",
            "Summary of Findings:",
            "Special Case Detected",
            "Detailed Analysis:",
            "Relationship Analysis:",
            "Investigation Process:",
            "Potential Root Causes:",
            "Root Cause:",
            "Fix Plan:",
            "Summary",
            "Recommendations"
        ]
        
        # Select the appropriate sections based on the phase
        required_sections = phase1_sections if self.phase == "phase1" else phase2_sections
        
        # Create a focused prompt for the LLM
        system_prompt = f"""
        You are an AI assistant tasked with determining if a text contains sufficient information 
        to indicate that a troubleshooting process is complete. Your task is to analyze the given text 
        and determine if it contains the required sections and information for a {self.phase} report.
        
        For {self.phase}, the following sections are expected in a complete report:
        {', '.join(required_sections)}
        
        A complete report should have some of these sections and provide comprehensive information 
        in each section. The report should feel complete and not leave major questions unanswered.
        If just a call tools result, then return 'NO'.
        
        Respond with "YES" if you believe the text represents a complete report, or "NO" if it seems incomplete.
        """
        
        user_prompt = f"""
        Analyze the following text and determine if it represents a complete {self.phase} report:
        
        {content}  # Limit content length to avoid token limits
        
        Does this text contain sufficient information to be considered a complete report? Respond with only YES or NO.
        """
        
        try:
            # Create messages for the LLM
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            # Call the LLM
            response = self.model.invoke(messages)
            
            # Check if the response indicates completion
            response_text = response.content.strip().upper()
            
            # Log the LLM's response
            logger.info(f"LLM completion detection response for {self.phase}: {response_text}")
            
            # Return True if the LLM detected completion
            return "YES" in response_text
        except Exception as e:
            # Log any errors and fall back to the original behavior
            logger.error(f"Error in LLM completion detection: {e}")
            
            # Fall back to counting sections
            sections_found = sum(1 for section in required_sections if section in content)
            threshold = 3 if self.phase == "phase1" else 2
            return sections_found >= threshold

class SimpleEndConditionChecker(EndConditionChecker):
    """Simple end condition checker that uses regex patterns to check for end conditions."""
    
    def __init__(self, max_iterations: int = 30):
        """Initialize the simple end condition checker.
        
        Args:
            max_iterations: Maximum number of iterations before forcing end
        """
        self.max_iterations = max_iterations
        # Define patterns that indicate completion
        self.end_markers = [
            r"\[END_GRAPH\]", 
            r"\[END\]", 
            r"End of graph", 
            r"GRAPH END",
            r"This concludes the (analysis|investigation|troubleshooting)",
            r"Fix Plan:",
            r"Root Cause:",
            r"Summary of Findings:"
        ]
    
    def check_conditions(self, state: Dict[str, Any]) -> Dict[str, str]:
        """Check if specific end conditions are met.
        
        Args:
            state: The current state of the graph
            
        Returns:
            Dict with "result" key set to "end" or "continue"
        """
        messages = state.get("messages", [])
        if not messages:
            return {"result": "continue"}
            
        last_message = messages[-1]
        
        # Check if we've reached max iterations
        ai_messages = [m for m in messages if getattr(m, "type", "") == "ai"]
        if len(ai_messages) > self.max_iterations:
            logger.info(f"Ending graph: reached max iterations ({self.max_iterations})")
            return {"result": "end"}
            
        # Skip content checks if the last message isn't from the AI
        if getattr(last_message, "type", "") != "ai":
            return {"result": "continue"}
            
        content = getattr(last_message, "content", "")
        if not content:
            return {"result": "continue"}
            
        # Check for end markers in the content
        for pattern in self.end_markers:
            if re.search(pattern, content, re.IGNORECASE):
                logger.info(f"Ending graph: detected end marker matching pattern {pattern}")
                return {"result": "end"}
                
        # Check for convergence (model repeating itself)
        if len(ai_messages) > 3:
            last_content = content
            third_to_last_content = getattr(ai_messages[-3], "content", "")
            
            if last_content and third_to_last_content:
                # Get first 100 chars of each message
                last_start = last_content[:100] if len(last_content) > 100 else last_content
                third_start = third_to_last_content[:100] if len(third_to_last_content) > 100 else third_to_last_content
                
                if last_start == third_start:
                    logger.info("Ending graph: detected convergence (model repeating itself)")
                    return {"result": "end"}
                    
        # Default: continue execution
        return {"result": "continue"}

class EndConditionFactory:
    """Factory class for creating end condition checkers."""
    
    @staticmethod
    def create_checker(checker_type: str, **kwargs) -> EndConditionChecker:
        """Create an end condition checker of the specified type.
        
        Args:
            checker_type: Type of checker to create ('llm' or 'simple')
            **kwargs: Additional arguments to pass to the checker constructor
            
        Returns:
            An EndConditionChecker instance
        """
        if checker_type.lower() == "llm":
            return LLMBasedEndConditionChecker(**kwargs)
        return SimpleEndConditionChecker(**kwargs)
