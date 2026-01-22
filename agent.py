"""
Aizellee Voice Receptionist Agent for Harry Levine Insurance.

This module contains the AizelleeAgent class - a conversational voice receptionist
that collects caller information and routes calls appropriately.

Uses function tools to capture caller information and update the RouteDecision.
"""

import logging
import re
import time

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    WorkerOptions,
    cli,
    function_tool,
)
from livekit.plugins import deepgram, openai, silero

from models import (
    AizelleeUserData,
    ConversationState,
    InsuranceType,
    IntentCategory,
    classify_intent,
    log_route_decision,
)

# Load environment variables from .env file
load_dotenv()

# Configure logging to show DEBUG messages
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger("aizellee")
# Set to DEBUG to see CAPTURED and FINAL logs during development
logger.setLevel(logging.DEBUG)


# Filler words/phrases to skip when recording intent
FILLER_WORDS: set[str] = {
    "yep",
    "nope",
    "yeah",
    "uh-huh",
    "uh huh",
    "thanks",
    "thank you",
    "ok",
    "okay",
    "yes",
    "no",
    "sure",
    "right",
    "alright",
    "got it",
    "mm-hmm",
    "mmhmm",
    "mhm",
}


# Word-to-digit mapping for phone number normalization
WORD_TO_DIGIT = {
    "zero": "0",
    "oh": "0",
    "o": "0",
    "one": "1",
    "two": "2",
    "to": "2",
    "too": "2",
    "three": "3",
    "four": "4",
    "for": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
}


def normalize_phone_number(phone: str) -> str:
    """
    Normalize a phone number to digits only.

    Handles:
    - Removing non-digit characters (spaces, dashes, parentheses)
    - Converting spoken word numbers to digits ("five five five" -> "555")

    Args:
        phone: Raw phone number string from caller

    Returns:
        Digits-only string
    """
    # First, try to convert any spoken words to digits
    words = phone.lower().split()
    converted = []
    for word in words:
        # Remove common punctuation from word
        clean_word = re.sub(r"[^\w]", "", word)
        if clean_word in WORD_TO_DIGIT:
            converted.append(WORD_TO_DIGIT[clean_word])
        else:
            # Keep the original word (will be stripped of non-digits later)
            converted.append(word)

    # Join and strip all non-digit characters
    result = "".join(converted)
    digits_only = re.sub(r"\D", "", result)

    return digits_only


