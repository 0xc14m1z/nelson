# Nelson Flow Diagrams

## Purpose

This document provides visual flow summaries for Nelson v1 using Mermaid diagrams.

These diagrams are explanatory, not normative. If a diagram and a specification diverge, the normative source wins:

- [`../IMPLEMENTATION_PLAN.md`](../IMPLEMENTATION_PLAN.md)
- [`APPLICATION_PROTOCOL.md`](./APPLICATION_PROTOCOL.md)
- [`EVENT_SCHEMA.md`](./EVENT_SCHEMA.md)
- [`RUN_RESULT_SCHEMA.md`](./RUN_RESULT_SCHEMA.md)
- [`CLI_SPEC.md`](./CLI_SPEC.md)
- [`PROMPT_SPEC.md`](./PROMPT_SPEC.md)
- [`ACCEPTANCE_TESTS.md`](./ACCEPTANCE_TESTS.md)

## 1. User Entry Flows

### 1.1 `auth set`

```mermaid
flowchart TD
    A[User runs auth set with API key] --> B{API key argument present?}
    B -- No --> C[Exit 2: invalid CLI usage]
    B -- Yes --> D[Create nelson config directory if needed]
    D --> E[Write saved OpenRouter key with user-only permissions]
    E --> F{Write succeeded?}
    F -- No --> G[Exit 3: credential storage error]
    F -- Yes --> H[Emit auth events and AuthSetResult]
    H --> I[Human success output]
    I --> J[Exit 0]
```

### 1.2 `auth status`

```mermaid
flowchart TD
    A[User runs auth status] --> B[Resolve effective key source]
    B --> C{Key available?}
    C -- No --> D[Report saved/env status]
    D --> E[Emit auth events and AuthStatusResult]
    E --> F[Exit 3]
    C -- Yes --> G[Call OpenRouter key verification endpoint]
    G --> H{Verification valid?}
    H -- No --> I[Emit auth events and AuthStatusResult]
    I --> J[Exit 4]
    H -- Yes --> K[Emit auth events and AuthStatusResult]
    K --> L[Human status output]
    L --> M[Exit 0]
```

### 1.3 `auth clear`

```mermaid
flowchart TD
    A[User runs auth clear] --> B{Saved key file exists?}
    B -- No --> C[No-op success]
    B -- Yes --> D[Delete saved key file]
    D --> E{Delete succeeded?}
    E -- No --> F[Exit 3: filesystem error]
    E -- Yes --> G[Emit auth events and AuthClearResult]
    C --> G
    G --> H[Exit 0]
```

## 2. Run Startup Flows

### 2.1 Input source selection

```mermaid
flowchart TD
    A[User runs run command] --> B{Exactly one input source?}
    B -- No --> C[Exit 2: invalid CLI usage]
    B -- Yes --> D{Source type}
    D -- Prompt flag --> E[Use prompt text]
    D -- Prompt file flag --> F[Read UTF-8 prompt file]
    D -- Stdin flag --> G[Read UTF-8 stdin]
    E --> H[Construct RunCommand]
    F --> H
    G --> H
    H --> I[Dispatch to application protocol]
```

### 2.2 Output mode selection

```mermaid
flowchart TD
    A[RunCommand dispatched] --> B{Output mode}
    B -- Human --> C[Render progress to stderr]
    B -- JSON mode --> D[Await terminal RunResult]
    B -- JSONL mode --> E[Stream events only to stdout]
    C --> F[Render final answer block to stdout]
    D --> G[Emit one final JSON document]
    E --> H[Emit ordered JSONL events]
```

### 2.3 Command-to-core boundary

```mermaid
flowchart LR
    A[CLI adapter] --> B[Typed ApplicationCommand]
    B --> C[dispatch command]
    C --> D[CommandExecution events stream]
    C --> E[CommandExecution terminal result]
    D --> F[Human renderer or JSONL stream]
    E --> G[JSON terminal output]
```

## 3. Happy-Path Orchestration Flow

### 3.1 High-level run lifecycle

