#!/usr/bin/env python3
"""
Knowledge Graph Implementation for Kubernetes Volume Troubleshooting

This module provides NetworkX-based Knowledge Graph functionality to organize
diagnostic data, entities, and relationships for comprehensive root cause analysis
and fix plan generation in the CSI Baremetal driver troubleshooting system.
"""

import logging
import networkx as nx
from typing import Dict, List, Any, Optional, Tuple
import json

# Configure logger for knowledge graph operations
kg_logger = logging.getLogger('knowledge_graph')
kg_logger.setLevel(logging.INFO)
# Don't propagate to root logger to avoid console output
kg_logger.propagate = False


class KnowledgeGraph:
    """
    Knowledge Graph for organizing diagnostic data and relationships
    """
    
    def __init__(self):
        """Initialize the Knowledge Graph"""
        self.graph = nx.DiGraph()
        self.entities = {
            'gnodes': {
                'pods': {},
                'pvcs': {},
                'pvs': {},
                'drives': {},
                'nodes': {},
                'storage_classes': {},
                'lvgs': {},
                'acs': {},
                'volumes': {},
                'system_entities': {},
                'cluster_nodes': {}
            }
        }
        self.issues = []
        kg_logger.info("Knowledge Graph initialized")
    
    def add_gnode_pod(self, name: str, namespace: str, **attributes) -> str:
        """
        Add a Pod node to the knowledge graph
        
        Args:
            name: Pod name
            namespace: Pod namespace
            **attributes: Additional pod attributes (errors, SecurityContext, etc.)
            
        Returns:
            str: Node ID
        """
        node_id = f"gnode:Pod:{namespace}/{name}"
        self.graph.add_node(node_id, 
                           entity_type="gnode",
                           gnode_subtype="Pod",
                           name=name,
                           namespace=namespace,
                           **attributes)
        self.entities['gnodes']['pods'][node_id] = {
            'name': name,
            'namespace': namespace,
            **attributes
        }
        kg_logger.debug(f"Added Pod node: {node_id}")
        return node_id
    
    def add_gnode_pvc(self, name: str, namespace: str, **attributes) -> str:
        """
        Add a PVC node to the knowledge graph
        
        Args:
            name: PVC name
            namespace: PVC namespace
            **attributes: Additional PVC attributes (storageClass, bound PV, etc.)
            
        Returns:
            str: Node ID
        """
        node_id = f"gnode:PVC:{namespace}/{name}"
        self.graph.add_node(node_id,
                           entity_type="gnode",
                           gnode_subtype="PVC",
                           name=name,
                           namespace=namespace,
                           **attributes)
        self.entities['gnodes']['pvcs'][node_id] = {
            'name': name,
            'namespace': namespace,
            **attributes
        }
        kg_logger.debug(f"Added PVC node: {node_id}")
        return node_id
    
    def add_gnode_pv(self, name: str, **attributes) -> str:
        """
        Add a PV node to the knowledge graph
        
        Args:
            name: PV name
            **attributes: Additional PV attributes (diskPath, nodeAffinity, etc.)
            
        Returns:
            str: Node ID
        """
        node_id = f"gnode:PV:{name}"
        self.graph.add_node(node_id,
                           entity_type="gnode",
                           gnode_subtype="PV",
                           name=name,
                           **attributes)
        self.entities['gnodes']['pvs'][node_id] = {
            'name': name,
            **attributes
        }
        kg_logger.debug(f"Added PV node: {node_id}")
        return node_id
    
    def add_gnode_drive(self, uuid: str, **attributes) -> str:
        """
        Add a Drive node to the knowledge graph
        
        Args:
            uuid: Drive UUID
            **attributes: Additional drive attributes (Health, Status, Path, etc.)
            
        Returns:
            str: Node ID
        """
        node_id = f"gnode:Drive:{uuid}"
        self.graph.add_node(node_id,
                           entity_type="gnode",
                           gnode_subtype="Drive",
                           uuid=uuid,
                           **attributes)
        self.entities['gnodes']['drives'][node_id] = {
            'uuid': uuid,
            **attributes
        }
        kg_logger.debug(f"Added Drive node: {node_id}")
        return node_id
    
    def add_gnode_node(self, name: str, **attributes) -> str:
        """
        Add a Node node to the knowledge graph
        
        Args:
            name: Node name
            **attributes: Additional node attributes (Ready, DiskPressure, etc.)
            
        Returns:
            str: Node ID
        """
        node_id = f"gnode:Node:{name}"
        self.graph.add_node(node_id,
                           entity_type="gnode",
                           gnode_subtype="Node",
                           name=name,
                           **attributes)
        self.entities['gnodes']['nodes'][node_id] = {
            'name': name,
            **attributes
        }
        kg_logger.debug(f"Added Node node: {node_id}")
        return node_id
    
    def add_gnode_storage_class(self, name: str, **attributes) -> str:
        """
        Add a StorageClass node to the knowledge graph
        
        Args:
            name: StorageClass name
            **attributes: Additional storage class attributes (provisioner, etc.)
            
        Returns:
            str: Node ID
        """
        node_id = f"gnode:StorageClass:{name}"
        self.graph.add_node(node_id,
                           entity_type="gnode",
                           gnode_subtype="StorageClass",
                           name=name,
                           **attributes)
        self.entities['gnodes']['storage_classes'][node_id] = {
            'name': name,
            **attributes
        }
        kg_logger.debug(f"Added StorageClass node: {node_id}")
        return node_id
    
    def add_gnode_lvg(self, name: str, **attributes) -> str:
        """
        Add a LogicalVolumeGroup node to the knowledge graph
        
        Args:
            name: LVG name
            **attributes: Additional LVG attributes (Health, drive UUIDs, etc.)
            
        Returns:
            str: Node ID
        """
        node_id = f"gnode:LVG:{name}"
        self.graph.add_node(node_id,
                           entity_type="gnode",
                           gnode_subtype="LVG",
                           name=name,
                           **attributes)
        self.entities['gnodes']['lvgs'][node_id] = {
            'name': name,
            **attributes
        }
        kg_logger.debug(f"Added LVG node: {node_id}")
        return node_id
    
    def add_gnode_ac(self, name: str, **attributes) -> str:
        """
        Add an AvailableCapacity node to the knowledge graph
        
        Args:
            name: AC name
            **attributes: Additional AC attributes (size, storage class, location, etc.)
            
        Returns:
            str: Node ID
        """
        node_id = f"gnode:AC:{name}"
        self.graph.add_node(node_id,
                           entity_type="gnode",
                           gnode_subtype="AC",
                           name=name,
                           **attributes)
        self.entities['gnodes']['acs'][node_id] = {
            'name': name,
            **attributes
        }
        kg_logger.debug(f"Added AC node: {node_id}")
        return node_id
    
    def add_gnode_volume(self, name: str, namespace: str, **attributes) -> str:
        """
        Add a Volume node to the knowledge graph
        
        Args:
            name: Volume name
            namespace: Volume namespace
            **attributes: Additional volume attributes (Health, LocationType, size, storage class, location, Usage, etc.)
            
        Returns:
            str: Node ID
        """
        node_id = f"gnode:Volume:{namespace}/{name}"
        self.graph.add_node(node_id,
                           entity_type="gnode",
                           gnode_subtype="Volume",
                           name=name,
                           namespace=namespace,
                           **attributes)
        self.entities['gnodes']['volumes'][node_id] = {
            'name': name,
            'namespace': namespace,
            **attributes
        }
        kg_logger.debug(f"Added Volume node: {node_id}")
        return node_id
    
    def add_gnode_system_entity(self, entity_name: str, entity_subtype: str, **attributes) -> str:
        """
        Add a System entity node to the knowledge graph (for logs, kernel, services, etc.)
        
        Args:
            entity_name: System entity name (e.g., "kernel", "kubelet", "boot")
            entity_subtype: System entity subtype (e.g., "logs", "service", "hardware")
            **attributes: Additional system entity attributes
            
        Returns:
            str: Node ID
        """
        node_id = f"gnode:System:{entity_name}"
        self.graph.add_node(node_id,
                           entity_type="gnode",
                           gnode_subtype="System",
                           name=entity_name,
                           subtype=entity_subtype,
                           **attributes)
        self.entities['gnodes']['system_entities'][node_id] = {
            'name': entity_name,
            'subtype': entity_subtype,
            **attributes
        }
        kg_logger.debug(f"Added System entity node: {node_id}")
        return node_id

    def add_gnode_cluster_node(self, name: str, **attributes) -> str:
        """
        Add a ClusterNode node to the knowledge graph
        
        Args:
            name: ClusterNode name
            **attributes: Additional cluster node attributes
            
        Returns:
            str: Node ID
        """
        node_id = f"gnode:ClusterNode:{name}"
        self.graph.add_node(node_id,
                           entity_type="gnode",
                           gnode_subtype="ClusterNode",
                           name=name,
                           **attributes)
        self.entities['gnodes']['cluster_nodes'][node_id] = {
            'name': name,
            **attributes
        }
        kg_logger.debug(f"Added ClusterNode node: {node_id}")
        return node_id
    
    def add_relationship(self, source_id: str, target_id: str, relationship: str, **attributes):
        """
        Add a relationship edge between two nodes
        
        Args:
            source_id: Source node ID
            target_id: Target node ID
            relationship: Type of relationship
            **attributes: Additional edge attributes
        """
        self.graph.add_edge(source_id, target_id,
                           relationship=relationship,
                           **attributes)
        kg_logger.debug(f"Added relationship: {source_id} --{relationship}--> {target_id}")
    
    def add_issue(self, node_id: str, issue_type: str, description: str, severity: str = "medium"):
        """
        Add an issue to a node and the issues list
        
        Args:
            node_id: Node ID where the issue was found
            issue_type: Type of issue (e.g., "permission", "disk_health", "configuration")
            description: Description of the issue
            severity: Issue severity (low, medium, high, critical)
        """
        issue = {
            'node_id': node_id,
            'type': issue_type,
            'description': description,
            'severity': severity
        }
        
        # Add to issues list
        self.issues.append(issue)
        
        # Add to node attributes
        if self.graph.has_node(node_id):
            current_issues = self.graph.nodes[node_id].get('issues', [])
            current_issues.append(issue)
            self.graph.nodes[node_id]['issues'] = current_issues
        
        kg_logger.info(f"Added {severity} severity issue to {node_id}: {description}")
    
    def get_issues_by_severity(self, severity: str) -> List[Dict]:
        """
        Get all issues of a specific severity
        
        Args:
            severity: Issue severity to filter by
            
        Returns:
            List[Dict]: List of issues
        """
        return [issue for issue in self.issues if issue['severity'] == severity]
    
    def get_all_issues(self) -> List[Dict]:
        """
        Get all issues sorted by severity
        
        Returns:
            List[Dict]: List of all issues sorted by severity
        """
        severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        return sorted(self.issues, key=lambda x: severity_order.get(x['severity'], 4))
    
    def find_nodes_by_type(self, gnode_subtype: str) -> List[str]:
        """
        Find all nodes of a specific gnode subtype
        
        Args:
            gnode_subtype: Subtype of gnode to find
            
        Returns:
            List[str]: List of node IDs
        """
        return [node_id for node_id, attrs in self.graph.nodes(data=True) 
                if attrs.get('entity_type') == 'gnode' and attrs.get('gnode_subtype') == gnode_subtype]
    
    def find_connected_nodes(self, node_id: str, relationship: str = None) -> List[str]:
        """
        Find nodes connected to a given node
        
        Args:
            node_id: Source node ID
            relationship: Optional relationship type to filter by
            
        Returns:
            List[str]: List of connected node IDs
        """
        connected = []
        if self.graph.has_node(node_id):
            for target in self.graph.successors(node_id):
                edge_data = self.graph.edges[node_id, target]
                if relationship is None or edge_data.get('relationship') == relationship:
                    connected.append(target)
        return connected
    
    def find_path(self, source_id: str, target_id: str) -> Optional[List[str]]:
        """
        Find the shortest path between two nodes
        
        Args:
            source_id: Source node ID
            target_id: Target node ID
            
        Returns:
            Optional[List[str]]: Path as list of node IDs, or None if no path exists
        """
        try:
            return nx.shortest_path(self.graph, source_id, target_id)
        except nx.NetworkXNoPath:
            return None
    
    def analyze_issues(self) -> Dict[str, Any]:
        """
        Analyze issues in the knowledge graph to identify patterns and root causes
        
        Returns:
            Dict[str, Any]: Analysis results
        """
        analysis = {
            'total_issues': len(self.issues),
            'issues_by_severity': {},
            'issues_by_type': {},
            'affected_entities': {},
            'potential_root_causes': [],
            'issue_patterns': []
        }
        
        # Count issues by severity
        for severity in ['critical', 'high', 'medium', 'low']:
            analysis['issues_by_severity'][severity] = len(self.get_issues_by_severity(severity))
        
        # Count issues by type
        for issue in self.issues:
            issue_type = issue['type']
            analysis['issues_by_type'][issue_type] = analysis['issues_by_type'].get(issue_type, 0) + 1
        
        # Count affected entities by type
        for issue in self.issues:
            node_id = issue['node_id']
            if self.graph.has_node(node_id):
                entity_type = self.graph.nodes[node_id].get('entity_type', 'unknown')
                analysis['affected_entities'][entity_type] = analysis['affected_entities'].get(entity_type, 0) + 1
        
        # Identify potential root causes
        analysis['potential_root_causes'] = self._identify_root_causes()
        
        # Identify issue patterns
        analysis['issue_patterns'] = self._identify_patterns()
        
        kg_logger.info(f"Knowledge Graph analysis completed: {analysis['total_issues']} issues found")
        return analysis
    
    def _identify_root_causes(self) -> List[Dict]:
        """
        Identify potential root causes based on graph topology and issue patterns
        
        Returns:
            List[Dict]: List of potential root causes
        """
        root_causes = []
        
        # Check for drive health issues
        for drive_id in self.find_nodes_by_type('Drive'):
            drive_attrs = self.graph.nodes[drive_id]
            if drive_attrs.get('Health') in ['SUSPECT', 'BAD']:
                # Find all affected pods through the chain: Drive -> PV -> PVC -> Pod
                affected_pods = self._trace_drive_to_pods(drive_id)
                root_causes.append({
                    'type': 'disk_health',
                    'severity': 'high',
                    'source': drive_id,
                    'description': f"Drive {drive_attrs.get('uuid', 'unknown')} has health status: {drive_attrs.get('Health')}",
                    'affected_pods': affected_pods
                })
        
        # Check for node issues
        for node_id in self.find_nodes_by_type('Node'):
            node_attrs = self.graph.nodes[node_id]
            if not node_attrs.get('Ready', True) or node_attrs.get('DiskPressure', False):
                affected_pods = self._trace_node_to_pods(node_id)
                root_causes.append({
                    'type': 'node_health',
                    'severity': 'high',
                    'source': node_id,
                    'description': f"Node {node_attrs.get('name')} has issues: Ready={node_attrs.get('Ready')}, DiskPressure={node_attrs.get('DiskPressure')}",
                    'affected_pods': affected_pods
                })
        
        # Check for permission issues
        permission_issues = [issue for issue in self.issues if issue['type'] == 'permission']
        if permission_issues:
            root_causes.append({
                'type': 'permission',
                'severity': 'medium',
                'source': 'multiple',
                'description': f"Found {len(permission_issues)} permission-related issues",
                'issues': permission_issues
            })
        
        return root_causes
    
    def _identify_patterns(self) -> List[Dict]:
        """
        Identify patterns in issues across the graph
        
        Returns:
            List[Dict]: List of identified patterns
        """
        patterns = []
        
        # Pattern: Multiple pods affected by same drive
        drive_to_pods = {}
        for pod_id in self.find_nodes_by_type('Pod'):
            drives = self._trace_pod_to_drives(pod_id)
            for drive_id in drives:
                if drive_id not in drive_to_pods:
                    drive_to_pods[drive_id] = []
                drive_to_pods[drive_id].append(pod_id)
        
        for drive_id, pod_ids in drive_to_pods.items():
            if len(pod_ids) > 1:
                patterns.append({
                    'type': 'multiple_pods_same_drive',
                    'description': f"Multiple pods ({len(pod_ids)}) using the same drive",
                    'drive': drive_id,
                    'pods': pod_ids
                })
        
        # Pattern: Same error across multiple pods
        error_to_pods = {}
        for issue in self.issues:
            if issue['type'] == 'pod_error':
                error_desc = issue['description']
                if error_desc not in error_to_pods:
                    error_to_pods[error_desc] = []
                error_to_pods[error_desc].append(issue['node_id'])
        
        for error_desc, pod_ids in error_to_pods.items():
            if len(pod_ids) > 1:
                patterns.append({
                    'type': 'same_error_multiple_pods',
                    'description': f"Same error across {len(pod_ids)} pods: {error_desc}",
                    'pods': pod_ids
                })
        
        return patterns
    
    def _trace_drive_to_pods(self, drive_id: str) -> List[str]:
        """
        Trace from a drive to all pods that use it
        
        Args:
            drive_id: Drive node ID
            
        Returns:
            List[str]: List of pod node IDs
        """
        pods = []
        
        # Find PVs that map to this drive
        for pv_id in self.find_nodes_by_type('PV'):
            if drive_id in self.find_connected_nodes(pv_id, 'maps_to'):
                # Find PVCs bound to this PV
                for pvc_id in self.find_nodes_by_type('PVC'):
                    if pv_id in self.find_connected_nodes(pvc_id, 'bound_to'):
                        # Find pods that use this PVC
                        for pod_id in self.find_nodes_by_type('Pod'):
                            if pvc_id in self.find_connected_nodes(pod_id, 'uses'):
                                pods.append(pod_id)
        
        return pods
    
    def _trace_pod_to_drives(self, pod_id: str) -> List[str]:
        """
        Trace from a pod to all drives it uses
        
        Args:
            pod_id: Pod node ID
            
        Returns:
            List[str]: List of drive node IDs
        """
        drives = []
        
        # Find PVCs used by this pod
        pvc_ids = self.find_connected_nodes(pod_id, 'uses')
        for pvc_id in pvc_ids:
            # Find PVs bound to these PVCs
            pv_ids = self.find_connected_nodes(pvc_id, 'bound_to')
            for pv_id in pv_ids:
                # Find drives mapped to these PVs
                drive_ids = self.find_connected_nodes(pv_id, 'maps_to')
                drives.extend(drive_ids)
        
        return drives
    
    def _trace_node_to_pods(self, node_id: str) -> List[str]:
        """
        Trace from a node to all pods scheduled on it
        
        Args:
            node_id: Node node ID
            
        Returns:
            List[str]: List of pod node IDs
        """
        pods = []
        
        # Find pods with affinity to this node
        for pod_id in self.find_nodes_by_type('Pod'):
            pod_attrs = self.graph.nodes[pod_id]
            if pod_attrs.get('node_name') == self.graph.nodes[node_id].get('name'):
                pods.append(pod_id)
        
        return pods
    
    def generate_fix_plan(self, analysis: Dict[str, Any]) -> List[Dict]:
        """
        Generate a prioritized fix plan based on graph analysis
        
        Args:
            analysis: Analysis results from analyze_issues()
            
        Returns:
            List[Dict]: Prioritized list of fix actions
        """
        fix_plan = []
        
        # Process root causes by severity
        root_causes = sorted(analysis['potential_root_causes'], 
                           key=lambda x: {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}.get(x['severity'], 4))
        
        for root_cause in root_causes:
            if root_cause['type'] == 'disk_health':
                fix_plan.append({
                    'step': len(fix_plan) + 1,
                    'type': 'disk_replacement',
                    'priority': 'high',
                    'description': f"Replace unhealthy drive: {root_cause['description']}",
                    'actions': [
                        'Backup data from affected volumes',
                        'Drain affected pods',
                        'Replace the faulty drive',
                        'Restore data and reschedule pods'
                    ],
                    'affected_entities': root_cause.get('affected_pods', [])
                })
            
            elif root_cause['type'] == 'node_health':
                fix_plan.append({
                    'step': len(fix_plan) + 1,
                    'type': 'node_remediation',
                    'priority': 'high',
                    'description': f"Fix node issues: {root_cause['description']}",
                    'actions': [
                        'Investigate node health issues',
                        'Clear disk pressure if present',
                        'Restart node services if needed',
                        'Verify node readiness'
                    ],
                    'affected_entities': root_cause.get('affected_pods', [])
                })
            
            elif root_cause['type'] == 'permission':
                fix_plan.append({
                    'step': len(fix_plan) + 1,
                    'type': 'permission_fix',
                    'priority': 'medium',
                    'description': f"Fix permission issues: {root_cause['description']}",
                    'actions': [
                        'Update Pod SecurityContext',
                        'Verify filesystem permissions',
                        'Restart affected pods'
                    ],
                    'affected_entities': [issue['node_id'] for issue in root_cause.get('issues', [])]
                })
        
        # Add pattern-based fixes
        for pattern in analysis['issue_patterns']:
            if pattern['type'] == 'multiple_pods_same_drive':
                fix_plan.append({
                    'step': len(fix_plan) + 1,
                    'type': 'resource_optimization',
                    'priority': 'low',
                    'description': f"Optimize resource usage: {pattern['description']}",
                    'actions': [
                        'Consider distributing pods across multiple drives',
                        'Monitor drive performance and capacity'
                    ],
                    'affected_entities': pattern['pods']
                })
        
        kg_logger.info(f"Generated fix plan with {len(fix_plan)} steps")
        return fix_plan
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the knowledge graph
        
        Returns:
            Dict[str, Any]: Summary information
        """
        summary = {
            'total_nodes': self.graph.number_of_nodes(),
            'total_edges': self.graph.number_of_edges(),
            'entity_counts': {},
            'total_issues': len(self.issues),
            'critical_issues': len(self.get_issues_by_severity('critical')),
            'high_issues': len(self.get_issues_by_severity('high')),
            'medium_issues': len(self.get_issues_by_severity('medium')),
            'low_issues': len(self.get_issues_by_severity('low'))
        }
        
        # Count entities by type
        for entity_type in ['Pod', 'PVC', 'PV', 'Drive', 'Node', 'StorageClass', 'LVG', 'AC', 'Volume', 'System', 'ClusterNode']:
            summary['entity_counts'][entity_type] = len(self.find_nodes_by_type(entity_type))
        
        return summary
    
    def print_graph(self, include_detailed_entities: bool = True, include_relationships: bool = True, 
                   include_issues: bool = True, include_analysis: bool = True,
                   use_rich: bool = True) -> str:
        """
        Print the knowledge graph in a nice formatted way
        
        Args:
            include_detailed_entities: Whether to include detailed entity information
            include_relationships: Whether to include relationship details
            include_issues: Whether to include issues breakdown
            include_analysis: Whether to include analysis and patterns
            use_rich: Whether to use rich formatting for enhanced visual output
            
        Returns:
            str: Formatted graph representation
        """
        # Import rich components if available
        try:
            from rich.console import Console
            from rich.panel import Panel
            from rich.table import Table
            from rich.tree import Tree
            from rich import print as rprint
            rich_available = True
        except ImportError:
            rich_available = False
            use_rich = False
            
        # Create console for rich output
        if use_rich and rich_available:
            console = Console(record=True)
            file_console = Console(file=open('troubleshoot.log', 'a'))
        
        output = []
        
        # Header
        if use_rich and rich_available:
            console.print(Panel(
                "[bold cyan]📊 KUBERNETES STORAGE KNOWLEDGE GRAPH[/bold cyan]",
                border_style="blue",
                width=80
            ))
        else:
            output.append("=" * 80)
            output.append("📊 KUBERNETES STORAGE KNOWLEDGE GRAPH")
            output.append("=" * 80)
        
        # Summary Statistics
        summary = self.get_summary()
        if use_rich and rich_available:
            # Create summary table
            summary_table = Table(
                title="[bold]🔍 GRAPH SUMMARY",
                show_header=True,
                header_style="bold cyan",
                box=True,
                border_style="blue"
            )
            
            summary_table.add_column("Metric", style="dim")
            summary_table.add_column("Value", justify="right")
            
            def safe_format(value: Any) -> str:
                """Safely convert any value to a string for rich formatting"""
                try:
                    # Explicitly handle boolean values first
                    if isinstance(value, bool):
                        return "True" if value else "False"
                    # For all other types, convert to string
                    return str(value)
                except Exception:
                    return "N/A"

            summary_table.add_row("Total Nodes", f"[blue]{safe_format(summary['total_nodes'])}[/blue]")
            summary_table.add_row("Total Edges", f"[blue]{safe_format(summary['total_edges'])}[/blue]")
            summary_table.add_row("Total Issues", f"[yellow]{safe_format(summary['total_issues'])}[/yellow]")
            summary_table.add_row("Critical Issues", f"[red]{safe_format(summary['critical_issues'])}[/red]")
            summary_table.add_row("High Issues", f"[orange3]{safe_format(summary['high_issues'])}[/orange3]")
            summary_table.add_row("Medium Issues", f"[yellow]{safe_format(summary['medium_issues'])}[/yellow]")
            summary_table.add_row("Low Issues", f"[green]{safe_format(summary['low_issues'])}[/green]")
            
            try:
                console.print(summary_table)
            except Exception as e:
                kg_logger.error(f"Error printing rich summary table: {e}")
                # Fallback to plain text
                output.append("\n🔍 GRAPH SUMMARY:")
                output.append("-" * 40)
                output.append(f"📦 Total Nodes: {summary['total_nodes']}")
                output.append(f"🔗 Total Edges: {summary['total_edges']}")
                output.append(f"⚠️  Total Issues: {summary['total_issues']}")
                output.append(f"🔴 Critical Issues: {summary['critical_issues']}")
                output.append(f"🟠 High Issues: {summary['high_issues']}")
                output.append(f"🟡 Medium Issues: {summary['medium_issues']}")
                output.append(f"🟢 Low Issues: {summary['low_issues']}")
        else:
            output.append("\n🔍 GRAPH SUMMARY:")
            output.append("-" * 40)
            output.append(f"📦 Total Nodes: {summary['total_nodes']}")
            output.append(f"🔗 Total Edges: {summary['total_edges']}")
            output.append(f"⚠️  Total Issues: {summary['total_issues']}")
            output.append(f"🔴 Critical Issues: {summary['critical_issues']}")
            output.append(f"🟠 High Issues: {summary['high_issues']}")
            output.append(f"🟡 Medium Issues: {summary['medium_issues']}")
            output.append(f"🟢 Low Issues: {summary['low_issues']}")
        
        # Entity Breakdown
        output.append("\n📋 ENTITY BREAKDOWN:")
        output.append("-" * 40)
        entity_icons = {
            'Pod': '🚀',
            'PVC': '💾',
            'PV': '🗃️',
            'Drive': '💿',
            'Node': '🖥️',
            'StorageClass': '📁',
            'LVG': '📚',
            'AC': '🏪',
            'Volume': '📦',
            'System': '⚙️',
            'ClusterNode': '🌐'
        }
        
        for entity_type, count in summary['entity_counts'].items():
            if count > 0:
                icon = entity_icons.get(entity_type, '📄')
                output.append(f"{icon} {entity_type}: {count}")
        
        # Detailed Entity Information
        if include_detailed_entities and summary['total_nodes'] > 0:
            output.append("\n🔎 DETAILED ENTITIES:")
            output.append("-" * 40)
            
            for entity_type in ['Pod', 'PVC', 'PV', 'Drive', 'Node', 'StorageClass', 'LVG', 'AC', 'Volume', 'System', 'ClusterNode']:
                nodes = self.find_nodes_by_type(entity_type)
                if nodes:
                    icon = entity_icons.get(entity_type, '📄')
                    output.append(f"\n{icon} {entity_type}s:")
                    for node_id in nodes[:5]:  # Limit to first 5 to avoid too much output
                        node_attrs = self.graph.nodes[node_id]
                        name = node_attrs.get('name', node_attrs.get('uuid', 'unknown'))
                        
                        # Add status indicators
                        status_indicators = []
                        if entity_type == 'Drive':
                            health = node_attrs.get('Health', 'UNKNOWN')
                            if health == 'GOOD':
                                status_indicators.append('✅ Healthy')
                            elif health in ['SUSPECT', 'BAD']:
                                status_indicators.append(f'❌ {health}')
                            else:
                                status_indicators.append(f'❓ {health}')
                        elif entity_type == 'Node':
                            if node_attrs.get('Ready', True):
                                status_indicators.append('✅ Ready')
                            else:
                                status_indicators.append('❌ Not Ready')
                            if node_attrs.get('DiskPressure', False):
                                status_indicators.append('⚠️ Disk Pressure')
                        elif entity_type == 'Pod':
                            if 'issues' in node_attrs and node_attrs['issues']:
                                status_indicators.append(f"⚠️ {len(node_attrs['issues'])} issues")
                        elif entity_type == 'Volume':
                            health = node_attrs.get('Health', 'UNKNOWN')
                            if health == 'GOOD':
                                status_indicators.append('✅ Healthy')
                            elif health in ['SUSPECT', 'BAD']:
                                status_indicators.append(f'❌ {health}')
                            usage = node_attrs.get('Usage', 'UNKNOWN')
                            if usage:
                                status_indicators.append(f'📊 {usage}')
                        elif entity_type == 'System':
                            subtype = node_attrs.get('subtype', 'unknown')
                            status_indicators.append(f'🔧 {subtype}')
                            if 'issues' in node_attrs and node_attrs['issues']:
                                status_indicators.append(f"⚠️ {len(node_attrs['issues'])} issues")
                        
                        status_str = ' | '.join(status_indicators) if status_indicators else '⚪ No status'
                        output.append(f"  • {name} - {status_str}")
                    
                    if len(nodes) > 5:
                        output.append(f"  ... and {len(nodes) - 5} more")
        
        # Relationships
        if include_relationships and self.graph.number_of_edges() > 0:
            output.append("\n🔗 KEY RELATIONSHIPS:")
            output.append("-" * 40)
            
            relationship_counts = {}
            for u, v, data in self.graph.edges(data=True):
                rel_type = data.get('relationship', 'unknown')
                relationship_counts[rel_type] = relationship_counts.get(rel_type, 0) + 1
            
            for rel_type, count in sorted(relationship_counts.items()):
                rel_icon = {
                    'uses': '🔄',
                    'bound_to': '🔗',
                    'maps_to': '📍',
                    'affinity_to': '🎯',
                    'uses_storage_class': '📂',
                    'contains': '📦',
                    'located_on': '🏠',
                    'available_on': '🏪',
                    'monitors': '👁️'
                }.get(rel_type, '↔️')
                output.append(f"{rel_icon} {rel_type}: {count} connections")
            
            # Show Volume→Storage relationships specifically
            volume_relationships = []
            for volume_id in self.find_nodes_by_type('Volume'):
                volume_name = self.graph.nodes[volume_id].get('name', volume_id.split(':')[-1])
                
                # Find direct Drive connections
                for drive_id in self.find_connected_nodes(volume_id, 'bound_to'):
                    if drive_id.startswith('Drive:'):
                        drive_uuid = drive_id.split(':')[-1][:8] + "..."  # Truncate UUID for display
                        volume_relationships.append(f"📦 {volume_name} → 💿 {drive_uuid}")
                
                # Find LVG connections
                for lvg_id in self.find_connected_nodes(volume_id, 'bound_to'):
                    if lvg_id.startswith('LVG:'):
                        lvg_name = lvg_id.split(':')[-1][:8] + "..."  # Truncate UUID for display
                        volume_relationships.append(f"📦 {volume_name} → 📚 {lvg_name}")
            
            if volume_relationships:
                output.append("\n📦 Volume→Storage Relationships:")
                for rel in volume_relationships[:5]:  # Show first 5
                    output.append(f"  • {rel}")
                if len(volume_relationships) > 5:
                    output.append(f"  ... and {len(volume_relationships) - 5} more")
            
            # Show some example relationships
            output.append("\n📝 Example Relationships:")
            shown_relationships = 0
            for u, v, data in self.graph.edges(data=True):
                if shown_relationships >= 5:  # Limit examples
                    break
                rel_type = data.get('relationship', 'unknown')
                u_name = self.graph.nodes[u].get('name', u.split(':')[-1])
                v_name = self.graph.nodes[v].get('name', v.split(':')[-1])
                output.append(f"  • {u_name} --{rel_type}--> {v_name}")
                shown_relationships += 1
        
        # Issues Breakdown
        if include_issues and self.issues:
            output.append("\n⚠️  ISSUES BREAKDOWN:")
            output.append("-" * 40)
            
            issues_by_severity = {
                'critical': [i for i in self.issues if i['severity'] == 'critical'],
                'high': [i for i in self.issues if i['severity'] == 'high'],
                'medium': [i for i in self.issues if i['severity'] == 'medium'],
                'low': [i for i in self.issues if i['severity'] == 'low']
            }
            
            severity_icons = {
                'critical': '🔴',
                'high': '🟠',
                'medium': '🟡',
                'low': '🟢'
            }
            
            for severity, issues_list in issues_by_severity.items():
                if issues_list:
                    icon = severity_icons[severity]
                    output.append(f"\n{icon} {severity.upper()} Issues ({len(issues_list)}):")
                    for issue in issues_list[:3]:  # Show first 3 issues per severity
                        node_name = self.graph.nodes[issue['node_id']].get('name', issue['node_id'].split(':')[-1])
                        output.append(f"  • {node_name}: {issue['description']}")
                    if len(issues_list) > 3:
                        output.append(f"  ... and {len(issues_list) - 3} more")
        
        # Analysis and Patterns
        if include_analysis:
            try:
                analysis = self.analyze_issues()
                
                if analysis['potential_root_causes']:
                    output.append("\n🎯 ROOT CAUSE ANALYSIS:")
                    output.append("-" * 40)
                    for i, cause in enumerate(analysis['potential_root_causes'][:3], 1):
                        severity_icon = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢'}.get(cause['severity'], '⚪')
                        output.append(f"{i}. {severity_icon} {cause['type'].upper()}")
                        output.append(f"   📝 {cause['description']}")
                        if 'affected_pods' in cause and cause['affected_pods']:
                            output.append(f"   🎯 Affects {len(cause['affected_pods'])} pod(s)")
                
                if analysis['issue_patterns']:
                    output.append("\n🔍 DETECTED PATTERNS:")
                    output.append("-" * 40)
                    for pattern in analysis['issue_patterns'][:3]:
                        pattern_icon = {
                            'multiple_pods_same_drive': '💿',
                            'same_error_multiple_pods': '🔄'
                        }.get(pattern['type'], '🔍')
                        output.append(f"{pattern_icon} {pattern['description']}")
                
            except Exception as e:
                output.append(f"\n⚠️  Analysis Error: {str(e)}")
        
        # Footer
        output.append("\n" + "=" * 80)
        
        formatted_output = '\n'.join(output)
        
        # Also log the formatted output
        kg_logger.info("Knowledge Graph formatted output generated")
        
        return formatted_output
    
    def export_graph(self, format: str = 'json') -> str:
        """
        Export the knowledge graph in the specified format
        
        Args:
            format: Export format ('json', 'yaml', etc.)
            
        Returns:
            str: Serialized graph data
        """
        if format == 'json':
            graph_data = {
                'nodes': dict(self.graph.nodes(data=True)),
                'edges': [{'source': u, 'target': v, 'attributes': d} 
                         for u, v, d in self.graph.edges(data=True)],
                'issues': self.issues,
                'summary': self.get_summary()
            }
            return json.dumps(graph_data, indent=2, default=str)
        else:
            raise ValueError(f"Unsupported export format: {format}")
