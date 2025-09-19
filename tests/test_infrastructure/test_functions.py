# tests/test_infrastructure/test_functions.py
"""Tests for the function loader."""

from unittest.mock import patch, Mock

import pytest

from playbook.infrastructure.functions import PythonFunctionLoader


class TestPythonFunctionLoader:
    """Test cases for the PythonFunctionLoader."""

    @pytest.fixture
    def loader(self):
        """Create a function loader instance."""
        return PythonFunctionLoader()

    @patch("importlib.import_module")
    def test_load_and_call_success(self, mock_import, loader):
        """Test successful function loading and calling."""
        # Mock module and function
        mock_module = Mock()
        mock_function = Mock(return_value="function result")
        mock_module.test_function = mock_function
        mock_import.return_value = mock_module

        result = loader.load_and_call("test.module.test_function", {"param1": "value1"})

        assert result == "function result"
        mock_import.assert_called_once_with("test.module")
        mock_function.assert_called_once_with(param1="value1")

    @patch("importlib.import_module")
    def test_load_and_call_module_not_found(self, mock_import, loader):
        """Test loading non-existent module."""
        mock_import.side_effect = ImportError("No module named 'nonexistent'")

        with pytest.raises(ValueError, match="Module not found: nonexistent.module"):
            loader.load_and_call("nonexistent.module.function", {})

    @patch("importlib.import_module")
    def test_load_and_call_function_not_found(self, mock_import, loader):
        """Test loading non-existent function."""
        mock_module = Mock(spec=[])  # Empty spec means no attributes
        mock_import.return_value = mock_module

        with pytest.raises(
            ValueError, match="Function not found: nonexistent_function in test.module"
        ):
            loader.load_and_call("test.module.nonexistent_function", {})

    @patch("importlib.import_module")
    def test_load_and_call_function_error(self, mock_import, loader):
        """Test function execution error."""
        mock_module = Mock()
        mock_function = Mock(side_effect=ValueError("Function error"))
        mock_module.test_function = mock_function
        mock_import.return_value = mock_module

        with pytest.raises(RuntimeError, match="Error calling function"):
            loader.load_and_call("test.module.test_function", {})

    @patch("importlib.import_module")
    def test_load_and_call_with_no_params(self, mock_import, loader):
        """Test function loading with no parameters."""
        mock_module = Mock()
        mock_function = Mock(return_value="no params result")
        mock_module.no_param_function = mock_function
        mock_import.return_value = mock_module

        result = loader.load_and_call("test.module.no_param_function", {})

        assert result == "no params result"
        mock_function.assert_called_once_with()

    @patch("importlib.import_module")
    def test_load_and_call_with_complex_params(self, mock_import, loader):
        """Test function loading with complex parameters."""
        mock_module = Mock()
        mock_function = Mock(return_value="complex result")
        mock_module.complex_function = mock_function
        mock_import.return_value = mock_module

        params = {
            "string_param": "test",
            "int_param": 42,
            "float_param": 3.14,
            "bool_param": True,
        }

        result = loader.load_and_call("test.module.complex_function", params)

        assert result == "complex result"
        mock_function.assert_called_once_with(
            string_param="test", int_param=42, float_param=3.14, bool_param=True
        )

    def test_load_and_call_invalid_function_path(self, loader):
        """Test loading with invalid function path."""
        with pytest.raises(ValueError, match="not enough values to unpack"):
            loader.load_and_call("invalid_path", {})

        with pytest.raises(ValueError, match="not enough values to unpack"):
            loader.load_and_call("", {})

    @patch("importlib.import_module")
    def test_load_and_call_nested_module(self, mock_import, loader):
        """Test loading function from nested module."""
        mock_module = Mock()
        mock_function = Mock(return_value="nested result")
        mock_module.nested_function = mock_function
        mock_import.return_value = mock_module

        result = loader.load_and_call(
            "package.subpackage.module.nested_function", {"param": "value"}
        )

        assert result == "nested result"
        mock_import.assert_called_once_with("package.subpackage.module")
        mock_function.assert_called_once_with(param="value")
