import unittest
from unittest.mock import patch, Mock
import logging

# Assuming tools.core.config can be imported this way.
# If the structure is /app/tools/core/config.py, then Python's import resolution
# might require adjusting PYTHONPATH or using relative imports if these tests are part of a package.
# For this context, I'll assume direct importability.
from tools.core.config import validate_command, execute_command

# Disable logging for tests unless specifically testing log output
logging.disable(logging.CRITICAL)

class TestValidateCommand(unittest.TestCase):
    def test_empty_command_list(self):
        is_valid, reason = validate_command([], {}, False)
        self.assertFalse(is_valid)
        self.assertEqual(reason, "Empty command list")

    def test_no_restrictions(self):
        config = {"commands": {}}
        is_valid, reason = validate_command(["ls", "-l"], config, False)
        self.assertTrue(is_valid)
        self.assertEqual(reason, "No allowed list specified - command permitted")

    def test_allowed_command(self):
        config = {"commands": {"allowed": ["ls *"]}}
        is_valid, reason = validate_command(["ls", "-l"], config, False)
        self.assertTrue(is_valid)
        self.assertEqual(reason, "Command matches allowed pattern: ls *")

    def test_disallowed_command(self):
        config = {"commands": {"disallowed": ["rm *"]}}
        is_valid, reason = validate_command(["rm", "-rf", "/"], config, False)
        self.assertFalse(is_valid)
        self.assertEqual(reason, "Command matches disallowed pattern: rm *")

    def test_allowed_takes_precedence_over_implicit_deny(self):
        config = {"commands": {"allowed": ["cat *"], "disallowed": ["rm *"]}}
        is_valid, reason = validate_command(["cat", "file.txt"], config, False)
        self.assertTrue(is_valid)
        self.assertEqual(reason, "Command matches allowed pattern: cat *")

    def test_disallowed_takes_precedence_over_allowed(self):
        # This depends on the implementation detail: disallowed is checked first.
        config = {"commands": {"allowed": ["sudo *"], "disallowed": ["sudo rm *"]}}
        is_valid, reason = validate_command(["sudo", "rm", "-rf"], config, False)
        self.assertFalse(is_valid)
        self.assertEqual(reason, "Command matches disallowed pattern: sudo rm *")

    def test_command_not_in_allowed_list(self):
        config = {"commands": {"allowed": ["ls *", "grep *"]}}
        is_valid, reason = validate_command(["cat", "file.txt"], config, False)
        self.assertFalse(is_valid)
        self.assertEqual(reason, "Command does not match any allowed pattern")

    def test_config_data_is_none(self):
        # As per current implementation, config_data=None is an error
        is_valid, reason = validate_command(["ls"], None, False)
        self.assertFalse(is_valid)
        self.assertEqual(reason, "Configuration data not provided")


class TestExecuteCommand(unittest.TestCase):
    def setUp(self):
        self.config_data = {} # Dummy config
        self.command_list = ["echo", "hello"]
        self.purpose = "Test purpose"

    @patch('tools.core.config.subprocess.run')
    def test_successful_execution(self, mock_run):
        mock_process = Mock()
        mock_process.stdout = "hello world"
        mock_process.stderr = ""
        mock_process.returncode = 0
        mock_run.return_value = mock_process

        output = execute_command(self.command_list, self.config_data, False, self.purpose, requires_approval=False)
        self.assertEqual(output, "hello world")
        mock_run.assert_called_once_with(self.command_list, shell=False, check=True, stdout=unittest.mock.ANY, stderr=unittest.mock.ANY, universal_newlines=True)

    @patch('tools.core.config.subprocess.run')
    def test_called_process_error(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(1, self.command_list, stderr="Test error")
        output = execute_command(self.command_list, self.config_data, False, self.purpose, requires_approval=False)
        self.assertTrue(output.startswith("Error: Command failed with exit code 1: Test error"))

    @patch('tools.core.config.subprocess.run')
    def test_file_not_found_error(self, mock_run):
        mock_run.side_effect = FileNotFoundError("No such file")
        output = execute_command(["nonexistentcmd"], self.config_data, False, self.purpose, requires_approval=False)
        self.assertTrue(output.startswith("Error: Command not found: nonexistentcmd"))

    @patch('tools.core.config.logging.info')
    @patch('tools.core.config.subprocess.run')
    def test_logging_purpose(self, mock_run, mock_logging_info):
        mock_process = Mock(stdout="output", returncode=0)
        mock_run.return_value = mock_process

        execute_command(self.command_list, self.config_data, False, self.purpose, requires_approval=False)
        mock_logging_info.assert_any_call(f"Executing command for purpose '{self.purpose}': {' '.join(self.command_list)}")

    @patch('tools.core.config.builtins.input')
    @patch('tools.core.config.subprocess.run')
    def test_approval_yes(self, mock_run, mock_input):
        mock_input.return_value = "yes"
        mock_process = Mock(stdout="approved", returncode=0)
        mock_run.return_value = mock_process

        output = execute_command(self.command_list, self.config_data, True, self.purpose, requires_approval=True)
        self.assertEqual(output, "approved")
        mock_input.assert_called_once()

    @patch('tools.core.config.builtins.input')
    @patch('tools.core.config.subprocess.run')
    def test_approval_no(self, mock_run, mock_input):
        mock_input.return_value = "no"
        output = execute_command(self.command_list, self.config_data, True, self.purpose, requires_approval=True)
        self.assertEqual(output, "Error: Command execution cancelled by user.")
        mock_run.assert_not_called()

    @patch('tools.core.config.builtins.input', side_effect=EOFError)
    @patch('tools.core.config.subprocess.run')
    def test_approval_eof_error(self, mock_run, mock_input_eof):
        output = execute_command(self.command_list, self.config_data, True, self.purpose, requires_approval=True)
        self.assertEqual(output, "Error: Command approval required but could not obtain user input (EOFError).")
        mock_run.assert_not_called()

    @patch('tools.core.config.builtins.input')
    @patch('tools.core.config.subprocess.run')
    def test_no_approval_needed_interactive_false(self, mock_run, mock_input):
        mock_process = Mock(stdout="output", returncode=0)
        mock_run.return_value = mock_process
        execute_command(self.command_list, self.config_data, False, self.purpose, requires_approval=True)
        mock_input.assert_not_called()
        mock_run.assert_called_once()

    @patch('tools.core.config.builtins.input')
    @patch('tools.core.config.subprocess.run')
    def test_no_approval_needed_requires_approval_false(self, mock_run, mock_input):
        mock_process = Mock(stdout="output", returncode=0)
        mock_run.return_value = mock_process
        execute_command(self.command_list, self.config_data, True, self.purpose, requires_approval=False)
        mock_input.assert_not_called()
        mock_run.assert_called_once()

if __name__ == '__main__':
    unittest.main()
