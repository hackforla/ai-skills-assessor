# AISA Bot - Project TODO List

**Project**: AI-Enabled Skills and Contribution Assessor (POC Phase)
**Architecture**: GitHub Bot (cron-triggered workflow)
**Created**: 2025-10-20
**Total Tasks**: 45
**Progress**: 1/45 (2.2%)

---

## 🤖 GitHub Bot Architecture Overview

This is a **GitHub-based bot** that runs as a scheduled workflow:

- **Trigger**: GitHub Actions cron schedule (daily)
- **Runtime**: GitHub Actions runner executes `scripts/run_poc.py`
- **Authentication**: Bot account with Personal Access Token
- **Data Storage**: All data stored IN THE REPO (config, taxonomy, output files)
- **Configuration**: Bot reads `config/` files from repo
- **Outputs**: Bot commits CSV/JSON results to `data/output/` in repo
- **Secrets Management** (pending Bonnie's decision):
  - **Option 1**: Master secrets stored in **1Password**, retrieved and configured as GitHub Actions secrets
  - **Option 2**: Secrets stored directly in **GitHub repository secrets**
  - Bot accesses via environment variables at runtime (same for both options)

### Data Flow:
```
1. GitHub Actions cron triggers workflow
2. Bot reads config/contributors.json from repo
3. Bot reads data/taxonomy/skills.json from repo
4. Bot fetches GitHub issues via API (using bot PAT)
5. Bot calls OpenAI API (using secret API key)
6. Bot posts comments/labels to issues
7. Bot writes CSV/JSON to data/output/
8. Bot commits data/output/ files back to repo
```

---

## Phase 1: Setup & Configuration (Tasks 1-9)

### ✅ Task 1: Project Structure
**Status**: COMPLETED
**Description**: Set up project structure: Create AISA_Bot/ directory with src/, config/, data/, tests/, and scripts/ subdirectories

### ⏳ Task 2: Python Package Initialization
**Status**: PENDING
**Description**: Initialize Python package: Create __init__.py files in src/ and tests/ directories

### ⏳ Task 3: .gitignore
**Status**: PENDING
**Description**: Create .gitignore file excluding .env, __pycache__, *.pyc (but INCLUDE data/output/ and data/taxonomy/ for GitHub repo storage)

### ⏳ Task 4: Requirements File
**Status**: PENDING
**Description**: Create requirements.txt with dependencies: PyGithub, python-dotenv, openai, pytest, openpyxl/pandas for CSV parsing

### ⏳ Task 5: Environment Template
**Status**: PENDING
**Description**: Create .env.example template with GITHUB_TOKEN, OPENAI_API_KEY, GITHUB_ORG, GITHUB_REPO placeholders (actual secrets stored in 1Password OR GitHub secrets per Bonnie's decision, configured as GitHub Actions secrets)

### ⏳ Task 6: Settings Configuration
**Status**: PENDING
**Description**: Create config/settings.py for constants: API endpoints, rate limits (500 RPM, 30K TPM), 1-minute timeout per issue, file paths, SKILL_OUTPUT_MODE configuration

### ⏳ Task 7: Contributors List
**Status**: PENDING
**Description**: Create config/contributors.json with predefined contributor list for POC phase

### ⏳ Task 8: Skills Taxonomy
**Status**: PENDING
**Description**: Locate and examine HfLA_skills.csv file structure for skill taxonomy (convert to data/taxonomy/skills.json if needed)

### ⏳ Task 9: Data Directory Structure
**Status**: PENDING
**Description**: Create data/ directory structure: data/taxonomy/, data/temp/, data/output/ for CSV/JSON output files

---

## Phase 2: Core Modules - GitHub Integration (Tasks 10-11)

### ⏳ Task 10: GitHub Fetcher Implementation
**Status**: PENDING
**Description**: Implement src/github_fetcher.py: fetch_issue(), fetch_issue_comments(), fetch_issues_for_contributors(), check_existing_labels()

### ⏳ Task 11: GitHub Fetcher Tests
**Status**: PENDING
**Description**: Create tests/test_github_fetcher.py with unit tests using mocked GitHub API responses and error handling

---

## Phase 2: Core Modules - Prompt Building (Tasks 12-14)

### ⏳ Task 12: Prompt Builder Implementation
**Status**: PENDING
**Description**: Implement src/prompt_builder.py: load_taxonomy(), format_issue_context(), format_contributor_comments(), build_llm_prompt() for resume bullets and skill classification

### ⏳ Task 13: LLM Prompt Design
**Status**: PENDING
**Description**: Design LLM prompt format: STAR method instructions, 30-word limit, skill taxonomy inclusion, JSON output structure for bullets and labels

### ⏳ Task 14: Prompt Builder Tests
**Status**: PENDING
**Description**: Create tests/test_prompt_builder.py with unit tests for prompt formatting and taxonomy loading

---

## Phase 2: Core Modules - OpenAI Integration (Tasks 15-16)

### ⏳ Task 15: OpenAI Client Implementation
**Status**: PENDING
**Description**: Implement src/openai_client.py: initialize_client(), call_gpt4(), parse_response(), handle_rate_limiting() with exponential backoff for 500 RPM / 30K TPM limits

### ⏳ Task 16: OpenAI Client Tests
**Status**: PENDING
**Description**: Create tests/test_openai_client.py with unit tests using mocked OpenAI API responses

---

## Phase 2: Core Modules - Label Handling (Tasks 17-20)

### ⏳ Task 17: Label Handler Implementation
**Status**: PENDING
**Description**: Implement src/label_handler.py: extract_labels_from_response(), validate_labels_against_taxonomy(), get_new_labels() for deduplication, supports both GitHub API labels and comment checklist modes

### ⏳ Task 18: Label Applier Implementation
**Status**: PENDING
**Description**: Implement src/label_applier.py: apply_labels_via_api() to apply skill labels directly to issues via GitHub API, check existing labels to avoid duplicates

### ⏳ Task 19: Label Handler Tests
**Status**: PENDING
**Description**: Create tests/test_label_handler.py with unit tests for label validation, deduplication, and taxonomy matching

### ⏳ Task 20: Label Applier Tests
**Status**: PENDING
**Description**: Create tests/test_label_applier.py with unit tests for GitHub API label application and error handling

---

## Phase 2: Core Modules - Comment Posting (Tasks 21-24)

### ⏳ Task 21: Comment Poster Implementation
**Status**: PENDING
**Description**: Implement src/comment_poster.py: format_resume_comment(), format_skill_checklist_comment(), post_comment() with mode configuration for comment vs. API labels

### ⏳ Task 22: Resume Bullet Template Design
**Status**: PENDING
**Description**: Design resume bullet comment template: opening message with automation link, bullets grouped by @username

### ⏳ Task 23: Skill Label Template Design
**Status**: PENDING
**Description**: Design skill label comment template: opening message, markdown checklist format with - [ ] Python, - [ ] Project Management (only used if SKILL_OUTPUT_MODE=comment)

### ⏳ Task 24: Comment Poster Tests
**Status**: PENDING
**Description**: Create tests/test_comment_poster.py with unit tests for both comment formats and posting logic

---

## Phase 2: Core Modules - Output & Utils (Tasks 25-26)

### ⏳ Task 25: Output Writer Implementation
**Status**: PENDING
**Description**: Implement src/output_writer.py: save CSV/JSON files to /data/output/ with schema: contributor_id, contributor_name, issue_id, resume_bullets, skill_labels

### ⏳ Task 26: Utilities Implementation
**Status**: PENDING
**Description**: Implement src/utils.py: logging utilities, file I/O helpers, temp file management (comments, prompts, responses, logs per issue)

---

## Phase 3: Pipeline Orchestration (Tasks 27-29)

### ⏳ Task 27: Pipeline Implementation
**Status**: PENDING
**Description**: Implement src/pipeline.py: process_issue() with configurable skill output mode (api_labels, comment_checklist, or both), process_contributors(), log_pipeline_activity() with 1-minute timeout

### ⏳ Task 28: Pipeline Tests
**Status**: PENDING
**Description**: Create tests/test_pipeline.py with end-to-end integration tests for all three skill output modes

### ⏳ Task 29: CLI Entry Point
**Status**: PENDING
**Description**: Implement scripts/run_poc.py: CLI entry point with arguments (--issue, --contributors, --dry-run, --skill-mode [api|comment|both]), progress reporting

---

## Phase 4: Error Handling & Logging (Tasks 30-33)

### ⏳ Task 30: Error Handling Implementation
**Status**: PENDING
**Description**: Implement error handling: post public error messages to issues with error code and user-friendly message, log full error details to structured error log

### ⏳ Task 31: Rate Limiting Implementation
**Status**: PENDING
**Description**: Implement rate limiting with throttling logic: respect OpenAI Tier 1 limits (500 RPM, 30K TPM) and GitHub API limits, implement exponential backoff

### ⏳ Task 32: Audit Logging System
**Status**: PENDING
**Description**: Create audit logging system: log all bot activity (user mentions, generated content, labels applied/posted, errors) to structured log files

### ⏳ Task 33: Temp File Generation
**Status**: PENDING
**Description**: Implement temp file generation per issue: issue_<number>_comments.json, issue_<number>_prompt.txt, issue_<number>_response.json, issue_<number>_log.json

---

## Phase 5: Documentation (Tasks 34-35)

### ⏳ Task 34: README Documentation
**Status**: PENDING
**Description**: Create comprehensive README.md: project overview, GitHub bot architecture, setup instructions for Actions secrets (from 1Password OR GitHub secrets per Bonnie's decision), environment configuration, skill output mode options, usage examples, credit to true-github-contributors

### ⏳ Task 35: Configuration Documentation
**Status**: PENDING
**Description**: Document configuration options: SKILL_OUTPUT_MODE (api_labels, comment_checklist, both), GitHub Actions secrets setup, bot account permissions, secrets management (1Password vs GitHub) in README and settings.py

---

## Phase 6: Testing & Validation (Tasks 36-39)

### ⏳ Task 36: Unit Testing
**Status**: PENDING
**Description**: Run unit tests for all three skill output modes and achieve >80% code coverage

### ⏳ Task 37: Integration Testing
**Status**: PENDING
**Description**: Perform integration testing with real GitHub API and OpenAI API on test repository for all output modes

### ⏳ Task 38: Output Quality Validation
**Status**: PENDING
**Description**: Validate LLM output quality: verify STAR format compliance, 30-word limit per bullet, skill labels match HfLA_skills.csv taxonomy

### ⏳ Task 39: Label Application Testing
**Status**: PENDING
**Description**: Test label application: verify GitHub API labels are applied correctly, existing labels are not duplicated, checklist comments format properly

---

## Phase 7: Performance & Deployment (Tasks 40-42)

### ⏳ Task 40: Performance Testing
**Status**: PENDING
**Description**: Performance testing: measure processing time per issue (must be ≤1 minute), identify bottlenecks, optimize if needed

### ⏳ Task 41: GitHub Actions Workflow
**Status**: PENDING
**Description**: Create GitHub Actions workflow: .github/workflows/ai-skills-assessor.yml with cron schedule (daily trigger), job that runs scripts/run_poc.py, configurable skill output mode, secrets for GITHUB_TOKEN and OPENAI_API_KEY, auto-commit data/output/ files back to repo

### ⏳ Task 41b: Configure GitHub Actions Secrets
**Status**: PENDING
**Description**: Configure GitHub Actions secrets in hackforla/ai-skills-assessor repo: retrieve GITHUB_TOKEN (bot PAT) and OPENAI_API_KEY from 1Password OR use GitHub-stored secrets per Bonnie's decision, add as repository secrets, verify bot account has collaborator permissions

### ⏳ Task 42: Workflow Testing
**Status**: PENDING
**Description**: Test workflow execution: verify daily trigger works, secrets are properly configured, skill output mode configuration works, runs across all open issues in Hack for LA org

---

## Phase 8: POC Evaluation (Tasks 43-44)

### ⏳ Task 43: POC Evaluation Run
**Status**: PENDING
**Description**: Run POC evaluation on 10-20 closed test issues from hackforla/website repo with different skill output modes

### ⏳ Task 44: Evaluation Report
**Status**: PENDING
**Description**: Generate evaluation report with metrics: processing time, output quality, error rates, API cost analysis, comparison of skill output modes

---

## Key Technical Requirements

### API Rate Limits
- **OpenAI Tier 1**: 500 RPM, 30,000 TPM
- **Processing Time**: ≤1 minute per issue
- **Throttling**: Exponential backoff required

### Skill Output Modes
1. **api_labels**: Apply labels directly via GitHub API
2. **comment_checklist**: Post markdown checklist in comment
3. **both**: Apply labels AND post checklist

### Output Requirements
- **Resume Bullets**: STAR format, ≤30 words, grouped by @username
- **Skill Labels**: From HfLA_skills.csv taxonomy
- **File Formats**: CSV and JSON to /data/output/
- **Temp Files**: 4 files per issue (comments, prompt, response, log)

### Testing Requirements
- Unit tests with >80% coverage
- Integration tests for all 3 skill output modes
- Performance tests (≤1 minute per issue)
- Output quality validation

---

## Project Structure

```
AISA_Bot/
├── src/
│   ├── __init__.py
│   ├── github_fetcher.py
│   ├── prompt_builder.py
│   ├── openai_client.py
│   ├── label_handler.py
│   ├── label_applier.py
│   ├── comment_poster.py
│   ├── output_writer.py
│   ├── utils.py
│   └── pipeline.py
├── config/
│   ├── settings.py
│   └── contributors.json
├── data/
│   ├── taxonomy/
│   │   └── skills.json
│   ├── temp/
│   └── output/
├── tests/
│   ├── __init__.py
│   ├── test_github_fetcher.py
│   ├── test_prompt_builder.py
│   ├── test_openai_client.py
│   ├── test_label_handler.py
│   ├── test_label_applier.py
│   ├── test_comment_poster.py
│   └── test_pipeline.py
├── scripts/
│   └── run_poc.py
├── .env
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
└── TODO.md (this file)
```

---

## References
- **Requirements Document**: AISA Requirements Doc v2.pdf
- **Context Files**: CLAUDE_CONTEXT.md, LAST_CLAUDE_CHAT.md
- **Original Package**: true-github-contributors (JavaScript)
- **Skills Taxonomy**: HfLA_skills.csv

---

*Last Updated: 2025-10-20*
