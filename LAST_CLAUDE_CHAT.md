# AI Skills Assessor - Project Knowledge Summary

**Last Updated:** 2025-10-17
**Session Focus:** Initial project setup and requirements clarification

---

## Executive Summary

The AI Skills Assessor is a Python-based automation tool that analyzes GitHub issue contributions for Hack for LA contributors and generates:
1. **Resume-ready bullet points** (STAR format, ≤30 words) posted as comments to issues
2. **Skill labels** automatically applied to issues via GitHub API (based on taxonomy)

This document captures the current understanding of the project and provides a roadmap for the Proof of Concept (PoC) phase.

---

## Project Context

### Repository Background
This repository originally housed the **true-github-contributors** JavaScript package (v1.0.5), an Octokit mixin that aggregates GitHub contributors from both commits AND issue comments. That work serves as foundational research for this new Python-based project.

**Key Files from Original Work:**
- `trueContributors-mixin.js` - JavaScript implementation
- `API_repo_labels/` - Label management scripts (Python-based)
- `API_repo_labels/data/excel_labels_data.xlsx` - Skills taxonomy
- `examples/` - Usage examples for various endpoints

### New Project Home
The AI Skills Assessor will live in a new directory:
```
ai-skills-assessor-python/
```

All prior work in the repo root is considered R&D and will be referenced but not directly integrated.

---

## What This Tool Does

### Problem Statement
Hack for LA needs to:
- Recognize intern/volunteer contributions across issue discussions (not just code commits)
- Help contributors generate resume bullets from their open-source work
- Classify skills gained per issue for contributor growth tracking

### Solution Architecture
**Input:** GitHub issue with multiple contributor comments
**Process:** LLM analyzes issue context + comments
**Output:**
1. Comment posted to issue with STAR-formatted resume bullets grouped by contributor
2. Skill labels applied directly to the issue (no duplication of existing labels)

### Key Features
- **Automated skill classification** from predefined taxonomy (`excel_labels_data.xlsx`)
- **Resume bullet generation** using STAR methodology (Situation, Task, Action, Result)
- **Per-issue pipeline** designed for future webhook-based triggering
- **Platform-agnostic LLM integration** (not locked to specific provider)
- **Error handling** with public error messages posted to issues + detailed logging

---

## Technical Architecture

### Core Components (Modular Pipeline)

| Module | Purpose | Key Functionality |
|--------|---------|-------------------|
| `github_fetcher.py` | GitHub API interactions | Fetch issue data (title, body, comments, URLs) |
| `llm_client.py` | LLM API wrapper | Platform-agnostic LLM calls (OpenAI, Anthropic, etc.) |
| `prompt_builder.py` | Prompt formatting | Combine issue context + taxonomy + comments into structured prompt |
| `label_applier.py` | Label management | Apply labels via GitHub API, skip existing labels (reuses `API_repo_labels` logic) |
| `comment_poster.py` | Comment posting | Post formatted resume bullets to issue |
| `pipeline.py` | Orchestration | Full workflow coordination |

### Data Flow
```
1. Fetch issue data (GitHub API)
   ↓
2. Load taxonomy (excel_labels_data.xlsx)
   ↓
3. Build LLM prompt (issue context + comments + taxonomy)
   ↓
4. Call LLM API
   ↓
5. Parse LLM response (extract labels + bullets)
   ↓
6. Apply labels to issue (GitHub API) [skip duplicates]
   ↓
7. Post resume bullets as comment (GitHub API)
   ↓
8. Log all activity to temp files
```

### Temp Files Generated (Per Issue)
1. **`issue_<number>_comments.json`** - All GitHub comments with URLs
2. **`issue_<number>_prompt.txt`** - Full LLM prompt sent
3. **`issue_<number>_response.json`** - LLM API response (labels + bullets)
4. **`issue_<number>_log.json`** - Audit log (which comments used, which labels applied)

### Authentication
- **GitHub Bot Token:** Available, configured with proper permissions
- **LLM API Key:** Pending, will use environment variable placeholders

---

## PoC Phase Requirements (from AISA Requirements Doc v2)

### Scope Constraints
- **Predefined contributor list** (no user input)
- **Single repository:** `hackforla/website`
- **Closed issues only** (all issues are completed for PoC)
- **No GUI** - automated backend scripts only

