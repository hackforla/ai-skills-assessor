# AISA Bot - Project TODO List  

**Project**: AI-Enabled Skills and Contribution Assessor (POC Phase)  
**Architecture**: GitHub Bot (cron-triggered workflow)  
**Created**: 2025-10-20  
**Total Tasks**: 44  
**Completed**: 1 | **Partially Completed**: 7 | **Pending**: 36  
**Progress**: 8/44 (18.2%)  

---  

## 🤖 GitHub Bot Architecture Overview  

This is a **GitHub-based bot** that runs as a scheduled workflow:  

- **Trigger**: GitHub Actions cron schedule (daily)  
- **Runtime**: GitHub Actions runner executes `scripts/run_poc.py`  
- **Authentication**: Bot account with Personal Access Token  
- **Data Storage**: All data stored IN THE REPO (config, taxonomy, output files)  
- **Configuration**: Bot reads `config/` files from repo (GitHub org/repo names in settings.py)  
- **Outputs**: Bot commits CSV/JSON results to `data/output/` in repo  
- **Secrets Management**:  
  - **Two secrets required**: GITHUB_TOKEN and OPENAI_API_KEY  
  - **Dual storage**: Master copies stored in **1Password** AND configured as **GitHub Actions secrets**  
  - Bot accesses via environment variables at runtime  

### Data Flow:  
```  
1. GitHub Actions cron triggers workflow  
2. Bot reads config/contributors.json from repo  
3. Bot reads data/taxonomy/skills.json from repo  
4. Bot fetches GitHub issues via API (using bot PAT)  
5. Bot calls OpenAI API (using secret API key)  
5.5 > Writes its recommendation of what labels and comments to write the the issue. (Dump the return into a temp file)  
6. Bot posts comments/labels to issues  
7. Bot writes CSV/JSON to data/output/ (logs, errors), Bot commits data/output/ files back to repo  
    - Logs: Audit trail of bot activity (which issues were processed, what actions were taken)  
    - Errors: Any errors encountered during execution  

```  

---  

## Phase 1: Setup & Configuration (Tasks 1-8)  

### ✅ Task 1: Project Structure  
**Status**: COMPLETED  
**Programmer**: Claude Code (2025-10-20)  
**Description**: Set up project structure: Create AISA_Bot/ directory with src/, config/, data/, tests/, and scripts/ subdirectories  

### ⏳ Task 2: Python Package Initialization  
**Status**: PENDING  
**Description**: Initialize Python package: Create __init__.py files in src/ and tests/ directories  

