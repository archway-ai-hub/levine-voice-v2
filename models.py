"""
Data models for the Aizellee voice receptionist.

Contains:
- IntentCategory: Enum for classifying caller intent
- InsuranceType: Enum for business vs personal insurance
- ConversationState: Enum for tracking conversation flow
- RouteDecision: Dataclass for the final routing decision
- AizelleeUserData: Dataclass for session state management
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

logger = logging.getLogger("aizellee")


class IntentCategory(Enum):
    """Classification categories for caller intent."""
    NEW_QUOTE = "new_quote"
    PAYMENT_OR_ID_DEC = "payment_or_id_dec"
    MAKE_CHANGE = "make_change"
    CANCELLATION = "cancellation"
    COVERAGE_QUESTIONS = "coverage_questions"
    ANNUAL_REVIEW = "annual_review"
    SOMETHING_ELSE = "something_else"
    MORTGAGEE_LIENHOLDER = "mortgagee_lienholder"
    CERTIFICATES = "certificates"
    CLAIMS = "claims"
    HOURS_LOCATION = "hours_location"
    SPECIFIC_AGENT = "specific_agent"


class InsuranceType(Enum):
    """Type of insurance the caller is inquiring about."""
    BUSINESS = "business"
    PERSONAL = "personal"


class ConversationState(Enum):
    """Tracks where we are in the conversation flow."""
    GREETING = "greeting"
    COLLECT_NAME = "collect_name"
    COLLECT_PHONE = "collect_phone"
    CONFIRM_PHONE = "confirm_phone"
    LISTEN_INTENT = "listen_intent"
    ASK_BIZ_PERSONAL = "ask_biz_personal"
    COLLECT_BUSINESS_NAME = "collect_business_name"
    COLLECT_POLICY_LAST_NAME = "collect_policy_last_name"
    SUMMARIZE = "summarize"
    CHECK_MORE = "check_more"
    FAREWELL = "farewell"
    COMPLETE = "complete"


@dataclass
class RouteDecision:
    """
    Represents the complete routing decision for a call.
    Logged at the end of each conversation for analytics and follow-up.
    """
    # Caller identification
    caller_name: str = ""
    callback_phone: str = ""

    # Intent classification
    intent: Optional[IntentCategory] = None
    intent_raw_text: str = ""  # Original statement from caller about why they're calling

    # Insurance type
    insurance_type: Optional[InsuranceType] = None

    # Business or personal details
    business_name: Optional[str] = None  # Populated if insurance_type == BUSINESS
    policy_last_name: Optional[str] = None  # Populated if insurance_type == PERSONAL

    # Specific agent request (if intent == SPECIFIC_AGENT)
    requested_agent_name: Optional[str] = None

    # Metadata
    call_timestamp: datetime = field(default_factory=datetime.now)
    call_duration_seconds: float = 0.0
    conversation_complete: bool = False  # True if all required info collected

    # Additional notes from conversation
    notes: str = ""

    def to_log_dict(self) -> dict:
        """Convert to dictionary for logging."""
        return {
            "caller_name": self.caller_name,
            "callback_phone": self.callback_phone,
            "intent": self.intent.value if self.intent else None,
            "intent_raw_text": self.intent_raw_text,
            "insurance_type": self.insurance_type.value if self.insurance_type else None,
            "business_name": self.business_name,
            "policy_last_name": self.policy_last_name,
            "requested_agent_name": self.requested_agent_name,
            "call_timestamp": self.call_timestamp.isoformat(),
            "call_duration_seconds": self.call_duration_seconds,
            "conversation_complete": self.conversation_complete,
            "notes": self.notes,
        }

    def is_complete(self) -> bool:
        """Check if all required fields are populated."""
        # Required: name, phone, intent, insurance_type
        if not self.caller_name or not self.callback_phone:
            return False
        if not self.intent:
            return False

        # Some intents don't require insurance type (hours/location, specific agent)
        if self.intent in (IntentCategory.HOURS_LOCATION, IntentCategory.SPECIFIC_AGENT):
            return True

        if not self.insurance_type:
            return False

        # If business, need business name
        if self.insurance_type == InsuranceType.BUSINESS and not self.business_name:
            return False

        # If personal, need last name
        if self.insurance_type == InsuranceType.PERSONAL and not self.policy_last_name:
            return False

        return True

    def summary(self) -> str:
        """Generate a human-readable summary of the route decision."""
        parts = []
        parts.append(f"Caller: {self.caller_name}")
        parts.append(f"Phone: {self.callback_phone}")

        if self.intent:
            intent_display = self.intent.value.replace("_", " ").title()
            parts.append(f"Reason: {intent_display}")

        if self.insurance_type:
            parts.append(f"Type: {self.insurance_type.value.title()}")

        if self.business_name:
            parts.append(f"Business: {self.business_name}")
        elif self.policy_last_name:
            parts.append(f"Policy Name: {self.policy_last_name}")

        if self.requested_agent_name:
            parts.append(f"Requested Agent: {self.requested_agent_name}")

        return " | ".join(parts)


@dataclass
class AizelleeUserData:
    """
    Stores all conversation state and collected data.
    Passed to AgentSession as userdata.
    """
    # Conversation state tracking
    state: ConversationState = ConversationState.GREETING

    # The routing decision being built up
    route_decision: RouteDecision = field(default_factory=RouteDecision)

    # Temporary storage for phone confirmation
    phone_pending_confirmation: str = ""

    # Track if we've given the initial greeting
    greeting_given: bool = False

    # Track number of clarification attempts (to avoid infinite loops)
    clarification_attempts: int = 0
    max_clarification_attempts: int = 2

    def reset_clarification_counter(self):
        """Reset clarification counter when moving to new state."""
        self.clarification_attempts = 0

    def advance_state(self, new_state: ConversationState):
        """Advance to new state and reset clarification counter."""
        self.state = new_state
        self.reset_clarification_counter()

    def summarize(self) -> str:
        """Provide a summary for logging/debugging."""
        return f"State: {self.state.value}, Name: {self.route_decision.caller_name}, Phone: {self.route_decision.callback_phone}"


def log_route_decision(route_decision: RouteDecision) -> None:
    """Log the final routing decision for analytics."""
    logger.info(
        "ROUTE_DECISION: %s",
        json.dumps(route_decision.to_log_dict(), indent=2)
    )


# Keyword mapping for intent classification
INTENT_KEYWORDS: dict[str, list[str]] = {
    "new_quote": ["quote", "new policy", "get insurance", "price", "how much", "estimate"],
    "payment_or_id_dec": ["payment", "pay bill", "id card", "insurance card", "declaration", "dec page"],
    "make_change": ["change", "add a vehicle", "add vehicle", "add a car", "add car", "remove", "update address", "modify"],
    "cancellation": ["cancel", "cancellation", "stop policy", "end my policy"],
    "coverage_questions": ["coverage", "covered", "does my policy cover", "what's covered", "am i covered"],
    "annual_review": ["review", "annual", "check discounts", "review my policy", "discount"],
    "mortgagee_lienholder": ["mortgagee", "lienholder", "mortgage company", "bank"],
    "certificates": ["certificate", "certificate of insurance", "coi", "proof of insurance"],
    "claims": ["claim", "accident", "file a claim", "damage", "incident"],
    "hours_location": ["hours", "open", "location", "address", "directions", "when are you"],
    "specific_agent": ["speak to", "talk to", "looking for", "is there", "agent named"],
}


def classify_intent(user_input: str) -> str:
    """
    Classify user input into an intent category based on keyword matching.

    Args:
        user_input: The raw text from the caller describing why they're calling.

    Returns:
        One of the 12 intent category strings:
        - new_quote
        - payment_or_id_dec
        - make_change
        - cancellation
        - coverage_questions
        - annual_review
        - something_else
        - mortgagee_lienholder
        - certificates
        - claims
        - hours_location
        - specific_agent
    """
    normalized_input = user_input.lower().strip()

    for intent, keywords in INTENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in normalized_input:
                return intent

    return "something_else"
