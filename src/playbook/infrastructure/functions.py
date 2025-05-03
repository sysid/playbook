# src/playbook/infrastructure/functions.py
import importlib
from typing import Any, Dict

from ..domain.ports import FunctionLoader


class PythonFunctionLoader(FunctionLoader):
    """Dynamic Python function loading adapter"""

    def load_and_call(self, function_path: str, params: Dict) -> Any:
        """Load function by its path and call with params"""
        # Split module path and function name
        module_path, function_name = function_path.rsplit(".", 1)

        # Import module dynamically
        try:
            module = importlib.import_module(module_path)
            function = getattr(module, function_name)

            # Process parameters that need interactive input
            processed_params = {}
            for key, value in params.items():
                if value == "${ask}":
                    # This would be handled by the CLI interface
                    # For now, we'll just use an empty string
                    processed_params[key] = ""
                else:
                    processed_params[key] = value

            # Call function with parameters
            return function(**processed_params)

        except ImportError:
            raise ValueError(f"Module not found: {module_path}")
        except AttributeError:
            raise ValueError(f"Function not found: {function_name} in {module_path}")
        except Exception as e:
            raise RuntimeError(f"Error calling function: {str(e)}")
