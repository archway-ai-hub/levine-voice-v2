# Swarm - Parallel Multi-Agent Orchestration for LiveKit Voice AI

Execute complex voice AI tasks by decomposing them and running multiple specialized agents in parallel, with MCP tool integration including LiveKit documentation.

## Task to Execute
$ARGUMENTS

## Instructions

You are orchestrating a swarm of specialized agents for LiveKit voice AI development. Follow this process exactly:

### Step 0: Parse Options

Check if the task includes any flags:
- `--dry-run` or `-d`: Show execution plan without running agents
- `--focus=<phase>`: Only run specific phase (e.g., `--focus=2`)
- `--fast`: Use haiku model for simple subtasks to reduce token usage
- `--no-mcp`: Disable MCP tool usage (agents only)

If `--dry-run` is present, skip to Step 3 and stop after showing the plan.

### MCP Tools Available

The swarm can leverage these MCP tools when beneficial:

#### LiveKit Documentation
| MCP | Tool | Use For |
|-----|------|---------|
| **livekit-docs** | `get_docs_overview`, `get_pages` | Browse LiveKit documentation structure |
| **livekit-docs** | `docs_search` | Search LiveKit docs for specific topics |
| **livekit-docs** | `get_python_agent_example` | Get example voice agent code |
| **livekit-docs** | `code_search` | Search LiveKit SDK source code |
| **livekit-docs** | `get_changelog` | Check recent updates to SDKs |

#### Documentation & Research
| MCP | Tool | Use For |
|-----|------|---------|
| **context7** | `resolve-library-id`, `query-docs` | Look up library documentation (Python, OpenAI, etc.) |

#### Code Intelligence
| MCP | Tool | Use For |
|-----|------|---------|
| **serena** | `find_symbol`, `get_symbols_overview` | Symbolic code navigation and understanding |
| **serena** | `replace_symbol_body`, `insert_after_symbol` | Precise code modifications |
| **serena** | `find_referencing_symbols` | Find all usages of a function/class |
| **morph-mcp** | `edit_file` | Fast, accurate file editing |
| **morph-mcp** | `warpgrep_codebase_search` | Intelligent codebase search |

#### Browser Testing
| MCP | Tool | Use For |
|-----|------|---------|
| **playwright** | `browser_navigate`, `browser_snapshot` | E2E testing, UI verification |
| **playwright** | `browser_click`, `browser_type` | Automated user interactions |
| **chrome-devtools** | `take_snapshot`, `list_network_requests` | Debug frontend issues |

#### Problem Solving
| MCP | Tool | Use For |
|-----|------|---------|
| **sequential-thinking** | `sequentialthinking` | Complex multi-step reasoning |

**When to use MCPs:**
- Need LiveKit docs/examples -> Use **livekit-docs** before implementing
- Need library docs -> Use **context7** before implementing
- Complex code search -> Use **morph-mcp** warpgrep or **serena** symbols
- Precise edits -> Use **serena** symbolic editing or **morph-mcp** edit_file
- UI verification -> Use **playwright** or **chrome-devtools**
- Complex reasoning -> Use **sequential-thinking**

### Agent Color Reference

Use these colored indicators for each agent in ALL output:

```
voice-ai-developer (red)
python-developer, audio-engineer (yellow)
agent-organizer, code-reviewer, llm-specialist (orange)
test-engineer (green)
devops-engineer (cyan)
observability-sheriff, regression-guardian (magenta)
Explore, Plan, general-purpose (white/default)
```

### Step 1: Announce Swarm Initiation

Output this EXACT format:

```

                     INITIATING SWARM


Bringing in agent-organizer to assign tasks for:
> "$ARGUMENTS"

Analyzing task complexity...
```

### Step 2: Call Agent Organizer

Use the Task tool to call the **agent-organizer** agent with this prompt:

"Analyze and decompose this task into subtasks that can be executed by specialized agents. Identify which agents to use, map dependencies, and determine which tasks can run in parallel.

Task: $ARGUMENTS

