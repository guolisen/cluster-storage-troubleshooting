import unittest
from unittest.mock import patch, ANY  # ANY is useful for some params

# Assuming direct importability
from tools.kubernetes.core import (
    kubectl_get,
    kubectl_describe,
    kubectl_apply,
    kubectl_delete,
    kubectl_exec,
    kubectl_logs
)
# We will be mocking execute_command from tools.core.config

class TestKubernetesCoreTools(unittest.TestCase):

    def setUp(self):
        self.mock_config_data = {"user": "test_user"}
        self.mock_interactive_mode = False

    @patch('tools.kubernetes.core.execute_command')
    def test_kubectl_get(self, mock_execute_command):
        mock_execute_command.return_value = "kubectl get output"

        result = kubectl_get(
            resource_type="pod",
            resource_name="my-pod",
            namespace="default",
            output_format="json",
            config_data=self.mock_config_data,
            interactive_mode=self.mock_interactive_mode
        )

        self.assertEqual(result, "kubectl get output")
        expected_cmd = ["kubectl", "get", "pod", "my-pod", "-n", "default", "-o", "json"]
        expected_purpose = "Get Kubernetes pod my-pod in namespace default"
        mock_execute_command.assert_called_once_with(
            command_list=expected_cmd,
            config_data=self.mock_config_data,
            interactive_mode=self.mock_interactive_mode,
            purpose=expected_purpose,
            requires_approval=False
        )

    @patch('tools.kubernetes.core.execute_command')
    def test_kubectl_exec_simple_command(self, mock_execute_command):
        mock_execute_command.return_value = "kubectl exec output"
        pod_name = "my-exec-pod"
        namespace = "dev"
        command_args = ["ls", "-l"]

        result = kubectl_exec(
            pod_name=pod_name,
            command_args=command_args,
            namespace=namespace,
            config_data=self.mock_config_data,
            interactive_mode=self.mock_interactive_mode
        )

        self.assertEqual(result, "kubectl exec output")
        expected_cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--"] + command_args
        expected_purpose = f"Execute command in pod {pod_name} in namespace {namespace}"
        mock_execute_command.assert_called_once_with(
            command_list=expected_cmd,
            config_data=self.mock_config_data,
            interactive_mode=self.mock_interactive_mode,
            purpose=expected_purpose,
            requires_approval=False
        )

    @patch('tools.kubernetes.core.execute_command')
    def test_kubectl_exec_command_with_spaces_in_arg(self, mock_execute_command):
        mock_execute_command.return_value = "exec output with spaces"
        pod_name = "another-pod"
        # This is the key part: arguments with spaces should be preserved as single arguments
        command_args = ["echo", "Hello world with spaces", "another arg"]

        kubectl_exec(
            pod_name=pod_name,
            command_args=command_args,
            # namespace not specified
            config_data=self.mock_config_data,
            interactive_mode=self.mock_interactive_mode
        )

        expected_cmd = ["kubectl", "exec", pod_name, "--"] + command_args
        # Purpose will not include namespace here
        expected_purpose = f"Execute command in pod {pod_name}"
        mock_execute_command.assert_called_once_with(
            command_list=expected_cmd,
            config_data=self.mock_config_data,
            interactive_mode=self.mock_interactive_mode,
            purpose=expected_purpose,
            requires_approval=False
        )

    @patch('tools.kubernetes.core.execute_command')
    def test_kubectl_exec_empty_command_args(self, mock_execute_command):
        # This tests the internal check in kubectl_exec for empty command_args
        pod_name = "empty-cmd-pod"
        result = kubectl_exec(
            pod_name=pod_name,
            command_args=[], # Empty command
            namespace="test",
            config_data=self.mock_config_data,
            interactive_mode=self.mock_interactive_mode
        )
        self.assertEqual(result, "Error: No command provided to kubectl_exec.")
        mock_execute_command.assert_not_called() # execute_command should not be called

    @patch('tools.kubernetes.core.subprocess.run')
    def test_kubectl_apply(self, mock_subprocess_run):
        mock_process = Mock()
        mock_process.stdout = "apply successful"
        mock_process.stderr = ""
        mock_process.returncode = 0
        mock_subprocess_run.return_value = mock_process

        yaml_content = "apiVersion: v1\nkind: Pod\nmetadata:\n  name: test-pod"
        namespace = "staging"

        result = kubectl_apply(
            yaml_content=yaml_content,
            namespace=namespace,
            config_data=self.mock_config_data, # These params are now part of signature
            interactive_mode=self.mock_interactive_mode # but not used by its current direct subprocess call
        )

        self.assertEqual(result, "apply successful")
        expected_cmd = ["kubectl", "apply", "-f", "-", "-n", namespace]
        mock_subprocess_run.assert_called_once_with(
            expected_cmd,
            input=yaml_content,
            check=True,
            stdout=unittest.mock.ANY, # Or subprocess.PIPE
            stderr=unittest.mock.ANY, # Or subprocess.PIPE
            text=True
        )

if __name__ == '__main__':
    unittest.main()
