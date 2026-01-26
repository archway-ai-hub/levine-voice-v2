"""
Aizellee Voice Receptionist Agent for Harry Levine Insurance.

This module contains the AizelleeAgent class - a conversational voice receptionist
that collects caller information and routes calls appropriately.

Uses function tools to capture caller information and update the RouteDecision.
"""

import logging
import re
import time
from dataclasses import dataclass
from typing import Optional

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
    RouteDecision,
    classify_intent,
    log_route_decision,
)
from staff_directory import (
    CL_AE_FALLBACK,
    GENERAL_FALLBACK,
    PL_AE_FALLBACK,
    STAFF_DIRECTORY,
    normalize_last_name,
    pick_cl_ae,
    pick_pl_ae,
    pick_pl_sales,
)
from transfer_provider import TransferResult, get_transfer_provider

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
     * SKIP this if caller already gave full name (first AND last) - we can derive it

   FOR CLAIMS (intent = claims):
   - Route to claims department - NO last_name or business_name needed
   - Just need insurance_type (business or personal)

   FOR EXISTING POLICY SERVICING (make_change, payment_or_id_dec, cancellation, coverage_questions, annual_review, something_else):
   - Business: "What's the business name on the policy?"
   - Personal: "What's the last name on the policy?"
     * SKIP this if caller already gave full name (first AND last) - we can derive it
     * For policy servicing, confirm unclear names by asking to spell if needed

6. When all fields are collected -> Transfer the call (see ENDING THE CALL)

Never ask for info you already have. Never re-ask intent after they've stated it.

CLARIFYING QUESTIONS FOR ROUTING:
When you need specific information to route the call, ask these questions naturally:

- Insurance Type (when you don't know if it's business or personal):
  "Is this for your business or personal insurance?"

- Business Name (for business insurance calls):
  "What's the name of your business?"

- Last Name (for personal insurance when unclear):
  "Can you spell your last name for me?"