Available agents:
- Explore: Codebase exploration, finding files
- Plan: Architecture and design
- voice-ai-developer: LiveKit Agents, voice pipelines, STT/TTS/LLM integration
- python-developer: Python async code, APIs, backend logic
- audio-engineer: Audio processing, VAD, noise cancellation, audio quality
- llm-specialist: LLM optimization, prompts, function calling, context management
- test-engineer: Unit/integration tests, voice agent behavioral testing
- devops-engineer: CI/CD, Docker, LiveKit Cloud deployment
- code-reviewer: Code quality review
- observability-sheriff: Logging contract checks, ensures USER_TEXT/CAPTURED/ROUTE_DECISION logs are present
- regression-guardian: Final quality gate, runs make check + make sim before declaring success
- general-purpose: Complex research

Available MCP tools (use when beneficial):
- livekit-docs: LiveKit documentation, examples, SDK search
- context7: Library documentation lookup (Python, OpenAI, etc.)
- serena: Symbolic code navigation (find_symbol, replace_symbol_body)
- morph-mcp: Smart file editing (edit_file) and search (warpgrep_codebase_search)
- playwright: Browser automation for E2E testing
- chrome-devtools: Frontend debugging
- sequential-thinking: Complex multi-step reasoning

For each subtask, specify:
1. Agent: Which agent handles this
2. Complexity: Low/Medium/High
3. Estimated tokens: Small (<2k), Medium (2-5k), Large (5k+)
4. MCP tools: List SPECIFIC MCP tools that SHOULD be used (be explicit):
   - livekit-docs: For LiveKit docs/examples (get_pages, docs_search, get_python_agent_example)
   - context7: For looking up library docs (specify which library)
   - serena: For code navigation/editing (specify: find_symbol, replace_symbol_body, etc.)
   - morph-mcp: For file editing (edit_file) or search (warpgrep_codebase_search)
   - playwright: For browser testing (browser_navigate, browser_snapshot, browser_click)
   - sequential-thinking: For complex multi-step reasoning
   - 'none': Only if no MCP tools apply

Be specific about WHY each MCP tool helps the subtask (e.g., 'livekit-docs: Look up AgentSession configuration').

Provide a clear execution plan with phases, identifying which agents can run in parallel."

### Step 3: Display Execution Plan

After agent-organizer responds, output the plan with colors and MCP indicators:

```

                   SWARM EXECUTION PLAN


Task: [Brief summary]

+-------------------------------------------------------------+
| PHASE 1: [Description]                          [PARALLEL]  |
+-------------------------------------------------------------+
|  voice-ai-developer   | [task]           | ~3k tokens    |
|     livekit-docs: AgentSession docs                       |
|  python-developer  | [task]           | ~4k tokens    |
|     serena: find_symbol                               |
+-------------------------------------------------------------+

+-------------------------------------------------------------+
| PHASE 2: [Description]                         [SEQUENTIAL] |
+-------------------------------------------------------------+
|  test-engineer       | [task]           | ~2k tokens    |
|     livekit-docs: get examples                          |
+-------------------------------------------------------------+

+-------------------------------------------------------------+
|                      ESTIMATES                           |
+-------------------------------------------------------------+
|  Agents: [X]  |  Phases: [Y]  |  Est. Tokens: ~[Z]k        |
|  MCPs Used: [N]  |  Parallel Efficiency: [X]%              |
+-------------------------------------------------------------+
```

**Parallel Efficiency** = (Total if sequential - Actual with parallel) / Total if sequential * 100
- Higher is better (more work done in parallel)

**If `--dry-run` was specified, STOP HERE and output:**
```
================================================================
DRY RUN COMPLETE - No agents were deployed
Estimated token usage: ~[X]k tokens
Run without --dry-run to execute this plan
================================================================
```

### Step 4: Deploy Agents

Output:
```

                    DEPLOYING AGENTS

```

### Step 5: Execute Each Phase

For EACH phase, track time and show status with colors:

```
+-------------------------------------------------------------+
| PHASE 1: [Description]                                      |
| Started: [timestamp]  |  Agents: [X]  |  Mode: PARALLEL     |
+-------------------------------------------------------------+

  voice-ai-developer starting...
     Task: [brief description]
     MCPs: livekit-docs (docs), serena (code)

  python-developer starting...
     Task: [brief description]
     MCPs: morph-mcp (editing)
```

Then launch ALL agents for that phase in a SINGLE message with multiple Task tool calls.

**CRITICAL - MCP TOOL INJECTION**: For EACH agent's Task call, you MUST include MCP instructions in the prompt. Use this template:

