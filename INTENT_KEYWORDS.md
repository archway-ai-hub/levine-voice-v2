# Intent Classification Keywords

## Overview

The `classify_intent()` function uses **deterministic keyword matching with precedence scoring** to classify caller intent from transcribed speech. This system maps caller statements to 11 specific intents or a fallback `something_else` category. The matching algorithm ensures that longer, more specific keywords take precedence over shorter, more generic ones.

The classification system is critical for routing calls to the appropriate business unit and determining what additional information (insurance type, policy details, etc.) needs to be collected during the conversation.

## How It Works

### 1. Text Normalization

Input text is normalized before keyword matching:

- **Lowercase**: All text converted to lowercase for case-insensitive matching
- **Punctuation Removal**: All punctuation removed except apostrophes (to preserve contractions like "I'm", "what's")
- **Whitespace Collapse**: Multiple consecutive spaces collapsed to single spaces
- **Trim**: Leading and trailing whitespace removed

**Example**:
```
Input:  "I'd like to CANCEL my policy!"
Normalized: "id like to cancel my policy"
```

### 2. Keyword Matching

For each intent category, the system checks if any of its keywords appear as **substrings** in the normalized text. A keyword matches if it appears anywhere in the text, not just as a whole word.

**Example**:
```
Text: "cancel my policy tomorrow"
Matches: "cancel my policy" keyword from cancellation intent
```

### 3. Precedence Scoring

When multiple intents match, the system uses **length-based precedence scoring**:

- Each matching keyword contributes a score equal to its character length
- The intent with the **highest matching keyword length** wins
- This ensures specific keywords beat generic ones

**Example**:
```
Text: "cancel my policy and change my address"
Matches:
  - cancellation: "cancel my policy" (length: 15)
  - make_change: "change my address" (length: 16) and "change my" (length: 9)
Result: make_change (highest score: 16 chars)
```

### 4. Fallback to Something Else

If no keywords match, the intent defaults to `something_else`. This category has an empty keyword list and serves as the catch-all for unrecognized intents.

---

## Intent Reference

### 1. new_quote
**Description**: Caller wants to get a new insurance quote or start a new policy

**Keywords**:
- new quote, get a quote, need a quote, quote for, price quote
- insurance quote, how much, pricing, new policy, start a policy
- want insurance, looking for insurance, shop for insurance
- quote, get insurance, price, estimate

**STT Variants**: None specifically noted

**Common Phrases**:
- "I need a quote for auto insurance"
- "How much would a new policy cost?"
- "I'm looking to shop for insurance"

---

### 2. payment_or_id_dec
**Description**: Payment requests or requests for ID card/proof of insurance/declaration pages

**Keywords**:
- **Payment**: make a payment, pay bill, pay my bill, payment, paid
- **ID Card**: id card, i d card, i d, i.d., i.d. card, identification card, insurance card, auto id, policy card
- **Proof of Insurance**: proof of insurance, evidence of insurance
- **Declaration Page**: dec page, deck page, declaration page, declarations page, declaration, declarations

**STT Variants**:
- "i d card" (STT often mishears "ID" as spoken letters)
- "deck page" (STT mishearing of "declaration")

**Common Phrases**:
- "I need to make a payment"
- "Can I get my ID card?"
- "I need a declaration page"
- "Do you have proof of insurance?"

---

### 3. make_change
**Description**: Caller wants to make changes to their existing policy (add/remove vehicles, drivers, change address, update coverage, etc.)

**Keywords**:
- make a change, change my, add a vehicle, add vehicle, add a car
- remove vehicle, remove a vehicle, change address, new address
- update address, add driver, remove driver, change coverage
- update coverage, update policy, update my policy, modify policy
- change my policy, change my coverage, add car, remove, modify
- update my, change

**STT Variants**: None specifically noted

**Common Phrases**:
- "I need to add a vehicle to my policy"
- "I want to change my address"
- "Can I update my coverage?"
- "Remove my daughter from the policy"

---

### 4. cancellation
**Description**: Caller wants to cancel or terminate their insurance policy

