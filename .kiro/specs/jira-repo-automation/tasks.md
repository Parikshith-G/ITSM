# Implementation Plan: Jira Repo Automation

## Overview

Implement a Python CLI pipeline that fetches a Jira ticket, extracts repository details, clones/fetches the repo, generates a Kiro spec from the ticket content, and wires a post-task hook to commit and push the feature branch once Kiro finishes executing the spec tasks.

## Tasks

- [x] 1. Set up project structure, dependencies, and exception hierarchy
  - Create the `jira_repo_automation/` package with `__init__.py` and `exceptions.py`
  - Define the full `AutomationError` exception hierarchy: `ConfigError`, `JiraAuthError`, `JiraTicketNotFoundError`, `JiraConnectionError`, `TicketParseError`, `RepoError`, `BranchNotFoundError`, `PushConflictError`, `SpecGenerationError`, `EmptyChangeSetError`
  - Create `pyproject.toml` with pinned dependencies: `jira`, `gitpython`, `python-dotenv`, `hypothesis`, `pytest`
  - Create `.env.example` documenting all required environment variables
  - _Requirements: 1.3, 1.4, 1.5, 2.4, 2.5, 3.5, 3.6, 4.4, 5.4, 5.5_

- [x] 2. Implement `ConfigLoader` and `Config`
  - [x] 2.1 Implement `Config` dataclass and `ConfigLoader.load` in `config.py`
    - Read `JIRA_BASE_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN`, `GIT_SSH_KEY_PATH`, `GIT_PAT` from environment variables using `python-dotenv`
    - Merge optional config file values, with env vars taking precedence
    - Raise `ConfigError` (message must contain the missing credential name) when any required credential is absent
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [x] 2.2 Write property test for env var precedence over config file (Property 18)
    - **Property 18: Env var takes precedence over config file value**
    - **Validates: Requirements 6.3**

  - [x] 2.3 Write property test for missing credential error (Property 19)
    - **Property 19: Missing credential error contains the credential name**
    - **Validates: Requirements 6.4**

  - [x] 2.4 Write unit tests for `ConfigLoader`
    - Test successful load from env vars only
    - Test successful merge of config file with env var override
    - Test `ConfigError` raised for each missing required credential
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [x] 3. Implement structured logging
  - [x] 3.1 Implement `logging_setup.py` with text and JSON formatters
    - Expose `setup_logging(log_format: str, verbose: bool) -> None`
    - Emit DEBUG entries when `verbose=True`
    - _Requirements: 7.3, 7.4_

  - [x] 3.2 Write property test for error log entry contents (Property 20)
    - **Property 20: Error log entry contains operation name, error message, and ticket ID**
    - **Validates: Requirements 7.2**

  - [x] 3.3 Write unit tests for logging setup
    - Test text format output
    - Test JSON format output
    - Test DEBUG entries emitted only when verbose is enabled
    - _Requirements: 7.3, 7.4_

