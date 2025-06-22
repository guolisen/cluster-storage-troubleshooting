"""
Tool Execution Strategies for Kubernetes Volume I/O Error Troubleshooting

This module defines strategy classes for tool execution in the troubleshooting system.
It implements the Strategy Pattern to separate different execution approaches.
"""

import logging
import concurrent.futures
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Literal, Optional, Union
from enum import Enum

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.config import get_config_list

# Configure logging
logger = logging.getLogger('strategies')
logger.setLevel(logging.INFO)

class ExecutionType(Enum):
    """Enumeration for tool execution types."""
    SERIAL = "Serial"
    PARALLEL = "Parallel"

class ToolExecutionStrategy(ABC):
    """Abstract base class for tool execution strategies."""
    
    @abstractmethod
    def execute(
        self,
        tool_calls: List[Dict[str, Any]],
        input_type: Literal["list", "dict", "tool_calls"],
        config: RunnableConfig,
        run_one_callback: callable,
    ) -> List[ToolMessage]:
        """Execute tool calls according to a specific strategy.
        
        Args:
            tool_calls: List of tool calls to execute
            input_type: Type of input (list, dict, or tool_calls)
            config: Runnable configuration
            run_one_callback: Callback function to execute a single tool
            
        Returns:
            List of ToolMessage results
        """
        pass
    
    @abstractmethod
    async def execute_async(
        self,
        tool_calls: List[Dict[str, Any]],
        input_type: Literal["list", "dict", "tool_calls"],
        config: RunnableConfig,
        run_one_callback: callable,
    ) -> List[ToolMessage]:
        """Execute tool calls asynchronously according to a specific strategy.
        
        Args:
            tool_calls: List of tool calls to execute
            input_type: Type of input (list, dict, or tool_calls)
            config: Runnable configuration
            run_one_callback: Callback function to execute a single tool
            
        Returns:
            List of ToolMessage results
        """
        pass

class SerialToolExecutionStrategy(ToolExecutionStrategy):
    """Strategy for executing tools sequentially."""
    
    def execute(
        self,
        tool_calls: List[Dict[str, Any]],
        input_type: Literal["list", "dict", "tool_calls"],
        config: RunnableConfig,
        run_one_callback: callable,
    ) -> List[ToolMessage]:
        """Execute tools sequentially in the order they appear.
        
        Args:
            tool_calls: List of tool calls to execute serially
            input_type: Type of input (list, dict, or tool_calls)
            config: Runnable configuration
            run_one_callback: Callback function to execute a single tool
            
        Returns:
            List of ToolMessage results
        """
        if not tool_calls:
            return []
            
        config_list = get_config_list(config, len(tool_calls))
        outputs = []
        
        # Process tools sequentially
        for i, tool_call in enumerate(tool_calls):
            # Get the individual config for this tool call
            tool_config = config_list[i] if i < len(config_list) else config_list[-1]
            
            # Run the tool with "Serial" call type
            output = run_one_callback(tool_call, input_type, tool_config, ExecutionType.SERIAL.value)
            outputs.append(output)
            
        return outputs
    
    async def execute_async(
        self,
        tool_calls: List[Dict[str, Any]],
        input_type: Literal["list", "dict", "tool_calls"],
        config: RunnableConfig,
        run_one_callback: callable,
    ) -> List[ToolMessage]:
        """Execute tools sequentially in the order they appear (async version).
        
        Args:
            tool_calls: List of tool calls to execute serially
            input_type: Type of input (list, dict, or tool_calls)
            config: Runnable configuration
            run_one_callback: Callback function to execute a single tool
            
        Returns:
            List of ToolMessage results
        """
        if not tool_calls:
            return []
            
        config_list = get_config_list(config, len(tool_calls))
        outputs = []
        
        # Process tools sequentially
        for i, tool_call in enumerate(tool_calls):
            # Get the individual config for this tool call
            tool_config = config_list[i] if i < len(config_list) else config_list[-1]
            
            # Run the tool with "Serial" call type
            output = await run_one_callback(tool_call, input_type, tool_config, ExecutionType.SERIAL.value)
            outputs.append(output)
            
        return outputs

