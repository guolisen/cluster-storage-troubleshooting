import unittest
from unittest.mock import Mock, patch, ANY
import functools

from tools.registry import get_all_tools

# Attempt to import KnowledgeGraph for type hinting Mock spec
try:
    from tools.knowledge_graph import KnowledgeGraph
except ImportError:
    try:
        from knowledge_graph import KnowledgeGraph # Fallback
    except ImportError:
        KnowledgeGraph = ANY # If not found, use ANY for spec

class TestToolRegistry(unittest.TestCase):

    def test_module_importable(self):
        """Test that tools.registry module can be imported without syntax errors."""
        try:
            import tools.registry
            # If the import works, we can consider this a basic pass.
            # The module itself might do more complex imports that could fail,
            # but a direct SyntaxError in tools.registry would be caught here.
            self.assertTrue(True, "tools.registry imported successfully.")
        except ImportError as e:
            # This will catch syntax errors during import of tools.registry,
            # or issues with its direct dependencies.
            self.fail(f"Failed to import tools.registry: {e}")

    def find_tool_by_name(self, tools, name):
        """Helper to find a tool in a list, checking functools.partial wrapped functions."""
        for tool in tools:
            if isinstance(tool, functools.partial):
                if tool.func.__name__ == name:
                    return tool
            elif callable(tool) and tool.__name__ == name: # For non-partially wrapped tools
                return tool
        return None

    @patch('tools.core.knowledge_graph.kg_get_entity_info') # Path to the original tool
    def test_get_kg_tool_via_registry(self, mock_original_kg_tool):
        mock_original_kg_tool.return_value = "Mocked KG Info"

        mock_kg_instance = Mock(spec=KnowledgeGraph)
        mock_config_data = {}
        interactive_mode = False

        all_tools = get_all_tools(mock_kg_instance, mock_config_data, interactive_mode)

        wrapped_kg_tool = self.find_tool_by_name(all_tools, "kg_get_entity_info")
        self.assertIsNotNone(wrapped_kg_tool, "kg_get_entity_info tool not found in registry")

        # Call the wrapped tool
        result = wrapped_kg_tool(entity_type="Pod", entity_id="test-pod")
        self.assertEqual(result, "Mocked KG Info")

        # Assert that the original tool was called with kg_instance as the first arg
        mock_original_kg_tool.assert_called_once_with(mock_kg_instance, entity_type="Pod", entity_id="test-pod")

    @patch('tools.kubernetes.core.kubectl_get') # Path to the original tool
    def test_get_k8s_tool_via_registry(self, mock_original_k8s_tool):
        mock_original_k8s_tool.return_value = "Mocked kubectl get output"

        mock_kg_instance = Mock(spec=KnowledgeGraph) # Needed for get_all_tools
        mock_config_data = {"user": "test_user"}
        interactive_mode = True

        all_tools = get_all_tools(mock_kg_instance, mock_config_data, interactive_mode)

        wrapped_k8s_tool = self.find_tool_by_name(all_tools, "kubectl_get")
        self.assertIsNotNone(wrapped_k8s_tool, "kubectl_get tool not found in registry")

        # Call the wrapped tool
        result = wrapped_k8s_tool(resource_type="pod", resource_name="test-k8s-pod")
        self.assertEqual(result, "Mocked kubectl get output")

        # Assert that the original tool was called with config_data and interactive_mode
        # The functools.partial in registry was done like:
        # functools.partial(tool, config_data=config_data, interactive_mode=interactive_mode)
        # So these will be keyword arguments to the mock, or positional if the original func defined them positionally after specific args
        # Let's check original signature: kubectl_get(resource_type: str, ..., config_data: Dict[str, Any] = None, interactive_mode: bool = False)
        # The partial was created with keyword arguments, so they will be passed as keywords.
        mock_original_k8s_tool.assert_called_once_with(
            resource_type="pod",
            resource_name="test-k8s-pod",
            config_data=mock_config_data,
            interactive_mode=interactive_mode
        )

    @patch('tools.diagnostics.hardware.ssh_execute') # Path to the original tool
    def test_get_hardware_tool_via_registry(self, mock_original_hw_tool):
        mock_original_hw_tool.return_value = "Mocked SSH output"

        mock_kg_instance = Mock(spec=KnowledgeGraph)
        mock_config_data = {"ssh_config": {"user": "custom_user"}}
        interactive_mode = False

        all_tools = get_all_tools(mock_kg_instance, mock_config_data, interactive_mode)

        wrapped_hw_tool = self.find_tool_by_name(all_tools, "ssh_execute")
        self.assertIsNotNone(wrapped_hw_tool, "ssh_execute tool not found in registry")

        # Call the wrapped tool
        result = wrapped_hw_tool(node_name="node1", command="ls -l")
        self.assertEqual(result, "Mocked SSH output")

        # Original signature: ssh_execute(node_name: str, command: str, config_data: Dict[str, Any] = None, interactive_mode: bool = False)
        mock_original_hw_tool.assert_called_once_with(
            node_name="node1",
            command="ls -l",
            config_data=mock_config_data,
            interactive_mode=interactive_mode
        )

    # Test for a testing tool, which should not be wrapped by partial for these context args
    @patch('tools.testing.pod_creation.create_test_pod') # Path to the original tool
    def test_get_testing_tool_via_registry(self, mock_original_testing_tool):
        mock_original_testing_tool.return_value = "Mocked test pod creation"

        mock_kg_instance = Mock(spec=KnowledgeGraph)
        mock_config_data = {"test_param": "test_value"}
        interactive_mode = False

        all_tools = get_all_tools(mock_kg_instance, mock_config_data, interactive_mode)

        testing_tool = self.find_tool_by_name(all_tools, "create_test_pod")
        self.assertIsNotNone(testing_tool, "create_test_pod tool not found in registry")
        self.assertFalse(isinstance(testing_tool, functools.partial) and 'config_data' in testing_tool.keywords,
                         "Testing tool should not be partially wrapped with config_data/interactive_mode like others")

        # Call the tool - it should not receive kg_instance, config_data, or interactive_mode from the registry's partial application
        # (unless its original signature happened to include them, which is not the case for these context args)
        result = testing_tool(pod_name="my-test-pod", namespace="test-ns") # Example args
        self.assertEqual(result, "Mocked test pod creation")

        mock_original_testing_tool.assert_called_once_with(pod_name="my-test-pod", namespace="test-ns")


if __name__ == '__main__':
    unittest.main()
