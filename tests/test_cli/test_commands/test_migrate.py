import tomllib

from playbook.cli.main import app


def test_migrate_writes_v2_file(cli_runner, temp_dir):
    source = temp_dir / "legacy.playbook.toml"
    source.write_text(
        """
[runbook]
title = "Legacy"

[review]
type = "Manual"
description = "Review it"
depends_on = []
"""
    )
    output = temp_dir / "migrated.playbook.toml"

    result = cli_runner.invoke(
        app,
        ["migrate", str(source), "--output", str(output)],
    )

    assert result.exit_code == 0
    migrated = tomllib.loads(output.read_text())
    assert migrated["schema_version"] == 2
    assert migrated["steps"][0]["id"] == "review"
    assert "Migrated" in result.output


def test_migrate_refuses_to_overwrite(cli_runner, temp_dir):
    source = temp_dir / "legacy.playbook.toml"
    source.write_text('[runbook]\ntitle = "Legacy"\n')
    output = temp_dir / "existing.playbook.toml"
    output.write_text("keep me")

    result = cli_runner.invoke(
        app,
        ["migrate", str(source), "--output", str(output)],
    )

    assert result.exit_code == 1
    assert output.read_text() == "keep me"
    assert "Refusing to overwrite" in result.output
