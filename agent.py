"""
Aizellee Voice Receptionist Agent for Harry Levine Insurance.

This module contains the AizelleeAgent class - a conversational voice receptionist
that collects caller information and routes calls appropriately.

Uses function tools to capture caller information and update the RouteDecision.
"""

import logging
import re

from dotenv import load_dotenv
from livekit.agents import Agent, AgentSession, JobContext, JobProcess, RunContext, WorkerOptions, cli, function_tool
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
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger("aizellee")
# Set to DEBUG to see CAPTURED and FINAL logs during development
logger.setLevel(logging.DEBUG)


# Word-to-digit mapping for phone number normalization
WORD_TO_DIGIT = {
    "zero": "0", "oh": "0", "o": "0",
    "one": "1",
    "two": "2", "to": "2", "too": "2",
    "three": "3",
    "four": "4", "for": "4",
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
        clean_word = re.sub(r'[^\w]', '', word)
        if clean_word in WORD_TO_DIGIT:
            converted.append(WORD_TO_DIGIT[clean_word])
        else:
            # Keep the original word (will be stripped of non-digits later)
            converted.append(word)
    
    # Join and strip all non-digit characters
    result = ''.join(converted)
    digits_only = re.sub(r'\D', '', result)
    
    return digits_only


# System instructions for the Aizellee agent
SYSTEM_INSTRUCTIONS = """You are Aizellee, the friendly and professional voice receptionist for Harry Levine Insurance.

GREETING (EXACT - DO NOT MODIFY):
When the call begins, say EXACTLY: "Thank you for calling Harry Levine Insurance, this is Aizellee, how can I help you?"

VOICE BEHAVIOR:
- Speak naturally and conversationally, as if you're a helpful receptionist on a phone call
- Keep responses concise (1-2 sentences when possible)
- Use verbal confirmations like "Got it", "Sure", "Okay, let me note that down"
- Be warm, patient, and professional
- Spell back important information (names, phone numbers) to confirm accuracy

CONVERSATION FLOW:
You must collect the following information in order:
1. Caller's name (first and last)
2. Callback phone number
3. Reason for calling (classify into one of the intent categories)
4. Business or personal insurance
5. Based on the answer to #4:
   - If BUSINESS: Ask for the business name
   - If PERSONAL: Ask for the last name on the policy and spelling if unclear

IMPORTANT - RECORDING INFORMATION:
You MUST call the appropriate function tool IMMEDIATELY after collecting each piece of information. Do NOT wait until the end of the call. Call the tools as follows:
- When you get the caller's name: call record_caller_name(name)
- When you get the phone number: call record_callback_phone(phone)
- When you understand why they're calling: call record_intent(raw_text) with their exact words about why they're calling
- When you learn if it's business or personal: call record_insurance_type(insurance_type) with "business" or "personal"
- When you get the business name: call record_business_name(business_name)
- When you get the policy last name: call record_policy_last_name(last_name)

INTENT CLASSIFICATION:
Listen carefully to why they're calling and classify into ONE of these categories:
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

COLLECTING INFORMATION:
- Ask for the caller's name first: "May I have your name please?"
- Then ask for callback number: "And what's a good callback number?"
- Read back the phone number to confirm: "Just to confirm, that's [number], correct?"
- Listen to their reason for calling and classify it
- Ask: "Is this for your business or personal insurance?"
- Based on their answer:
  * Business: "What's the name of the business?"
  * Personal: "What's the last name on the policy?" (If unclear: "Could you spell that for me?")

HANDLING UNCLEAR RESPONSES:
- If you don't understand something, ask once for clarification
- If still unclear, say "I want to make sure I get this right" and ask them to repeat or spell it
- Never guess at important information like names or phone numbers

ENDING THE CALL:
Once you have all information, summarize: "Alright, I have you down as [name] at [phone number], calling about [reason] for your [business/personal] insurance, [business name or last name on policy]. We'll have someone get back to you shortly. Is there anything else I can help you with?"

If they say no: "Thank you for calling Harry Levine Insurance. Have a great day!"

THINGS TO AVOID:
- Don't offer specific insurance advice or quotes
- Don't promise specific callback times
- Don't discuss policy details you don't have access to
- Don't use text formatting (bullets, numbers, asterisks)
- Don't use emojis
- If asked something outside your role, say "I'll make sure to pass that along to the team"
"""


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
        """Record the caller's reason for calling.

        Args:
            raw_text: The caller's original statement about why they're calling (verbatim).
        """
        userdata: AizelleeUserData = context.userdata
        
        # DEBUG: Log raw transcript received
        logger.debug(f"DEBUG: Raw transcript received: {raw_text}")
        
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

        # Mark greeting as given
        userdata.greeting_given = True
        userdata.advance_state(ConversationState.COLLECT_NAME)

        # Speak the exact greeting - this is the ONLY thing we say on entry
        # The LLM will handle the rest of the conversation naturally
        await self.session.say(
            "Thank you for calling Harry Levine Insurance, this is Aizellee, how can I help you?",
            allow_interruptions=True
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

        # DEBUG: Log each field individually before final log
        logger.debug(f"FINAL caller_name: {route_decision.caller_name}")
        logger.debug(f"FINAL callback_phone: {route_decision.callback_phone}")
        logger.debug(f"FINAL intent: {route_decision.intent.value if route_decision.intent else None}")
        logger.debug(f"FINAL intent_raw_text: {route_decision.intent_raw_text}")
        logger.debug(f"FINAL insurance_type: {route_decision.insurance_type.value if route_decision.insurance_type else None}")
        logger.debug(f"FINAL business_name: {route_decision.business_name}")
        logger.debug(f"FINAL policy_last_name: {route_decision.policy_last_name}")

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
    """
    proc.userdata["vad"] = silero.VAD.load()
    logger.info("VAD model prewarmed and ready")


async def entrypoint(ctx: JobContext) -> None:
    """
    Entrypoint function for each agent session.

    Creates an AgentSession with:
    - STT: Deepgram (nova-2 model)
    - LLM: OpenAI (gpt-4o-mini)
    - TTS: OpenAI (alloy voice)
    - VAD: Silero (prewarmed)
    - Turn detection: VAD-based only (no semantic)
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

        # Text-to-Speech: OpenAI with alloy voice for natural speech
        tts=openai.TTS(voice="alloy"),

        # Voice Activity Detection: Silero (prewarmed)
        vad=ctx.proc.userdata["vad"],

        # Turn detection: VAD-based only (simpler, no semantic model)
        # This detects turn completion based on silence after speech
        turn_detection="vad",

        # Allow interruptions for natural conversation flow
        allow_interruptions=True,

        # Store userdata for state tracking
        userdata=userdata,
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