### Functional Requirements

#### Data Processing
- Fetch comments per issue for each contributor via GitHub Issue API
- Extract context from issue title, body, and action items
- Submit combined context to LLM (the chosen LLM, platform-agnostic)

#### Output: Resume Bullets
- **Format:** STAR method (Situation, Task, Action, Result)
- **Length:** Maximum 30 words per bullet
- **Style:** Formal, software development concepts
- **Status:** Explicitly state task completion (all closed for PoC)
- **Grouping:** Organized by contributor GitHub handle

**Example Comment Format:**
```markdown
[Opening message describing purpose with automation documentation link]

@username1
- Resume Bullet 1
- Resume Bullet 2

@username2
- Resume Bullet 1
- Resume Bullet 2
```

#### Output: Skill Labels
- **Source:** `HfLA_skills.csv` (actually `excel_labels_data.xlsx` in `API_repo_labels/data/`)
- **Application:** Multiple skill labels assigned per issue
- **Method:** GitHub API label application (no duplication)
- **Visibility:** Labels appear on issue, NOT mentioned in comments

### Non-Functional Requirements

#### Performance
- **Target:** ≤1 minute per issue per user
- **Bottleneck:** LLM API latency (not GitHub API)

#### Error Handling
- **Public errors:** Post user-friendly error message to issue
- **Logging:** Detailed error log files for pattern analysis
- **Rate limiting:** Respect LLM API limits (e.g., OpenAI Tier 1: 500 RPM, 30K TPM)

#### Security
- No encryption/anonymization required
- No privacy concerns
- Standard bot authentication via Personal Access Token

#### Deployment
- Runs daily via time-triggered script (GitHub Actions)
- Output files in CSV/JSON formats under `/Data` folder
- Sequential batch processing (low concurrency)

#### Audit & Maintenance
- Log all bot activity (user mentions, generated content, errors)
- Monitor GitHub and LLM provider dashboards for outages

---

## Key Clarifications from Discussion

### 1. Label Handling (CRITICAL CORRECTION)
**Initial Misunderstanding:** Labels were suggestions posted in comments as markdown checklists.

**Actual Requirement:** Labels are **applied directly to the issue via GitHub API**. They are NOT mentioned in comments. The system checks existing labels and only applies new ones.

### 2. LLM Provider
**Status:** Not yet chosen. All references are platform-agnostic.
- File names use generic terms (e.g., `llm_client.py` not `openai_client.py`)
- Code abstractions support multiple providers
- Requirements mention ChatGPT/GPT-4 as placeholder

### 3. Skills Taxonomy
**Source:** `API_repo_labels/data/excel_labels_data.xlsx` (not a separate CSV)
**Action Required:** Parse Excel file at runtime or convert to JSON/CSV for easier processing

### 4. Label Application Logic
**Reuse Existing Code:** The `API_repo_labels/scripts/` directory contains Python scripts for label management:
- `repo_labeler.py` - Label application logic
- `label_delete.py` - Label cleanup
- `excel_to_json.py` - Taxonomy conversion

**Strategy:** Extract and adapt core label application logic into new `label_applier.py` module.

### 5. Project Structure
**New Home:** `ai-skills-assessor-python/` folder in repo root
**Existing Work:** Considered R&D; new implementation starts fresh but references prior art

---

## Proposed Project Structure

