# LiveKit Agents - Global Context Engineering Rules

This file provides comprehensive guidance for AI assistants working with LiveKit Agents - the framework for building realtime voice AI applications with multimodal capabilities, turn detection, and tool integration.

## 🎯 Framework Overview

LiveKit Agents is a Python framework for building realtime AI participants that can:
- Process and generate audio, video, and text in realtime
- Handle sophisticated turn detection and interruptions
- Execute tools with function calling
- Support multiple AI providers (OpenAI, Anthropic, Google, etc.)
- Deploy to LiveKit Cloud or custom environments

## 🔧 Development Environment

### Package Management with UV

**ALWAYS use UV for dependency management:**
```bash
# Initialize new project
uv init my-voice-agent

# Install dependencies
uv add livekit-agents "livekit-plugins-openai[realtime]" livekit-plugins-deepgram livekit-plugins-cartesia

# Sync dependencies
uv sync

# Run agent in development mode
uv run python agent.py dev

# Run agent in console mode for testing
uv run python agent.py console

# Run tests
uv run pytest -v --asyncio-mode=auto
```

### Required Python Version
- **Python 3.9 or later required** - Check with `python --version`
- All agent code must use async/await patterns

## 📦 Core Architecture Patterns

### AgentSession Configuration

The `AgentSession` is the central orchestration component:

```python
from livekit.agents import AgentSession, Agent, RoomInputOptions
from livekit.plugins import openai, deepgram, cartesia, silero, noise_cancellation

# Standard voice pipeline configuration
session = AgentSession(
    stt=deepgram.STT(model="nova-2"),
    llm=openai.LLM(model="gpt-4.1-mini"),
    tts=cartesia.TTS(voice="f786b574-daa5-4673-aa0c-cbe3e8534c02"),
    vad=silero.VAD.load(),
    turn_detection="semantic"  # or "vad_based"
)

# Realtime model configuration
session = AgentSession(
    llm=openai.realtime.RealtimeModel(voice="echo")
)
```

### Agent Lifecycle Methods

**ALWAYS implement agents using the Agent base class:**

```python
class Assistant(Agent):
    def __init__(self):
        super().__init__(
            instructions="You are a helpful voice assistant.",
            tools=[...]  # Optional tools
        )
    
    async def on_enter(self):
        """Called when agent becomes active"""
        await self.session.generate_reply(
            instructions="Greet the user"
        )
    
    async def on_exit(self):
        """Called when agent is being replaced"""
        # Cleanup logic
```

## 🎤 Voice Pipeline Patterns

### Turn Detection Strategies

**Three primary approaches:**
1. **Semantic Model** (Recommended): Uses custom turn detection model
2. **VAD-Based**: Uses voice activity detection
3. **STT Endpoint**: Uses speech recognition endpoints

```python
from livekit.plugins.turn_detector import SemanticModel, VADModel

# Semantic turn detection (best for natural conversation)
session = AgentSession(
    turn_detection=SemanticModel()
)

# VAD-based (faster, less contextual)
session = AgentSession(
    turn_detection=VADModel()
)
```

### Interruption Handling

**ALWAYS handle interruptions gracefully:**
```python
# Allow interruptions during speech
await session.say("Long message here...", allow_interruptions=True)

# Handle state changes
@session.on("agent_state_changed")
def on_state_changed(ev):
    if ev.new_state == "interrupted":
        # Handle interruption
        pass
```

## 🛠️ Tool Integration Patterns

### Function Tool Decorator

**ALWAYS use @function_tool for tool definitions:**

```python
from livekit.agents import function_tool, RunContext

class Assistant(Agent):
    @function_tool
    async def get_weather(self, context: RunContext, location: str) -> str:
        """Get weather for a location"""
        # Implementation
        return f"Weather in {location}: Sunny, 72°F"
    
    @function_tool
    async def search_database(self, context: RunContext, query: str) -> str:
        """Search internal database"""
        # Implementation
        return f"Found 5 results for: {query}"
```

### MCP Server Integration

```python
from livekit.agents import mcp

# Connect to MCP server
mcp_server = mcp.MCPServer("ws://localhost:8080")
session = AgentSession(
    tools=[mcp_server]
)
```

## 🌐 Multi-Agent Workflows

### Agent Handoffs

```python
class GreeterAgent(Agent):
    async def on_enter(self):
        await self.session.generate_reply(
            instructions="Greet the user and ask how you can help"
        )
        
        # Handoff to specialist
        if needs_specialist:
            await self.session.set_agent(SpecialistAgent())

class SpecialistAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions="You are a technical specialist.",
            tts=cartesia.TTS(voice="different-voice-id")
        )
```

