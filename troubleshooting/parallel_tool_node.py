import asyncio
import json
from copy import copy, deepcopy
from dataclasses import replace
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
    cast,
    get_type_hints,
)
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    ToolCall,
    ToolMessage,
    convert_to_messages,
)
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.config import (
    get_config_list,
    get_executor_for_config,
)
from langchain_core.tools import BaseTool, InjectedToolArg
from langchain_core.tools import tool as create_tool
from langchain_core.tools.base import get_all_basemodel_annotations
from pydantic import BaseModel
from typing_extensions import Annotated, get_args, get_origin

from langgraph.errors import GraphBubbleUp
from langgraph.store.base import BaseStore
from langgraph.types import Command, Send
from langgraph.utils.runnable import RunnableCallable
from langgraph.prebuilt.tool_node import (
    msg_content_output,
    _handle_tool_error,
    _infer_handled_types,
    _get_state_args,
    _get_store_arg,
    INVALID_TOOL_NAME_ERROR_TEMPLATE,
    TOOL_CALL_ERROR_TEMPLATE,
)

# Hook type definitions
BeforeCallToolsHook = Callable[[str, Dict[str, Any]], None]
AfterCallToolsHook = Callable[[str, Dict[str, Any], Any], None]

# Configure logging
logger = logging.getLogger('parallel_tool_node')
logger.setLevel(logging.INFO)

