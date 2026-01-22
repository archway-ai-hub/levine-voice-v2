# Aizellee Voice Receptionist - Implementation Plan

Harry Levine Insurance Agency voice receptionist built with LiveKit Agents.

## Call Flow (from levine.pdf)

```
Greeting → Collect Info → Business/Personal? → Intent Classification → Route
```

### Intent Categories (12)
1. **new_quote** - Transfer to sales agent by alpha-split
2. **payment_or_id_dec** - VA ring group, fallback to AE
3. **make_change** - Route to AE
4. **cancellation** - Route to AE
5. **coverage_questions** - Route to AE
6. **annual_review** - Route to AE
7. **something_else** - Get summary, warm transfer to AE
8. **mortgagee_lienholder** - Direct to email info@hlinsure.com
9. **certificates** - Direct to email Certificate@hlinsure.com
10. **claims** - Transfer to team (after hours: provide carrier claims number)
11. **hours_location** - Provide info directly
12. **specific_agent** - Transfer (special handling for Rachel M / Brad)

### Routing Rules
- **Personal Lines (PL)**:
  - New quotes → Sales Agents (Queens A-L, Brad M-Z)
  - Existing policies → Account Executives (Yarislyn A-G, Al H-M, Luis N-Z)
- **Commercial Lines (CL)**:
  - All → Account Executives (Adriana A-F, Rayvon G-O, Dionna P-Z)
  - Alpha-split by business name (skip "The" and "Law Offices of")
- **Special**: Jason/Fred not directly transferable; Rachel M/Brad redirect existing policy callers

---

## Phases

### Phase 1: MVP ✅ NEXT
**Goal**: Core conversation flow without transfers

**Deliverables**:
- `agent.py` - Main Aizellee agent
- Greeting: "Thank you for calling Harry Levine Insurance, this is Aizellee, how can I help you?"
- Collect caller name + phone number
- Intent classification (12 categories)
- Business vs personal determination
- Collect business name OR last name spelling
- Log routing decision (no actual transfer)

**Stack**: AgentSession + deepgram STT + openai LLM + openai TTS + silero VAD + semantic turn detection

**Command**:
```
/swarm Create the MVP Aizellee voice receptionist in agent.py with: (1) greeting "Thank you for calling Harry Levine Insurance, this is Aizellee, how can I help you?", (2) collect caller name and phone number for callback, (3) classify intent into one of 12 categories (new_quote, payment_or_id_dec, make_change, cancellation, coverage_questions, annual_review, something_else, mortgagee_lienholder, certificates, claims, hours_location, specific_agent), (4) ask "Is this for your business or personal insurance?" and collect business name OR last name spelling accordingly. Use AgentSession with deepgram STT, openai LLM, openai TTS, silero VAD, and semantic turn detection. Store collected info in agent state. No transfers yet - just log the routing decision. Keep it minimal with no tools for now.
```

---

### Phase 2: Routing
**Goal**: Alpha-split transfers and staff directory

**Deliverables**:
- `staff_directory.py` - Staff data + extensions + alpha-split logic
- `transfer_to_agent` function tool (stub/mock initially)
- Routing logic for all 12 intents
- VA ring group logic for payments

---

### Phase 3: Edge Cases
**Goal**: Handle special scenarios

**Deliverables**:
- Rachel M / Brad redirect for existing policies
- Certificates/mortgagee email responses
- After-hours claims handling (carrier claims numbers)
- "Which Rachel?" disambiguation
- On-hold experience messaging

---

### Phase 4: Tests
**Goal**: Behavioral testing for conversation quality

**Deliverables**:
- `tests/test_intents.py` - Intent classification tests
- `tests/test_routing.py` - Alpha-split routing tests
- `tests/test_conversations.py` - End-to-end conversation scenarios

---

### Phase 5: Deploy
**Goal**: Production ready

**Deliverables**:
- `Dockerfile`
- `livekit.toml`
- Environment configuration
- LiveKit Cloud deployment

---

## Staff Directory

| Department | Name | Assigned | Ext |
|------------|------|----------|-----|
| Agency Support | Anamer L. | Agency Support | 7013 |
| CL- Account Executive | Adriana | A-F | 7002 |
| CL- Account Executive | Rayvon | G-O | 7018 |
| CL- Account Executive | Dionna | P-Z | 7006 |
| CL- Department Manager | Rachel T. | Platinum | 7005 |
| CL- Producer | Kevin K. | Producer | 7003 |
| CL- Service | Stephanie | CSR | 7014 |
| Management | Julie L. | Manager, Admin | 7001 |
| Management | Jason L. | Manager, General | 7000 |
| Management | Kelly U. | Manager, Operations | 7009 |
| PL- Account Executive | Yarislyn | A-G | 7011 |
| PL- Account Executive | Al | H-M | 7015 |
| PL- Account Executive | Luis | N-Z | 7017 |
| PL- Sales Agent | Queens | A-L | 7010 |
| PL- Sales Agent | Brad | M-Z | 7007 |
| PL- Service | Ann | CSR | 7016 |
| PL- Service | Sheree | CSR | 7008 |
| PL- Special Projects | Fred | | 7012 |

---

## File Structure

```
agent.py                 # Main Aizellee agent (Phase 1)
staff_directory.py       # Staff data + routing (Phase 2)
tests/
  test_intents.py        # Intent tests (Phase 4)
  test_routing.py        # Routing tests (Phase 4)
  test_conversations.py  # E2E tests (Phase 4)
Dockerfile               # Container (Phase 5)
livekit.toml             # Deploy config (Phase 5)
```