## 🧪 Testing Patterns

### Behavioral Testing

**ALWAYS include behavioral tests:**

```python
import pytest
from livekit.agents.testing import AgentTestSuite, Judge

@pytest.mark.asyncio
async def test_agent_greeting():
    suite = AgentTestSuite()
    judge = Judge(
        criteria="Agent should greet user warmly"
    )
    
    result = await suite.test_agent(
        agent=Assistant(),
        scenario="User joins session",
        judge=judge
    )
    
    assert result.passed
```

### Tool Invocation Testing

```python
@pytest.mark.asyncio
async def test_tool_calls():
    agent = Assistant()
    
    # Test tool is called correctly
    response = await agent.handle_message(
        "What's the weather in NYC?"
    )
    
    assert "get_weather" in agent.tool_calls
    assert "NYC" in agent.tool_calls["get_weather"]["location"]
```

## ☁️ Deployment Patterns

### LiveKit Cloud Deployment

**Required files for deployment:**

1. **Dockerfile**:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen
COPY . .
CMD ["uv", "run", "python", "agent.py"]
```

2. **livekit.toml**:
```toml
[agent]
job_type = "room"
worker_type = "agent"

[agent.prewarm]
count = 1  # Keep warm instances
```

3. **Deploy command**:
```bash
lk agent deploy
```

### Environment Configuration

**ALWAYS use environment variables:**
```python
# .env file
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your-key
LIVEKIT_API_SECRET=your-secret
OPENAI_API_KEY=your-openai-key
DEEPGRAM_API_KEY=your-deepgram-key
```

## 🎯 Provider Configuration

### Base Configuration (Recommended Start)
```python
# Start with these providers for best results
session = AgentSession(
    stt=deepgram.STT(model="nova-2"),
    llm=openai.LLM(model="gpt-4.1-mini"),
    tts=openai.TTS(voice="echo")
)
```

### Optional Providers
- **TTS**: Cartesia (fastest), ElevenLabs (quality), PlayHT
- **STT**: AssemblyAI, Azure Speech, Whisper
- **LLM**: Anthropic, Google, Groq, Together
- **Realtime**: OpenAI Realtime API, Google Gemini Live

## ⚠️ Common Gotchas

### Python Version
- **MUST use Python 3.9+** - Earlier versions not supported
- Check with: `python --version`

### Async Patterns
- **ALL agent methods must be async** - Use `async def`
- **ALL plugin calls must be awaited** - Use `await`

### Model Downloads
- **TTS models may download on first use** - Can be slow
- Pre-download in Docker: `RUN uv run python -c "from livekit.plugins import cartesia; cartesia.TTS()"`

### Proxy Issues
- Set `HTTP_PROXY` and `HTTPS_PROXY` if behind corporate firewall
- WebRTC requires UDP ports 50000-60000

### Turn Detection
- **Semantic model requires English** - Use VAD for other languages
- **Adjust sensitivity** for noisy environments

### Testing
- **Use pytest with asyncio mode**: `pytest --asyncio-mode=auto`
- **Mock external services** in unit tests
- **Use behavioral testing** for conversation flows

## 📚 Documentation Structure

When documenting agents:
1. **Purpose**: What the agent does
2. **Configuration**: Required environment variables
3. **Tools**: List of available tools
4. **Workflows**: Multi-agent handoff patterns
5. **Testing**: How to test the agent
6. **Deployment**: How to deploy to production

## 🔍 Debugging Tips

### Enable Debug Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Console Testing
```bash
# Test in terminal with audio
uv run python agent.py console

# Test specific scenarios
uv run python agent.py test --scenario "greeting"
```

### Monitor Agent State
```python
@session.on("agent_state_changed")
def on_state_changed(ev):
    print(f"State: {ev.old_state} -> {ev.new_state}")
```

## 🚀 Performance Optimization

### Reduce Latency
- Use regional deployments close to users
- Choose faster providers (Deepgram for STT, Cartesia for TTS)
- Use streaming where possible

### Scale Efficiently
- Set appropriate prewarm counts in livekit.toml
- Use connection pooling for database/API calls
- Implement caching for frequently accessed data

## 🎓 Best Practices

1. **Start Simple**: Begin with basic STT-LLM-TTS pipeline
2. **Test Locally**: Use console mode before deployment
3. **Handle Errors**: Implement try/catch in all async methods
4. **Log Everything**: Use structured logging for debugging
5. **Version Control**: Pin all dependency versions
6. **Monitor Usage**: Track token usage and costs
7. **Secure Credentials**: Never commit API keys
8. **Document Tools**: Provide clear descriptions for all tools
9. **Test Behaviors**: Use judges for conversation quality
10. **Iterate Quickly**: Deploy often, gather feedback

## 🔄 Migration from v0.x to v1.0

Major changes in v1.0:
- `VoicePipelineAgent` → `AgentSession` + `Agent` class
- `ChatContext` → Built into `Agent.instructions`
- Function calling → `@function_tool` decorator
- Event handling → Session event handlers
- OpenAI Assistants API support removed

## 📎 Quick Reference

```python
# Complete minimal agent
from livekit import agents
from livekit.agents import AgentSession, Agent
from livekit.plugins import openai, deepgram

