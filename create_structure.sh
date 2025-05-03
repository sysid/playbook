
#!/usr/bin/env bash
set -euo pipefail

mkdir -p playbook/src/playbook/{domain,service,infrastructure}
mkdir -p playbook/tests/{test_domain,test_service,test_infrastructure}

touch playbook/pyproject.toml
touch playbook/README.md

touch playbook/src/playbook/__init__.py
touch playbook/src/playbook/config.py

# Domain
touch playbook/src/playbook/domain/__init__.py
touch playbook/src/playbook/domain/models.py
touch playbook/src/playbook/domain/ports.py

# Service
touch playbook/src/playbook/service/__init__.py
touch playbook/src/playbook/service/engine.py

# Infrastructure
touch playbook/src/playbook/infrastructure/__init__.py
touch playbook/src/playbook/infrastructure/cli.py
touch playbook/src/playbook/infrastructure/persistence.py
touch playbook/src/playbook/infrastructure/process.py
touch playbook/src/playbook/infrastructure/functions.py
touch playbook/src/playbook/infrastructure/visualization.py

# Tests
touch playbook/tests/__init__.py