- Specific Agent (when caller asks for someone but you can't find them):
  "Who are you trying to reach?"

Only ask these when needed - don't ask every caller all questions.

IMPORTANT - RECORDING INFORMATION:
Call the appropriate function tool IMMEDIATELY after collecting each piece of information:
- record_caller_name(name) - when you get their name
- record_callback_phone(phone) - when you get the number
- record_insurance_type(insurance_type) - "business" or "personal"
- record_business_name(business_name) - for business inquiries
- record_policy_last_name(last_name) - for personal inquiries

Do NOT call record_intent - it's handled automatically by the system.

TOOL DIRECTIVES - FOLLOW THESE EXACTLY:
After calling any record_* tool, check the response for a directive:

- "ok. ASK_NEXT: [question]" -> Ask this exact question
- "ok. READY_TRANSFER: [agent] at [ext]" -> Say "Got it - I'm going to connect you now." then call transfer_to_agent with the exact agent/extension from the directive
- "ok. READY_TRANSFER: [department]" -> Say "Got it - I'm going to connect you now." then call transfer_to_agent
- "ok. PROVIDE_INFO_ONLY" -> Provide the requested info directly, no transfer needed
- "ok. CONTINUE" -> Continue the conversation naturally

CRITICAL: When you see READY_TRANSFER, use the EXACT agent name and extension from the directive.

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
Once you have everything needed, confirm and transfer:
"Alright [name], I've got you at [phone number], calling about [reason] for your [business/personal] insurance. Let me connect you now."

FALLBACK/TRANSFER PHRASING:
When transferring a call (whether after successful routing or fallback), say EXACTLY:
"Got it — I'm going to connect you now."
Then immediately call the transfer_to_agent tool. Do not add additional commentary, wrap-up, or alternative phrasing.

IMPORTANT: Most calls should end with a transfer to the appropriate team member. The only exceptions are:
- hours_location: Provide the info directly, no transfer needed
- certificates: Let them know we'll email it, no transfer needed
- mortgagee_lienholder: Let them know we'll email the update, no transfer needed

For ALL other intents (quotes, payments, changes, claims, etc.), always transfer the call - never just say "anything else?" and hang up.

If they have a follow-up question after transfer info: Address it, then transfer.
If they say goodbye: "Thanks for calling Harry Levine Insurance. Have a great day!"

THINGS TO AVOID:
- Don't offer specific insurance advice or quotes
- Don't promise specific callback times
- Don't discuss policy details you don't have access to
- Don't use text formatting (bullets, numbers, asterisks)
- Don't use emojis
- Don't ask why they're calling if they already told you
- Don't call the record_intent tool - it's handled automatically
- If asked something outside your role: "Got it - I'm going to connect you now."
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
        directive = get_ssot_directive(userdata)
        return f"ok. {directive}"

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
        directive = get_ssot_directive(userdata)
        return f"ok. {directive}"

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
            logger.warning(f"Invalid insurance_type value: {insurance_type}")
            return "ok. CONTINUE"
        userdata.route_decision.insurance_type = type_enum
        logger.debug(f"CAPTURED insurance_type: {type_enum.value}")
        directive = get_ssot_directive(userdata)
        return f"ok. {directive}"

    @function_tool()
    async def record_business_name(self, context: RunContext, business_name: str) -> str:
        """Record the business name for business insurance inquiries.

        Args:
            business_name: The name of the business.
        """
        userdata: AizelleeUserData = context.userdata
        userdata.route_decision.business_name = business_name
        logger.debug(f"CAPTURED business_name: {business_name}")
        directive = get_ssot_directive(userdata)
        return f"ok. {directive}"

    @function_tool()
    async def record_policy_last_name(self, context: RunContext, last_name: str) -> str:
        """Record the last name on the policy for personal insurance inquiries.

        Args:
            last_name: The last name on the insurance policy.
        """
        userdata: AizelleeUserData = context.userdata
        userdata.route_decision.policy_last_name = last_name
        logger.debug(f"CAPTURED policy_last_name: {last_name}")
        directive = get_ssot_directive(userdata)
        return f"ok. {directive}"

    @function_tool()
    async def transfer_to_agent(
        self,
        context: RunContext,
        target_name: str,
        target_extension: str,
        reason: str,
    ) -> str:
        """Transfer the call to another agent.

        Args:
            target_name: Name of the staff member to transfer to.
            target_extension: Extension number to dial.
            reason: Brief explanation of why transferring.
        """
        userdata: AizelleeUserData = context.userdata
        route_decision = userdata.route_decision

        # Use SSOT values if available (set by get_ssot_directive)
        actual_target = route_decision.target_agent_name or target_name
        actual_ext = route_decision.target_extension or target_extension
        actual_reason = route_decision.transfer_reason or reason

        # Log if LLM provided different values
        if target_name != actual_target or target_extension != actual_ext:
            logger.warning(
                f"LLM transfer mismatch: {target_name}/{target_extension} -> SSOT: {actual_target}/{actual_ext}"
            )

        # Build caller_info dict for the transfer provider
        caller_info = {
            "name": route_decision.caller_name,
            "phone": route_decision.callback_phone,
            "intent": route_decision.intent.value if route_decision.intent else None,
        }

        # Log final route decision before transfer (per logging contract)
        logger.info(
            "ROUTE_DECISION: intent=%s | caller_name=%s | callback_phone=%s | insurance_type=%s | target_agent=%s | target_extension=%s | target_department=%s",
            route_decision.intent.value if route_decision.intent else None,
            route_decision.caller_name,
            route_decision.callback_phone,
            route_decision.insurance_type.value if route_decision.insurance_type else None,
            actual_target,
            actual_ext,
            route_decision.target_department,
        )

        # Call the transfer provider exactly ONCE
        provider = get_transfer_provider()

        logger.info(
            "TRANSFER_ATTEMPT provider=%s target=%s ext=%s reason=%s",
            provider.__class__.__name__,
            actual_target,
            actual_ext,
            actual_reason,
        )

        result: TransferResult = await provider.transfer(
            target_name=actual_target,
            target_extension=actual_ext,
            reason=actual_reason,
            caller_info=caller_info,
        )

        if result.status == "success":
            logger.info(
                "TRANSFER_RESULT status=%s provider=%s message=%s",
                result.status,
                result.provider,
                result.message,
            )
            return "TRANSFER_OK"
        else:
            # Transfer failed - fall back to GENERAL_FALLBACK
            fallback_target = GENERAL_FALLBACK
            logger.warning(
                "TRANSFER_FALLBACK reason=transfer_failed original_target=%s original_ext=%s message=%s",
                actual_target,
                actual_ext,
                result.message,
            )

            # Update RouteDecision with fallback target
            route_decision.target_agent_name = fallback_target
            route_decision.target_extension = None  # main_line doesn't have an extension
            route_decision.transfer_reason = f"Transfer failed: {result.message}"
            route_decision.notes = (
                f"Original target: {actual_target} (ext {actual_ext}). {route_decision.notes}"
            )

            return f"Transfer to {actual_target} failed. Please hold while I connect you to our main line."

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
# Call Routing
# ---------------------------------------------------------------------------


@dataclass
class RouteResult:
    """Result of call routing decision."""

    target_department: str  # e.g., "PL Sales", "PL AE", "CL AE", "info-only", "email", "claims"
    target_agent: Optional[str] = None  # Agent name if transfer
    target_extension: Optional[str] = None  # Extension number if transfer
    transfer_reason: str = ""  # Brief explanation of routing


# Intents that route to existing policy servicing (AE)
_EXISTING_POLICY_INTENTS = {
    IntentCategory.PAYMENT_OR_ID_DEC,
    IntentCategory.MAKE_CHANGE,
    IntentCategory.CANCELLATION,
    IntentCategory.COVERAGE_QUESTIONS,
    IntentCategory.ANNUAL_REVIEW,
    IntentCategory.SPECIFIC_AGENT,
}

# Intents that require routing (need insurance_type)
_ROUTING_INTENTS = {
    IntentCategory.CLAIMS,
    IntentCategory.NEW_QUOTE,
    IntentCategory.MAKE_CHANGE,
    IntentCategory.PAYMENT_OR_ID_DEC,
    IntentCategory.CANCELLATION,
    IntentCategory.COVERAGE_QUESTIONS,
    IntentCategory.ANNUAL_REVIEW,
    IntentCategory.SPECIFIC_AGENT,
    IntentCategory.SOMETHING_ELSE,
}

# Intents that need alpha-split routing (business_name or last_name)
_ALPHA_SPLIT_INTENTS = {
    IntentCategory.NEW_QUOTE,
    IntentCategory.MAKE_CHANGE,
    IntentCategory.PAYMENT_OR_ID_DEC,
    IntentCategory.CANCELLATION,
    IntentCategory.COVERAGE_QUESTIONS,
    IntentCategory.ANNUAL_REVIEW,
    IntentCategory.SOMETHING_ELSE,
}

# Info-only intents that should NEVER transfer
_NO_TRANSFER_INTENTS = {
    IntentCategory.HOURS_LOCATION,
    IntentCategory.CERTIFICATES,
    IntentCategory.MORTGAGEE_LIENHOLDER,
}

# Intents that require insurance_type (everything except info-only intents)
_REQUIRES_INSURANCE_TYPE_INTENTS = {
    IntentCategory.CLAIMS,
    IntentCategory.NEW_QUOTE,
    IntentCategory.MAKE_CHANGE,
    IntentCategory.PAYMENT_OR_ID_DEC,
    IntentCategory.CANCELLATION,
    IntentCategory.COVERAGE_QUESTIONS,
    IntentCategory.ANNUAL_REVIEW,
    IntentCategory.SPECIFIC_AGENT,
    IntentCategory.SOMETHING_ELSE,
}

# Max retry count for routing requirements
_MAX_ROUTING_RETRIES = 2


def _get_staff_by_name(name: str):
    """Look up staff member by name (case-insensitive)."""
    name_lower = name.lower()
    for staff in STAFF_DIRECTORY:
        if staff.name.lower() == name_lower:
            return staff
    return None


def check_routing_requirements(
    userdata: AizelleeUserData, intent: IntentCategory
) -> tuple[str, Optional[str], Optional[str]]:
    """
    Check if all routing requirements are met and return appropriate action.

    This function implements bounded retry logic with graceful fallbacks for
    route hardening. It checks each requirement and returns the appropriate
    action to take.

    Args:
        userdata: The AizelleeUserData containing the route_decision and retry counters.
        intent: The classified intent.

    Returns:
        A tuple of (action, value1, value2) where:
        - ("no_transfer", None, None): Info-only intent, don't transfer
        - ("ask", question, field_name): Need to ask for more info
        - ("fallback", agent_name, transfer_reason): Max retries exceeded, use fallback
        - ("ready", None, None): All requirements met, proceed with routing
    """
    route_decision = userdata.route_decision
    insurance_type = route_decision.insurance_type

    # -------------------------------------------------------------------------
    # E) Transfer Guards for Info-Only Intents - NEVER transfer
    # -------------------------------------------------------------------------
    if intent in _NO_TRANSFER_INTENTS:
        return ("no_transfer", None, None)

    # -------------------------------------------------------------------------
    # A) Missing Insurance Type - check BEFORE claims routing
    # -------------------------------------------------------------------------
    if intent in _REQUIRES_INSURANCE_TYPE_INTENTS and insurance_type is None:
        if userdata.asked_insurance_type_count < _MAX_ROUTING_RETRIES:
            userdata.asked_insurance_type_count += 1
            return ("ask", "Is this for business or personal insurance?", "insurance_type")
        else:
            # Fallback to main line
            return ("fallback", GENERAL_FALLBACK, "missing_insurance_type")

    # -------------------------------------------------------------------------
    # Claims routes to claims department (insurance_type now guaranteed)
    # -------------------------------------------------------------------------
    if intent == IntentCategory.CLAIMS:
        return ("ready", None, None)

    # -------------------------------------------------------------------------
    # D) Specific Agent Intent - Check if agent exists
    # -------------------------------------------------------------------------
    if intent == IntentCategory.SPECIFIC_AGENT:
        requested_agent = route_decision.requested_agent_name
        if not requested_agent or not _get_staff_by_name(requested_agent):
            if userdata.asked_specific_agent_count < _MAX_ROUTING_RETRIES:
                userdata.asked_specific_agent_count += 1
                return (
                    "ask",
                    "Who are you trying to reach? Do you know their last name or what they help you with?",
                    "specific_agent",
                )
            else:
                # Fallback to department bucket based on insurance_type
                if insurance_type == InsuranceType.BUSINESS:
                    return ("fallback", CL_AE_FALLBACK, "unknown_specific_agent")
                else:
                    return ("fallback", PL_AE_FALLBACK, "unknown_specific_agent")
        # Agent found - proceed with routing
        return ("ready", None, None)

    # -------------------------------------------------------------------------
    # B) Business Path Needs Business Name
    # -------------------------------------------------------------------------
    if insurance_type == InsuranceType.BUSINESS and intent in _ALPHA_SPLIT_INTENTS:
        if not route_decision.business_name:
            if userdata.asked_business_name_count < _MAX_ROUTING_RETRIES:
                userdata.asked_business_name_count += 1
                return ("ask", "What's the name of your business?", "business_name")
            else:
                return ("fallback", CL_AE_FALLBACK, "missing_business_name")

    # -------------------------------------------------------------------------
    # C) Personal Path Needs Last Name
    # -------------------------------------------------------------------------
    if insurance_type == InsuranceType.PERSONAL and intent in _ALPHA_SPLIT_INTENTS:
        # First try extracting last name from caller_name
        last_name = route_decision.policy_last_name
        if not last_name and route_decision.caller_name:
            # Try to extract last name from full name
            extracted = normalize_last_name(route_decision.caller_name)
            if extracted:
                # Check if caller_name is a single word (no last name extractable)
                name_parts = route_decision.caller_name.strip().split()
                if len(name_parts) >= 2:
                    # Multi-word name, we can use extracted last name
                    last_name = extracted
                    route_decision.policy_last_name = extracted
                    logger.debug(
                        f"CAPTURED policy_last_name: {extracted} (auto-extracted from caller_name)"
                    )

        if not last_name:
            if userdata.asked_last_name_count < _MAX_ROUTING_RETRIES:
                userdata.asked_last_name_count += 1
                return ("ask", "Could you spell your last name for me?", "last_name")
            else:
                return ("fallback", PL_AE_FALLBACK, "missing_last_name")

    # All requirements met
    return ("ready", None, None)


def route_call(state: RouteDecision) -> RouteResult:
    """
    Determine call routing based on intent and insurance type.

    Args:
        state: ConversationState (RouteDecision) with intent, insurance_type,
               caller_name, callback_phone, business_name, policy_last_name

    Returns:
        RouteResult with target_department, target_agent, target_extension, transfer_reason
    """
    intent = state.intent
    insurance_type = state.insurance_type

    # -------------------------------------------------------------------------
    # Special Cases (No Transfer)
    # -------------------------------------------------------------------------

    # Hours/location - provide info only, no transfer
    if intent == IntentCategory.HOURS_LOCATION:
        return RouteResult(
            target_department="info-only",
            transfer_reason="Caller asking about hours or location - provide info directly",
        )

    # Certificates - route to email
    if intent == IntentCategory.CERTIFICATES:
        return RouteResult(
            target_department="email",
            transfer_reason="Certificate request - email certificates to requesting party",
        )

    # Mortgagee/lienholder - route to email
    if intent == IntentCategory.MORTGAGEE_LIENHOLDER:
        return RouteResult(
            target_department="email",
            transfer_reason="Mortgagee/lienholder update - email update to mortgage company",
        )

    # Claims - route to claims department
    if intent == IntentCategory.CLAIMS:
        return RouteResult(
            target_department="claims",
            transfer_reason="Claim inquiry - route to claims department",
        )

    # Payment or ID card - route to VA ring group
    if intent == IntentCategory.PAYMENT_OR_ID_DEC:
        return RouteResult(
            target_department="VA",
            transfer_reason="Payment or ID card request - route to VA ring group",
        )

    # -------------------------------------------------------------------------
    # Commercial Lines (CL) - All intents route to CL AE by business name
    # -------------------------------------------------------------------------

    if insurance_type == InsuranceType.BUSINESS:
        business_name = state.business_name or ""
        staff = pick_cl_ae(business_name)
        return RouteResult(
            target_department="CL AE",
            target_agent=staff.name,
            target_extension=staff.ext,
            transfer_reason=f"Commercial lines - routing to {staff.name} (ext {staff.ext}) for business '{business_name}'",
        )

    # -------------------------------------------------------------------------
    # Personal Lines (PL)
    # -------------------------------------------------------------------------

    # Get last name for routing - from caller_name field
    last_name = state.policy_last_name or ""
    if not last_name and state.caller_name:
        # Extract last name from full caller name
        last_name = normalize_last_name(state.caller_name)

    # New quote -> Sales (alpha split by last name)
    if intent == IntentCategory.NEW_QUOTE:
        staff = pick_pl_sales(last_name)
        return RouteResult(
            target_department="PL Sales",
            target_agent=staff.name,
            target_extension=staff.ext,
            transfer_reason=f"New quote - routing to {staff.name} (ext {staff.ext})",
        )

    # Existing policy intents -> AE (alpha split by last name)
    if intent in _EXISTING_POLICY_INTENTS:
        staff = pick_pl_ae(last_name)
        return RouteResult(
            target_department="PL AE",
            target_agent=staff.name,
            target_extension=staff.ext,
            transfer_reason=f"Existing policy service - routing to {staff.name} (ext {staff.ext})",
        )

    # something_else -> Route to appropriate AE based on insurance_type
    # Default to personal lines AE if no insurance_type specified
    staff = pick_pl_ae(last_name)
    return RouteResult(
        target_department="PL AE",
        target_agent=staff.name,
        target_extension=staff.ext,
        transfer_reason=f"General inquiry - routing to {staff.name} (ext {staff.ext})",
    )


# ---------------------------------------------------------------------------
# SSOT (Single Source of Truth) Directive Functions
# ---------------------------------------------------------------------------


def get_extension_for_agent(agent_name: str) -> str | None:
    """Get the extension number for a staff member by name."""
    for staff in STAFF_DIRECTORY:
        if staff.name.lower() == agent_name.lower():
            return staff.ext
    return None


def get_ssot_directive(userdata: AizelleeUserData) -> str:
    """
    Generate directive string for LLM based on current routing state.
    This is THE orchestration function - SINGLE SOURCE OF TRUTH for what agent should do next.
    """
    intent = userdata.route_decision.intent
    if intent is None:
        return "CONTINUE"

    # Check requirements using existing check_routing_requirements
    action, value1, value2 = check_routing_requirements(userdata, intent)

    if action == "no_transfer":
        return "PROVIDE_INFO_ONLY"

    if action == "ready":
        route = route_call(userdata.route_decision)
        # Populate RouteDecision target fields
        userdata.route_decision.target_department = route.target_department
        userdata.route_decision.target_agent_name = route.target_agent
        userdata.route_decision.target_extension = route.target_extension
        userdata.route_decision.transfer_reason = route.transfer_reason

        if route.target_agent:
            return f"READY_TRANSFER: {route.target_agent} at {route.target_extension}"
        else:
            return f"READY_TRANSFER: {route.target_department}"

    if action == "fallback":
        # value1 is fallback agent name, value2 is reason
        # Get fallback extension from staff directory
        ext = get_extension_for_agent(value1)
        dept = (
            "CL AE"
            if value1 == CL_AE_FALLBACK
            else ("PL AE" if value1 == PL_AE_FALLBACK else "general")
        )
        userdata.route_decision.target_department = dept
        userdata.route_decision.target_agent_name = value1
        userdata.route_decision.target_extension = ext
        userdata.route_decision.transfer_reason = value2

        if ext:
            return f"READY_TRANSFER: {value1} at {ext}"
        else:
            return f"READY_TRANSFER: {value1}"

    if action == "ask":
        # value1 is question, value2 is field name (counter already incremented in check_routing_requirements)
        return f"ASK_NEXT: {value1}"

    return "CONTINUE"


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
