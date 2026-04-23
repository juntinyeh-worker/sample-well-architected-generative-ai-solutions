# AgentCore Memory Integration

## Status: DISABLED by default

Memory integration is an optional feature that requires authentication infrastructure and careful consideration of data isolation. It is **disabled** unless explicitly enabled via the `AgentCoreMemoryId` deployment parameter.

---

## Overview

AgentCore Memory provides persistent context for the Cloud Operation Assistant. It enables the agent to recall previous interactions, user preferences, and account-specific knowledge across sessions.

Two memory layers:
- **Short-term**: conversation turns within a single session
- **Long-term**: auto-extracted facts and insights, searchable via semantic similarity

## Architecture

```
                          ┌─────────────────────┐
User → Orchestrator ──→  │  AgentCore Runtime   │
           │              │  (Kiro CLI Agent)    │
           │              │                      │
           │              │  ┌────────────────┐  │
           │              │  │ Memory Session  │  │  ← Agent retrieves/writes
           │              │  │ Manager         │  │     memory natively
           │              │  └───────┬────────┘  │
           │              └──────────┼───────────┘
           │                         │
           │              ┌──────────▼───────────┐
           │              │  AgentCore Memory    │
           │              │  (AWS Managed)       │
           │              │                      │
           │              │  /users/{user_id}/   │
           │              │    └─ facts          │
           │              │  /accounts/{acct}/   │
           │              │    └─ knowledge      │
           │              │  /sessions/{sid}/    │
           │              │    └─ summaries      │
           │              └──────────────────────┘
```

### Where Memory Lives: Agent vs Orchestrator

Memory retrieval and writing should happen **at the agent level** (inside the AgentCore Runtime), not at the orchestrator level. Here's why:

| | Orchestrator-level | Agent-level |
|---|---|---|
| **Retrieval timing** | Before dispatch — one-shot, may miss context | During reasoning — agent decides what to recall |
| **Relevance** | Orchestrator guesses what's relevant | Agent knows what it needs mid-task |
| **Write granularity** | Only final result | Can write intermediate findings |
| **Native support** | Manual API calls | AgentCore SDK `MemorySessionManager` built-in |

The current implementation in `app.py` is a **transitional approach** — it retrieves context at the orchestrator level before dispatch. The production path is to move memory management into the Kiro CLI AgentCore runtime itself, where the agent can:
- Decide when to recall memories during multi-step reasoning
- Write intermediate discoveries (not just final answers)
- Use the native `AgentCoreMemorySessionManager` integration

### Memory Recall Mechanism

How does the agent decide what to remember?

**Automatic recall (semantic search)**:
- On each invocation, the agent's session manager automatically retrieves relevant long-term memories based on the user's current query
- Uses embedding similarity — no explicit user action needed
- Configured via `RetrievalConfig` with `top_k` and `relevance_score` thresholds

**User-prompted recall**:
- User can explicitly ask: "What did we find about my EC2 instances last week?"
- The agent treats this as a query against memory, same as any other tool use

**Automatic write**:
- Every conversation turn is written to short-term memory
- The SEMANTIC strategy automatically extracts facts into long-term memory
- The SUMMARIZATION strategy condenses sessions into summaries

There is **no manual browse/search UI** in the current design. Memory is transparent to the user — the agent uses it behind the scenes. A future enhancement could add a "Memory" panel to the UI for visibility, but it's not required for the mechanism to work.

---

## ⚠️ Context Pollution: Cross-User Data Leakage

**This is the primary risk of enabling memory without proper authentication.**

### The Problem

AgentCore Memory uses `actorId` to isolate data between users. If `actorId` is not correctly tied to an authenticated user identity:

- **Shared session IDs**: If two users happen to share a session ID (or if session IDs are predictable), User B could retrieve User A's memories
- **No auth = no isolation**: Without authentication, there's no reliable way to assign a unique, persistent `actorId`. Browser-generated UUIDs can be spoofed, cleared, or shared
- **Sensitive data exposure**: Memory stores extracted facts from conversations — resource IDs, account configurations, billing data, security findings. Cross-user leakage means exposing one customer's infrastructure details to another

### Example Scenario

```
User A asks: "List my EC2 instances" → Memory stores: "User has 12 EC2 instances in us-west-2"
User B asks: "What do you know about my infrastructure?" → Agent retrieves User A's facts
```

### Mitigation: Authentication is Mandatory

Memory MUST NOT be enabled without:
1. **Authenticated user identity** (Cognito, SSO, or equivalent)
2. **`actorId` derived from auth token** (e.g., Cognito `sub` claim)
3. **Server-side validation** — `actorId` must never come from the client

---

## Prerequisites to Enable Memory

All of the following must be in place before setting `AgentCoreMemoryId`:

### 1. Authentication (REQUIRED)
- Cognito User Pool or equivalent IdP configured
- Frontend authenticates users and passes tokens via WebSocket
- Backend validates tokens and extracts user identity
- `actorId` = authenticated user's unique ID (e.g., Cognito `sub`)

### 2. AgentCore Memory Resource (REQUIRED)
- Created via AgentCore CLI or AWS Console
- Strategy: `SEMANTIC` at minimum, optionally `SUMMARIZATION`
- Region must match the orchestrator's region

### 3. IAM Permissions (REQUIRED)
- ECS task role needs permissions for:
  - `bedrock-agentcore:CreateMemoryEvent`
  - `bedrock-agentcore:SearchMemory`
  - `bedrock-agentcore:ListMemoryRecords`
  - `bedrock-agentcore:GetMemorySession`

### 4. Namespace Design (RECOMMENDED)
Plan the namespace structure before enabling:
```
/users/{user_id}/facts           → per-user facts
/accounts/{aws_account_id}/      → shared account knowledge
/sessions/{session_id}/summary   → session summaries
```

---

## Configuration

### CFN Parameter
```yaml
AgentCoreMemoryId:
  Type: String
  Default: ''    # DISABLED by default
  Description: AgentCore Memory resource ID (leave empty to disable)
```

### Environment Variable
```
AGENTCORE_MEMORY_ID=          # disabled (default)
AGENTCORE_MEMORY_ID=mem-xxx   # enabled
```

### Behavior When Disabled
- `memory_service.is_enabled()` returns `False`
- `retrieve_context()` returns empty string
- `write_turns()` is a no-op
- Zero API calls, zero latency impact, zero cost

---

## Migration Path

| Phase | What | Auth Required |
|-------|------|---------------|
| **Current** | No memory. Orchestrator injects last task result as context for follow-ups | No |
| **Phase 1** | Enable memory at orchestrator level (current `memory_service.py`) | Yes |
| **Phase 2** | Move memory to agent level (Kiro runtime `MemorySessionManager`) | Yes |
| **Phase 3** | Add SUMMARIZATION strategy, namespace by account | Yes |
| **Phase 4** | Memory visibility UI (browse/search panel) | Yes |

---

## Files

| File | Purpose |
|------|---------|
| `orchestrator/services/memory_service.py` | Memory read/write, gated by env var |
| `orchestrator/app.py` | Integration points (transitional) |
| `deployment-scripts/agentcore-longrun-orchestrator-0.1.0.yaml` | CFN parameter |
| `docs/MEMORY.md` | This document |
