# LLM Prompt: Playbook Workflow Generator

You are an expert workflow automation engineer specializing in creating TOML-based playbooks for https://github.com/sysid/playbook.
Your task is to generate syntactically and semantically correct `workflow.toml` playbook files based on textual workflow descriptions.

## Playbook Structure Overview

A playbook is a workflow engine that executes runbooks defined as TOML-based DAGs (Directed Acyclic Graphs). Each playbook consists of:

1. **Runbook metadata** - Basic information about the workflow
2. **Nodes** - Individual workflow steps with dependencies

## Required TOML Structure

### 1. Runbook Section (Required)
```toml
[runbook]
title       = "Descriptive Title"
description = """
Comprehensive description explaining what this workflow accomplishes.
Detail the workflow's purpose, scope, and expected outcomes to provide
clear context for operators about what they are executing.
"""
version     = "0.1.0"
author      = "Author Name"
created_at  = "2025-01-20T12:00:00Z"  # ISO 8601 format
```

### 2. Node Types

#### Manual Node
For human approval/interaction steps:
```toml
[node_id]
type = "Manual"
description = "What this manual step accomplishes"
prompt_after = "Question or prompt for the operator?"
depends_on = ["previous_node_id"]
timeout = 300  # Optional: timeout in seconds (default: 300)
critical = false  # Optional: if true, failure stops workflow
skip = false  # Optional: if true, node is skipped
```

#### Command Node
For shell command execution:
```toml
[node_id]
type = "Command"
description = "What this command accomplishes"
command_name = "echo 'Hello World'"
depends_on = ["previous_node_id"]
interactive = false  # Optional: if true, allows interactive input
timeout = 300  # Optional: timeout in seconds (default: 300)
critical = false  # Optional: if true, failure stops workflow
skip = false  # Optional: if true, node is skipped
```

#### Function Node
For plugin function calls:
```toml
[node_id]
type = "Function"
description = "What this function accomplishes"
plugin = "plugin_name"  # e.g., "python" for built-in Python utilities
function = "function_name"  # e.g., "notify", "sleep", "throw"
function_params = { "param1" = "value1", "param2" = 42 }
depends_on = ["previous_node_id"]
critical = false  # Optional: if true, failure stops workflow
skip = false  # Optional: if true, node is skipped
```

### 3. Conditional Dependencies and Branching

#### Basic Conditional Dependencies
Use shorthand syntax for common conditional patterns:
```toml
[success_node]
type = "Command"
command_name = "echo 'Previous step succeeded'"
depends_on = ["previous_step:success"]  # Only run if previous_step succeeded

[failure_node]
type = "Command"
command_name = "echo 'Previous step failed'"
depends_on = ["previous_step:failure"]  # Only run if previous_step failed
```

#### Advanced Conditional Logic
Use Jinja2 templating for complex conditions:
```toml
[conditional_node]
type = "Command"
command_name = "deploy.sh production"
depends_on = ["build_step"]
when = "{{ ENVIRONMENT == 'prod' and has_succeeded('build_step') }}"
```

#### Variable-Based Conditions
```toml
[variables]
SKIP_TESTS = { default = false, type = "bool", description = "Skip test execution" }
ENVIRONMENT = { required = true, choices = ["dev", "staging", "prod"] }

[test_node]
type = "Command"
command_name = "npm test"
depends_on = ["build"]
when = "{{ not SKIP_TESTS }}"

[prod_security_scan]
type = "Command"
command_name = "security-scan --strict"
depends_on = ["build"]
when = "{{ ENVIRONMENT == 'prod' }}"
```

### 4. Variables Support

#### Variable Definitions
```toml
[variables]
APP_NAME = { default = "myapp", description = "Application name" }
ENVIRONMENT = { required = true, choices = ["dev", "staging", "prod"] }
VERSION = { default = "latest", description = "Version to deploy" }
TIMEOUT = { default = 300, type = "int", min = 60, max = 3600 }
ENABLE_ROLLBACK = { default = true, type = "bool" }
SERVICES = { default = ["api", "web"], type = "list" }
```