```
ai-skills-assessor-python/
├── src/
│   ├── __init__.py
│   ├── github_fetcher.py          # GitHub API: fetch issues, comments, metadata
│   ├── llm_client.py               # LLM API: platform-agnostic wrapper
│   ├── prompt_builder.py           # Prompt engineering: format context + taxonomy
│   ├── label_applier.py            # GitHub API: apply labels (adapted from API_repo_labels)
│   ├── comment_poster.py           # GitHub API: post resume bullets to issue
│   ├── pipeline.py                 # Orchestration: full workflow coordination
│   └── utils.py                    # Shared utilities (logging, file I/O, etc.)
├── config/
│   ├── contributors.json           # Predefined contributor list for PoC
│   ├── settings.py                 # Configuration (API endpoints, timeouts, etc.)
│   └── .env.example                # Environment variable template
├── data/
│   ├── taxonomy/                   # Skills taxonomy files
│   │   └── skills.json             # Converted from excel_labels_data.xlsx
│   └── temp/                       # Temp files per issue (comments, prompts, responses, logs)
├── tests/
│   ├── __init__.py
│   ├── test_github_fetcher.py
│   ├── test_llm_client.py
│   ├── test_prompt_builder.py
│   ├── test_label_applier.py
│   ├── test_comment_poster.py
│   └── test_pipeline.py
├── scripts/
│   └── run_poc.py                  # Main entry point for PoC execution
├── .env                            # Environment variables (git-ignored)
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Outstanding Questions for User

### 1. Project Structure Approval
Does the proposed directory structure meet your needs, or would you prefer adjustments?

### 2. Taxonomy File Handling
Should we:
- **Option A:** Parse `excel_labels_data.xlsx` directly at runtime using `openpyxl`?
- **Option B:** Convert it to JSON/CSV once for faster processing?
- **Option C:** Copy it into `ai-skills-assessor-python/data/taxonomy/`?

**Question:** What are the columns/structure of the Excel file?

### 3. Label Application Logic
Looking at `API_repo_labels/scripts/repo_labeler.py`:
- Should we **import/reuse** this script directly?
- Or **extract core functions** and adapt them into the new `label_applier.py`?

**Question:** What are the key functions/logic we need from the existing scripts?

### 4. PoC Configuration
For the PoC phase:
- **Contributor list:** Where should this be defined? (JSON config? Hardcoded?)
- **Repository scope:** Hardcoded to `hackforla/website` or configurable?
- **Issue selection:** Test with specific issue numbers, or fetch all closed issues involving contributors?

### 5. Output & Logging Preferences
Temp files (4 per issue):
- **Naming:** `issue_<number>_<type>.json` format acceptable?
- **Retention:** Keep all temp files permanently for audit, or clean up after success?
- **Log format:** JSON or CSV? What fields are highest priority?

### 6. Error Handling Priorities
Which errors should we implement first?
- GitHub API rate limiting?
- LLM API timeouts/rate limits?
- Missing/malformed issue data?
- Label application failures (permissions, invalid labels)?

### 7. Development Approach
Preferred workflow:
- **Option A:** Build full structure first, then implement module by module
- **Option B:** Start with one module (e.g., GitHub fetcher), test thoroughly, then proceed
- **Option C:** Create minimal end-to-end prototype with hardcoded data, then expand

---

## Tentative Development Roadmap for PoC

### Phase 1: Foundation & Setup (Week 1)
**Goal:** Establish project structure and tooling

#### 1.1 Repository Setup
- [ ] Create `ai-skills-assessor-python/` directory structure
- [ ] Initialize Python package (`__init__.py` files)
- [ ] Create `.gitignore` (exclude `.env`, `data/temp/`, `__pycache__/`)
- [ ] Set up `requirements.txt` with initial dependencies:
  - `PyGithub` or `requests` for GitHub API
  - `python-dotenv` for environment variables
  - `openpyxl` or `pandas` for Excel parsing (if needed)
  - `pytest` for testing
  - LLM SDK (TBD: `openai`, `anthropic`, etc.)

#### 1.2 Configuration Files
- [ ] Create `.env.example` template:
  ```
  GITHUB_TOKEN=your_token_here
  LLM_API_KEY=your_key_here
  GITHUB_ORG=hackforla
  GITHUB_REPO=website
  ```
- [ ] Create `config/settings.py` for constants:
  - API endpoints
  - Rate limit thresholds
  - Timeout values
  - File paths
- [ ] Create `config/contributors.json` with predefined contributor list:
  ```json
  {
    "contributors": ["username1", "username2", "username3"]
  }
  ```

#### 1.3 Taxonomy Conversion
- [ ] Examine `API_repo_labels/data/excel_labels_data.xlsx` structure
- [ ] Decide on parsing strategy (runtime vs. pre-conversion)
- [ ] Convert/copy taxonomy to `data/taxonomy/skills.json` if needed
- [ ] Document taxonomy schema

#### 1.4 Documentation
- [ ] Create `README.md` with:
  - Project overview
  - Setup instructions
  - Environment variable configuration
  - Running the PoC
- [ ] Credit original `true-github-contributors` author (Kian Badie)

---

### Phase 2: Core Module Development (Weeks 2-3)

#### 2.1 GitHub Fetcher (`github_fetcher.py`)
**Purpose:** Fetch issue data from GitHub API

**Functions:**
- `fetch_issue(repo, issue_number)` → Returns issue object with title, body, labels, state
- `fetch_issue_comments(repo, issue_number)` → Returns list of comments with author, body, URL, timestamp
- `fetch_issues_for_contributors(repo, contributors)` → Returns list of closed issues involving contributors
- `check_existing_labels(repo, issue_number)` → Returns list of current labels on issue

**Testing:**
- [ ] Unit tests with mocked GitHub API responses
- [ ] Integration tests with real API calls (rate-limited)
- [ ] Error handling: 404s, rate limits, network timeouts

**Temp File Output:**
- [ ] Save fetched data to `data/temp/issue_<number>_comments.json`

---

#### 2.2 Prompt Builder (`prompt_builder.py`)
**Purpose:** Format structured prompts for LLM

**Functions:**
- `load_taxonomy(taxonomy_path)` → Parse skills taxonomy
- `format_issue_context(issue_data)` → Extract issue title, body, action items
- `format_contributor_comments(comments, contributors)` → Group comments by contributor
- `build_prompt(issue_context, contributor_comments, taxonomy)` → Generate full LLM prompt

**Prompt Structure:**
```
ROLE: You are an AI assistant helping open-source contributors create resume bullets.

