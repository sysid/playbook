# tests/test_cli/test_commands/test_create.py
"""Tests for the create command."""

from playbook.cli.main import app


class TestCreateCommand:
    """Test cases for the create command."""

    def test_create_with_all_options(self, cli_runner, temp_dir):
        """Test create command with all options provided."""
        output_file = temp_dir / "test.playbook.toml"

        result = cli_runner.invoke(
            app,
            [
                "create",
                "--title",
                "Test Workflow",
                "--author",
                "Test Author",
                "--description",
                "Test Description",
                "--output",
                str(output_file),
            ],
            input="n\n",  # Don't add manual nodes
        )

        assert result.exit_code == 0
        assert output_file.exists()

        content = output_file.read_text()
        assert "Test Workflow" in content
        assert "Test Author" in content
        assert "Test Description" in content

    def test_create_interactive_mode(self, cli_runner, temp_dir):
        """Test create command in interactive mode."""
        output_file = temp_dir / "interactive.playbook.toml"

        # Simulate interactive input
        inputs = [
            "Interactive Workflow",  # title
            "Interactive Author",  # author
            "Interactive Description",  # description
            str(output_file),  # output path
            "n",  # don't add manual nodes
        ]

        result = cli_runner.invoke(app, ["create"], input="\n".join(inputs))

        assert result.exit_code == 0
        assert output_file.exists()

    def test_create_with_manual_nodes(self, cli_runner, temp_dir):
        """Test create command with manual nodes."""
        output_file = temp_dir / "with_nodes.playbook.toml"

        # Simulate adding one manual node
        inputs = [
            "Node Workflow",  # title
            "Node Author",  # author
            "Node Description",  # description
            str(output_file),  # output path
            "y",  # add manual nodes
            "node1",  # node id
            "First Node",  # node name
            "First step description",  # node description
            "Continue?",  # prompt after
            "",  # dependencies (empty)
            "y",  # critical
            "n",  # don't add another node
        ]

        result = cli_runner.invoke(app, ["create"], input="\n".join(inputs))

        assert result.exit_code == 0
        assert output_file.exists()

        content = output_file.read_text()
        assert "[node1]" in content
        assert "First Node" in content

    def test_create_file_exists_overwrite_no(self, cli_runner, temp_dir):
        """Test create command when file exists and user chooses not to overwrite."""
        output_file = temp_dir / "existing.playbook.toml"
        output_file.write_text("existing content")

        result = cli_runner.invoke(
            app,
            [
                "create",
                "--title",
                "Test",
                "--author",
                "Test",
                "--description",
                "Test",
                "--output",
                str(output_file),
            ],
            input="n\n",  # Don't overwrite
        )

        assert result.exit_code == 0
        assert output_file.read_text() == "existing content"

    def test_create_file_exists_overwrite_yes(self, cli_runner, temp_dir):
        """Test create command when file exists and user chooses to overwrite."""
        output_file = temp_dir / "overwrite.playbook.toml"
        output_file.write_text("existing content")

        inputs = [
            "y",  # Overwrite existing file
            "n",  # Don't add manual nodes
        ]

        result = cli_runner.invoke(
            app,
            [
                "create",
                "--title",
                "New Workflow",
                "--author",
                "New Author",
                "--description",
                "New Description",
                "--output",
                str(output_file),
            ],
            input="\n".join(inputs),
        )

        assert result.exit_code == 0
        content = output_file.read_text()
        assert "New Workflow" in content
        assert "existing content" not in content