```mermaid
flowchart TD
    A[Run starts] --> B[Resolve credentials]
    B --> C[Task framing]
    C --> D[Round 1 starts]
    D --> E[Participants generate contributions]
    E --> F[Moderator synthesizes candidate]
    F --> G[Participants review candidate]
    G --> H{Consensus reached?}
    H -- Yes --> I[Optional release gate]
    I --> J{Release gate passes?}
    J -- Yes --> K[Emit run_completed]
    K --> L[Return final RunResult]
    J -- No --> M[Continue or fail per gate policy]
    H -- No --> N{Rounds remaining?}
    N -- Yes --> O[Next round]
    O --> E
    N -- No --> P[Emit run_completed with partial result]
```

### 3.2 Round lifecycle

```mermaid
flowchart TD
    A[round_started] --> B[Participant model calls]
    B --> C[candidate_created or candidate_updated]
    C --> D[review_started]
    D --> E[Participant review model calls]
    E --> F[review_completed]
    F --> G{Decision state}
    G -- Approve --> H[consensus_reached]
    G -- Mixed but usable --> I[consensus_pending]
    G -- Budget exhausted --> J[consensus_partial]
    H --> K[round_completed]
    I --> K
    J --> K
```

## 4. Reframing Flow

### 4.1 Material framing update inside consensus

```mermaid
flowchart TD
    A[Moderator evaluates current round] --> B{Material framing problem found?}
    B -- No --> C[Normal synthesis and review flow]
    B -- Yes --> D[Emit task_framing_updated]
    D --> E[Mark current candidate invalid]
    E --> F[Skip review and consensus for that candidate]
    F --> G[round_completed with invalidation flags]
    G --> H{Another round available?}
    H -- No --> I[run_failed with framing_update_budget_exhausted]
    H -- Yes --> J[Next round starts with new framing version]
    J --> K[All active participants regenerate fresh contributions]
```

## 5. Failure and Recovery Flows

### 5.1 Structured output failure and repair

```mermaid
flowchart TD
    A[Model invocation starts] --> B{Valid structured output?}
    B -- Yes --> C[model_completed]
    B -- No --> D[model_failed with structured output error]
    D --> E[Start repair invocation with new invocation id]
    E --> F{Repair succeeds?}
    F -- Yes --> G[model_completed for repair]
    F -- No --> H[model_failed for repair]
    G --> I[Continue workflow]
    H --> J[Apply role-specific failure rules]
```

### 5.2 Participant exclusion

```mermaid
flowchart TD
    A[Participant invocation fails after allowed retry or repair] --> B[participant_excluded]
    B --> C{Quorum still preserved?}
    C -- Yes --> D[Continue current round with remaining active participants]
    C -- No --> E[run_failed]
    D --> F[Future rounds use reduced active set]
```

### 5.3 Moderator failure

```mermaid
flowchart TD
    A[Moderator invocation fails irrecoverably] --> B[model_failed]
    B --> C[run_failed]
    C --> D[command_failed]
    D --> E[CommandExecution result resolves to failed RunResult]
```

### 5.4 Timeout handling

```mermaid
flowchart TD
    A[Invocation exceeds timeout] --> B[model_failed with timeout error]
    B --> C{Retry or repair still allowed?}
    C -- Yes --> D[Start next invocation attempt]
    C -- No --> E[Apply participant or moderator terminal failure policy]
```

## 6. Final Output Flows

### 6.1 Human mode

```mermaid
flowchart TD
    A[Ordered events arrive] --> B[Render progress to stderr]
    B --> C{Run terminal state}
    C -- Success or partial --> D[Render final answer to stdout]
    C -- Failed --> E[Render fatal error to stderr]
```

### 6.2 JSON mode

```mermaid
flowchart TD
    A[CommandExecution result resolves] --> B{Result kind}
    B -- RunResult success --> C[Emit one JSON document]
    B -- RunResult partial --> C
    B -- RunResult failed --> D[Emit one JSON failure document]
```

### 6.3 JSONL mode

```mermaid
flowchart TD
    A[Event stream starts] --> B[Write one JSON object per line]
    B --> C{Terminal event}
    C -- run_completed --> D[Stop stream]
    C -- run_failed --> D
```