CONTEXT:
Issue Title: [title]
Issue Description: [body]
Issue Status: Closed

CONTRIBUTOR COMMENTS:
@username1:
- [comment 1 text]
- [comment 2 text]

@username2:
- [comment 1 text]

SKILLS TAXONOMY:
[List of available skill labels from taxonomy]

TASK:
1. Generate resume bullets (STAR format, ≤30 words each) for each contributor
2. Identify applicable skill labels from taxonomy

OUTPUT FORMAT:
{
  "resume_bullets": {
    "username1": ["bullet 1", "bullet 2"],
    "username2": ["bullet 1"]
  },
  "skill_labels": ["Python", "Project Management", "API Development"]
}
```

**Testing:**
- [ ] Unit tests with sample issue data
- [ ] Validate prompt format against LLM requirements
- [ ] Test taxonomy loading and formatting

**Temp File Output:**
- [ ] Save prompt to `data/temp/issue_<number>_prompt.txt`

---

#### 2.3 LLM Client (`llm_client.py`)
**Purpose:** Platform-agnostic LLM API wrapper

**Functions:**
- `initialize_client(provider, api_key)` → Set up API client (OpenAI, Anthropic, etc.)
- `call_llm(prompt, max_tokens, temperature)` → Make API request
- `parse_response(response)` → Extract structured data from LLM output
- `handle_rate_limiting()` → Implement backoff/retry logic

**Supported Providers (initially):**
- OpenAI (GPT-4 Turbo/GPT-4o)
- Anthropic (Claude) - if chosen
- Abstract interface for easy provider swapping

**Testing:**
- [ ] Unit tests with mocked API responses
- [ ] Integration tests with real API calls (use test prompts)
- [ ] Rate limiting simulation
- [ ] Error handling: timeouts, invalid responses, token limits

**Temp File Output:**
- [ ] Save LLM response to `data/temp/issue_<number>_response.json`

---

#### 2.4 Label Applier (`label_applier.py`)
**Purpose:** Apply skill labels to GitHub issues

**Functions:**
- `extract_labels_from_response(llm_response)` → Parse label list from LLM output
- `validate_labels(labels, taxonomy)` → Ensure labels exist in taxonomy
- `get_new_labels(proposed_labels, existing_labels)` → Filter out duplicates
- `apply_labels(repo, issue_number, labels)` → GitHub API call to add labels
- `log_label_application(issue_number, new_labels, skipped_labels)` → Audit log

**Reuse from `API_repo_labels/scripts/`:**
- Review `repo_labeler.py` for label application logic
- Adapt error handling for label permission issues
- Reuse label validation/formatting

**Testing:**
- [ ] Unit tests with mock GitHub API
- [ ] Test duplicate label filtering
- [ ] Error handling: invalid labels, permission errors, API failures

---

#### 2.5 Comment Poster (`comment_poster.py`)
**Purpose:** Post resume bullets to GitHub issues

**Functions:**
- `format_resume_comment(resume_bullets, automation_link)` → Generate markdown comment
- `post_comment(repo, issue_number, comment_body)` → GitHub API call
- `log_comment_post(issue_number, comment_url)` → Audit log

**Comment Template:**
```markdown
## 🤖 AI-Generated Resume Bullets