class Assistant(Agent):
    def __init__(self):
        super().__init__(instructions="You are helpful.")
    
    async def on_enter(self):
        await self.session.generate_reply(
            instructions="Say hello"
        )

async def entrypoint(ctx: agents.JobContext):
    session = AgentSession(
        stt=deepgram.STT(),
        llm=openai.LLM(),
        tts=openai.TTS()
    )
    
    await session.start(
        room=ctx.room,
        agent=Assistant()
    )

if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(
        entrypoint_fnc=entrypoint
    ))
```

Remember: The goal is to create simple yet powerful voice AI agents that provide natural, responsive conversations with users!

---

## 🐝 Claude Code Agents & Swarm Command

This project includes a sophisticated multi-agent system for Claude Code that enables parallel task execution and specialized expertise for voice AI development.

### Available Claude Agents

Located in `.claude/agents/`:

| Agent | Color | Domain | Use For |
|-------|-------|--------|---------|
| **voice-ai-developer** | Red | LiveKit Agents | AgentSession, voice pipelines, STT/TTS/LLM, function tools, multi-agent handoffs |
| **python-developer** | Yellow | Python Backend | Async code, API integrations, Pydantic, data processing |
| **audio-engineer** | Yellow | Audio/Speech | VAD configuration, noise cancellation, STT/TTS tuning, audio quality |
| **llm-specialist** | Orange | LLM Optimization | Prompt engineering, function calling, context management, model selection |
| **test-engineer** | Green | Testing | Unit tests, integration tests, behavioral testing for voice agents |
| **devops-engineer** | Cyan | DevOps | CI/CD, Docker, LiveKit Cloud deployment, environment management |
| **agent-organizer** | Orange | Orchestration | Task decomposition, agent selection, workflow design |
| **code-reviewer** | Orange | Quality | Code review, best practices, security review |

### Swarm Command

The `/swarm` command orchestrates multiple agents in parallel for complex tasks:

```bash
# Standard execution
/swarm Add weather tool calling to the voice agent

# Preview plan without executing
/swarm --dry-run Implement multi-agent handoff for customer service

# Fast mode (uses haiku for simple subtasks)
/swarm --fast Add a greeting customization

# Focus on specific phase
/swarm --focus=2 Add semantic turn detection
```

**How Swarm Works:**
1. Analyzes the task and decomposes it into subtasks
2. Selects optimal agents for each subtask
3. Maps dependencies and identifies parallelization opportunities
4. Executes agents in parallel phases
5. Reports progress with metrics and file changes

### MCP Tools Integration

Agents have access to these MCP tools:

| MCP | Purpose |
|-----|---------|
| **livekit-docs** | LiveKit documentation, examples, SDK source code |
| **context7** | General library documentation (Python, OpenAI, etc.) |
| **serena** | Symbolic code navigation and precise editing |
| **morph-mcp** | Fast file editing and codebase search |
| **playwright** | Browser automation for E2E testing |
| **sequential-thinking** | Complex multi-step reasoning |

### Example Swarm Usage

```
/swarm Add a booking tool that integrates with a hotel API
```

This might produce:
1. **Phase 1 (Parallel)**:
   - `Explore`: Find existing tool patterns
   - `llm-specialist`: Design function tool schema
2. **Phase 2 (Parallel)**:
   - `voice-ai-developer`: Implement @function_tool
   - `python-developer`: Build API integration
3. **Phase 3 (Sequential)**:
   - `test-engineer`: Write tests
   - `code-reviewer`: Review implementation

### Agent Configuration

Settings in `.claude/settings.local.json` define:
- Allowed bash commands (uv, python, pytest, docker, git, lk)
- MCP tool permissions
- Development tool access

### When to Use Swarm

Use `/swarm` for:
- Multi-component features (tool + API + tests)
- Refactoring that spans multiple files
- Adding new agent capabilities
- Performance optimization across pipeline
- Complex debugging requiring multiple perspectives

For simple tasks, use agents directly via the Task tool or work manually.