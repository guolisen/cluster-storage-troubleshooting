#!/usr/bin/env python3
"""
Static Plan Step Reader for Investigation Planning

This module reads static plan steps from a JSON file and integrates them
into the investigation plan.
"""

import logging
import json
import os
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

class StaticPlanStepReader:
    """
    Reads static plan steps from a JSON file and integrates them into the investigation plan
    """
    
    def __init__(self, config_data: Dict[str, Any] = None):
        """
        Initialize the Static Plan Step Reader
        
        Args:
            config_data: Configuration data for the reader
        """
        self.config_data = config_data or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.static_plan_step_path = self.config_data.get('plan_phase', {}).get(
            'static_plan_step_path', 'static_plan_step.json'
        )
    
    def read_static_steps(self) -> List[Dict[str, Any]]:
        """
        Read static plan steps from the configured JSON file
        
        Returns:
            List[Dict[str, Any]]: List of static plan steps
        """
        try:
            # Check if file exists
            if not os.path.exists(self.static_plan_step_path):
                self.logger.error(f"Static plan step file not found: {self.static_plan_step_path}")
                return []
            
            # Read and parse JSON file
            with open(self.static_plan_step_path, 'r') as f:
                static_steps = json.load(f)
            
            # Validate static steps
            if not isinstance(static_steps, list):
                self.logger.error(f"Invalid static plan step file format: {self.static_plan_step_path}")
                return []
            
            # Validate each step
            valid_steps = []
            for i, step in enumerate(static_steps):
                if not isinstance(step, dict):
                    self.logger.error(f"Invalid step format at index {i}: {step}")
                    continue
                
                if 'description' not in step or 'tool' not in step or 'expected' not in step:
                    self.logger.error(f"Missing required fields in step at index {i}: {step}")
                    continue
                
                valid_steps.append(step)
            
            self.logger.info(f"Successfully read {len(valid_steps)} static plan steps")
            return valid_steps
            
        except Exception as e:
            self.logger.error(f"Error reading static plan steps: {str(e)}")
            return []
    
    def add_static_steps(self, preliminary_steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Add static plan steps to the preliminary steps
        
        Args:
            preliminary_steps: Preliminary investigation steps from rule-based generator
            
        Returns:
            List[Dict[str, Any]]: Combined list of preliminary and static steps
        """
        static_steps = self.read_static_steps()
        
        if not static_steps:
            self.logger.warning("No static plan steps found, returning only preliminary steps")
            return preliminary_steps
        
        # Add step numbers to static steps
        step_number = len(preliminary_steps) + 1
        for step in static_steps:
            step['step'] = step_number
            step['source'] = 'static'  # Mark the source for later reference
            step_number += 1
        
        # Combine preliminary and static steps
        combined_steps = preliminary_steps + static_steps
        self.logger.info(f"Combined {len(preliminary_steps)} preliminary steps with {len(static_steps)} static steps")
        
        return combined_steps