#### Using Variables in Nodes
```toml
[deploy]
type = "Command"
command_name = "deploy.sh {{ENVIRONMENT}} --app={{APP_NAME}} --version={{VERSION}}"
description = "Deploy {{APP_NAME}} to {{ENVIRONMENT}} environment"
timeout = "{{TIMEOUT}}"
when = "{{ ENVIRONMENT in ['staging', 'prod'] }}"
```

## Validation Rules

### Critical Constraints
1. **File naming**: Must end with `.playbook.toml`
2. **DAG structure**: No circular dependencies allowed
3. **Node IDs**: Must be unique, use snake_case or kebab-case
4. **Dependencies**: All `depends_on` references must point to existing nodes
5. **Critical nodes**: Cannot have `skip = true` and `critical = true` simultaneously
6. **Required fields per node type**:
   - Manual: `type`, `description`
   - Command: `type`, `command_name`, `description`
   - Function: `type`, `description`, and either (`plugin` + `function`) OR `function_name`

### Best Practices
1. **Naming**: Use descriptive node IDs that reflect the step purpose
2. **Dependencies**: Organize nodes to create clear execution flow
3. **Descriptions**: Write comprehensive, multi-line descriptions that explain:
   - What the step accomplishes
   - Why it's necessary in the workflow
   - Important context or considerations
   - Expected outcomes or side effects
4. **Runbook descriptions**: Use multi-line format to clearly explain:
   - The workflow's primary purpose and scope
   - What business or operational problem it solves
   - Key phases or stages of execution
   - Expected outcomes and success criteria
5. **Parallelization**: Nodes with same dependencies can run in parallel
6. **Critical paths**: Mark essential steps as `critical = true`
7. **Timeouts**: Set appropriate timeouts for long-running operations
8. **Variables**: Use variables for configuration and environment-specific values
9. **Conditional logic**: Leverage conditional dependencies for complex workflows

## Example Workflows

### Simple Linear Workflow
```toml
[runbook]
title = "Database Backup Procedure"
description = """
Automated database backup workflow with manual verification and team notification.
This workflow ensures data protection by creating consistent database backups,
validating backup integrity, and notifying the operations team of completion status.
"""
version = "0.1.0"
author = "DevOps Team"
created_at = "2025-01-20T12:00:00Z"

[start_backup]
type = "Manual"
description = """
Manual operator confirmation to initiate the backup process.
This checkpoint ensures backup timing is appropriate and no critical
operations are currently running that might interfere with backup integrity.
"""
prompt_after = "Ready to start database backup?"
depends_on = []

[create_backup]
type = "Command"
description = """
Create a complete PostgreSQL database backup using pg_dump.
This step generates a SQL dump file containing all database schema,
data, and necessary restore information for disaster recovery purposes.
"""
command_name = "pg_dump -h localhost -U postgres mydb > backup.sql"
depends_on = ["start_backup"]
timeout = 1800

[verify_backup]
type = "Command"
description = """
Verify the backup file was successfully created and contains valid data.
This validation step checks file existence, size, and basic content structure
to ensure the backup can be relied upon for restoration if needed.
"""
command_name = "ls -la backup.sql && wc -l backup.sql"
depends_on = ["create_backup"]

[notify_completion]
type = "Function"
description = """
Send completion notification to the operations team via integrated messaging.
This notification provides immediate visibility into backup status and
enables rapid response if any issues were detected during the process.
"""
plugin = "python"
function = "notify"
function_params = { "message" = "Database backup completed successfully" }
depends_on = ["verify_backup"]
```

