# Barge-in config (Invariant 10)

Native flag confirmed — no custom build needed.

## Setup

1. Agent dashboard → Advanced tab → Client Events → enable `interruption`.
2. Platform fires `interrupt()` on barge-in automatically; TTS stops mid-utterance, no tail silence.

## Per-tool override

Use `interruption_mode` on tool config (`allow` / `disable_during_tool` / `disable_during_tool_and_turn`):

- `book_appointment`, `check_insurance` → `disable_during_tool` (don't let a barge-in corrupt an in-flight write/lookup).
- Everything else → default `allow`.

## Not exposed

No documented control over VAD threshold, no-interrupt windows, or state-transition rules. If barge-in feels too trigger-happy on demo day, the only lever is the client-event toggle and per-tool mode above — no deeper tuning available.

Sources: [Conversation flow docs](https://elevenlabs.io/docs/eleven-agents/customization/conversation-flow), [2026-06-22 changelog](https://elevenlabs.io/docs/changelog/2026/6/22).
