import unittest

class TestToolsPackageInit(unittest.TestCase):

    def test_import_kubectl_get_directly(self):
        """Test that kubectl_get can be imported directly from the tools package."""
        try:
            # Attempt the direct import
            from tools import kubectl_get

            # Check if it's a callable (function)
            self.assertTrue(callable(kubectl_get), "kubectl_get should be a callable function.")

            # Optional: More specific check against the original function.
            # This can be fragile if the object imported is a functools.partial object
            # due to the changes in tools.registry.py which tools/__init__.py might reflect.
            # If tools are already partially applied when exposed via tools/__init__.py,
            # then kubectl_get would be a functools.partial object.
            # For now, checking name and callable status is a good first step.

            # To check if it's the original or a partial:
            # import functools
            # from tools.kubernetes.core import kubectl_get as original_kubectl_get
            # if isinstance(kubectl_get, functools.partial):
            #    self.assertEqual(kubectl_get.func, original_kubectl_get, "Imported kubectl_get (partial) does not wrap the original function.")
            # else:
            #    self.assertIs(kubectl_get, original_kubectl_get, "Imported kubectl_get is not the original function.")

        except ImportError as e:
            self.fail(f"Failed to import kubectl_get from tools: {e}")
        except Exception as e:
            # Catch any other unexpected errors during the import or check
            self.fail(f"An unexpected error occurred during import test: {e}")

    def test_import_get_all_tools_directly(self):
        """Test that a registry function (get_all_tools) can be imported directly."""
        try:
            from tools import get_all_tools
            self.assertTrue(callable(get_all_tools), "get_all_tools should be a callable function.")
        except ImportError as e:
            self.fail(f"Failed to import get_all_tools from tools: {e}")
        except Exception as e:
            self.fail(f"An unexpected error occurred during import test: {e}")

    def test_import_validate_command_directly(self):
        """Test that a core utility (validate_command) can be imported directly."""
        try:
            from tools import validate_command
            self.assertTrue(callable(validate_command), "validate_command should be a callable function.")
        except ImportError as e:
            self.fail(f"Failed to import validate_command from tools: {e}")
        except Exception as e:
            self.fail(f"An unexpected error occurred during import test: {e}")


if __name__ == '__main__':
    unittest.main()
