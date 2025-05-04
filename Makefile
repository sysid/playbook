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
build: clean format  ## Build package
	python -m build

.PHONY: publish
publish:  ## publish
	@echo "upload to Pypi"
	twine upload --verbose dist/*

.PHONY: install
install: uninstall  ## uv install
	uv tool install -e .
	playbook --install-completion bash

.PHONY: uninstall
uninstall:  ## uv uninstall
	-uv tool uninstall $(PACKAGE_NAME)

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