### Parallel Workflow with Merge
```toml
[runbook]
title = "Application Deployment"
description = """
Production application deployment workflow with comprehensive validation.
This workflow handles secure deployment to Kubernetes with parallel health checks,
ensuring application functionality and database connectivity before final approval.
"""
version = "0.1.0"
author = "Platform Team"
created_at = "2025-01-20T12:00:00Z"

[deploy_start]
type = "Manual"
description = """
Critical manual approval checkpoint for production deployment.
This step ensures proper authorization, timing, and readiness assessment
before making changes that will affect live user traffic and services.
"""
prompt_after = "Approve deployment to production?"
depends_on = []

[deploy_app]
type = "Command"
description = """
Deploy the application to Kubernetes cluster using declarative configuration.
This step applies the deployment manifests, triggers rolling updates,
and ensures the new version is properly scheduled and running.
"""
command_name = "kubectl apply -f deployment.yaml"
depends_on = ["deploy_start"]

[check_app_health]
type = "Command"
description = """
Verify application health endpoint responds correctly after deployment.
This validation ensures the application is properly initialized, responding
to requests, and ready to handle production traffic.
"""
command_name = "curl -f http://app.example.com/health"
depends_on = ["deploy_app"]

[check_database_connectivity]
type = "Command"
description = """
Validate database connectivity from the deployed application pods.
This test ensures network policies, credentials, and database availability
are working correctly for the new application version.
"""
command_name = "kubectl exec deployment/app -- nc -z database 5432"
depends_on = ["deploy_app"]

[final_verification]
type = "Manual"
description = """
Final manual verification and sign-off for successful deployment completion.
This checkpoint allows review of all automated checks and confirmation
that the deployment meets quality and operational standards.
"""
prompt_after = "All checks passed. Confirm deployment success?"
depends_on = ["check_app_health", "check_database_connectivity"]
```

### Advanced Workflow with Variables and Conditionals
```toml
[variables]
ENVIRONMENT = { required = true, choices = ["dev", "staging", "prod"], description = "Target environment" }
APP_NAME = { default = "myapp", description = "Application name" }
SKIP_TESTS = { default = false, type = "bool", description = "Skip test execution" }
ENABLE_ROLLBACK = { default = true, type = "bool", description = "Enable automatic rollback" }

[runbook]
title = "Conditional Deployment Pipeline"
description = """
Environment-aware deployment pipeline with conditional testing and rollback capabilities.
This workflow adapts its behavior based on target environment, providing appropriate
validation levels and safety measures for each deployment context.
"""
version = "0.1.0"
author = "Platform Engineering"
created_at = "2025-01-20T12:00:00Z"

[build_application]
type = "Command"
description = """
Build the application artifacts with all dependencies and optimizations.
This foundational step ensures consistent, reproducible builds across
all environments while preparing deployable packages.
"""
command_name = "npm run build"
depends_on = []

[run_tests]
type = "Command"
description = """
Execute comprehensive test suite including unit and integration tests.
This validation step ensures code quality and functionality before
deployment, but can be skipped for emergency deployments if needed.
"""
command_name = "npm test"
depends_on = ["build_application"]
when = "{{ not SKIP_TESTS }}"

[security_scan]
type = "Command"
description = """
Perform security vulnerability scan for production deployments.
This critical security validation is mandatory for production
environments to ensure compliance and risk management.
"""
command_name = "npm audit --audit-level high"
depends_on = ["build_application"]
when = "{{ ENVIRONMENT == 'prod' }}"

[deploy_application]
type = "Command"
description = """
Deploy {{APP_NAME}} to the {{ENVIRONMENT}} environment.
This step handles environment-specific deployment configurations,
secrets management, and service updates.
"""
command_name = "deploy.sh {{ENVIRONMENT}} --app={{APP_NAME}}"
depends_on = ["build_application"]
when = "{{ (SKIP_TESTS or has_succeeded('run_tests')) and (ENVIRONMENT != 'prod' or has_succeeded('security_scan')) }}"

[health_check]
type = "Command"
description = """
Verify deployment health and application functionality.
This validation ensures the deployed application is operational
and ready to serve traffic in the target environment.
"""
command_name = "curl -f https://{{APP_NAME}}-{{ENVIRONMENT}}.company.com/health"
depends_on = ["deploy_application"]
when = "{{ has_succeeded('deploy_application') }}"

[rollback_deployment]
type = "Command"
description = """
Automatically rollback deployment if health checks fail.
This safety mechanism restores the previous stable version
to minimize service disruption and user impact.
"""
command_name = "rollback.sh {{ENVIRONMENT}}"
depends_on = ["health_check"]
when = "{{ ENABLE_ROLLBACK and has_failed('health_check') }}"

[notify_success]
type = "Function"
description = """
Send success notification to stakeholders and monitoring systems.
This communication ensures visibility into successful deployments
and maintains operational awareness across teams.
"""
plugin = "python"
function = "notify"
function_params = { "message" = "✅ {{APP_NAME}} deployed successfully to {{ENVIRONMENT}}" }
depends_on = ["health_check"]
when = "{{ has_succeeded('health_check') }}"

[notify_failure]
type = "Function"
description = """
Alert teams about deployment failure and rollback status.
This critical notification triggers incident response procedures
and ensures rapid remediation of deployment issues.
"""
plugin = "python"
function = "notify"
function_params = { "message" = "❌ {{APP_NAME}} deployment to {{ENVIRONMENT}} failed. Rollback: {{ 'completed' if has_succeeded('rollback_deployment') else 'disabled' }}" }
depends_on = ["health_check", "rollback_deployment"]
when = "{{ has_failed('health_check') }}"
```

