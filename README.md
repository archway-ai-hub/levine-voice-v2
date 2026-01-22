# Aizellee Voice Receptionist

A LiveKit-powered voice AI receptionist for Harry Levine Insurance that collects caller information and routes calls appropriately.

## What Aizellee Does

Aizellee is a conversational voice receptionist that:
- Greets callers with: "Thank you for calling Harry Levine Insurance, this is Aizellee, how can I help you?"
- Collects caller name and callback phone number
- Classifies the reason for calling into 12 intent categories
- Asks if this is for business or personal insurance
- Collects business name OR last name on policy accordingly
- Logs a RouteDecision with all collected information

## Quick Start

### 1. Install Dependencies

```bash
uv sync
```

### 2. Set Up Environment Variables

Create a `.env` file with your credentials:

```env
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret
OPENAI_API_KEY=your-openai-key
DEEPGRAM_API_KEY=your-deepgram-key
```

### 3. Download Model Files

```bash
uv run python agent.py download-files
```

### 4. Run the Agent

```bash
# Console mode (local testing with mic/speaker)
uv run python agent.py console

# Development mode (connects to LiveKit server)
uv run python agent.py dev

# Production mode
uv run python agent.py start
```

## Intent Categories

Aizellee classifies caller intent into one of these 12 categories:

| Category | Description |
|----------|-------------|
| `new_quote` | Wants a new insurance quote or policy |
| `payment_or_id_dec` | Payment questions, needs ID cards, or declarations page |
| `make_change` | Wants to change something on existing policy |
| `cancellation` | Wants to cancel a policy |
| `coverage_questions` | Questions about what their policy covers |
| `annual_review` | Wants to review their policy, check for discounts |
| `something_else` | Doesn't fit other categories |
| `mortgagee_lienholder` | Questions about mortgage company or lienholder changes |
| `certificates` | Needs a certificate of insurance |
| `claims` | Filing a claim or claim status question |
| `hours_location` | Asking about office hours or location |
| `specific_agent` | Asking for a specific person by name |

## Voice Pipeline Configuration

| Component | Provider | Model/Voice |
|-----------|----------|-------------|
| STT | Deepgram | nova-2 |
| LLM | OpenAI | gpt-4o-mini |
| TTS | OpenAI | alloy |
| VAD | Silero | (default) |
| Turn Detection | VAD-based | - |

## Project Structure

```
livekit-agent-levine/
├── agent.py                    # Main Aizellee agent
├── models.py                   # Data models (RouteDecision, etc.)
├── tests/
│   └── test_intent_classifier.py  # Intent classifier tests
├── docs/
│   └── AIZELLEE_MVP_DESIGN.md  # Design document
├── pyproject.toml              # Dependencies
└── README.md
```

## Running Tests

```bash
uv run pytest tests/test_intent_classifier.py -v
```

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key for LLM/TTS |
| `DEEPGRAM_API_KEY` | Yes | Deepgram API key for STT |
| `LIVEKIT_URL` | No | LiveKit server URL (for deployment) |
| `LIVEKIT_API_KEY` | No | LiveKit API key (for deployment) |
| `LIVEKIT_API_SECRET` | No | LiveKit API secret (for deployment) |

## Deploy to LiveKit Cloud

1. Install the LiveKit CLI:
   ```bash
   # Mac
   brew install livekit

   # Windows
   winget install LiveKit.LiveKitCLI
   ```

2. Authenticate:
   ```bash
   lk cloud auth
   ```

3. Deploy:
   ```bash
   lk agent deploy
   ```

## Resources

- [LiveKit Agents Documentation](https://docs.livekit.io/agents/)
- [LiveKit Python SDK](https://github.com/livekit/agents)
