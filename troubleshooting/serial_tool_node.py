import asyncio
import json
from copy import copy, deepcopy
from dataclasses import replace
from typing import (
    Any,
    Callable,
    Dict,
    Literal,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
    cast,
    get_type_hints,
)

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

class SerialToolNode(RunnableCallable):
    """A node that runs the tools called in the last AIMessage in serial order.

    Unlike the standard ToolNode that runs tools in parallel, SerialToolNode
    executes them sequentially in the order they appear in the tool_calls list.
    This ensures tools are executed in a specific sequence, allowing later tools
    to potentially depend on the output of earlier tools.

    It can be used either in StateGraph with a "messages" state key (or a custom key passed via SerialToolNode's 'messages_key').
    The output will be a list of ToolMessages, one for each tool call, in the same order as the tools were called.

    Tool calls can also be passed directly as a list of `ToolCall` dicts.

    Args:
        tools: A sequence of tools that can be invoked by the SerialToolNode.
        name: The name of the SerialToolNode in the graph. Defaults to "tools".
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
            The same key will be used for the output from the SerialToolNode.
            Defaults to "messages".

    The `SerialToolNode` is roughly analogous to:

    ```python
    tools_by_name = {tool.name: tool for tool in tools}
    def serial_tool_node(state: dict):
        result = []
        for tool_call in state["messages"][-1].tool_calls:
            tool = tools_by_name[tool_call["name"]]
            observation = tool.invoke(tool_call["args"])
            result.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))
        return {"messages": result}
    ```

    Important:
        - The input state can be one of the following:
            - A dict with a messages key containing a list of messages.
            - A list of messages.
            - A list of tool calls.
        - If operating on a message list, the last message must be an `AIMessage` with
            `tool_calls` populated.
        - Tools are executed in the exact order they appear in the tool_calls list.
    """

    name: str = "SerialToolNode"

    def __init__(
        self,
        tools: Sequence[Union[BaseTool, Callable]],
        *,
        name: str = "tools",
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
        config_list = get_config_list(config, len(tool_calls))
        outputs = []
        
        # Process tools sequentially instead of in parallel
        for i, tool_call in enumerate(tool_calls):
            # Get the individual config for this tool call
            tool_config = config_list[i] if i < len(config_list) else config_list[-1]
            
            # Run the tool
            output = self._run_one(tool_call, input_type, tool_config)
            outputs.append(output)

        return self._combine_tool_outputs(outputs, input_type)

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
        config_list = get_config_list(config, len(tool_calls))
        outputs = []
        
        # Process tools sequentially instead of in parallel
        for i, tool_call in enumerate(tool_calls):
            # Get the individual config for this tool call
            tool_config = config_list[i] if i < len(config_list) else config_list[-1]
            
            # Run the tool
            output = await self._arun_one(tool_call, input_type, tool_config)
            outputs.append(output)

        return self._combine_tool_outputs(outputs, input_type)

    def _combine_tool_outputs(
        self,
        outputs: list[ToolMessage],
        input_type: Literal["list", "dict", "tool_calls"],
    ) -> list[Union[Command, list[ToolMessage], dict[str, list[ToolMessage]]]]:
        # preserve existing behavior for non-command tool outputs for backwards
        # compatibility
        if not any(isinstance(output, Command) for output in outputs):
            # TypedDict, pydantic, dataclass, etc. should all be able to load from dict
            return outputs if input_type == "list" else {self.messages_key: outputs}

        # LangGraph will automatically handle list of Command and non-command node
        # updates
        combined_outputs: list[
            Command | list[ToolMessage] | dict[str, list[ToolMessage]]
        ] = []

        # combine all parent commands with goto into a single parent command
        parent_command: Optional[Command] = None
        for output in outputs:
            if isinstance(output, Command):
                if (
                    output.graph is Command.PARENT
                    and isinstance(output.goto, list)
                    and all(isinstance(send, Send) for send in output.goto)
                ):
                    if parent_command:
                        parent_command = replace(
                            parent_command,
                            goto=cast(list[Send], parent_command.goto) + output.goto,
                        )
                    else:
                        parent_command = Command(graph=Command.PARENT, goto=output.goto)
                else:
                    combined_outputs.append(output)
            else:
                combined_outputs.append(
                    [output] if input_type == "list" else {self.messages_key: [output]}
                )

        if parent_command:
            combined_outputs.append(parent_command)
        return combined_outputs

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
                print(f"Error in before_call_hook: {hook_error}")

        try:
            input = {**call, **{"type": "tool_call"}}
            response = self.tools_by_name[tool_name].invoke(input, config)

            # Call after_call_hook if registered
            if self.after_call_hook:
                try:
                    self.after_call_hook(tool_name, tool_args, response)
                except Exception as hook_error:
                    # Log the error but continue with normal flow
                    print(f"Error in after_call_hook: {hook_error}")

            return response

        # GraphInterrupt is a special exception that will always be raised.
        # It can be triggered in the following scenarios:
        # (1) a NodeInterrupt is raised inside a tool
        # (2) a NodeInterrupt is raised inside a graph node for a graph called as a tool
        # (3) a GraphInterrupt is raised when a subgraph is interrupted inside a graph called as a tool
        # (2 and 3 can happen in a "supervisor w/ tools" multi-agent architecture)
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
                    print(f"Error in after_call_hook: {hook_error}")
                    
            return error_message

        if isinstance(response, Command):
            return self._validate_tool_command(response, call, input_type)
        elif isinstance(response, ToolMessage):
            response.content = cast(
                Union[str, list], msg_content_output(response.content)
            )
            return response
        else:
            raise TypeError(
                f"Tool {call['name']} returned unexpected type: {type(response)}"
            )

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
                print(f"Error in before_call_hook: {hook_error}")

        try:
            input = {**call, **{"type": "tool_call"}}
            response = await self.tools_by_name[tool_name].ainvoke(input, config)

            # Call after_call_hook if registered
            if self.after_call_hook:
                try:
                    self.after_call_hook(tool_name, tool_args, response)
                except Exception as hook_error:
                    # Log the error but continue with normal flow
                    print(f"Error in after_call_hook: {hook_error}")

            return response

        # GraphInterrupt is a special exception that will always be raised.
        # It can be triggered in the following scenarios:
        # (1) a NodeInterrupt is raised inside a tool
        # (2) a NodeInterrupt is raised inside a graph node for a graph called as a tool
        # (3) a GraphInterrupt is raised when a subgraph is interrupted inside a graph called as a tool
        # (2 and 3 can happen in a "supervisor w/ tools" multi-agent architecture)
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
                    print(f"Error in after_call_hook: {hook_error}")
                    
            return error_message

        if isinstance(response, Command):
            return self._validate_tool_command(response, call, input_type)
        elif isinstance(response, ToolMessage):
            response.content = cast(
                Union[str, list], msg_content_output(response.content)
            )
            return response
        else:
            raise TypeError(
                f"Tool {call['name']} returned unexpected type: {type(response)}"
            )

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
        else:
            raise ValueError("No message found in input")

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
                    f"Invalid input to SerialToolNode. Tool {tool_call['name']} requires "
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

    def _validate_tool_command(
        self,
        command: Command,
        call: ToolCall,
        input_type: Literal["list", "dict", "tool_calls"],
    ) -> Command:
        if isinstance(command.update, dict):
            # input type is dict when SerialToolNode is invoked with a dict input (e.g. {"messages": [AIMessage(..., tool_calls=[...])]})
            if input_type not in ("dict", "tool_calls"):
                raise ValueError(
                    f"Tools can provide a dict in Command.update only when using dict with '{self.messages_key}' key as SerialToolNode input, "
                    f"got: {command.update} for tool '{call['name']}'"
                )

            updated_command = deepcopy(command)
            state_update = cast(dict[str, Any], updated_command.update) or {}
            messages_update = state_update.get(self.messages_key, [])
        elif isinstance(command.update, list):
            # input type is list when SerialToolNode is invoked with a list input (e.g. [AIMessage(..., tool_calls=[...])])
            if input_type != "list":
                raise ValueError(
                    f"Tools can provide a list of messages in Command.update only when using list of messages as SerialToolNode input, "
                    f"got: {command.update} for tool '{call['name']}'"
                )

            updated_command = deepcopy(command)
            messages_update = updated_command.update
        else:
            return command

        # convert to message objects if updates are in a dict format
        messages_update = convert_to_messages(messages_update)
        has_matching_tool_message = False
        for message in messages_update:
            if not isinstance(message, ToolMessage):
                continue

            if message.tool_call_id == call["id"]:
                message.name = call["name"]
                has_matching_tool_message = True

        # validate that we always have a ToolMessage matching the tool call in
        # Command.update if command is sent to the CURRENT graph
        if updated_command.graph is None and not has_matching_tool_message:
            example_update = (
                '`Command(update={"messages": [ToolMessage("Success", tool_call_id=tool_call_id), ...]}, ...)`'
                if input_type == "dict"
                else '`Command(update=[ToolMessage("Success", tool_call_id=tool_call_id), ...], ...)`'
            )
            raise ValueError(
                f"Expected to have a matching ToolMessage in Command.update for tool '{call['name']}', got: {messages_update}. "
                "Every tool call (LLM requesting to call a tool) in the message history MUST have a corresponding ToolMessage. "
                f"You can fix it by modifying the tool to return {example_update}."
            )
        return updated_command
