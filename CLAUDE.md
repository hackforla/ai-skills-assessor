# Project-Specific Instructions for AI Skills Assessor

## Agent Delegation Rules

When working on coding tasks in this project, **proactively delegate to specialized agents** located in `.claude/agents/`:

### Automatic Delegation Triggers:

1. **After writing significant code** → Immediately use the `code-review-specialist` agent
   - Trigger: Any time you create or modify 10+ lines of code
   - Trigger: When implementing authentication, security, or data handling logic
   - Trigger: After refactoring existing functionality

2. **When implementing new features** → Start with the `code-writer` agent
   - Trigger: User asks to "implement", "create", "add", or "build" functionality
   - Trigger: When fixing bugs that require code changes
   - Trigger: When refactoring existing code
   - The code-writer will automatically generate comprehensive tests

3. **After any code changes** → Use the `test-runner` agent
   - Trigger: After the code-writer completes its work
   - Trigger: After you make direct code edits
   - Trigger: When user asks to "verify", "test", or "check" functionality
   - Trigger: After fixing bugs

### Coordination Pattern:

For complex tasks, use this sequence:
1. **Planning Phase**: Use TodoWrite to break down the task
2. **Implementation Phase**: Delegate to `code-writer` agent for implementation with tests
3. **Review Phase**: Delegate to `code-review-specialist` for security and quality review
4. **Verification Phase**: Delegate to `test-runner` to ensure all tests pass
5. **Completion**: Mark todos as complete and summarize results

### Example Delegation Prompts:

When delegating, use clear, specific prompts:
- "Use the code-writer agent to implement [specific feature] with comprehensive test coverage"
- "Use the code-review-specialist to review the changes in [files] for security and best practices"
- "Use the test-runner to execute all relevant tests and fix any failures"

### Important Notes:

- These agents are defined in `.claude/agents/` with specialized instructions
- Always wait for agent completion before proceeding to the next step
- If an agent identifies issues, address them before moving forward
- The agents use the Sonnet model for efficiency

## Project-Specific Context

This is the Ai Skills Assessor monorepo containing the python application and supporting files that will become a chron job GitHub action. When working with code:
- Respect the existing monorepo structure
- Follow established patterns in the codebase
- Ensure changes work across both web and mobile when applicable

## Testing Requirements

- Always run relevant tests after code changes
- Ensure no regression in existing functionality
- Mobile app changes should be tested in the Expo environment
- Web app changes should be tested in the Next.js environment

 ## Development Server Management

  - DO NOT start development servers (npm run dev, yarn dev, etc.) without asking, only ask if it is necessary for the project
  - The user manages all dev server lifecycles via confirmations
  - Assume the dev server is not already running when making changes
  - Changes should hot-reload automatically, help the user set this up at first
  - Rely on user feedback for visual verification of UI changes