# System instructions for the Aizellee agent
SYSTEM_INSTRUCTIONS = """You are Aizellee, the friendly and professional voice receptionist for Harry Levine Insurance.

GREETING (EXACT - DO NOT MODIFY):
When the call begins, say EXACTLY: "Thank you for calling Harry Levine Insurance, this is Aizellee, how can I help you?"

VOICE BEHAVIOR:
- Speak naturally and conversationally, like a friendly receptionist
- Keep responses short - one sentence when possible
- Use brief confirmations: "Got it", "Sure thing", "Perfect"
- Be warm and professional
- Read back phone numbers to confirm

CRITICAL - INTENT IS AUTO-CAPTURED:
The system AUTOMATICALLY captures the caller's intent. Once they state their reason, acknowledge it briefly and move on - do NOT re-ask or confirm the intent.

Examples of brief acknowledgments:
- "Got it - a quote."
- "Sure, I can help with that."
- "No problem."

Then proceed directly to collecting their information.

CONVERSATION FLOW - DRIVEN BY MISSING FIELDS:
After acknowledging their reason for calling, collect info in this order:

1. If caller_name AND callback_phone are BOTH missing -> Combine: "Can I get your name and the best number to reach you?"
   - If they only give one, ask for the other naturally: "And the number?" or "And your name?"

2. If only caller_name is missing -> "And your name?"

3. If only callback_phone is missing -> "What's the best number to reach you?"
   - Read it back: "Got it, [number] - is that right?"

4. If insurance_type is missing -> "Is this for business or personal?"

5. Based on (intent, insurance_type), collect the identifier:

   FOR NEW QUOTES (intent = new_quote):
   - Business: "What's the business name?"
   - Personal: "And the last name?" (accept as given, don't ask to spell)

   FOR EXISTING POLICY SERVICING (all other intents):
   - Business: "What's the business name on the policy?"
   - Personal: "What's the last name on the policy?"
     * For policy servicing, confirm unclear names by asking to spell if needed

6. When all fields are collected -> Wrap up the call

Never ask for info you already have. Never re-ask intent after they've stated it.

IMPORTANT - RECORDING INFORMATION:
Call the appropriate function tool IMMEDIATELY after collecting each piece of information:
- record_caller_name(name) - when you get their name
- record_callback_phone(phone) - when you get the number
- record_insurance_type(insurance_type) - "business" or "personal"
- record_business_name(business_name) - for business inquiries
- record_policy_last_name(last_name) - for personal inquiries

Do NOT call record_intent - it's handled automatically by the system.

INTENT CLASSIFICATION (FOR REFERENCE ONLY - AUTO-CAPTURED):
The system classifies intents into these categories:
- new_quote: Wants a new insurance quote or policy
- payment_or_id_dec: Payment questions, needs ID cards, or declarations page
- make_change: Wants to change something on existing policy (add vehicle, change address, etc.)
- cancellation: Wants to cancel a policy or discuss cancellation
- coverage_questions: Questions about what their policy covers
- annual_review: Wants to review their policy, check for discounts
- something_else: Doesn't fit other categories
- mortgagee_lienholder: Questions about mortgage company or lienholder changes
- certificates: Needs a certificate of insurance
- claims: Filing a claim or claim status question
- hours_location: Asking about office hours or location
- specific_agent: Asking for a specific person by name

HANDLING UNCLEAR RESPONSES:
- If unclear, ask once: "Sorry, could you say that again?"
- If still unclear: "I want to make sure I get this right - could you spell that for me?"
- Never guess at names or phone numbers

ENDING THE CALL:
Once you have everything: "Alright [name], I've got you at [phone number], calling about [reason] for your [business/personal] insurance. Someone will be in touch soon. Anything else I can help with?"

If they say no: "Thanks for calling Harry Levine Insurance. Have a great day!"

THINGS TO AVOID:
- Don't offer specific insurance advice or quotes
- Don't promise specific callback times
- Don't discuss policy details you don't have access to
- Don't use text formatting (bullets, numbers, asterisks)
- Don't use emojis
- Don't ask why they're calling if they already told you
- Don't call the record_intent tool - it's handled automatically
- If asked something outside your role: "I'll make sure to pass that along to the team"
"""


# Intent-change signal patterns that indicate caller wants to override
INTENT_CHANGE_SIGNALS = (
    "actually",
    "never mind",
    "nevermind",
    "instead",
    "no wait",
    "i meant",
    "sorry, i need",
    "sorry i need",
)


def maybe_record_intent(userdata: AizelleeUserData, raw_text: str) -> str | None:
    """
    Classify and record intent from raw text into userdata.

    This helper extracts the core intent classification logic so it can be called
    from both the @function_tool and other contexts (e.g., automatic intent capture).

    Args:
        userdata: The AizelleeUserData containing the route_decision to update.
        raw_text: The caller's original statement about why they're calling.

    Returns:
        A status message string if intent was recorded or already exists,
        or None if the text was skipped (e.g., filler words).
    """
    # Skip filler words - return None to indicate nothing was recorded
    if raw_text.lower().strip() in FILLER_WORDS:
        logger.debug(f"INTENT SKIPPED: Filler word detected: {raw_text}")
        return None

    # DEBUG: Log raw transcript received
    logger.debug(f"DEBUG: Raw transcript received: {raw_text}")

    # DEBUG: Log classifier input
    logger.debug(f"DEBUG: Classifier input: {raw_text}")

    # Use classify_intent to determine the intent from the raw text
    # This ensures consistent classification matching what tests use
    classified_intent = classify_intent(raw_text)

    # DEBUG: Log classifier output
    logger.debug(f"DEBUG: Classifier output: {classified_intent}")

    # Convert string to IntentCategory enum
    try:
        intent_enum = IntentCategory(classified_intent)
    except ValueError:
        intent_enum = IntentCategory.SOMETHING_ELSE

    # Check if intent is already set - apply persistence logic
    current_intent = userdata.route_decision.intent
    if current_intent is not None:
        raw_text_lower = raw_text.lower()

        # Check for intent-change signals
        has_change_signal = any(signal in raw_text_lower for signal in INTENT_CHANGE_SIGNALS)

        # Check if upgrading from SOMETHING_ELSE to a more specific intent
        is_upgrade_from_something_else = (
            current_intent == IntentCategory.SOMETHING_ELSE
            and intent_enum != IntentCategory.SOMETHING_ELSE
        )

        # Only overwrite if there's a change signal or upgrading from SOMETHING_ELSE
        if not has_change_signal and not is_upgrade_from_something_else:
            logger.debug(
                f"INTENT PERSISTENCE: Keeping existing intent '{current_intent.value}' "
                f"(new classification was '{intent_enum.value}' from: {raw_text})"
            )
            return f"Intent already recorded as: {current_intent.value}"

    userdata.route_decision.intent = intent_enum
    userdata.route_decision.intent_raw_text = raw_text
    # DEBUG: Log when state.intent is set
    logger.debug(f"DEBUG: state.intent SET to {intent_enum.value} with raw_text: {raw_text}")
    return f"Recorded intent: {intent_enum.value}"