class ParallelToolExecutionStrategy(ToolExecutionStrategy):
    """Strategy for executing tools concurrently."""
    
    def __init__(self, max_workers: Optional[int] = None):
        """Initialize the parallel execution strategy.
        
        Args:
            max_workers: Maximum number of worker threads to use for parallel execution.
                Defaults to None (uses ThreadPoolExecutor default).
        """
        self.max_workers = max_workers
    
    def execute(
        self,
        tool_calls: List[Dict[str, Any]],
        input_type: Literal["list", "dict", "tool_calls"],
        config: RunnableConfig,
        run_one_callback: callable,
    ) -> List[ToolMessage]:
        """Execute tools concurrently using ThreadPoolExecutor.
        
        Args:
            tool_calls: List of tool calls to execute in parallel
            input_type: Type of input (list, dict, or tool_calls)
            config: Runnable configuration
            run_one_callback: Callback function to execute a single tool
            
        Returns:
            List of ToolMessage results
        """
        if not tool_calls:
            return []
            
        config_list = get_config_list(config, len(tool_calls))
        outputs = []
        
        try:
            # Process tools in parallel using ThreadPoolExecutor
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Create a dictionary to map futures to their corresponding tool calls and configs
                future_to_tool = {}
                
                # Submit all tool calls to the executor
                for i, tool_call in enumerate(tool_calls):
                    # Get the individual config for this tool call
                    tool_config = config_list[i] if i < len(config_list) else config_list[-1]
                    
                    # Submit the tool call to the executor with "Parallel" call type
                    future = executor.submit(
                        run_one_callback, tool_call, input_type, tool_config, ExecutionType.PARALLEL.value
                    )
                    future_to_tool[future] = (tool_call, tool_config)
                
                # Process completed futures as they finish
                for future in concurrent.futures.as_completed(future_to_tool):
                    try:
                        output = future.result()
                        outputs.append(output)
                    except Exception as exc:
                        # If an exception occurs in the thread, log it and create an error message
                        tool_call, _ = future_to_tool[future]
                        logger.error(f"Tool {tool_call['name']} generated an exception: {exc}")
                        error_message = ToolMessage(
                            content=f"Error executing tool {tool_call['name']}: {str(exc)}",
                            name=tool_call["name"],
                            tool_call_id=tool_call["id"],
                            status="error",
                        )
                        outputs.append(error_message)
        except Exception as e:
            # If ThreadPoolExecutor fails, log the error and fall back to sequential execution
            logger.error(f"Parallel execution failed, falling back to sequential: {e}")
            # Fall back to sequential execution
            serial_strategy = SerialToolExecutionStrategy()
            outputs = serial_strategy.execute(tool_calls, input_type, config, run_one_callback)
            
        return outputs
    
    async def execute_async(
        self,
        tool_calls: List[Dict[str, Any]],
        input_type: Literal["list", "dict", "tool_calls"],
        config: RunnableConfig,
        run_one_callback: callable,
    ) -> List[ToolMessage]:
        """Execute tools concurrently using asyncio.gather.
        
        Args:
            tool_calls: List of tool calls to execute in parallel
            input_type: Type of input (list, dict, or tool_calls)
            config: Runnable configuration
            run_one_callback: Callback function to execute a single tool
            
        Returns:
            List of ToolMessage results
        """
        if not tool_calls:
            return []
            
        config_list = get_config_list(config, len(tool_calls))
        outputs = []
        
        try:
            # Process tools in parallel using asyncio.gather
            tasks = []
            for i, tool_call in enumerate(tool_calls):
                # Get the individual config for this tool call
                tool_config = config_list[i] if i < len(config_list) else config_list[-1]
                
                # Create a task for each tool call with "Parallel" call type
                task = asyncio.create_task(
                    run_one_callback(tool_call, input_type, tool_config, ExecutionType.PARALLEL.value)
                )
                tasks.append(task)
            
            # Wait for all tasks to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    # If an exception occurred, create an error message
                    tool_call = tool_calls[i]
                    logger.error(f"Tool {tool_call['name']} generated an exception: {result}")
                    error_message = ToolMessage(
                        content=f"Error executing tool {tool_call['name']}: {str(result)}",
                        name=tool_call["name"],
                        tool_call_id=tool_call["id"],
                        status="error",
                    )
                    outputs.append(error_message)
                else:
                    outputs.append(result)
        except Exception as e:
            # If asyncio.gather fails, log the error and fall back to sequential execution
            logger.error(f"Parallel async execution failed, falling back to sequential: {e}")
            # Fall back to sequential execution
            serial_strategy = SerialToolExecutionStrategy()
            outputs = await serial_strategy.execute_async(tool_calls, input_type, config, run_one_callback)
            
        return outputs

class StrategyFactory:
    """Factory class for creating execution strategies."""
    
    @staticmethod
    def create_strategy(strategy_type: ExecutionType, max_workers: Optional[int] = None) -> ToolExecutionStrategy:
        """Create a strategy based on execution type.
        
        Args:
            strategy_type: Type of execution strategy (SERIAL or PARALLEL)
            max_workers: Maximum number of worker threads for parallel execution
            
        Returns:
            An instance of a ToolExecutionStrategy
        """
        if strategy_type == ExecutionType.PARALLEL:
            return ParallelToolExecutionStrategy(max_workers)
        return SerialToolExecutionStrategy()