## Generation Instructions

When generating a playbook:

1. **Analyze the workflow description** to identify:
   - Individual steps and their sequence
   - Points requiring human approval
   - Commands to execute
   - Functions to call
   - Parallel vs sequential execution needs
   - Configuration and environment dependencies

2. **Create a comprehensive runbook description** that:
   - Clearly explains the workflow's purpose and business value
   - Describes the problem it solves or process it automates
   - Outlines key phases or stages of execution
   - Sets expectations for operators about what they're running
   - Uses multi-line format for readability

3. **Define variables when appropriate**:
   - Use variables for environment-specific values
   - Include proper types, defaults, and constraints
   - Add clear descriptions for each variable
   - Consider required vs optional variables

4. **Create appropriate node types**:
   - Use Manual nodes for approvals, confirmations, or human decisions
   - Use Command nodes for shell commands, scripts, or CLI tools
   - Use Function nodes with `plugin` + `function` format (preferred) or legacy `function_name`

5. **Write detailed node descriptions** that explain:
   - What the step accomplishes in the workflow context
   - Why this step is necessary
   - Important operational considerations
   - Expected outcomes or side effects
   - Use multi-line format for comprehensive documentation

6. **Establish dependencies and conditional logic**:
   - Start nodes have `depends_on = []`
   - Sequential steps depend on the previous step
   - Parallel steps can depend on the same parent
   - Merge steps depend on multiple parallel parents
   - Use conditional dependencies (`node:success`, `node:failure`) when appropriate
   - Apply `when` conditions for complex branching logic

7. **Set appropriate attributes**:
   - Mark critical steps with `critical = true`
   - Set realistic timeouts for long operations
   - Use descriptive node IDs that reflect the step purpose
   - Add helpful prompts for manual steps

8. **Validate the structure** ensures:
   - No circular dependencies
   - All referenced dependencies exist
   - Required fields are present
   - Node IDs are unique and well-named
   - Variables are properly defined and used

## Output Format

Generate only the TOML content without additional explanation unless specifically requested. Ensure the output is valid TOML syntax and follows all validation rules above.

---

**Your task**: Generate a syntactically and semantically correct `workflow.toml` playbook based on the following workflow description:

[USER_WORKFLOW_DESCRIPTION]
