import unittest
from unittest.mock import Mock, patch
import json

# Assuming direct importability as before
from tools.core.knowledge_graph import (
    kg_get_entity_info,
    kg_get_related_entities,
    kg_find_path,
    kg_print_graph,
    _find_node_id # For direct testing if needed and accessible
)
# The KnowledgeGraph class itself would be imported by the module,
# so we primarily mock its instances.

class TestKnowledgeGraphTools(unittest.TestCase):

    def setUp(self):
        self.mock_kg_instance = Mock()
        self.mock_kg_instance.graph = Mock() # Mock the graph attribute
        self.mock_kg_instance.graph.nodes = {} # Mock a nodes dictionary
        self.mock_kg_instance.graph.has_node = Mock(return_value=False)

    # Test _find_node_id directly.
    # _find_node_id is a module-level function, so it can be imported.
    def test_find_node_id_direct_hit(self):
        self.mock_kg_instance.graph.has_node.side_effect = lambda nid: nid == "Pod:my-pod"
        self.mock_kg_instance.graph.nodes = {"Pod:my-pod": {"entity_type": "Pod"}}

        node_id = _find_node_id(self.mock_kg_instance, "Pod", "Pod:my-pod")
        self.assertEqual(node_id, "Pod:my-pod")

    def test_find_node_id_by_name(self):
        self.mock_kg_instance.graph.has_node.return_value = False # Initial direct check fails
        self.mock_kg_instance.graph.nodes = {
            "node1": {"entity_type": "Pod", "name": "my-pod-nginx", "uuid": "uuid1"},
            "node2": {"entity_type": "Service", "name": "my-service"},
        }
        # Configure has_node for potential_node_id check
        self.mock_kg_instance.graph.has_node.side_effect = lambda nid: nid == "Pod:my-pod-nginx" and nid in self.mock_kg_instance.graph.nodes # for specific check

        # Simulate iterating over nodes for the name/uuid check
        # For simplicity, we'll assume _find_node_id correctly iterates.
        # A more robust mock would involve mocking the iteration if graph.nodes(data=True) was complex.
        # Here, we rely on the mock_kg_instance.graph.nodes being a dict for the iteration.

        # Test find by name
        node_id = _find_node_id(self.mock_kg_instance, "Pod", "my-pod-nginx")
        # If the logic first tries "Pod:my-pod-nginx" and has_node is true for it, it might return that.
        # If it iterates, it would find node1. Let's refine the mock for iteration.

        # Reset side_effect for general use in _find_node_id's iteration logic
        self.mock_kg_instance.graph.has_node.return_value = False # For prefixed ID check
        # Ensure iteration works
        self.mock_kg_instance.graph.nodes.items = Mock(return_value=[
            ("node1", {"entity_type": "Pod", "name": "my-pod-nginx", "uuid": "uuid1"}),
            ("node2", {"entity_type": "Service", "name": "my-service"}),
        ])

        node_id_by_name = _find_node_id(self.mock_kg_instance, "Pod", "my-pod-nginx")
        self.assertEqual(node_id_by_name, "node1")

    def test_find_node_id_not_found(self):
        self.mock_kg_instance.graph.has_node.return_value = False
        self.mock_kg_instance.graph.nodes.items = Mock(return_value=[
            ("node1", {"entity_type": "Pod", "name": "another-pod"}),
        ])
        node_id = _find_node_id(self.mock_kg_instance, "Pod", "unknown-pod")
        self.assertIsNone(node_id)

    @patch('tools.core.knowledge_graph._find_node_id')
    def test_kg_get_entity_info_success(self, mock_find_node_id):
        mock_find_node_id.return_value = "Pod:actual-pod-id"
        self.mock_kg_instance.graph.nodes = {
            "Pod:actual-pod-id": {"name": "my-pod", "status": "Running", "entity_type": "Pod"}
        }
        self.mock_kg_instance.graph.in_edges = Mock(return_value=[])
        self.mock_kg_instance.graph.out_edges = Mock(return_value=[])

        result_str = kg_get_entity_info(self.mock_kg_instance, "Pod", "my-pod")
        result_json = json.loads(result_str)

        self.assertEqual(result_json["node_id"], "Pod:actual-pod-id")
        self.assertEqual(result_json["attributes"]["name"], "my-pod")
        mock_find_node_id.assert_called_once_with(self.mock_kg_instance, "Pod", "my-pod")

    @patch('tools.core.knowledge_graph._find_node_id')
    def test_kg_get_entity_info_not_found(self, mock_find_node_id):
        mock_find_node_id.return_value = None
        result_str = kg_get_entity_info(self.mock_kg_instance, "Pod", "unknown-pod")
        result_json = json.loads(result_str)
        self.assertIn("error", result_json)
        self.assertEqual(result_json["error"], "Entity not found: Pod with ID/name 'unknown-pod'")

    def test_kg_print_graph_params_mapping(self):
        # This tests if parameters are passed correctly to the underlying method
        kg_print_graph(self.mock_kg_instance, include_details=True, include_issues=False)
        self.mock_kg_instance.print_graph.assert_called_once_with(
            include_detailed_entities=True,
            include_issues=False,
            include_analysis=True, # This is hardcoded in kg_print_graph
            include_relationships=True # This is hardcoded in kg_print_graph
        )

    # Example for kg_find_path - testing "not found" for one of the entities
    @patch('tools.core.knowledge_graph._find_node_id')
    def test_kg_find_path_source_not_found(self, mock_find_node_id):
        # Simulate source not found, target found
        mock_find_node_id.side_effect = [None, "Service:target-svc-id"]

        result_str = kg_find_path(self.mock_kg_instance, "Pod", "unknown-pod", "Service", "target-svc")
        result_json = json.loads(result_str)

        self.assertIn("error", result_json)
        self.assertEqual(result_json["error"], "Source entity not found: Pod with ID/name 'unknown-pod'")
        mock_find_node_id.assert_any_call(self.mock_kg_instance, "Pod", "unknown-pod")


if __name__ == '__main__':
    unittest.main()
