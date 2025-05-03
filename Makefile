.DEFAULT_GOAL := help
MAKEFLAGS += --no-print-directory

VERSION       = $(shell cat VERSION)
PACKAGE_NAME  = playbook

app_root = .
pkg_src  = $(app_root)/src/$(PACKAGE_NAME)
tests_src = $(app_root)/tests

################################################################################
# Development \
DEVELOP: ## ############################################################

################################################################################
# Testing \
TESTING: ## ############################################################

.PHONY: test
test:  ## Run tests with pytest
	python -m pytest --cov-report=xml --cov-report term --cov=$(pkg_src) $(tests_src)

################################################################################
# Code Quality \
QUALITY: ## ############################################################

.PHONY: lint
lint: ruff mypy  ## Run all linters

.PHONY: ruff
ruff:  ## Run ruff
	ruff $(pkg_src) $(tests_src)

.PHONY: mypy
mypy:  ## Run mypy
	mypy $(pkg_src)

.PHONY: format
format:  ## Format code with ruff
	ruff format $(pkg_src) $(tests_src)

################################################################################
# Building \
BUILDING: ## ############################################################

.PHONY: build
build: clean format  ## Build package
	python -m build

.PHONY: clean
clean: clean-build clean-pyc  ## Clean all build artifacts

.PHONY: clean-build
clean-build:
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +

.PHONY: clean-pyc
clean-pyc:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

.PHONY: install
install: uninstall  ## pipx install
	uv tool install -e .
	playbook --install-completion bash

.PHONY: uninstall
uninstall:  ## pipx uninstall
	-uv tool uninstall $(PACKAGE_NAME)

.PHONY: bump-major
bump-major:  ## bump-major, tag and push
	bump-my-version bump --commit --tag major
	git push
	git push --tags
	@$(MAKE) create-release

.PHONY: bump-minor
bump-minor:  ## bump-minor, tag and push
	bump-my-version bump --commit --tag minor
	git push
	git push --tags
	@$(MAKE) create-release

.PHONY: bump-patch
bump-patch:  ## bump-patch, tag and push
	bump-my-version bump --commit --tag patch
	git push
	git push --tags
	@$(MAKE) create-release

.PHONY: create-release
create-release:  ## create a release on GitHub via the gh cli
	@if command -v gh version &>/dev/null; then \
		echo "Creating GitHub release for v$(VERSION)"; \
		gh release create "v$(VERSION)" --generate-notes; \
	else \
		echo "You do not have the github-cli installed. Please create release from the repo manually."; \
		exit 1; \
	fi


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
