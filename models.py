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
import re
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

    # Monotonic start time for call duration tracking
    call_start_time: float = 0.0

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
    logger.info("ROUTE_DECISION: %s", json.dumps(route_decision.to_log_dict(), indent=2))


# Keyword mapping for intent classification
# Keywords are ordered roughly by specificity (longer = more specific = higher precedence)
INTENT_KEYWORDS: dict[str, list[str]] = {
    "new_quote": [
        "new quote",
        "get a quote",
        "need a quote",
        "quote for",
        "price quote",
        "insurance quote",
        "how much",
        "pricing",
        "new policy",
        "start a policy",
        "want insurance",
        "looking for insurance",
        "shop for insurance",
        "quote",
        "get insurance",
        "price",
        "estimate",
    ],
    "payment_or_id_dec": [
        # Payment
        "make a payment",
        "pay bill",
        "pay my bill",
        "payment",
        "paid",
        # ID card variants + STT mishearings
        "id card",
        "i d card",
        "i d",
        "i.d.",
        "i.d. card",
        "identification card",
        "insurance card",
        "auto id",
        "policy card",
        # Proof of insurance
        "proof of insurance",
        "evidence of insurance",
        # Dec page variants + STT mishearings
        "dec page",
        "deck page",
        "declaration page",
        "declarations page",
        "declaration",
        "declarations",
    ],
    "make_change": [
        "make a change",
        "change my",
        "add a vehicle",
        "add vehicle",
        "add a car",
        "remove vehicle",
        "remove a vehicle",
        "change address",
        "new address",
        "update address",
        "add driver",
        "remove driver",
        "change coverage",
        "update coverage",
        "update policy",
        "update my policy",
        "modify policy",
        "change my policy",
        "change my coverage",
        "add car",
        "remove",
        "modify",
        "update my",
        "change",
    ],
    "cancellation": [
        "cancel my policy",
        "cancel policy",
        "cancel insurance",
        "cancel my auto",
        "cancel",
        "cancellation",
        "terminate",
        "terminate coverage",
        "stop insurance",
        "stop my insurance",
        "discontinue",
        "end my policy",
        "stop policy",
        "stop coverage",
    ],
    "coverage_questions": [
        "coverage question",
        "what does my policy cover",
        "what am i covered for",
        "what am i covered",
        "covered for",
        "am i covered",
        "deductible",
        "limits",
        "coverage limits",
        "premium",
        "rate went up",
        "why did my rate",
        "rate increase",
        "explain coverage",
        "understand policy",
        "coverage",
        "covered",
        "whats covered",
        "explain my coverage",
        "understand my policy",
    ],
    "annual_review": [
        "annual review",
        "policy review",
        "renewal",
        "renew",
        "renew my policy",
        "renew insurance",
        "up for renewal",
        "re-shop",
        "reshop",
        "review my policy",
        "check discounts",
        "discount",
        "policy is up for renewal",
    ],
    "mortgagee_lienholder": [
        "mortgagee",
        "mortgage",
        "mortgage company",
        "mortgage update",
        "lienholder",
        "lien holder",
        "lien",
        "bank information",
        "escrow",
        "loan company",
        "loss payee",
    ],
    "certificates": [
        "certificate of insurance",
        "certificate",
        "coi",
        "c.o.i.",
        "c o i",
        "acord",
        "acord form",
        "acord certificate",
        "send a certificate",
        "evidence of coverage",
    ],
    "claims": [
        "file a claim",
        "make a claim",
        "report a claim",
        "claim",
        "claims",
        "accident",
        "had an accident",
        "car accident",
        "damage",
        "report damage",
        "vandalism",
        "theft",
        "stolen",
        "incident",
        "collision",
        "hit",
    ],
    "hours_location": [
        "hours",
        "what are your hours",
        "when do you open",
        "when do you close",
        "business hours",
        "open today",
        "location",
        "where are you",
        "located",
        "directions",
        "address",
        "how do i get there",
        "hours of operation",
        "where are you located",
        "open",
        "when are you",
    ],
    "specific_agent": [
        "talk to",
        "speak to",
        "speak with",
        "transfer to",
        "connect me",
        "extension",
        "ext",
        "reach",
        "specific person",
        "agent",
        "my agent",
        "is there",
        "looking for",
        "agent named",
    ],
    "something_else": [],  # Fallback - matches nothing specific
}


def _normalize_text(text: str) -> str:
    """
    Normalize text for intent matching.

    Args:
        text: Raw input text

    Returns:
        Normalized text: lowercase, punctuation stripped (keeping apostrophes),
        multiple whitespace collapsed, leading/trailing whitespace stripped
    """
    # Lowercase
    text = text.lower()

    # Strip punctuation except apostrophes (for contractions like "I'm", "what's")
    # Replace punctuation with space to avoid joining words
    text = re.sub(r"[^\w\s']", " ", text)

    # Collapse multiple whitespace to single space
    text = re.sub(r"\s+", " ", text)

    # Strip leading/trailing whitespace
    text = text.strip()

    return text


def classify_intent(text: str) -> str:
    """
    Classify caller intent using keyword matching with precedence scoring.

    Uses a scoring system where longer/more specific keyword matches get higher
    scores. When multiple intents match, returns the one with the highest score.
    This ensures specific intents (claims, certificates, cancellation, mortgagee)
    beat generic matches.

    Args:
        text: Raw transcript text from STT

    Returns:
        Intent category string (always returns valid IntentCategory value)

    Examples:
        >>> classify_intent("cancel my policy")
        'cancellation'
        >>> classify_intent("update my policy")
        'make_change'
        >>> classify_intent("file a claim for accident damage")
        'claims'
        >>> classify_intent("certificate of insurance")
        'certificates'
    """
    if not text or not text.strip():
        return "something_else"

    normalized = _normalize_text(text)

    # Score each intent based on keyword matches
    # Longer keyword matches get higher scores (more specific)
    scores: dict[str, int] = {}
    for intent, keywords in INTENT_KEYWORDS.items():
        if intent == "something_else":
            continue
        score = 0
        for keyword in keywords:
            if keyword in normalized:
                # Score = length of keyword (longer = more specific)
                score = max(score, len(keyword))
        if score > 0:
            scores[intent] = score

    if not scores:
        return "something_else"

    # Return intent with highest score
    return max(scores, key=scores.get)