```
[Agent's specific task description]

**MCP TOOLS - USE THESE:**
You have access to these MCP tools and SHOULD use them:

[If livekit-docs recommended]
- **livekit-docs**: Look up LiveKit documentation and examples
  - `mcp__livekit-docs__get_docs_overview` for documentation structure
  - `mcp__livekit-docs__get_pages` to read specific doc pages
  - `mcp__livekit-docs__docs_search` to search documentation
  - `mcp__livekit-docs__get_python_agent_example` for code examples
  - `mcp__livekit-docs__code_search` to search SDK source code

[If context7 recommended]
- **context7**: Look up library documentation before implementing
  - First call `mcp__context7__resolve-library-id` with the library name
  - Then call `mcp__context7__query-docs` with the resolved ID and your question
  - Example: Look up "OpenAI function calling" or "Python asyncio" docs

[If serena recommended]
- **serena**: Use for precise code navigation and editing
  - `mcp__serena__find_symbol` to find functions/classes by name
  - `mcp__serena__get_symbols_overview` for file structure
  - `mcp__serena__replace_symbol_body` for precise edits
  - `mcp__serena__find_referencing_symbols` to find all usages

[If morph-mcp recommended]
- **morph-mcp**: Use for fast file editing and search
  - `mcp__morph-mcp__edit_file` for efficient edits with minimal context
  - `mcp__morph-mcp__warpgrep_codebase_search` for intelligent code search

[If sequential-thinking recommended]
- **sequential-thinking**: Use for complex reasoning
  - `mcp__sequential-thinking__sequentialthinking` for multi-step analysis

**IMPORTANT**: Actively use these MCP tools during your work. They are already available and will improve your output quality.
```

**TOKEN OPTIMIZATION**: If `--fast` flag was used, add `model: "haiku"` to Task calls for Low complexity subtasks.

**MCP SKIP**: If `--no-mcp` flag was used, do NOT include the MCP TOOLS section in agent prompts. Skip all MCP tool injection and proceed with agents using only standard tools.

**CRITICAL**: Launch all phase agents in parallel (multiple Task calls in one message).
**CRITICAL**: Unless `--no-mcp` is set, each Task call MUST include the MCP tool instructions above for tools recommended in the execution plan.

### Step 6: Report Agent Completions

As each agent completes, check its response for MCP tool usage (look for `mcp__` tool calls in the output) and output with color and metrics:

**Detecting MCP usage**: Look for tool calls in the agent's response containing:
- `mcp__livekit-docs__` -> Report as livekit-docs
- `mcp__context7__` -> Report as context7
- `mcp__serena__` -> Report as serena
- `mcp__morph-mcp__` -> Report as morph-mcp
- `mcp__playwright__` -> Report as playwright
- `mcp__sequential-thinking__` -> Report as sequential-thinking

```
  voice-ai-developer completed
    Duration: [X]s
    Result: [1-2 sentence summary]
    Files: [count] modified
    MCP: livekit-docs (looked up AgentSession docs)
```

If multiple MCPs were used:
```
  python-developer completed
    Duration: [X]s
    Result: [1-2 sentence summary]
    Files: [count] modified
    MCPs: serena (find_symbol), morph-mcp (edit_file)
```

If no MCP was used (but was recommended, note this):
```
  audio-engineer completed
    Duration: [X]s
    Result: [1-2 sentence summary]
    Files: [count] modified
    MCP: none (recommended: livekit-docs)
```

If an agent FAILS, output:
```
  voice-ai-developer FAILED
    Duration: [X]s
    Error: [error description]
    Recovery: [Attempting retry / Skipping / Blocking]
```

### Step 7: Handle Failures

If an agent fails:

1. **Non-critical agent**: Log the failure, continue with remaining agents
```
  Non-critical failure: test-engineer
    Continuing with remaining agents...
```

2. **Critical agent (blocks other phases)**: Attempt ONE retry
```
Critical failure: voice-ai-developer
   Attempting retry (1/1)...
```

3. **Retry also fails**: Stop the swarm
```
SWARM HALTED
   Critical agent voice-ai-developer failed after retry

   Completed before failure:
   - [list of completed work]

   Manual intervention required for:
   - [remaining tasks]
```

### Step 8: Phase Transitions