class AizelleeAgent(Agent):
    """
    Voice receptionist agent for Harry Levine Insurance.

    Collects caller information through natural conversation:
    - Caller name
    - Callback phone number
    - Reason for calling (intent)
    - Business or personal insurance
    - Business name or policy last name

    State is tracked via session.userdata (AizelleeUserData).
    Function tools are used to capture information into RouteDecision.
    """

    def __init__(self) -> None:
        super().__init__(
            instructions=SYSTEM_INSTRUCTIONS,
            # Allow interruptions for natural conversation
            allow_interruptions=True,
        )

    # -------------------------------------------------------------------------
    # Function Tools - Called by LLM to capture caller information
    # -------------------------------------------------------------------------

    @function_tool()
    async def record_caller_name(self, context: RunContext, name: str) -> str:
        """Record the caller's full name.

        Args:
            name: The caller's first and last name.
        """
        userdata: AizelleeUserData = context.userdata
        userdata.route_decision.caller_name = name
        logger.debug(f"CAPTURED caller_name: {name}")
        return f"Recorded caller name: {name}"

    @function_tool()
    async def record_callback_phone(self, context: RunContext, phone: str) -> str:
        """Record the caller's callback phone number.

        Args:
            phone: The phone number provided by the caller.
        """
        userdata: AizelleeUserData = context.userdata
        normalized = normalize_phone_number(phone)
        userdata.route_decision.callback_phone = normalized
        logger.debug(f"CAPTURED callback_phone: {normalized} (raw: {phone})")
        return f"Recorded callback phone: {normalized}"

    @function_tool()
    async def record_intent(self, context: RunContext, raw_text: str) -> str:
        """INTERNAL USE ONLY - DO NOT CALL THIS TOOL.

        Intent is captured AUTOMATICALLY from the caller's first transcript.
        The system handles intent classification without LLM intervention.

        If you call this tool, it will be ignored and you will receive a warning.

        Args:
            raw_text: The caller's original statement about why they're calling (verbatim).
        """
        # Log that LLM tried to call this tool (it shouldn't)
        logger.warning(f"LLM called record_intent tool (should be auto-captured): {raw_text}")

        userdata: AizelleeUserData = context.userdata

        # If intent is already set, don't override
        if userdata.route_decision.intent is not None:
            return (
                f"Intent already recorded as: {userdata.route_decision.intent}. No action needed."
            )

        result = maybe_record_intent(userdata, raw_text)

        # If maybe_record_intent returns None (filler word), return a message
        # indicating no intent change was made
        if result is None:
            return "No intent recorded (filler word detected)"

        return result

    @function_tool()
    async def record_insurance_type(self, context: RunContext, insurance_type: str) -> str:
        """Record whether the caller is asking about business or personal insurance.

        Args:
            insurance_type: Either "business" or "personal".
        """
        userdata: AizelleeUserData = context.userdata
        # Convert string to InsuranceType enum
        try:
            type_enum = InsuranceType(insurance_type.lower().strip())
        except ValueError:
            type_enum = InsuranceType.PERSONAL  # Default to personal if unclear
        userdata.route_decision.insurance_type = type_enum
        logger.debug(f"CAPTURED insurance_type: {type_enum.value}")
        return f"Recorded insurance type: {type_enum.value}"

    @function_tool()
    async def record_business_name(self, context: RunContext, business_name: str) -> str:
        """Record the business name for business insurance inquiries.

        Args:
            business_name: The name of the business.
        """
        userdata: AizelleeUserData = context.userdata
        userdata.route_decision.business_name = business_name
        logger.debug(f"CAPTURED business_name: {business_name}")
        return f"Recorded business name: {business_name}"

    @function_tool()
    async def record_policy_last_name(self, context: RunContext, last_name: str) -> str:
        """Record the last name on the policy for personal insurance inquiries.

        Args:
            last_name: The last name on the insurance policy.
        """
        userdata: AizelleeUserData = context.userdata
        userdata.route_decision.policy_last_name = last_name
        logger.debug(f"CAPTURED policy_last_name: {last_name}")
        return f"Recorded policy last name: {last_name}"

    # -------------------------------------------------------------------------
    # Agent Lifecycle Methods
    # -------------------------------------------------------------------------

    async def on_enter(self) -> None:
        """
        Called when the agent becomes active.
        Speaks the exact greeting and initializes state.
        """
        logger.info("AizelleeAgent entering session")

        # Get userdata from session
        userdata: AizelleeUserData = self.session.userdata

        # Store monotonic start time for call duration tracking
        userdata.call_start_time = time.monotonic()

        # Mark greeting as given
        userdata.greeting_given = True
        userdata.advance_state(ConversationState.COLLECT_NAME)

        # Speak the exact greeting - this is the ONLY thing we say on entry
        # The LLM will handle the rest of the conversation naturally
        await self.session.say(
            "Thank you for calling Harry Levine Insurance, this is Aizellee, how can I help you?",
            allow_interruptions=True,
        )

    async def on_exit(self) -> None:
        """
        Called when the agent is being replaced or session ends.
        Logs the final route decision with DEBUG details.
        """
        logger.info("AizelleeAgent exiting session")

        # Get userdata and log the route decision
        userdata: AizelleeUserData = self.session.userdata
        route_decision = userdata.route_decision

        # Calculate call duration from monotonic start time
        if userdata.call_start_time > 0:
            route_decision.call_duration_seconds = round(
                time.monotonic() - userdata.call_start_time, 1
            )

        # DEBUG: Log each field individually before final log
        logger.debug(f"FINAL caller_name: {route_decision.caller_name}")
        logger.debug(f"FINAL callback_phone: {route_decision.callback_phone}")
        logger.debug(
            f"FINAL intent: {route_decision.intent.value if route_decision.intent else None}"
        )
        logger.debug(f"FINAL intent_raw_text: {route_decision.intent_raw_text}")
        logger.debug(
            f"FINAL insurance_type: {route_decision.insurance_type.value if route_decision.insurance_type else None}"
        )
        logger.debug(f"FINAL business_name: {route_decision.business_name}")
        logger.debug(f"FINAL policy_last_name: {route_decision.policy_last_name}")
        logger.debug(f"FINAL call_duration_seconds: {route_decision.call_duration_seconds}")

        # Mark if conversation was complete
        route_decision.conversation_complete = route_decision.is_complete()

        # Log the final decision
        log_route_decision(route_decision)

        logger.info("Route decision summary: %s", route_decision.summary())