This comment was automatically generated by the [AI Skills Assessor](link-to-docs).

@username1
- Resume Bullet 1
- Resume Bullet 2

@username2
- Resume Bullet 1
- Resume Bullet 2

---
*Generated on [timestamp] | [Feedback link]*
```

**Testing:**
- [ ] Unit tests with mock GitHub API
- [ ] Validate markdown formatting
- [ ] Error handling: comment posting failures, spam detection

---

### Phase 3: Pipeline Orchestration (Week 4)

#### 3.1 Pipeline Module (`pipeline.py`)
**Purpose:** Coordinate full workflow

**Functions:**
- `process_issue(repo, issue_number, contributors)` → Full pipeline for one issue
- `process_contributors(repo, contributors)` → Batch process all issues for contributor list
- `log_pipeline_activity(issue_number, status, duration, errors)` → Master log

**Workflow:**
```python
def process_issue(repo, issue_number, contributors):
    try:
        # 1. Fetch issue data
        issue = github_fetcher.fetch_issue(repo, issue_number)
        comments = github_fetcher.fetch_issue_comments(repo, issue_number)
        existing_labels = github_fetcher.check_existing_labels(repo, issue_number)

        # 2. Build prompt
        taxonomy = prompt_builder.load_taxonomy()
        prompt = prompt_builder.build_prompt(issue, comments, contributors, taxonomy)

        # 3. Call LLM
        response = llm_client.call_llm(prompt)

        # 4. Apply labels
        new_labels = label_applier.get_new_labels(response['skill_labels'], existing_labels)
        if new_labels:
            label_applier.apply_labels(repo, issue_number, new_labels)

        # 5. Post comment
        comment_poster.post_comment(repo, issue_number, response['resume_bullets'])

        # 6. Log success
        log_pipeline_activity(issue_number, "success", duration, None)

    except Exception as e:
        # Error handling
        post_error_to_issue(repo, issue_number, e)
        log_pipeline_activity(issue_number, "error", duration, e)
```

**Testing:**
- [ ] End-to-end integration tests with test issues
- [ ] Error propagation and recovery
- [ ] Performance monitoring (≤1 minute target)

---

#### 3.2 Main Entry Point (`scripts/run_poc.py`)
**Purpose:** CLI for running PoC

**Usage:**
```bash
# Process specific issue
python scripts/run_poc.py --issue 123

# Process all issues for predefined contributors
python scripts/run_poc.py --contributors config/contributors.json

# Dry run (no posting, just logging)
python scripts/run_poc.py --issue 123 --dry-run
```

**Features:**
- [ ] Argument parsing (`argparse`)
- [ ] Configuration loading from `.env`
- [ ] Progress reporting
- [ ] Summary statistics

---

### Phase 4: Error Handling & Logging (Week 5)

#### 4.1 Error Handling Strategy
**Public Errors (Posted to Issue):**
```markdown
## ⚠️ AI Skills Assessor Error

An error occurred while processing this issue:

**Error Code:** GITHUB_API_RATE_LIMIT
**Message:** GitHub API rate limit exceeded. Retrying in 60 seconds.