Between phases, show metrics:
```
+-------------------------------------------------------------+
| PHASE 1 COMPLETE                                         |
+-------------------------------------------------------------+
|  Duration: [X]s  |  Agents: [Y]  |  Success: [Z]/[Y]       |
|  Files Changed: [N]  |  Lines Modified: ~[M]               |
+-------------------------------------------------------------+

Proceeding to Phase 2...
```

### Step 9: Final Summary

After all phases, show comprehensive metrics:
```

                    SWARM COMPLETE


+-------------------------------------------------------------+
|                     STATISTICS                           |
+-------------------------------------------------------------+
|  Total Duration     |  [X]s                                 |
|  Agents Deployed    |  [count]                              |
|  Phases Executed    |  [count]                              |
|  Success Rate       |  [X]%                                 |
|  Retries            |  [count]                              |
+-------------------------------------------------------------+
|  Files Changed      |  [count]                              |
|  Lines Added        |  +[count]                             |
|  Lines Removed      |  -[count]                             |
+-------------------------------------------------------------+
|  MCP Tools Used     |  [count]                              |
|  LiveKit Docs       |  [count] (livekit-docs)               |
|  Code Navigations   |  [count] (serena)                     |
+-------------------------------------------------------------+

+-------------------------------------------------------------+
|                   AGENTS DEPLOYED                        |
+-------------------------------------------------------------+
|  voice-ai-developer    | 12s | Built pipeline  | livekit-docs|
|  python-developer   | 15s | Created tools  | serena  |
|  audio-engineer         | 8s | VAD config      | -          |
|  test-engineer        | 10s | 12 tests    | livekit-docs|
+-------------------------------------------------------------+

+-------------------------------------------------------------+
|                     SUMMARY                              |
+-------------------------------------------------------------+
|  [Key outcome 1]                                         |
|  [Key outcome 2]                                         |
|  [Key outcome 3]                                         |
+-------------------------------------------------------------+

+-------------------------------------------------------------+
|                   FILES CHANGED                          |
+-------------------------------------------------------------+
|  livekit_mcp_agent.py                    [+125 lines]    |
|  tests/test_agent.py                      [+89 lines]    |
|  pyproject.toml                           [+15 lines]    |
+-------------------------------------------------------------+

================================================================
                    All tasks completed successfully.
================================================================
```

## Agent Reference with Colors

### Core Development
| Color | Agent | Domain | Token Usage |
|-------|-------|--------|-------------|
| | **voice-ai-developer** | LiveKit Agents | Medium-Large |
| | **python-developer** | Python Backend | Medium-Large |
| | **audio-engineer** | Audio/Speech | Medium |

### Specialized
| Color | Agent | Domain | Token Usage |
|-------|-------|--------|-------------|
| | **llm-specialist** | LLM Optimization | Medium |
| | **test-engineer** | Testing | Medium |
| | **devops-engineer** | DevOps | Small-Medium |

### Quality & Research
| Color | Agent | Domain | Token Usage |
|-------|-------|--------|-------------|
| | **code-reviewer** | Quality | Small-Medium |
| | **Explore** | Research | Small |
| | **Plan** | Architecture | Medium |
| | **general-purpose** | General | Large |

### Final Gates
| Color | Agent | Domain | Token Usage |
|-------|-------|--------|-------------|
| magenta | **regression-guardian** | Final quality gate - runs `make check` + `make sim` | Small-Medium |
| magenta | **observability-sheriff** | Logging contract checks, minimal validation | Small |

## Default Swarm Order

Swarm should always run agents in this order:

1. **agent-organizer** - Plan and delegate tasks
2. **voice-ai-developer / python-developer** - Implementation work
3. **audio-engineer** - Only for voice polish tasks
4. **test-engineer** - Write and run tests
5. **observability-sheriff** - Logging contract checks (minimal)
6. **regression-guardian** - Final gate: run `make check` + `make sim`

**IMPORTANT**: `regression-guardian` must be the final step before declaring success.

## When to Use Each Agent

