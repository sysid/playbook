.DEFAULT_GOAL := help
MAKEFLAGS += --no-print-directory

VERSION       = $(shell cat VERSION)
PACKAGE_NAME  = playbook

app_root := $(if $(PROJ_DIR),$(PROJ_DIR),$(CURDIR))
pkg_src   = $(app_root)/src/playbook
tests_src = $(app_root)/tests

.PHONY: all
all: clean build  ## clean and build

################################################################################
# Development \
DEVELOP: ## ############################################################

.PHONY: install
install: uninstall  ## uv install
	uv tool install -e .
	playbook --install-completion bash

.PHONY: uninstall
uninstall:  ## uv uninstall
	-uv tool uninstall $(PACKAGE_NAME)

.PHONY: pre-commit-install
pre-commit-install:  ## install pre-commit hooks
	uv run pre-commit install

################################################################################
# Testing \
TESTING:  ## ############################################################

.PHONY: test
test:  ## run tests with coverage
	uv run pytest --cov=$(pkg_src) --cov-report=term-missing $(tests_src)

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