### 🔄 Task 3: .gitignore  
**Status**: PARTIALLY COMPLETED  
**Programmer**: JasonUranta  
**Existing Work**: Root-level [.gitignore](https://github.com/hackforla/ai-skills-assessor/blob/mixin/.gitignore) exists with `.env`, `node_modules/`, `package-lock.json`, `coverage/`  
**Remaining Work**: Need to add `__pycache__`, `*.pyc`, ensure data/output/ and data/taxonomy/ are NOT ignored, move or create AISA_Bot-specific .gitignore    

### 🔄 Task 4: Requirements File  
**Status**: PARTIALLY COMPLETED  
**Programmers**: chinaexpert1, ExperimentsInHonesty  
**Existing Work**: Root-level [requirements.txt](https://github.com/hackforla/ai-skills-assessor/blob/mixin/requirements.txt) exists with `requests>=2.32,<3.0`  
**Remaining Work**: Need to add PyGithub, python-dotenv, openai, pytest, openpyxl/pandas dependencies  

### ⏳ Task 5: Environment Template  
**Status**: PENDING  
**Description**: Create .env.example template with GITHUB_TOKEN and OPENAI_API_KEY placeholders (actual secrets stored in both 1Password AND GitHub secrets)  

### ⏳ Task 6: Settings Configuration  
**Status**: PENDING  
**Description**: Create config/settings.py for constants: GitHub org/repo names, API endpoints, rate limits (500 RPM, 30K TPM), 1-minute timeout per issue, file paths (all paths relative for GitHub Actions runner), SKILL_OUTPUT_MODE configuration  

### ⏳ Task 7: Contributors List  
**Status**: PENDING  
**Description**: Create config/contributors.json with predefined contributor list for POC phase (stored in repo, bot reads from here)  

### 🔄 Task 8: Data Directory Structure  
**Status**: PARTIALLY COMPLETED  
**Programmers**: JasonUranta (scripts/data), Sandy3w (issue_contributor_fetcher)  
**Existing Work**:  
- [`data/`](https://github.com/hackforla/ai-skills-assessor/tree/mixin/data) directory exists with [`issue_comments.json`](https://github.com/hackforla/ai-skills-assessor/blob/mixin/data/issue_comments.json) (246KB)  
- [`API_repo_labels/data/`](https://github.com/hackforla/ai-skills-assessor/tree/mixin/API_repo_labels/data) exists with [`excel_labels_data.xlsx`](https://github.com/hackforla/ai-skills-assessor/blob/mixin/API_repo_labels/data/excel_labels_data.xlsx) (3.5MB) and [`labels_data.json`](https://github.com/hackforla/ai-skills-assessor/blob/mixin/API_repo_labels/data/labels_data.json) (48KB - taxonomy)  
- [`config/`](https://github.com/hackforla/ai-skills-assessor/tree/mixin/config) directory exists with [`target_repos_status.json`](https://github.com/hackforla/ai-skills-assessor/blob/mixin/config/target_repos_status.json)  
**Remaining Work**:  
- Create `AISA_Bot/data/taxonomy/` and move/copy skills taxonomy  
- Create `AISA_Bot/data/temp/` (gitignored)  
- Create `AISA_Bot/data/output/` (committed)  

---  

## Phase 2: Core Modules - GitHub Integration (Tasks 9-10)  

### 🔄 Task 9: GitHub Fetcher Implementation  
**Status**: PARTIALLY COMPLETED  
**Programmers**: JasonUranta (scripts/fetch-issue-comments.py), Sandy3w (issue_contributor_fetcher)  
**Existing Work**:  
- **[scripts/fetch-issue-comments.py](https://github.com/hackforla/ai-skills-assessor/blob/mixin/scripts/fetch-issue-comments.py)** (672 lines) by   JasonUranta: Comprehensive issue comment fetcher with:  
  - Incremental sync using watermarks  
  - Per-endpoint watermarks (issues vs reviews)  
  - Full-resync support  
  - 304/ETag support for conditional requests  
  - Robust pagination with retry logic  
  - Rate-limit handling with exponential backoff (handles 403, 429, Retry-After, X-RateLimit-Reset)  
  - Reaction data collection  
  - Normalized timestamps  
  - Atomic JSON writes  
  - Outputs to [`data/issue_comments.json`](https://github.com/hackforla/ai-skills-assessor/blob/mixin/data/issue_comments.json)  
- **[issue_contributor_fetcher/org_fetcher/org_fetcher.py](https://github.com/hackforla/ai-skills-assessor/blob/mixin/issue_contributor_fetcher/org_fetcher/org_fetcher.py)** (226 lines) by Sandy3w: Org-level contribution fetching  
  - Fetches all repos for an organization  
  - Fetches contributions (issues/PRs) for specified users across repos  
  - HTTPAdapter with retry logic  
  - Pagination handling  
  - Outputs to CSV  
- **[issue_contributor_fetcher/repo_fetcher/repo_fetcher.py](https://github.com/hackforla/ai-skills-assessor/blob/mixin/issue_contributor_fetcher/repo_fetcher/repo_fetcher.py)** (172 lines) by Sandy3w: Repo-level contribution fetching  
  - GitHub Search API with "involves:" query  
  - Session management with retries  
**Remaining Work**:  
- Consolidate into `src/github_fetcher.py` with functions: `fetch_issue()`, `fetch_issue_comments()`, `fetch_issues_for_contributors()`, `check_existing_labels()`  
- Adapt for AISA_Bot requirements and bot account credentials  

### ⏳ Task 10: GitHub Fetcher Tests  
**Status**: PENDING  
**Description**: Create tests/test_github_fetcher.py with unit tests using mocked GitHub API responses and error handling  

---  
  
## Phase 2: Core Modules - Prompt Building (Tasks 11-13)  

### 🔄 Task 11: Prompt Builder Implementation  
**Status**: PARTIALLY COMPLETED  
**Programmer**: Sandy3w  
**Existing Work**:  
- **[API_repo_labels/scripts/excel_to_json.py](https://github.com/hackforla/ai-skills-assessor/blob/mixin/API_repo_labels/scripts/excel_to_json.py)**: Implements taxonomy loading and conversion  
  - Converts [`excel_labels_data.xlsx`](https://github.com/hackforla/ai-skills-assessor/blob/mixin/API_repo_labels/data/excel_labels_data.xlsx) to [`labels_data.json`](https://github.com/hackforla/ai-skills-assessor/blob/mixin/API_repo_labels/data/labels_data.json)  
  - Filters "sure" labels only  
  - Creates keywords from concepts for label assignment  
  - Maps label series to colors  
  - This implements the `load_taxonomy()` functionality  
**Remaining Work**:  
- Implement `format_issue_context()` function  
- Implement `format_contributor_comments()` function  
- Implement `build_llm_prompt()` function for resume bullets and skill classification  
- Consolidate into `src/prompt_builder.py`  

### ⏳ Task 12: LLM Prompt Design  
**Status**: PENDING (Research done by chinaexpert1, pending implementation from Sandy3w)  
**Programmers**: chinaexpert1 (research), Sandy3w (pending implementation)  
**Description**: Design LLM prompt format: STAR method instructions, 30-word limit, skill taxonomy inclusion, JSON output structure for bullets and labels  
**Note**: Prompt research has been completed by chinaexpert1; awaiting implementation from Sandy3w  

### ⏳ Task 13: Prompt Builder Tests  
**Status**: PENDING  
**Description**: Create tests/test_prompt_builder.py with unit tests for prompt formatting and taxonomy loading  

---  

## Phase 2: Core Modules - OpenAI Integration (Tasks 14-15)  

### ⏳ Task 14: OpenAI Client Implementation  
**Status**: PENDING  
**Description**: Implement src/openai_client.py: initialize_client() using GitHub Actions secrets, call_gpt4(), parse_response(), handle_rate_limiting() with exponential backoff for 500 RPM / 30K TPM limits  

### ⏳ Task 15: OpenAI Client Tests  
**Status**: PENDING  
**Description**: Create tests/test_openai_client.py with unit tests using mocked OpenAI API responses  

---  

## Phase 2: Core Modules - Label Handling (Tasks 16-19)  

### ⏳ Task 16: Label Handler Implementation  
**Status**: PENDING  
**Description**: Implement src/label_handler.py: extract_labels_from_response(), validate_labels_against_taxonomy(), get_new_labels() for deduplication, supports both GitHub API labels and comment checklist modes  

### 🔄 Task 17: Label Applier Implementation  
**Status**: PARTIALLY COMPLETED  
**Programmer**: Sandy3w  
**Existing Work**:  
- **[API_repo_labels/scripts/repo_labeler.py](https://github.com/hackforla/ai-skills-assessor/blob/mixin/API_repo_labels/scripts/repo_labeler.py)** (173 lines): Implements comprehensive label creation/application  
  - Checks repo access permissions  
  - Loads labels from [`labels_data.json`](https://github.com/hackforla/ai-skills-assessor/blob/mixin/API_repo_labels/data/labels_data.json)  
  - Creates labels via GitHub API with deduplication  
  - Sophisticated rate limiting:  
    - Primary rate limit handling (X-RateLimit-Remaining)  
    - Secondary rate limit detection ("secondary rate limit" and "abuse detection" in response)  
    - Exponential backoff (starts at 5s, max 60s)  
    - Batch rest every 10 successful creations  
  - This substantially implements the `apply_labels_via_api()` functionality  
**Remaining Work**:  
- Adapt for applying labels to issues (currently creates repo labels)  
- Add `check_existing_labels()` to avoid duplicates on issues  
- Consolidate into `src/label_applier.py`  

### ⏳ Task 18: Label Handler Tests  
**Status**: PENDING  
**Description**: Create tests/test_label_handler.py with unit tests for label validation, deduplication, and taxonomy matching  

### ⏳ Task 19: Label Applier Tests  
**Status**: PENDING  
**Description**: Create tests/test_label_applier.py with unit tests for GitHub API label application and error handling  

---  

## Phase 2: Core Modules - Comment Posting (Tasks 20-23)  

### ⏳ Task 20: Comment Poster Implementation  
**Status**: PENDING  
**Description**: Implement src/comment_poster.py: format_resume_comment(), format_skill_checklist_comment(), post_comment() using bot account with mode configuration for comment vs. API labels  

### ⏳ Task 21: Resume Bullet Template Design  
**Status**: PENDING  
**Description**: Design resume bullet comment template: opening message with automation link, bullets grouped by @username  

### ⏳ Task 22: Skill Label Template Design  
**Status**: PENDING  
**Description**: Design skill label comment template: opening message, markdown checklist format with - [ ] Python, - [ ] Project Management (only used if SKILL_OUTPUT_MODE=comment)  

### ⏳ Task 23: Comment Poster Tests  
**Status**: PENDING  
**Description**: Create tests/test_comment_poster.py with unit tests for both comment formats and posting logic  

---  

## Phase 2: Core Modules - Output & Utils (Tasks 24-25)  

### ⏳ Task 24: Output Writer Implementation  
**Status**: PENDING  
**Description**: Implement src/output_writer.py: save CSV/JSON files to data/output/ in repo (bot commits these files back to repo), schema: contributor_id, contributor_name, issue_id, resume_bullets, skill_labels  

### 🔄 Task 25: Utilities Implementation  
**Status**: PARTIALLY COMPLETED  
**Programmers**: JasonUranta (scripts/fetch-issue-comments.py utilities)  
**Existing Work**:  
- **[scripts/fetch-issue-comments.py](https://github.com/hackforla/ai-skills-assessor/blob/mixin/scripts/fetch-issue-comments.py)** by JasonUranta implements several utility functions:  
  - `save_json_atomic()`: Atomic JSON writes with temp file + rename pattern  
  - `_iso()`: ISO timestamp formatting  
  - `_parse_iso()`: ISO timestamp parsing  
  - `_min_updated()`: Find minimum update timestamp  
  - Logging setup using Python's logging module  
  - File I/O helpers (read_etag, write_etag, read_meta, write_meta)  
- **[API_repo_labels/scripts/repo_labeler.py](https://github.com/hackforla/ai-skills-assessor/blob/mixin/API_repo_labels/scripts/repo_labeler.py)** implements:  
  - Retry logic with exponential backoff  
  - Rate limit handling utilities  
**Remaining Work**:  
- Consolidate utility functions into `src/utils.py`  
- Add temp file management for: comments, prompts, responses, logs per issue  
- Ensure temp files are gitignored and outputs are committed  

---  

## Phase 3: Pipeline Orchestration (Tasks 26-28)  

### ⏳ Task 26: Pipeline Implementation  
**Status**: PENDING  
**Description**: Implement src/pipeline.py: process_issue() with configurable skill output mode (api_labels, comment_checklist, or both), process_contributors(), log_pipeline_activity() with 1-minute timeout   

### ⏳ Task 27: Pipeline Tests  
**Status**: PENDING  
**Description**: Create tests/test_pipeline.py with end-to-end integration tests for all three skill output modes  

### ⏳ Task 28: CLI Entry Point  
**Status**: PENDING   
**Description**: Implement scripts/run_poc.py: CLI entry point for GitHub Actions runner with arguments (--issue, --contributors, --dry-run, --skill-mode [api|comment|both]), progress reporting  

---  

## Phase 4: Error Handling & Logging (Tasks 29-32)  

### 🔄 Task 29: Error Handling Implementation  
**Status**: PARTIALLY COMPLETED  
**Programmers**: JasonUranta (scripts/fetch-issue-comments.py)  
**Existing Work**:  
- **[scripts/fetch-issue-comments.py](https://github.com/hackforla/ai-skills-assessor/blob/mixin/scripts/fetch-issue-comments.py)** by JasonUranta implements error handling:  
  - Try-except blocks for network errors, JSON parsing errors  
  - Logging of errors with logger.error() and logger.warning()  
  - Specific handling for different HTTP status codes (401, 404, 422, 500, 502, 503, 504)  
  - Graceful degradation with partial failure tolerance  
- **[API_repo_labels/scripts/repo_labeler.py](https://github.com/hackforla/ai-skills-assessor/blob/mixin/API_repo_labels/scripts/repo_labeler.py)** implements:  
  - Error detection and logging  
  - Retry logic for transient errors  
**Remaining Work**:  
- Add functionality to post public error messages to GitHub issues  
- Create structured error log file (stored in repo)  
- Implement user-friendly error messages with error codes  

### 🔄 Task 30: Rate Limiting Implementation  
**Status**: PARTIALLY COMPLETED (GitHub API only)  
**Programmers**: JasonUranta (scripts/fetch-issue-comments.py)  
**Existing Work - GitHub API Rate Limiting**:  
- **[scripts/fetch-issue-comments.py](https://github.com/hackforla/ai-skills-assessor/blob/mixin/scripts/fetch-issue-comments.py)** by JasonUranta (comprehensive implementation):  
  - Handles 403/429 status codes  
  - Respects X-RateLimit-Remaining header   
  - Secondary rate limit detection ("secondary rate limit", "abuse detection" in response body)  
  - Retry-After header parsing (both delta-seconds and HTTP-date formats)  
  - X-RateLimit-Reset header support  
  - Exponential backoff (BASE_BACKOFF=5s, MAX_BACKOFF=60s)  
  - Sleep budget tracking (MAX_TOTAL_SLEEP=600s per endpoint)  
  - Jitter addition to prevent thundering herd  
- **[API_repo_labels/scripts/repo_labeler.py](https://github.com/hackforla/ai-skills-assessor/blob/mixin/API_repo_labels/scripts/repo_labeler.py)**:  
  - Primary rate limit handling (X-RateLimit-Remaining)  
  - Secondary rate limit detection  
  - Exponential backoff (starts at 5s, max 60s)   
  - Batch rest every 10 successful creations  
- **[API_repo_labels/scripts/label_delete.py](https://github.com/hackforla/ai-skills-assessor/blob/mixin/API_repo_labels/scripts/label_delete.py)**:  
  - Retry logic with exponential backoff for 403 responses  
**Remaining Work**:  
- Implement OpenAI Tier 1 rate limiting (500 RPM, 30K TPM)  
- Consolidate GitHub rate limiting into src/utils.py or src/github_fetcher.py  

### ⏳ Task 31: Audit Logging System  
**Status**: PENDING  
**Description**: Create audit logging system: log all bot activity (user mentions, generated content, labels applied/posted, errors) to data/output/audit_log.json committed to repo  

### ⏳ Task 32: Temp File Generation  
**Status**: PENDING  
**Description**: Implement temp file generation per issue: data/temp/issue_<number>_comments.json, issue_<number>_prompt.txt, issue_<number>_response.json, issue_<number>_log.json (gitignored, not committed)  

---  

## Phase 5: Documentation (Tasks 33-34)  

### ⏳ Task 33: README Documentation  
**Status**: PENDING  
**Description**: Create comprehensive README.md: project overview, GitHub bot architecture, setup instructions for configuring two secrets (GITHUB_TOKEN and OPENAI_API_KEY stored in both 1Password and GitHub), environment configuration, skill output mode options, usage examples, credit to true-github-contributors  

### ⏳ Task 34: Configuration Documentation  
**Status**: PENDING  
**Description**: Document configuration options: SKILL_OUTPUT_MODE (api_labels, comment_checklist, both), GitHub Actions secrets setup (two secrets: GITHUB_TOKEN and OPENAI_API_KEY), bot account permissions in README and settings.py  

---  

## Phase 6: Testing & Validation (Tasks 35-38)  

### ⏳ Task 35: Unit Testing  
**Status**: PENDING  
**Description**: Run unit tests for all three skill output modes and achieve >80% code coverage  

### ⏳ Task 36: Integration Testing  
**Status**: PENDING  
**Description**: Perform integration testing with real GitHub API and OpenAI API on test repository for all output modes  
  
### ⏳ Task 37: Output Quality Validation  
**Status**: PENDING  
**Description**: Validate LLM output quality: verify STAR format compliance, 30-word limit per bullet, skill labels match HfLA_skills.csv taxonomy  

### ⏳ Task 38: Label Application Testing  
**Status**: PENDING  
**Description**: Test label application: verify GitHub API labels are applied correctly, existing labels are not duplicated, checklist comments format properly  

---  

## Phase 7: Performance & Deployment (Tasks 39-41)  

### ⏳ Task 39: Performance Testing  
**Status**: PENDING  
**Description**: Performance testing: measure processing time per issue (must be ≤1 minute), identify bottlenecks, optimize if needed  

### ⏳ Task 40: GitHub Actions Workflow  
**Status**: PENDING  
**Description**: Create GitHub Actions workflow: .github/workflows/ai-skills-assessor.yml with cron schedule (daily trigger), job that runs scripts/run_poc.py, configurable skill output mode, secrets for GITHUB_TOKEN and OPENAI_API_KEY, auto-commit data/output/ files back to repo  

### ⏳ Task 41: Configure GitHub Actions Secrets  
**Status**: PENDING  
**Description**: Configure GitHub Actions secrets in hackforla/ai-skills-assessor repo: add GITHUB_TOKEN (bot PAT) and OPENAI_API_KEY as repository secrets (master copies also stored in 1Password), verify bot account has collaborator permissions  

---  

## Phase 8: POC Evaluation (Tasks 42-44)  

### ⏳ Task 42: Workflow Testing  
**Status**: PENDING  
**Description**: Test workflow execution: verify cron trigger works, bot reads config/taxonomy from repo, processes issues, commits results to data/output/, secrets are properly configured, runs across all open issues in Hack for LA org  

### ⏳ Task 43: POC Evaluation Run  
**Status**: PENDING  
**Description**: Run POC evaluation on 10-20 closed test issues from hackforla/website repo with different skill output modes, verify data/output/ files are committed to repo  

### ⏳ Task 44: Evaluation Report  
**Status**: PENDING  
**Description**: Generate evaluation report with metrics: processing time, output quality, error rates, API cost analysis, comparison of skill output modes, commit report to repo  

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

### Planned AISA_Bot Structure (Target)  

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

### Current Repository Structure (As of 2025-10-20)  

```  
ai-skills-assessor/ (root)  
├── .github/  
│   └── workflows/                         [JasonUranta]  
├── .gitignore                             [JasonUranta]  
├── AISA_Bot/                              [Claude Code - NEW]  
│   ├── config/                            [Created, empty]  
│   ├── data/                              [Created, empty]  
│   ├── scripts/                           [Created, empty]  
│   ├── src/                               [Created, empty]  
│   ├── tests/                             [Created, empty]  
│   ├── TODO.docx                          [Generated]  
│   └── TODO.md                            [This file]  
├── API_repo_labels/                       [Sandy3w]  
│   ├── data/  
│   │   ├── excel_labels_data.xlsx         [Skills taxonomy - 3.5MB]  
│   │   └── labels_data.json               [Processed taxonomy - 48KB]  
│   └── scripts/  
│       ├── excel_to_json.py               [Taxonomy converter]  
│       ├── label_delete.py                [Label deletion with retry]  
│       └── repo_labeler.py                [Label creation/application - 173 lines]  
├── config/  
│   └── target_repos_status.json           [Configuration file]  
├── data/  
│   └── issue_comments.json                [Output - 246KB]  
├── issue_contributor_fetcher/             [Sandy3w]  
│   ├── org_fetcher/  
│   │   └── org_fetcher.py                 [Org-level fetching - 226 lines]  
│   └── repo_fetcher/  
│       └── repo_fetcher.py                [Repo-level fetching - 172 lines]  
├── scripts/                               [JasonUranta]  
│   └── fetch-issue-comments.py            [Comprehensive fetcher - 672 lines]  
├── CLAUDE_CONTEXT.md                      [Project context]  
├── conversion_to_python.py                [JS to Python conversion helper]  
├── convert_todo_to_docx.py                [TODO documentation generator]  
├── LAST_CLAUDE_CHAT.md                    [Previous session summary]  
├── README.md                              [TBD]  
└── requirements.txt                       [chinaexpert1, ExperimentsInHonesty]  
```  

**Structure Notes**:  
- **AISA_Bot/**: New target structure for consolidated bot code (created 2025-10-20)  
- **API_repo_labels/**: Sandy3w's R&D work on label taxonomy and application  
- **issue_contributor_fetcher/**: Sandy3w's R&D work on GitHub data fetching  
- **scripts/**: JasonUranta's production-quality comment fetcher  
- Root-level files contain existing R&D code to be consolidated  

---  

## References  
- **Requirements Document**: AISA Requirements Doc v2.pdf  
- **Context Files**: CLAUDE_CONTEXT.md, LAST_CLAUDE_CHAT.md  
- **Original Package**: true-github-contributors (JavaScript)  
- **Skills Taxonomy**: HfLA_skills.csv  

---  

## 📊 Code Completion Summary  

### Existing Code Assets (R&D Work)  

The following scripts contain substantial functionality that can be consolidated into AISA_Bot:  

1. **[scripts/fetch-issue-comments.py](https://github.com/hackforla/ai-skills-assessor/blob/mixin/scripts/fetch-issue-comments.py)** (672 lines) - **JasonUranta**  
   - Comprehensive GitHub issue/PR comment fetcher  
   - Incremental sync, ETag support, watermarks  
   - Sophisticated rate limiting and error handling  
   - Maps to: Task 9 (github_fetcher.py), Task 25 (utils.py), Task 29 (error handling), Task 30 (rate limiting)  

2. **[API_repo_labels/scripts/repo_labeler.py](https://github.com/hackforla/ai-skills-assessor/blob/mixin/API_repo_labels/scripts/repo_labeler.py)** (173 lines) - **Sandy3w**  
   - Label creation via GitHub API  
   - Deduplication, rate limiting, batch processing  
   - Maps to: Task 17 (label_applier.py), Task 30 (rate limiting)  

3. **[API_repo_labels/scripts/excel_to_json.py](https://github.com/hackforla/ai-skills-assessor/blob/mixin/API_repo_labels/scripts/excel_to_json.py)** - **Sandy3w**  
   - Taxonomy loading and conversion  
   - Maps to: Task 11 (prompt_builder.py - load_taxonomy())  

4. **[issue_contributor_fetcher/org_fetcher/org_fetcher.py](https://github.com/hackforla/ai-skills-assessor/blob/mixin/issue_contributor_fetcher/org_fetcher/org_fetcher.py)** (226 lines) - **Sandy3w**  
   - Organization-level contribution fetching  
   - Maps to: Task 9 (github_fetcher.py - fetch_issues_for_contributors())  

5. **[issue_contributor_fetcher/repo_fetcher/repo_fetcher.py](https://github.com/hackforla/ai-skills-assessor/blob/mixin/issue_contributor_fetcher/repo_fetcher/repo_fetcher.py)** (172 lines) - **Sandy3w**  
   - Repository-level contribution fetching  
   - Maps to: Task 9 (github_fetcher.py - fetch_issues_for_contributors())  

6. **[API_repo_labels/scripts/label_delete.py](https://github.com/hackforla/ai-skills-assessor/blob/mixin/API_repo_labels/scripts/label_delete.py)** - **Sandy3w**  
   - Label deletion with retry logic  
   - Maps to: Task 30 (rate limiting patterns)  

7. **LLM Prompt Research** - **chinaexpert1**  
   - Research completed for Task 12 (LLM prompt design)  
   - Awaiting implementation from Sandy3w  

### Completion Status by Phase  

- **Phase 1 (Setup)**: 1 completed, 3 partially completed, 4 pending  
- **Phase 2 (Core Modules)**: 0 completed, 4 partially completed, 11 pending  
- **Phase 3 (Pipeline)**: 0 completed, 0 partially completed, 3 pending  
- **Phase 4 (Error/Logging)**: 0 completed, 2 partially completed, 2 pending  
- **Phase 5 (Documentation)**: 0 completed, 0 partially completed, 2 pending  
- **Phase 6 (Testing)**: 0 completed, 0 partially completed, 4 pending  
- **Phase 7 (Deployment)**: 0 completed, 0 partially completed, 3 pending  
- **Phase 8 (Evaluation)**: 0 completed, 0 partially completed, 3 pending  

### Next Steps  

1. **Consolidation Phase**: Move existing R&D code into AISA_Bot structure  
   - Create src/github_fetcher.py from [scripts/fetch-issue-comments.py](https://github.com/hackforla/ai-skills-assessor/blob/mixin/scripts/fetch-issue-comments.py) + [org_fetcher.py](https://github.com/hackforla/ai-skills-assessor/blob/mixin/issue_contributor_fetcher/org_fetcher/org_fetcher.py) + [repo_fetcher.py](https://github.com/hackforla/ai-skills-assessor/blob/mixin/issue_contributor_fetcher/repo_fetcher/repo_fetcher.py)  
   - Create src/label_applier.py from [API_repo_labels/scripts/repo_labeler.py](https://github.com/hackforla/ai-skills-assessor/blob/mixin/API_repo_labels/scripts/repo_labeler.py)  
   - Create src/prompt_builder.py incorporating [API_repo_labels/scripts/excel_to_json.py](https://github.com/hackforla/ai-skills-assessor/blob/mixin/API_repo_labels/scripts/excel_to_json.py)  
   - Create src/utils.py from common utility functions  

2. **New Development**: Implement missing components  
   - OpenAI client (Task 14)  
   - Comment poster (Task 20)  
   - Pipeline orchestration (Task 26)  
   - CLI entry point (Task 28)  

---  

## 👥 Contributors  

### Code Contributors  
- **JasonUranta**: [scripts/fetch-issue-comments.py](https://github.com/hackforla/ai-skills-assessor/blob/mixin/scripts/fetch-issue-comments.py), [.github workflows](https://github.com/hackforla/ai-skills-assessor/tree/mixin/.github), [.gitignore](https://github.com/hackforla/ai-skills-assessor/blob/mixin/.gitignore), data management utilities  
- **Sandy3w**: [issue_contributor_fetcher](https://github.com/hackforla/ai-skills-assessor/tree/mixin/issue_contributor_fetcher) ([org_fetcher.py](https://github.com/hackforla/ai-skills-assessor/blob/mixin/issue_contributor_fetcher/org_fetcher/org_fetcher.py), [repo_fetcher.py](https://github.com/hackforla/ai-skills-assessor/blob/mixin/issue_contributor_fetcher/repo_fetcher/repo_fetcher.py)), [API_repo_labels](https://github.com/hackforla/ai-skills-assessor/tree/mixin/API_repo_labels) ([excel_to_json.py](https://github.com/hackforla/ai-skills-assessor/blob/mixin/API_repo_labels/scripts/excel_to_json.py), [repo_labeler.py](https://github.com/hackforla/ai-skills-assessor/blob/mixin/API_repo_labels/scripts/repo_labeler.py), [label_delete.py](https://github.com/hackforla/ai-skills-assessor/blob/mixin/API_repo_labels/scripts/label_delete.py)), pending prompt implementation  
- **chinaexpert1**: [requirements.txt](https://github.com/hackforla/ai-skills-assessor/blob/mixin/requirements.txt), LLM prompt research (Task 12)  
- **ExperimentsInHonesty**: [requirements.txt](https://github.com/hackforla/ai-skills-assessor/blob/mixin/requirements.txt)  
- **Claude Code**: Project structure setup (AISA_Bot directory)  

### Research & Documentation  
- **chinaexpert1**: LLM prompt design research (awaiting implementation from Sandy3w)  

### Pending Work Assignments  
- **Sandy3w**: Task 12 implementation (LLM prompt format)  

---  

*Last Updated: 2025-10-20*  