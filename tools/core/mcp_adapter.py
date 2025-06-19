#!/usr/bin/env python3
"""
MCP Adapter for Kubernetes Volume I/O Error Troubleshooting

This module provides integration with MCP (Multi-Cloud Platform) tools
using the langchain_mcp_adapters package. It handles initialization
of MCP servers and routing of tool calls based on configuration.
"""

from typing import Dict, List, Any, Optional, Union
import logging
import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient

logger = logging.getLogger(__name__)

# Global MCP adapter instance
_mcp_adapter = None

class MCPAdapter:
    """
    MCP Adapter for integrating MCP tools into the troubleshooting system
    
    Handles initialization of MCP servers and routing of tool calls
    based on configuration.
    """
    
    def __init__(self, config_data: Dict[str, Any]):
        """
        Initialize MCP Adapter with configuration
        
        Args:
            config_data: Configuration data from config.yaml
        """
        self.config_data = config_data
        self.mcp_enabled = config_data.get('mcp_enabled', False)
        self.mcp_servers = config_data.get('mcp_servers', {})
        self.mcp_clients = {}
        self.mcp_tools = {}
        self.mcp_tools_by_phase = {
            'plan_phase': [],
            'phase1': [],
            'phase2': []
        }
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    async def initialize_servers(self):
        """
        Initialize MCP servers based on configuration
        """
        if not self.mcp_enabled:
            self.logger.info("MCP integration is disabled")
            return
        
        for server_name, server_config in self.mcp_servers.items():
            try:
                # Extract server configuration
                server_type = server_config.get('type', 'sse')
                server_url = server_config.get('url', '')
                command = server_config.get('command', None)
                args = server_config.get('args', [])
                env = server_config.get('env', {})
                
                # Validate configuration
                if server_type == 'sse' and not server_url:
                    self.logger.error(f"Missing URL for SSE server: {server_name}")
                    continue
                
                if server_type == 'stdio' and not command:
                    self.logger.error(f"Missing command for stdio server: {server_name}")
                    continue
                
                # Configure server based on type
                server_config_dict = {}
                if server_type == 'sse':
                    server_config_dict = {
                        "url": server_url,
                        "transport": "sse"
                    }
                else:  # stdio
                    server_config_dict = {
                        "command": command,
                        "args": args,
                        "env": env,
                        "transport": "stdio"
                    }
                
                # Create MCP client for this server
                self.logger.info(f"Initializing MCP server: {server_name} ({server_type})")
                server_config = {server_name: server_config_dict}
                self.mcp_clients[server_name] = MultiServerMCPClient(server_config)
                
                # Get tools from this server 
                tools = await self.mcp_clients[server_name].get_tools()
                if tools:
                    self.mcp_tools[server_name] = tools
                    self.logger.info(f"Loaded {len(tools)} tools from MCP server: {server_name}")
                    
                    # Organize tools by phase
                    phase_config = server_config.get('tools', {})
                    if phase_config.get('plan_phase', False):
                        self.mcp_tools_by_phase['plan_phase'].extend(tools)
                    if phase_config.get('phase1', False):
                        self.mcp_tools_by_phase['phase1'].extend(tools)
                    if phase_config.get('phase2', False):
                        self.mcp_tools_by_phase['phase2'].extend(tools)
                else:
                    self.logger.warning(f"No tools loaded from MCP server: {server_name}")
                    
            except Exception as e:
                self.logger.error(f"Failed to initialize MCP server {server_name}: {str(e)}")
    
    def get_tools_for_phase(self, phase: str) -> List[Any]:
        """
        Get MCP tools for a specific phase
        
        Args:
            phase: Phase name ('plan_phase', 'phase1', or 'phase2')
            
        Returns:
            List[Any]: List of MCP tools for the specified phase
        """
        if not self.mcp_enabled:
            return []
            
        return self.mcp_tools_by_phase.get(phase, [])
    
    def get_all_tools(self) -> List[Any]:
        """
        Get all MCP tools from all servers
        
        Returns:
            List[Any]: List of all MCP tools
        """
        if not self.mcp_enabled:
            return []
            
        all_tools = []
        for server_name, tools in self.mcp_tools.items():
            all_tools.extend(tools)
        
        return all_tools
    
    async def call_tool(self, tool_name: str, **kwargs) -> Any:
        """
        Call an MCP tool by name
        
        Args:
            tool_name: Name of the tool to call
            **kwargs: Arguments to pass to the tool
            
        Returns:
            Any: Result of the tool call
        """
        if not self.mcp_enabled:
            raise ValueError("MCP integration is disabled")
            
        # Find the server that has this tool
        for server_name, tools in self.mcp_tools.items():
            for tool in tools:
                if tool.name == tool_name:
                    self.logger.info(f"Calling MCP tool: {tool_name} on server: {server_name}")
                    return await tool.invoke(kwargs)
                    
        raise ValueError(f"MCP tool not found: {tool_name}")
    
    async def close(self):
        """
        Close all MCP clients
        """
        if not self.mcp_enabled:
            return
            
        for server_name, client in self.mcp_clients.items():
            try:
                #await client.aclose()
                self.logger.info(f"Closed MCP client: {server_name}")
            except Exception as e:
                self.logger.error(f"Error closing MCP client {server_name}: {e}")


async def initialize_mcp_adapter(config_data: Dict[str, Any]) -> MCPAdapter:
    """
    Initialize the global MCP adapter
    
    Args:
        config_data: Configuration data from config.yaml
        
    Returns:
        MCPAdapter: Initialized MCP adapter
    """
    global _mcp_adapter
    
    if _mcp_adapter is None:
        _mcp_adapter = MCPAdapter(config_data)
        
        # Initialize MCP servers asynchronously
        await _mcp_adapter.initialize_servers()
    
    return _mcp_adapter


def get_mcp_adapter() -> Optional[MCPAdapter]:
    """
    Get the global MCP adapter instance
    
    Returns:
        Optional[MCPAdapter]: MCP adapter instance or None if not initialized
    """
    global _mcp_adapter
    return _mcp_adapter