def create_aizellee_agent() -> AizelleeAgent:
    """Factory function to create an AizelleeAgent instance."""
    return AizelleeAgent()


def create_userdata() -> AizelleeUserData:
    """Factory function to create initial userdata for the session."""
    return AizelleeUserData()


# ---------------------------------------------------------------------------
# Worker Configuration
# ---------------------------------------------------------------------------


def prewarm(proc: JobProcess) -> None:
    """
    Prewarm function to load VAD model once per process.
    This avoids loading the model for each session, reducing latency.

    VAD Configuration Tuning:
    - min_silence_duration=0.4: Reduced from default 0.55 for faster turn detection
      while still allowing natural pauses in speech
    - min_speech_duration=0.08: Slightly higher than default 0.05 to filter out
      brief noise bursts while keeping responsive to real speech
    - activation_threshold=0.5: Default value works well for most environments
    - prefix_padding_duration=0.3: Reduced from default 0.5 to capture speech start
      without excessive pre-roll that can feel laggy
    """
    proc.userdata["vad"] = silero.VAD.load(
        min_silence_duration=0.4,  # Faster turn detection (default: 0.55)
        min_speech_duration=0.08,  # Filter brief noise (default: 0.05)
        activation_threshold=0.5,  # Standard threshold (default: 0.5)
        prefix_padding_duration=0.3,  # Tighter audio capture (default: 0.5)
    )
    logger.info("VAD model prewarmed with tuned settings")


