#!/usr/bin/env python3
"""
Tool Registry Builder for Investigation Planning

This module contains utilities for preparing the tool registry
for consumption by the Investigation Planner and LLM.
"""

import logging
import inspect
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class ToolRegistryBuilder:
    """
    Prepares tool registry for Investigation Planning
    
    Extracts tool information including names, descriptions, and parameters
    to provide context for investigation planning.
    """
    
    def __init__(self):
        """
        Initialize the Tool Registry Builder
        """
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def prepare_tool_registry(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Prepare tool registry for LLM consumption
        
        Returns:
            Dict[str, List[Dict[str, Any]]]: Structured tool registry
        """
        try:
            from tools.registry import get_phase1_tools
            
            # Get tools with error handling
            try:
                tools = get_phase1_tools()
            except Exception as e:
                self.logger.error(f"Error getting Phase 1 tools: {str(e)}")
                tools = []
                
            formatted_tools = []
            
            for tool in tools:
                try:
                    # Initialize variables
                    tool_name = None
                    tool_description = None
                    tool_parameters = []
                    
                    # Handle both function tools and StructuredTool objects
                    if hasattr(tool, 'name'):
                        # StructuredTool object
                        tool_name = tool.name
                        tool_description = tool.description if hasattr(tool, 'description') else "No description available"
                        
                        # Get parameters from args_schema if available
                        if hasattr(tool, 'args_schema') and tool.args_schema:
                            schema_fields = tool.args_schema.__fields__ if hasattr(tool.args_schema, '__fields__') else {}
                            for field_name, field in schema_fields.items():
                                required = field.required if hasattr(field, 'required') else True
                                field_type = str(field.type_) if hasattr(field, 'type_') else "unknown"
                                default_value = field.default if hasattr(field, 'default') and field.default is not inspect.Parameter.empty else None
                                
                                tool_parameters.append({
                                    "name": field_name,
                                    "type": field_type,
                                    "required": required,
                                    "default": default_value
                                })
                        # If no args_schema, try to get parameters from the function
                        elif hasattr(tool, 'func') and callable(tool.func):
                            signature = inspect.signature(tool.func)
                            for param_name, param in signature.parameters.items():
                                if param_name != 'self':
                                    param_type = "unknown"
                                    if param.annotation != inspect.Parameter.empty:
                                        param_type = str(param.annotation).replace("<class '", "").replace("'>", "")
                                    
                                    required = param.default == inspect.Parameter.empty
                                    default_value = None if required else param.default
                                    
                                    tool_parameters.append({
                                        "name": param_name,
                                        "type": param_type,
                                        "required": required,
                                        "default": default_value
                                    })
                    else:
                        # Function tool
                        tool_name = tool.__name__
                        tool_description = tool.__doc__.strip() if tool.__doc__ else "No description available"
                        
                        # Extract parameters from function signature
                        signature = inspect.signature(tool)
                        for param_name, param in signature.parameters.items():
                            if param_name != 'self':
                                param_type = "unknown"
                                if param.annotation != inspect.Parameter.empty:
                                    param_type = str(param.annotation).replace("<class '", "").replace("'>", "")
                                
                                required = param.default == inspect.Parameter.empty
                                default_value = None if required else param.default
                                
                                tool_parameters.append({
                                    "name": param_name,
                                    "type": param_type,
                                    "required": required,
                                    "default": default_value
                                })
                    
                    # Add the formatted tool to the list
                    if tool_name:
                        formatted_tools.append({
                            "name": tool_name,
                            "description": tool_description,
                            "parameters": tool_parameters
                        })
                except Exception as e:
                    self.logger.error(f"Error processing tool: {str(e)}")
                    continue
            
            # Group tools by category
            tool_categories = {
                "knowledge_graph": [],
                "kubernetes": [],
                "csi_baremetal": [],
                "system_diagnostics": [],
                "hardware_diagnostics": []
            }
            
            for tool in formatted_tools:
                if tool["name"].startswith("kg_"):
                    tool_categories["knowledge_graph"].append(tool)
                elif tool["name"].startswith("kubectl_get_") and not tool["name"] == "kubectl_get":
                    tool_categories["csi_baremetal"].append(tool)
                elif tool["name"].startswith("kubectl_"):
                    tool_categories["kubernetes"].append(tool)
                elif any(tool["name"].startswith(prefix) for prefix in ["df_", "lsblk_", "mount_", "dmesg_", "journalctl_"]):
                    tool_categories["system_diagnostics"].append(tool)
                else:
                    tool_categories["hardware_diagnostics"].append(tool)
            
            return tool_categories
            
        except Exception as e:
            self.logger.error(f"Error preparing tool registry: {str(e)}")
            return {
                "knowledge_graph": [],
                "kubernetes": [],
                "csi_baremetal": [],
                "system_diagnostics": [],
                "hardware_diagnostics": []
            }
    
    def get_tool_by_name(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get tool information by name
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Optional[Dict[str, Any]]: Tool information or None if not found
        """
        try:
            tool_registry = self.prepare_tool_registry()
            
            # Search for the tool in all categories
            for category, tools in tool_registry.items():
                for tool in tools:
                    if tool["name"] == tool_name:
                        return tool
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting tool by name: {str(e)}")
            return None
    
    def get_tools_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        Get tools by category
        
        Args:
            category: Tool category
            
        Returns:
            List[Dict[str, Any]]: List of tools in the category
        """
        try:
            tool_registry = self.prepare_tool_registry()
            
            if category in tool_registry:
                return tool_registry[category]
            
            return []
            
        except Exception as e:
            self.logger.error(f"Error getting tools by category: {str(e)}")
            return []