| Agent | When to Use |
|-------|-------------|
| **agent-organizer** | First step for any complex task. Decomposes work and assigns to specialized agents. |
| **voice-ai-developer** | AgentSession setup, voice pipelines, STT/TTS/LLM integration, function tools, multi-agent handoffs. |
| **python-developer** | Async code, API integrations, Pydantic models, backend logic, data processing. |
| **audio-engineer** | VAD tuning, noise cancellation, STT/TTS quality, audio processing. Only for voice polish tasks. |
| **llm-specialist** | Prompt engineering, function calling design, context management, model selection. |
| **test-engineer** | Unit tests, integration tests, behavioral testing for voice agents. |
| **devops-engineer** | CI/CD pipelines, Docker, LiveKit Cloud deployment, environment configuration. |
| **code-reviewer** | Code quality review, best practices, security review. |
| **observability-sheriff** | Verify logging contracts are followed. Checks USER_INPUT, CAPTURED, and FINAL log formats. |
| **regression-guardian** | Use as the FINAL gate before marking any implementation task complete. Runs `make check` and `make sim` to verify no regressions. |
| **Explore** | Codebase exploration, finding files, understanding existing patterns. |
| **Plan** | Architecture design, high-level planning. |
| **general-purpose** | Complex research requiring multiple tool calls and reasoning. |

## Token Usage Guide

**Estimated tokens per agent complexity:**
- **Small** (<2k): Simple lookups, small edits, config changes
- **Medium** (2-5k): Feature implementation, component creation
- **Large** (5k+): Complex features, multi-file changes, research

**Tips to reduce token usage:**
1. Use `--fast` flag to use haiku model for simple subtasks
2. Be specific in task description to reduce exploration
3. Use `--focus=N` to run only needed phases
4. Use `--dry-run` first to preview and refine the plan

## Examples

### Standard Execution
```
/swarm Add tool calling with weather API to the voice agent
```

### Dry Run (Preview Only)
```
/swarm --dry-run Implement multi-agent handoff for customer service bot
```

### Fast Mode (Reduced Tokens)
```
/swarm --fast Add a simple greeting customization
```

### Focus on Specific Phase
```
/swarm --focus=2 Add semantic turn detection to existing agent
```

## Example Output

```

                     INITIATING SWARM


Bringing in agent-organizer to assign tasks for:
> "Add weather tool calling to voice agent"

Analyzing task complexity...


                   SWARM EXECUTION PLAN


Task: Implement weather tool with function calling

+-------------------------------------------------------------+
| PHASE 1: Discovery & Design                     [PARALLEL]  |
+-------------------------------------------------------------+
|  Explore              | Find patterns       | ~1k tokens |
|  llm-specialist         | Design tool call       | ~2k tokens |
+-------------------------------------------------------------+

+-------------------------------------------------------------+
| PHASE 2: Implementation                         [PARALLEL]  |
+-------------------------------------------------------------+
|  voice-ai-developer    | Build tool           | ~4k tokens |
|  python-developer   | API integration           | ~3k tokens |
+-------------------------------------------------------------+

+-------------------------------------------------------------+
| PHASE 3: Quality                               [SEQUENTIAL] |
+-------------------------------------------------------------+
|  test-engineer        | Write tests         | ~3k tokens |
|  code-reviewer        | Review code         | ~2k tokens |
+-------------------------------------------------------------+

+-------------------------------------------------------------+
|                      ESTIMATES                           |
+-------------------------------------------------------------+
|  Agents: 6   |  Phases: 3   |  Est. Tokens: ~15k           |
|  Parallel Efficiency: 67%  |  Est. Time: ~45s              |
+-------------------------------------------------------------+


                    DEPLOYING AGENTS


+-------------------------------------------------------------+
| PHASE 1: Discovery & Design                                 |
| Started: 14:32:05  |  Agents: 2  |  Mode: PARALLEL          |
+-------------------------------------------------------------+

  Explore starting...
     Task: Find existing tool patterns in codebase

  llm-specialist starting...
     Task: Design function tool schema

  Explore completed
    Duration: 8s
    Result: Found @function_tool pattern in livekit_mcp_agent.py
    Files: 0 modified

  llm-specialist completed
    Duration: 12s
    Result: Designed weather tool with location parameter
    Files: 0 modified

+-------------------------------------------------------------+
| PHASE 1 COMPLETE                                         |
+-------------------------------------------------------------+
|  Duration: 12s  |  Agents: 2  |  Success: 2/2              |
|  Files Changed: 0  |  Lines Modified: 0                    |
+-------------------------------------------------------------+

Proceeding to Phase 2...
```

Now begin the swarm execution for the provided task.