async def entrypoint(ctx: JobContext) -> None:
    """
    Entrypoint function for each agent session.

    Creates an AgentSession with:
    - STT: Deepgram (nova-2 model)
    - LLM: OpenAI (gpt-4o-mini)
    - TTS: OpenAI (nova voice - more natural than alloy)
    - VAD: Silero (prewarmed with tuned settings)
    - Turn detection: VAD-based only (no semantic)

    Turn-taking Configuration:
    - min_endpointing_delay=0.4: Reduced from default 0.5 for snappier responses
    - min_interruption_duration=0.4: Slightly lower than default 0.5 for responsive barge-in
    - false_interruption_timeout=1.5: Reduced from default 2.0 to resume faster after false pauses
    - resume_false_interruption=True: Ensures agent resumes after accidental interruptions
    """
    logger.info("Starting Aizellee agent session for room: %s", ctx.room.name)

    # Create userdata for this session
    userdata = create_userdata()

    # Create the agent session with providers
    # All API keys are loaded from environment variables automatically
    session = AgentSession(
        # Speech-to-Text: Deepgram nova-2 for fast, accurate transcription
        stt=deepgram.STT(model="nova-2"),
        # Large Language Model: OpenAI gpt-4o-mini for cost-effective reasoning
        llm=openai.LLM(model="gpt-4o-mini"),
        # Text-to-Speech: OpenAI with nova voice for more natural, warm speech
        # Nova is a feminine voice known for natural conversational quality
        # Alternative options: echo (masculine), shimmer (soft feminine)
        tts=openai.TTS(voice="nova"),
        # Voice Activity Detection: Silero (prewarmed with tuned settings)
        vad=ctx.proc.userdata["vad"],
        # Turn detection: VAD-based only (simpler, works with any language)
        # This detects turn completion based on silence after speech
        turn_detection="vad",
        # Allow interruptions for natural conversation flow
        allow_interruptions=True,
        # Faster endpointing for snappier responses (default: 0.5)
        min_endpointing_delay=0.4,
        # Lower threshold for responsive barge-in (default: 0.5)
        min_interruption_duration=0.4,
        # Faster recovery from false interruptions (default: 2.0)
        false_interruption_timeout=1.5,
        # Resume speaking after false interruptions (e.g., background noise)
        resume_false_interruption=True,
        # Store userdata for state tracking
        userdata=userdata,
    )

    # Track message IDs that originated from STT transcripts (vs chat input)
    _transcript_message_ids: set[str] = set()

    # Register event handler to capture intent from first meaningful transcript
    @session.on("user_input_transcribed")
    def on_user_transcript(transcript) -> None:
        """Automatically capture intent from the first meaningful user transcript."""
        if not transcript.is_final:
            return

        raw_text = transcript.transcript.strip()
        if not raw_text:
            return

        # Track this transcript text so conversation_item_added knows the source
        # We use the text itself as a simple identifier since message IDs aren't available here
        _transcript_message_ids.add(raw_text)

        # Capture intent before processing
        intent_before = userdata.route_decision.intent

        # Only attempt to record intent if not yet set
        if userdata.route_decision.intent is None:
            result = maybe_record_intent(userdata, raw_text)
            if result:
                logger.debug(f"AUTO-INTENT: {result}")

        # Capture intent after processing
        intent_after = userdata.route_decision.intent

        # Always log transcript with intent state
        logger.debug(
            f'TRANSCRIPT: "{raw_text}" | intent_before={intent_before} | intent_after={intent_after}'
        )

    # Register event handler for conversation items (captures both chat and STT)
    @session.on("conversation_item_added")
    def on_conversation_item_added(ev) -> None:
        """Capture intent from any user message (chat or transcript)."""
        # Only process user messages
        if ev.item.role != "user":
            return

        # Extract text content
        text = ev.item.text_content
        if not text or not text.strip():
            return

        text = text.strip()

        # Determine source: if text was already seen via transcript handler, it's from STT
        if text in _transcript_message_ids:
            source = "transcript"
            # Remove from set to avoid memory buildup (one-time use)
            _transcript_message_ids.discard(text)
        else:
            source = "chat"

        # Capture intent before processing
        intent_before = userdata.route_decision.intent

        # Call maybe_record_intent for unified intent capture
        maybe_record_intent(userdata, text)

        # Capture intent after processing
        intent_after = userdata.route_decision.intent

        # Debug logging with source information
        logger.debug(
            f'USER_TEXT: "{text}" | source={source} | intent_before={intent_before} | intent_after={intent_after}'
        )

    # Create the agent instance
    agent = create_aizellee_agent()

    # Start the session with the agent and connect to the room
    await session.start(agent=agent, room=ctx.room)
    await ctx.connect()

    logger.info("Aizellee agent session started and connected")


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        )
    )
