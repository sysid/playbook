.DEFAULT_GOAL := help
MAKEFLAGS += --no-print-directory

VERSION       = $(shell cat VERSION)
PACKAGE_NAME  = playbook-slack

# Not $(PROJ_DIR): direnv exports it for the parent project and it would
# resolve this nested package to the playbook root.
app_root  = .
pkg_src   = $(app_root)/src/playbook_slack
tests_src = $(app_root)/tests

.PHONY: all
all: clean build  ## clean and build

################################################################################
# Development \
DEVELOP: ## ############################################################

.PHONY: dev
dev: clean install-dev  ## set up development environment
	@echo "Development environment ready. Try: make test"

.PHONY: install-dev
install-dev:  ## install development dependencies
	uv sync --dev

.PHONY: pre-commit-install
pre-commit-install:  ## install pre-commit hooks
	uv run pre-commit install

################################################################################
# Testing \
TESTING:  ## ############################################################

.PHONY: test
test:  ## run tests with coverage
	uv run pytest --cov=$(pkg_src) --cov-report=term-missing $(tests_src)

.PHONY: test-verbose
test-verbose:  ## run tests with verbose output
	uv run pytest -v --cov=$(pkg_src) --cov-report=term-missing $(tests_src)

################################################################################
# Code Quality \
QUALITY:  ## ############################################################

.PHONY: format
format:  ## perform ruff formatting
	uv run ruff format $(pkg_src) $(tests_src)

.PHONY: lint
lint:  ## check style with ruff
	uv run ruff check $(pkg_src) $(tests_src)

.PHONY: lint-fix
lint-fix:  ## check style with ruff and autofix
	uv run ruff check --fix $(pkg_src) $(tests_src)

.PHONY: ty
ty:  ## check type hint annotations
	uv run ty check $(pkg_src)

.PHONY: check
check: lint ty test  ## run all quality gates

################################################################################
# Building, Deploying \
BUILDING:  ## ############################################################

.PHONY: build
build: clean format  ## format and build
	@echo "building"
	uv build

.PHONY: publish
publish:  ## publish to PyPI
	@echo "upload to Pypi"
	uv run twine upload --verbose dist/*

.PHONY: publish-test
publish-test:  ## publish to Test PyPI
	@echo "upload to Test Pypi"
	uv run twine upload --repository testpypi --verbose dist/*

################################################################################
# Examples \
EXAMPLES:  ## ############################################################

.PHONY: example-basic
example-basic:  ## run basic notification example
	@if [ -z "$$SLACK_WEBHOOK_URL" ]; then \
		echo "Please set SLACK_WEBHOOK_URL environment variable"; \
		exit 1; \
	fi
	playbook run examples/basic_notification.playbook.toml

.PHONY: example-advanced
example-advanced:  ## run advanced workflow example
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
clean-build:  ## remove build artifacts
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	find . \( -path ./env -o -path ./venv -o -path ./.env -o -path ./.venv \) -prune -o -name '*.egg-info' -exec rm -fr {} +
	find . \( -path ./env -o -path ./venv -o -path ./.env -o -path ./.venv \) -prune -o -name '*.egg' -exec rm -f {} +

.PHONY: clean-pyc
clean-pyc:  ## remove Python file artifacts
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

################################################################################
# Misc \
MISC:  ## ############################################################

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
	@uv run python -c "$$PRINT_HELP_PYSCRIPT" < $(MAKEFILE_LIST)