- [x] 4. Implement `JiraClient`
  - [x] 4.1 Implement `JiraClient` in `jira_client.py`
    - Authenticate using `jira.JIRA` with `(username, api_token)` basic auth
    - Implement `get_ticket(ticket_id: str) -> jira.Issue`
    - Map 401/403 responses to `JiraAuthError`
    - Map 404 responses to `JiraTicketNotFoundError` (message must contain `ticket_id`)
    - Map network failures to `JiraConnectionError` (message must contain the base URL)
    - Emit log entries at start and end of ticket retrieval
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 7.1_

  - [x] 4.2 Write property test for ticket-not-found error (Property 1)
    - **Property 1: Ticket-not-found error contains the ticket ID**
    - **Validates: Requirements 1.4**

  - [x] 4.3 Write property test for connection error URL (Property 2)
    - **Property 2: Connection error contains the endpoint URL**
    - **Validates: Requirements 1.5**

  - [x] 4.4 Write unit tests for `JiraClient`
    - Test successful ticket retrieval (mock `jira.JIRA`)
    - Test `JiraAuthError` on 401/403
    - Test `JiraTicketNotFoundError` on 404
    - Test `JiraConnectionError` on network failure
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [~] 5. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement `TicketParser`
  - [x] 6.1 Implement `ParsedTicket` dataclass and `TicketParser.parse` in `ticket_parser.py`
    - Strip `"gitlab repository - "` prefix from the `git url` custom field to extract `repo_url`
    - Strip `"branch - "` prefix from the `branch` custom field to extract `branch`
    - Populate `summary` and `description` from the corresponding Jira issue fields
    - Raise `TicketParseError` (message must contain field name and ticket ID) for absent or malformed fields
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 6.2 Write property test for git URL round-trip (Property 3)
    - **Property 3: Git URL field parsing is a round trip**
    - **Validates: Requirements 2.1**

  - [x] 6.3 Write property test for branch name round-trip (Property 4)
    - **Property 4: Branch field parsing is a round trip**
    - **Validates: Requirements 2.2**

  - [x] 6.4 Write property test for summary and description preservation (Property 5)
    - **Property 5: Change description preserves summary and description**
    - **Validates: Requirements 2.3**

  - [x] 6.5 Write property test for malformed git URL error (Property 6)
    - **Property 6: Malformed git URL field raises error with field name and ticket ID**
    - **Validates: Requirements 2.4**

  - [x] 6.6 Write property test for malformed branch field error (Property 7)
    - **Property 7: Malformed branch field raises error with field name and ticket ID**
    - **Validates: Requirements 2.5**

  - [x] 6.7 Write unit tests for `TicketParser`
    - Test successful parse with well-formed fields
    - Test `TicketParseError` for missing `git url` field
    - Test `TicketParseError` for missing `branch` field
    - Test `TicketParseError` for malformed `git url` value
    - Test `TicketParseError` for malformed `branch` value
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 7. Implement `RepoManager`
  - [x] 7.1 Implement `RepoManager.prepare` in `repo_manager.py`
    - Clone the repo into `<working_dir_base>/<ticket_id>/` if no local copy exists; fetch latest if it does
    - Check out the target branch; raise `BranchNotFoundError` if absent on remote
    - Create a feature branch named exactly `ticket_id`
    - Configure `GIT_SSH_COMMAND` when `git_ssh_key_path` is set; inject PAT into remote URL when `git_pat` is set
    - Raise `RepoError` (message must contain the repo URL) on clone/fetch failures
    - Emit log entries at start and end of clone/fetch and branch operations
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 7.1_

  - [x] 7.2 Write property test for checkout branch name (Property 8)
    - **Property 8: Checkout is called with the exact branch name**
    - **Validates: Requirements 3.3**

  - [x] 7.3 Write property test for feature branch naming (Property 9)
    - **Property 9: Feature branch is named after the ticket ID**
    - **Validates: Requirements 3.4**

  - [x] 7.4 Write property test for repo error URL (Property 10)
    - **Property 10: Repository error contains the repo URL**
    - **Validates: Requirements 3.5, 3.6**

  - [x] 7.5 Implement `RepoManager.commit_and_push`
    - Stage all files in the `ChangeSet`, create a commit with message `<ticket_id>: <summary>`
    - Push the feature branch; raise `PushConflictError` on non-fast-forward rejection (never force-push)
    - Raise `EmptyChangeSetError` if the `ChangeSet` is empty
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 7.6 Write property test for staged files (Property 16)
    - **Property 16: All change set files are staged before commit**
    - **Validates: Requirements 5.1**

  - [x] 7.7 Write property test for commit message (Property 17)
    - **Property 17: Commit message contains ticket ID and summary**
    - **Validates: Requirements 5.2**

  - [x] 7.8 Write unit tests for `RepoManager`
    - Test clone path when no local copy exists
    - Test fetch path when local copy exists
    - Test `BranchNotFoundError` when target branch is absent
    - Test `RepoError` on clone/fetch failure
    - Test `PushConflictError` on non-fast-forward push rejection
    - Test `EmptyChangeSetError` when change set is empty
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 5.1, 5.2, 5.3, 5.4, 5.5_