class ParallelToolNode(RunnableCallable):
    """A node that runs the tools labeled as parallel concurrently.

    Unlike the SerialToolNode that executes tools sequentially, ParallelToolNode
    executes tools concurrently using ThreadPoolExecutor. This allows for faster
    execution of independent tools that don't rely on each other's outputs.

    It filters tool calls to only process those labeled as parallel in the config,
    and passes any remaining tool calls to the next node in the graph.

    Args:
        tools: A sequence of tools that can be invoked by the ParallelToolNode.
        parallel_tools: A set of tool names that should be executed in parallel.
        name: The name of the ParallelToolNode in the graph. Defaults to "parallel_tools".
        max_workers: Maximum number of worker threads to use for parallel execution.
            Defaults to None (uses ThreadPoolExecutor default).
        tags: Optional tags to associate with the node. Defaults to None.
        handle_tool_errors: How to handle tool errors raised by tools inside the node. Defaults to True.
            Must be one of the following:
            - True: all errors will be caught and
                a ToolMessage with a default error message (TOOL_CALL_ERROR_TEMPLATE) will be returned.
            - str: all errors will be caught and
                a ToolMessage with the string value of 'handle_tool_errors' will be returned.
            - tuple[type[Exception], ...]: exceptions in the tuple will be caught and
                a ToolMessage with a default error message (TOOL_CALL_ERROR_TEMPLATE) will be returned.
            - Callable[..., str]: exceptions from the signature of the callable will be caught and
                a ToolMessage with the string value of the result of the 'handle_tool_errors' callable will be returned.
            - False: none of the errors raised by the tools will be caught
        messages_key: The state key in the input that contains the list of messages.
            The same key will be used for the output from the ParallelToolNode.
            Defaults to "messages".
    """

    name: str = "ParallelToolNode"

    def __init__(
        self,
        tools: Sequence[Union[BaseTool, Callable]],
        parallel_tools: set,
        *,
        name: str = "parallel_tools",
        max_workers: Optional[int] = None,
        tags: Optional[list[str]] = None,
        handle_tool_errors: Union[
            bool, str, Callable[..., str], tuple[type[Exception], ...]
        ] = True,
        messages_key: str = "messages",
    ) -> None:
        super().__init__(self._func, self._afunc, name=name, tags=tags, trace=False)
        self.tools_by_name: dict[str, BaseTool] = {}
        self.tool_to_state_args: dict[str, dict[str, Optional[str]]] = {}
        self.tool_to_store_arg: dict[str, Optional[str]] = {}
        self.handle_tool_errors = handle_tool_errors
        self.messages_key = messages_key
        self.parallel_tools = parallel_tools
        self.max_workers = max_workers
        # Initialize hook attributes
        self.before_call_hook: Optional[BeforeCallToolsHook] = None
        self.after_call_hook: Optional[AfterCallToolsHook] = None
        
        for tool_ in tools:
            if not isinstance(tool_, BaseTool):
                tool_ = create_tool(tool_)
            self.tools_by_name[tool_.name] = tool_
            self.tool_to_state_args[tool_.name] = _get_state_args(tool_)
            self.tool_to_store_arg[tool_.name] = _get_store_arg(tool_)
            
    def register_before_call_hook(self, hook: BeforeCallToolsHook) -> None:
        """Register a hook function to be called before tool execution.
        
        Args:
            hook: A callable that takes tool name and arguments as parameters
        """
        self.before_call_hook = hook
        
    def register_after_call_hook(self, hook: AfterCallToolsHook) -> None:
        """Register a hook function to be called after tool execution.
        
        Args:
            hook: A callable that takes tool name, arguments, and result as parameters
        """
        self.after_call_hook = hook

    def _func(
        self,
        input: Union[
            list[AnyMessage],
            dict[str, Any],
            BaseModel,
        ],
        config: RunnableConfig,
        *,
        store: Optional[BaseStore],
    ) -> Any:
        tool_calls, input_type = self._parse_input(input, store)
        
        # Filter tool calls to only include parallel tools
        parallel_tool_calls = [call for call in tool_calls if call["name"] in self.parallel_tools]
        remaining_tool_calls = [call for call in tool_calls if call["name"] not in self.parallel_tools]
        
        if not parallel_tool_calls:
            # If no parallel tools to execute, return the original tool calls for the next node
            return {"messages": [], "tool_calls": remaining_tool_calls}
        
        config_list = get_config_list(config, len(parallel_tool_calls))
        outputs = []
        
        # Process tools in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Create a dictionary to map futures to their corresponding tool calls and configs
            future_to_tool = {}
            
            # Submit all tool calls to the executor
            for i, tool_call in enumerate(parallel_tool_calls):
                # Get the individual config for this tool call
                tool_config = config_list[i] if i < len(config_list) else config_list[-1]
                
                # Submit the tool call to the executor
                future = executor.submit(self._run_one, tool_call, input_type, tool_config)
                future_to_tool[future] = (tool_call, tool_config)
            
            # Process completed futures as they finish
            for future in as_completed(future_to_tool):
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

        # Return the outputs from parallel tools and pass remaining tool calls to the next node
        return {"messages": outputs, "tool_calls": remaining_tool_calls}

    async def _afunc(
        self,
        input: Union[
            list[AnyMessage],
            dict[str, Any],
            BaseModel,
        ],
        config: RunnableConfig,
        *,
        store: Optional[BaseStore],
    ) -> Any:
        tool_calls, input_type = self._parse_input(input, store)
        
        # Filter tool calls to only include parallel tools
        parallel_tool_calls = [call for call in tool_calls if call["name"] in self.parallel_tools]
        remaining_tool_calls = [call for call in tool_calls if call["name"] not in self.parallel_tools]
        
        if not parallel_tool_calls:
            # If no parallel tools to execute, return the original tool calls for the next node
            return {"messages": [], "tool_calls": remaining_tool_calls}
        
        config_list = get_config_list(config, len(parallel_tool_calls))
        outputs = []
        
        # Process tools in parallel using asyncio.gather
        tasks = []
        for i, tool_call in enumerate(parallel_tool_calls):
            # Get the individual config for this tool call
            tool_config = config_list[i] if i < len(config_list) else config_list[-1]
            
            # Create a task for each tool call
            task = asyncio.create_task(self._arun_one(tool_call, input_type, tool_config))
            tasks.append(task)
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # If an exception occurred, create an error message
                tool_call = parallel_tool_calls[i]
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
 
         outputs.append(input[self.messages_key][-1])  # Append the last message to outputs

        # remove the last message from input if it is an AIMessage
        if isinstance(input, list) and input and isinstance(input[-1], AIMessage):
            input = input[:-1]
        elif isinstance(input, dict) and self.messages_key in input:
            input[self.messages_key] = input[self.messages_key][:-1]
        elif isinstance(input, BaseModel) and hasattr(input, self.messages_key):
            input = replace(input, **{self.messages_key: getattr(input, self.messages_key)[:-1]})
        elif isinstance(input, BaseModel) and hasattr(input, "tool_calls"):
            input = replace(input, tool_calls=input.tool_calls[:-1])
        else:
            # If input is not a list or dict with messages, we assume it's a BaseModel-like state
            input = deepcopy(input)

        # Return the outputs from parallel tools and pass remaining tool calls to the next node
        return {"messages": outputs, "tool_calls": remaining_tool_calls}

    def _run_one(
        self,
        call: ToolCall,
        input_type: Literal["list", "dict", "tool_calls"],
        config: RunnableConfig,
    ) -> ToolMessage:
        if invalid_tool_message := self._validate_tool_call(call):
            return invalid_tool_message

        # Extract tool name and arguments for hooks
        tool_name = call["name"]
        tool_args = call["args"] if "args" in call else {}
        
        # Call before_call_hook if registered
        if self.before_call_hook:
            try:
                self.before_call_hook(tool_name, tool_args)
            except Exception as hook_error:
                # Log the error but continue with tool execution
                logger.error(f"Error in before_call_hook: {hook_error}")

        try:
            input = {**call, **{"type": "tool_call"}}
            response = self.tools_by_name[tool_name].invoke(input, config)

            # Call after_call_hook if registered
            if self.after_call_hook:
                try:
                    self.after_call_hook(tool_name, tool_args, response)
                except Exception as hook_error:
                    # Log the error but continue with normal flow
                    logger.error(f"Error in after_call_hook: {hook_error}")

            return response

        # GraphInterrupt is a special exception that will always be raised.
        except GraphBubbleUp as e:
            raise e
        except Exception as e:
            if isinstance(self.handle_tool_errors, tuple):
                handled_types: tuple = self.handle_tool_errors
            elif callable(self.handle_tool_errors):
                handled_types = _infer_handled_types(self.handle_tool_errors)
            else:
                # default behavior is catching all exceptions
                handled_types = (Exception,)

            # Unhandled
            if not self.handle_tool_errors or not isinstance(e, handled_types):
                raise e
            # Handled
            else:
                content = _handle_tool_error(e, flag=self.handle_tool_errors)
            
            error_message = ToolMessage(
                content=content,
                name=call["name"],
                tool_call_id=call["id"],
                status="error",
            )
            
            # Call after_call_hook with error result if registered
            if self.after_call_hook:
                try:
                    self.after_call_hook(tool_name, tool_args, error_message)
                except Exception as hook_error:
                    # Log the error but continue with normal flow
                    logger.error(f"Error in after_call_hook: {hook_error}")
                    
            return error_message

    async def _arun_one(
        self,
        call: ToolCall,
        input_type: Literal["list", "dict", "tool_calls"],
        config: RunnableConfig,
    ) -> ToolMessage:
        if invalid_tool_message := self._validate_tool_call(call):
            return invalid_tool_message

        # Extract tool name and arguments for hooks
        tool_name = call["name"]
        tool_args = call["args"] if "args" in call else {}
        
        # Call before_call_hook if registered
        if self.before_call_hook:
            try:
                self.before_call_hook(tool_name, tool_args)
            except Exception as hook_error:
                # Log the error but continue with tool execution
                logger.error(f"Error in before_call_hook: {hook_error}")

        try:
            input = {**call, **{"type": "tool_call"}}
            response = await self.tools_by_name[tool_name].ainvoke(input, config)

            # Call after_call_hook if registered
            if self.after_call_hook:
                try:
                    self.after_call_hook(tool_name, tool_args, response)
                except Exception as hook_error:
                    # Log the error but continue with normal flow
                    logger.error(f"Error in after_call_hook: {hook_error}")

            return response

        # GraphInterrupt is a special exception that will always be raised.
        except GraphBubbleUp as e:
            raise e
        except Exception as e:
            if isinstance(self.handle_tool_errors, tuple):
                handled_types: tuple = self.handle_tool_errors
            elif callable(self.handle_tool_errors):
                handled_types = _infer_handled_types(self.handle_tool_errors)
            else:
                # default behavior is catching all exceptions
                handled_types = (Exception,)

            # Unhandled
            if not self.handle_tool_errors or not isinstance(e, handled_types):
                raise e
            # Handled
            else:
                content = _handle_tool_error(e, flag=self.handle_tool_errors)

            error_message = ToolMessage(
                content=content,
                name=call["name"],
                tool_call_id=call["id"],
                status="error",
            )
            
            # Call after_call_hook with error result if registered
            if self.after_call_hook:
                try:
                    self.after_call_hook(tool_name, tool_args, error_message)
                except Exception as hook_error:
                    # Log the error but continue with normal flow
                    logger.error(f"Error in after_call_hook: {hook_error}")
                    
            return error_message

    def _parse_input(
        self,
        input: Union[
            list[AnyMessage],
            dict[str, Any],
            BaseModel,
        ],
        store: Optional[BaseStore],
    ) -> Tuple[list[ToolCall], Literal["list", "dict", "tool_calls"]]:
        if isinstance(input, list):
            if isinstance(input[-1], dict) and input[-1].get("type") == "tool_call":
                input_type = "tool_calls"
                tool_calls = input
                return tool_calls, input_type
            else:
                input_type = "list"
                message: AnyMessage = input[-1]
        elif isinstance(input, dict) and (messages := input.get(self.messages_key, [])):
            input_type = "dict"
            message = messages[-1]
        elif messages := getattr(input, self.messages_key, None):
            # Assume dataclass-like state that can coerce from dict
            input_type = "dict"
            message = messages[-1]
        elif tool_calls := input.get("tool_calls", []):
            # Handle case where tool_calls are passed directly
            input_type = "dict"
            return [
                self.inject_tool_args(call, input, store) for call in tool_calls
            ], input_type
        else:
            raise ValueError("No message or tool_calls found in input")

        if not isinstance(message, AIMessage):
            raise ValueError("Last message is not an AIMessage")

        tool_calls = [
            self.inject_tool_args(call, input, store) for call in message.tool_calls
        ]
        return tool_calls, input_type

    def _validate_tool_call(self, call: ToolCall) -> Optional[ToolMessage]:
        if (requested_tool := call["name"]) not in self.tools_by_name:
            content = INVALID_TOOL_NAME_ERROR_TEMPLATE.format(
                requested_tool=requested_tool,
                available_tools=", ".join(self.tools_by_name.keys()),
            )
            return ToolMessage(
                content, name=requested_tool, tool_call_id=call["id"], status="error"
            )
        else:
            return None

    def _inject_state(
        self,
        tool_call: ToolCall,
        input: Union[
            list[AnyMessage],
            dict[str, Any],
            BaseModel,
        ],
    ) -> ToolCall:
        state_args = self.tool_to_state_args[tool_call["name"]]
        if state_args and isinstance(input, list):
            required_fields = list(state_args.values())
            if (
                len(required_fields) == 1
                and required_fields[0] == self.messages_key
                or required_fields[0] is None
            ):
                input = {self.messages_key: input}
            else:
                err_msg = (
                    f"Invalid input to ParallelToolNode. Tool {tool_call['name']} requires "
                    f"graph state dict as input."
                )
                if any(state_field for state_field in state_args.values()):
                    required_fields_str = ", ".join(f for f in required_fields if f)
                    err_msg += f" State should contain fields {required_fields_str}."
                raise ValueError(err_msg)
        if isinstance(input, dict):
            tool_state_args = {
                tool_arg: input[state_field] if state_field else input
                for tool_arg, state_field in state_args.items()
            }

        else:
            tool_state_args = {
                tool_arg: getattr(input, state_field) if state_field else input
                for tool_arg, state_field in state_args.items()
            }

        tool_call["args"] = {
            **tool_call["args"],
            **tool_state_args,
        }
        return tool_call

    def _inject_store(
        self, tool_call: ToolCall, store: Optional[BaseStore]
    ) -> ToolCall:
        store_arg = self.tool_to_store_arg[tool_call["name"]]
        if not store_arg:
            return tool_call

        if store is None:
            raise ValueError(
                "Cannot inject store into tools with InjectedStore annotations - "
                "please compile your graph with a store."
            )

        tool_call["args"] = {
            **tool_call["args"],
            store_arg: store,
        }
        return tool_call

    def inject_tool_args(
        self,
        tool_call: ToolCall,
        input: Union[
            list[AnyMessage],
            dict[str, Any],
            BaseModel,
        ],
        store: Optional[BaseStore],
    ) -> ToolCall:
        """Injects the state and store into the tool call.

        Tool arguments with types annotated as `InjectedState` and `InjectedStore` are
        ignored in tool schemas for generation purposes. This method injects them into
        tool calls for tool invocation.

        Args:
            tool_call (ToolCall): The tool call to inject state and store into.
            input (Union[list[AnyMessage], dict[str, Any], BaseModel]): The input state
                to inject.
            store (Optional[BaseStore]): The store to inject.

        Returns:
            ToolCall: The tool call with injected state and store.
        """
        if tool_call["name"] not in self.tools_by_name:
            return tool_call

        tool_call_copy: ToolCall = copy(tool_call)
        tool_call_with_state = self._inject_state(tool_call_copy, input)
        tool_call_with_store = self._inject_store(tool_call_with_state, store)
        return tool_call_with_store