Please contact the maintainers if this persists.
[Report Issue](link-to-repo)
```

**Private Logging:**
- [ ] Structured error logs in `data/temp/error_log.json`
- [ ] Include: timestamp, issue number, error type, stack trace, API response
- [ ] Pattern detection for recurring errors

#### 4.2 Rate Limiting
- [ ] Implement exponential backoff for API calls
- [ ] Respect LLM provider rate limits (e.g., OpenAI Tier 1: 500 RPM, 30K TPM)
- [ ] GitHub API rate limit monitoring

#### 4.3 Audit Logging
- [ ] Master log file: `data/temp/audit_log.json`
- [ ] Log fields:
  - Issue number
  - Contributors processed
  - Labels applied (new vs. skipped)
  - Comment URL
  - Processing duration
  - Errors encountered
  - Timestamps

---

### Phase 5: Testing & Validation (Week 6)

#### 5.1 Unit Testing
- [ ] Achieve >80% code coverage
- [ ] Mock all external APIs
- [ ] Test error paths and edge cases

#### 5.2 Integration Testing
- [ ] Test with real GitHub issues (use test repository)
- [ ] Validate LLM responses for quality
- [ ] End-to-end pipeline runs

#### 5.3 Manual Validation
- [ ] Human review of generated resume bullets (STAR format, ≤30 words)
- [ ] Verify skill labels match taxonomy
- [ ] Check label deduplication
- [ ] Confirm comment formatting

#### 5.4 Performance Testing
- [ ] Measure processing time per issue (target: ≤1 minute)
- [ ] Identify bottlenecks
- [ ] Optimize LLM prompt size if needed

---

### Phase 6: Documentation & Deployment (Week 7)

#### 6.1 Documentation
- [ ] Complete `README.md` with setup instructions
- [ ] Document API configuration (GitHub + LLM)
- [ ] Create troubleshooting guide
- [ ] Document taxonomy structure and updates
- [ ] Provide example outputs

#### 6.2 GitHub Actions Setup
- [ ] Create workflow file: `.github/workflows/ai-skills-assessor.yml`
- [ ] Configure daily trigger (cron schedule)
- [ ] Set up secrets (GitHub token, LLM API key)
- [ ] Test workflow execution

#### 6.3 PoC Evaluation
- [ ] Run PoC on 10-20 test issues
- [ ] Collect metrics:
  - Processing time per issue
  - Label accuracy (human validation)
  - Resume bullet quality scores
  - Error rates
- [ ] Generate evaluation report

---

## Success Criteria for PoC

### Functional
- ✅ Successfully fetches issue data for predefined contributors
- ✅ Generates STAR-formatted resume bullets (≤30 words)
- ✅ Applies skill labels from taxonomy (no duplicates)
- ✅ Posts formatted comments to GitHub issues
- ✅ Logs all activity with temp files

### Non-Functional
- ✅ Processes each issue in ≤1 minute
- ✅ Handles API errors gracefully (public messages + detailed logs)
- ✅ Respects rate limits (GitHub + LLM)
- ✅ Modular code ready for future enhancements

### Validation
- ✅ Human review confirms resume bullet quality
- ✅ Skill labels match contributor activities
- ✅ No duplicate labels applied
- ✅ Error logs capture actionable diagnostics

---

## Future Phases (Post-PoC)

### Phase 2: Pilot (Multi-Repo)
- Extend to all Hack for LA repositories
- Handle open issues (not just closed)
- Add label validation rules
- Define persistent data schema

### Phase 3: Optimization
- Prompt tuning based on PoC feedback
- Token usage optimization
- Latency reduction
- Audit dashboard prototype

### Phase 4: Automation
- Webhook-based triggering (`issues.closed` event)
- Cloud deployment (AWS Lambda, Fly.io, etc.)
- Real-time processing

### Phase 5: Analytics
- Skill acquisition trends across contributors
- Organizational insights dashboard
- Recognition metrics

### Phase 6: Production
- Full autonomous operation
- API key rotation
- Prompt version control
- Manual override UI

---

## Next Steps for Development Kickoff

1. **User provides answers to outstanding questions** (taxonomy structure, label logic, config preferences)
2. **Create project structure** (`ai-skills-assessor-python/` directory)
3. **Set up initial files** (requirements.txt, .env.example, README.md)
4. **Begin Phase 1: Foundation & Setup** (follow roadmap above)

---

## References

- **Original Package:** true-github-contributors (JavaScript, Kian Badie)
- **Requirements:** AISA Requirements Doc v2.pdf
- **Context:** CLAUDE_CONTEXT.md
- **Skills Taxonomy:** `API_repo_labels/data/excel_labels_data.xlsx`
- **Label Scripts:** `API_repo_labels/scripts/` (Python)

---

*This document represents the complete knowledge state as of the last Claude chat session and serves as a handoff document for future sessions.*
