---
name: memory
description: Decide whether a conversation should update long-term or daily memory.
compatibility: opencode
---

# Memory

Use this skill to decide whether the current conversation contains information worth remembering.

## Core Principle

Only store memory when the content is likely to help future interactions.

## Store In Long-Term Memory When

- The user explicitly says to remember something for the future
- The user reveals a stable preference
- The user provides a persistent fact about themselves or their workflow
- The conversation establishes a durable operating rule or decision

## Store In Daily Memory When

- The information is useful but short-lived
- It is tied to a current task, current day, or temporary constraint
- It may help later in the same work session but should not pollute long-term memory

## Ignore When

- The message is ordinary chit-chat
- The information is already obvious from the ledger or current message
- The content is a one-off answer with no future value

## Tool Guidance

- When the user explicitly asks to remember something, call `store_memory`
- Choose `long_term` for stable preferences, fixed rules, or durable facts
- Choose `daily` for temporary task context
- When the user asks what you remember, or when remembered information is clearly needed, call `search_memory`
- Do not store ordinary chit-chat or information that can be directly re-derived from the ledger

## Categories

- `preference`
- `fact`
- `task_context`
- `decision`
- `constraint`