- [ ] 8. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Implement `SpecGenerator`
  - [x] 9.1 Implement `KiroSpec` dataclass and `SpecGenerator.generate` in `spec_generator.py`
    - Create `<working_dir>/.kiro/specs/<ticket_id>/` directory
    - Write `.config.kiro` with a new `uuid4` specId and `"workflowType": "requirements-first"`
    - Write `requirements.md` from ticket summary and description (EARS-style extraction where applicable)
    - Write `design.md` stub with ticket ID, repo URL, branch, summary, and description
    - Write `tasks.md` with one numbered task per acceptance criterion
    - Write the post-task hook JSON to `<working_dir>/.kiro/hooks/commit-and-push.json`
    - Raise `SpecGenerationError` (message must contain the target file path) on any write failure
    - In `dry_run=True` mode, return a `KiroSpec` without writing any files
    - Emit log entries at start and end of spec generation
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 7.1_

  - [x] 9.2 Write property test for spec directory location (Property 11)
    - **Property 11: Spec directory is created under the working directory**
    - **Validates: Requirements 4.1**

  - [x] 9.3 Write property test for spec file content (Property 12)
    - **Property 12: Spec files contain the ticket summary and description**
    - **Validates: Requirements 4.1, 4.2**

  - [x] 9.4 Write property test for tasks file task count (Property 13)
    - **Property 13: Tasks file contains at least one task per acceptance criterion**
    - **Validates: Requirements 4.1**

  - [x] 9.5 Write property test for spec generation error path (Property 14)
    - **Property 14: Spec generation error contains the target file path**
    - **Validates: Requirements 4.4**

  - [x] 9.6 Write property test for dry-run no-write guarantee (Property 15)
    - **Property 15: Spec files are not written in dry-run mode**
    - **Validates: Requirements 8.1, 8.3**

  - [x] 9.7 Write unit tests for `SpecGenerator`
    - Test all four files are written with correct content
    - Test `SpecGenerationError` raised on write failure (mock permission denied)
    - Test dry-run returns `KiroSpec` without writing files
    - Test hook JSON is written to the correct path
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 8.1, 8.3_

- [x] 10. Implement the post-task hook script
  - [x] 10.1 Create `jira_repo_automation/hooks/commit_and_push.py`
    - Parse `--spec-dir` and `--working-dir` CLI arguments
    - Read ticket ID and summary from the spec's `requirements.md` front-matter
    - Use `git diff --name-status HEAD` via GitPython to build a `ChangeSet`
    - Call `RepoManager.commit_and_push`; exit non-zero on `EmptyChangeSetError` or `PushConflictError`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 10.2 Write unit tests for the hook script
    - Test successful commit-and-push flow (mock GitPython)
    - Test non-zero exit on `EmptyChangeSetError`
    - Test non-zero exit on `PushConflictError`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 11. Implement `Orchestrator` and CLI entry point
  - [x] 11.1 Implement `Orchestrator.run` in `orchestrator.py`
    - Drive the pipeline: `ConfigLoader` → `JiraClient` → `TicketParser` → `RepoManager.prepare` → `SpecGenerator.generate`
    - Short-circuit after `SpecGenerator.generate` in dry-run mode and print spec summary to stdout
    - Catch all `AutomationError` subclasses, log at ERROR level with operation name, error message, and ticket ID, then exit non-zero
    - Let unexpected exceptions propagate (stack trace)
    - _Requirements: 7.1, 7.2, 8.1, 8.2, 8.3_

  - [x] 11.2 Implement CLI entry point in `main.py`
    - Use `argparse` to accept `ticket_id`, `--dry-run`, `--config`, `--log-format`, `--verbose`
    - Instantiate `ConfigLoader`, build `Config`, instantiate `Orchestrator`, call `run`
    - _Requirements: 6.1, 6.2, 8.1, 8.2_

  - [x] 11.3 Write unit tests for `Orchestrator`
    - Test full happy-path pipeline (all components mocked)
    - Test dry-run short-circuit (no files written, summary printed)
    - Test each `AutomationError` subclass is caught, logged, and causes non-zero exit
    - _Requirements: 7.1, 7.2, 8.1, 8.2, 8.3_

- [ ] 12. Write integration tests
  - [ ] 12.1 Write integration tests using a local bare git repo
    - Create a local bare repo in a temp directory
    - Run the full clone → branch → spec-write → commit → push flow against it
    - Verify the feature branch exists on the remote with the correct commit message
    - Verify spec files are present in the committed tree
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 5.1, 5.2, 5.3_

- [ ] 13. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Property tests use `hypothesis` with `@settings(max_examples=200)` for critical properties (Properties 3–7, 18–19)
- Properties 11–15 use `tmp_path` for real filesystem writes; all other I/O-touching properties use mocks
- The post-task hook (task 10) is wired by `SpecGenerator` (task 9) — implement task 9 first