**Keywords**:
- cancel my policy, cancel policy, cancel insurance, cancel my auto
- cancel, cancellation, terminate, terminate coverage
- stop insurance, stop my insurance, discontinue, end my policy
- stop policy, stop coverage

**STT Variants**: None specifically noted

**Common Phrases**:
- "I want to cancel my policy"
- "Can you terminate my coverage?"
- "I need to stop my insurance"

---

### 5. coverage_questions
**Description**: Caller has questions about what their policy covers, deductibles, limits, premiums, rate changes, etc.

**Keywords**:
- coverage question, what does my policy cover, what am i covered for
- what am i covered, covered for, am i covered
- deductible, limits, coverage limits, premium, rate went up
- why did my rate, rate increase, explain coverage, understand policy
- coverage, covered, whats covered, explain my coverage
- understand my policy

**STT Variants**: None specifically noted

**Common Phrases**:
- "What does my policy cover?"
- "What's my deductible?"
- "Why did my premium go up?"
- "Am I covered for collision damage?"

---

### 6. annual_review
**Description**: Caller wants an annual policy review, renewal discussion, or wants to re-shop for discounts

**Keywords**:
- annual review, policy review, renewal, renew, renew my policy
- renew insurance, up for renewal, re-shop, reshop, review my policy
- check discounts, discount, policy is up for renewal

**STT Variants**: None specifically noted

**Common Phrases**:
- "I'm due for an annual review"
- "My policy is up for renewal"
- "Can I review my discounts?"
- "I want to renew my policy"

---

### 7. mortgagee_lienholder
**Description**: Caller has requests related to mortgage companies, lienholders, or other loss payee information

**Keywords**:
- mortgagee, mortgage, mortgage company, mortgage update
- lienholder, lien holder, lien, bank information, escrow
- loan company, loss payee

**STT Variants**: None specifically noted

**Common Phrases**:
- "I need to update my mortgagee information"
- "Can I add my lienholder?"
- "I need to update the bank information"

---

### 8. certificates
**Description**: Caller requests certificate of insurance (COI), ACORD forms, or other proof of coverage documentation

**Keywords**:
- certificate of insurance, certificate, coi, c.o.i., c o i
- acord, acord form, acord certificate, send a certificate
- evidence of coverage

**STT Variants**:
- "c o i" (spelled out letters)

**Common Phrases**:
- "I need a certificate of insurance"
- "Can you send me an ACORD form?"
- "I need proof of coverage"

---

### 9. claims
**Description**: Caller needs to file or report a claim (accident, theft, damage, collision, etc.)

**Keywords**:
- file a claim, make a claim, report a claim, claim, claims
- accident, had an accident, car accident, damage, report damage
- vandalism, theft, stolen, incident, collision, hit

**STT Variants**: None specifically noted

**Common Phrases**:
- "I need to file a claim"
- "I was in an accident"
- "My car was stolen"
- "I have vandalism damage"

---

### 10. hours_location
**Description**: Caller asking about business hours, office location, directions, or when the company is open

**Keywords**:
- hours, what are your hours, when do you open, when do you close
- business hours, open today, location, where are you, located
- directions, address, how do i get there
- hours of operation, where are you located, open, when are you

**STT Variants**: None specifically noted

**Common Phrases**:
- "What are your hours?"
- "Where is your office located?"
- "When do you open?"
- "Can you give me directions?"

---

### 11. specific_agent
**Description**: Caller wants to speak with a specific person, agent, or extension

**Keywords**:
- talk to, speak to, speak with, transfer to, connect me
- extension, ext, reach, specific person, agent, my agent
- is there, looking for, agent named

**STT Variants**: None specifically noted

**Common Phrases**:
- "Can I talk to Agent Smith?"
- "Transfer me to extension 123"
- "I want to speak with my agent"
- "Is John available?"

---

### 12. something_else
**Description**: Fallback category for intents that don't match any specific category

**Keywords**: (empty - matches nothing)

**STT Variants**: N/A

**Common Phrases**:
- "I have a question about insurance"
- "I'm calling about my account"
- (Any unrecognized intent)

---

## Precedence Examples

When text matches multiple keywords from different intents, the system selects the intent with the longest matching keyword:

| Input Text | Classified As | Winning Keyword | Length | Runner-up | Why |
|---|---|---|---|---|---|
| "cancel my policy" | cancellation | "cancel my policy" | 15 | "cancel" (6) | Longer keyword wins |
| "change my policy address" | make_change | "change my policy address" matched as substring of "change my policy" pattern | 16 | "cancel" (n/a) | "change my policy" (14) beats "change" (6) |
| "update my vehicle and coverage" | make_change | "update my" + "change coverage" | 16 | N/A | Both from make_change |
| "add vehicle and file claim" | claims | "file a claim" | 11 | "add a vehicle" (12) | "file a claim" (11) vs "add vehicle" (11) - tie, return first matched |
| "i need an id card" | payment_or_id_dec | "id card" | 7 | N/A | Matches payment_or_id_dec intent |
| "certificate for mortgage company" | certificates | "certificate" | 11 | "mortgage company" (16) from mortgagee_lienholder | Actually this is **ambiguous** - both match |

### Complex Precedence Case

```
Input: "I need a certificate of insurance for my mortgage company"

Matches found:
- certificates: "certificate of insurance" (length: 23)
- mortgagee_lienholder: "mortgage company" (length: 16)

Result: certificates (23 > 16)
Winner: "certificate of insurance"
```

### When Multiple Keywords Match Same Intent

```
Input: "add vehicle and update coverage"

Matches found:
- make_change: "add vehicle" (length: 11) and "update coverage" (length: 14)

Scoring within make_change:
- Maximum keyword length: 14

Result: make_change (highest score)
```

---

## Technical Details

### Implementation Notes

1. **Substring Matching**: Keywords are matched as substrings within the normalized text. This means "quote" will match "insurance quote", "quote for", etc.

2. **Order Independence**: The order of keywords in the list doesn't affect matching - only the length of matched keywords matters.

3. **No Whole-Word Requirement**: Keywords don't need to be surrounded by whitespace. "id" will match within "valid", for example. This is intentional to handle STT variations.

4. **Single Best Match**: The function returns the intent with the single highest-scoring keyword match. If there's a tie, Python's `max()` function returns the first one encountered.

5. **Deterministic**: The same input always produces the same output - no randomness or learning involved.

### Scoring Algorithm (Pseudocode)

```
function classify_intent(text):
    normalized = normalize(text)  // lowercase, remove punctuation, collapse whitespace

    scores = {}
    for each intent in INTENT_KEYWORDS:
        max_keyword_length = 0
        for each keyword in INTENT_KEYWORDS[intent]:
            if keyword in normalized:
                max_keyword_length = max(max_keyword_length, len(keyword))
        if max_keyword_length > 0:
            scores[intent] = max_keyword_length

    if scores is empty:
        return "something_else"

    return intent with highest score
```

---

## Best Practices

### Adding New Keywords

When adding keywords to improve classification accuracy:

1. **Longer is Better**: Use specific phrases rather than single words
2. **Test for Conflicts**: Ensure new keywords don't create unwanted matches in other intents
3. **Document Variants**: Include common STT mishearings with comments
4. **Maintain Specificity**: Order by specificity within the list (though not required for algorithm)

### Debugging Classification Issues

If a caller's intent is misclassified:

1. Check the normalized text (what the algorithm actually sees)
2. Find which keywords matched
3. Compare keyword lengths - the longest wins
4. Add longer, more specific keywords if needed
5. Test with `classify_intent()` function directly

### Common STT Challenges

- **Homophones**: "I'd" vs "I D" (handled with variants like "i d" for ID card)
- **Slurred Speech**: "declaration" vs "deck page" (included both)
- **Accent Variations**: Consider regional pronunciations
- **Background Noise**: May result in partial words or misrecognitions

---

## Related Code

The intent classification lives in `/Users/samruben/Downloads/livekit-agent-levine/models.py`:

- `INTENT_KEYWORDS`: Dictionary mapping intent names to keyword lists (lines 208-281)
- `_normalize_text()`: Normalization function (lines 284-308)
- `classify_intent()`: Main classification function (lines 311-359)
- `IntentCategory`: Enum defining valid intent values (lines 23-36)
