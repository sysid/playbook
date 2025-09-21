.DEFAULT_GOAL := help
MAKEFLAGS += --no-print-directory

VERSION       = $(shell cat VERSION)
PACKAGE_NAME  = playbook-slack

app_root = .
pkg_src  = $(app_root)/src/playbook_slack
tests_src = $(app_root)/tests

################################################################################
# Development \
DEVELOP: ## ############################################################

.PHONY: dev
dev: clean install-dev  ## Set up development environment
	@echo "Development environment ready!"
	@echo "Try: make test"

.PHONY: install-dev
install-dev:  ## Install development dependencies
	uv sync --dev

################################################################################
# Testing \
TESTING: ## ############################################################

.PHONY: test
test:  ## Run tests with pytest
	python -m pytest --cov-report=xml --cov-report term --cov=$(pkg_src) $(tests_src)

.PHONY: test-verbose
test-verbose:  ## Run tests with verbose output
	python -m pytest -v --cov-report=xml --cov-report term --cov=$(pkg_src) $(tests_src)

.PHONY: test-integration
test-integration:  ## Run integration tests (requires Slack credentials)
	@echo "Integration tests require SLACK_WEBHOOK_URL and SLACK_BOT_TOKEN"
	@echo "Set these environment variables and run: pytest tests/test_integration.py"

################################################################################
# Code Quality \
QUALITY: ## ############################################################

.PHONY: lint
lint: ruff mypy  ## Run all linters

.PHONY: ruff-fix
ruff-fix:  ## Run ruff and autofix
	ruff check --fix $(pkg_src) $(tests_src)

.PHONY: ruff
ruff:  ## Run ruff
	ruff check $(pkg_src) $(tests_src)

.PHONY: mypy
mypy:  ## Run mypy
	mypy $(pkg_src)

.PHONY: format
format:  ## Format code with ruff
	ruff format $(pkg_src) $(tests_src)

################################################################################
# Building \
BUILDING: ## ############################################################

.PHONY: all
all: clean build publish  ## all: build and publish

.PHONY: build
build: clean format lint test  ## Build package
	python -m build

.PHONY: publish
publish:  ## publish to PyPI
	@echo "Uploading to PyPI"
	twine upload --verbose dist/*

.PHONY: publish-test
publish-test:  ## publish to Test PyPI
	@echo "Uploading to Test PyPI"
	twine upload --repository testpypi --verbose dist/*

.PHONY: install
install: uninstall build  ## Install package locally
	pip install dist/*.whl

.PHONY: uninstall
uninstall:  ## Uninstall package
	-pip uninstall -y $(PACKAGE_NAME)

.PHONY: bump-major
bump-major: check-github-token  ## bump-major, tag and push
	bump-my-version bump --commit --tag major
	git push
	git push --tags
	@$(MAKE) create-release

.PHONY: bump-minor
bump-minor: check-github-token  ## bump-minor, tag and push
	bump-my-version bump --commit --tag minor
	git push
	git push --tags
	@$(MAKE) create-release

.PHONY: bump-patch
bump-patch: check-github-token  ## bump-patch, tag and push
	bump-my-version bump --commit --tag patch
	git push
	git push --tags
	@$(MAKE) create-release

.PHONY: create-release
create-release: check-github-token  ## create a release on GitHub via the gh cli
	@if ! command -v gh &>/dev/null; then \
		echo "You do not have the GitHub CLI (gh) installed. Please create the release manually."; \
		exit 1; \
	else \
		echo "Creating GitHub release for v$(VERSION)"; \
		gh release create "v$(VERSION)" --generate-notes; \
	fi

.PHONY: check-github-token
check-github-token:  ## Check if GITHUB_TOKEN is set
	@if [ -z "$$GITHUB_TOKEN" ]; then \
		echo "GITHUB_TOKEN is not set. Please export your GitHub token before running this command."; \
		exit 1; \
	fi
	@echo "GITHUB_TOKEN is set"

################################################################################
# Examples \
EXAMPLES: ## ############################################################

.PHONY: example-basic
example-basic:  ## Run basic notification example
	@echo "Running basic notification example..."
	@if [ -z "$$SLACK_WEBHOOK_URL" ]; then \
		echo "Please set SLACK_WEBHOOK_URL environment variable"; \
		exit 1; \
	fi
	playbook run examples/basic_notification.playbook.toml

.PHONY: example-advanced
example-advanced:  ## Run advanced workflow example
	@echo "Running advanced workflow example..."
	@if [ -z "$$SLACK_WEBHOOK_URL" ] || [ -z "$$SLACK_BOT_TOKEN" ]; then \
		echo "Please set SLACK_WEBHOOK_URL and SLACK_BOT_TOKEN environment variables"; \
		exit 1; \
	fi
	playbook run examples/advanced_workflow.playbook.toml

################################################################################
# Clean \
CLEAN:  ## ############################################################
.PHONY: clean
clean: clean-build clean-pyc  ## remove all build, test, coverage and Python artifacts

.PHONY: clean-build
clean-build: ## remove build artifacts
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	find . \( -path ./env -o -path ./venv -o -path ./.env -o -path ./.venv \) -prune -o -name '*.egg-info' -exec rm -fr {} +
	find . \( -path ./env -o -path ./venv -o -path ./.env -o -path ./.venv \) -prune -o -name '*.egg' -exec rm -f {} +

.PHONY: clean-pyc
clean-pyc: ## remove Python file artifacts
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

################################################################################
# Help \
HELP: ## ############################################################

define PRINT_HELP_PYSCRIPT
import re, sys

for line in sys.stdin:
    match = re.match(r'^([a-zA-Z0-9_-]+):.*?## (.*)$$', line)
    if match:
        target, help = match.groups()
        print("\033[36m%-20s\033[0m %s" % (target, help))
endef
export PRINT_HELP_PYSCRIPT

.PHONY: help
help:
	@python -c "$$PRINT_HELP_PYSCRIPT" < $(MAKEFILE_LIST)