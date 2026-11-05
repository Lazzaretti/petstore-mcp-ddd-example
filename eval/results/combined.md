# Buy me a friendly dog: all runs

Claude Code 2.1.316 headless, AUTH=off, same prompt and appended system prompt in every run.
PICKUP=off compares the same scope as the original Petstore API (no pickup on either side).

| model | PICKUP | side | runs | ⌀ tool calls | ⌀ reads before 1st write | ⌀ failed | ⌀ tokens in | ⌀ tokens out | pet bought | pickup | still for sale | results |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| claude-haiku-4-5 | off | after | 5 | 2.0 | 1.0 | 0.0 | 24,894 | 415 | 5/5 | — | 0/5 | [2026-11-01T17-30_claude-haiku-4-5_pickup-off](2026-11-01T17-30_claude-haiku-4-5_pickup-off/summary.md) |
| claude-haiku-4-5 | off | before | 5 | 1.6 | 0.0 | 0.8 | 26,972 | 749 | 0/5 | — | 0/5 | [2026-11-01T17-30_claude-haiku-4-5_pickup-off](2026-11-01T17-30_claude-haiku-4-5_pickup-off/summary.md) |
| claude-haiku-4-5 | on | after | 5 | 3.0 | 1.0 | 0.0 | 35,550 | 772 | 5/5 | 5/5 | 0/5 | [2026-11-01T16-14](2026-11-01T16-14/summary.md) |
| claude-haiku-4-5 | on | before | 5 | 0.8 | 0.0 | 0.2 | 18,456 | 576 | 0/5 | 0/5 | 0/5 | [2026-11-01T16-14](2026-11-01T16-14/summary.md) |
| claude-haiku-5-5 | off | after | 5 | 2.0 | 1.0 | 0.0 | 15,097 | 428 | 5/5 | — | 0/5 | [2026-11-01T16-36_claude-haiku-5-5_pickup-off](2026-11-01T16-36_claude-haiku-5-5_pickup-off/summary.md) |
| claude-haiku-5-5 | off | before | 5 | 3.0 | 2.0 | 0.0 | 23,895 | 978 | 5/5 | — | 5/5 | [2026-11-01T16-36_claude-haiku-5-5_pickup-off](2026-11-01T16-36_claude-haiku-5-5_pickup-off/summary.md) |
| claude-haiku-5-5 | on | after | 5 | 3.0 | 1.0 | 0.0 | 22,868 | 666 | 5/5 | 5/5 | 0/5 | [2026-11-01T16-18](2026-11-01T16-18/summary.md) |
| claude-haiku-5-5 | on | before | 5 | 3.0 | 2.0 | 0.0 | 23,825 | 930 | 5/5 | 0/5 | 5/5 | [2026-11-01T16-18](2026-11-01T16-18/summary.md) |
| claude-opus-5-5 | off | after | 5 | 2.4 | 1.0 | 0.0 | 14,388 | 354 | 5/5 | — | 0/5 | [2026-11-01T16-33_claude-opus-5-5_pickup-off](2026-11-01T16-33_claude-opus-5-5_pickup-off/summary.md) |
| claude-opus-5-5 | off | before | 5 | 2.8 | 1.8 | 0.0 | 20,729 | 575 | 5/5 | — | 5/5 | [2026-11-01T16-33_claude-opus-5-5_pickup-off](2026-11-01T16-33_claude-opus-5-5_pickup-off/summary.md) |
| claude-opus-5-5 | on | after | 5 | 3.0 | 1.0 | 0.0 | 19,377 | 575 | 5/5 | 5/5 | 0/5 | [2026-11-01T15-58](2026-11-01T15-58/summary.md) |
| claude-opus-5-5 | on | before | 5 | 2.6 | 1.4 | 0.0 | 21,928 | 570 | 5/5 | 0/5 | 5/5 | [2026-11-01T15-58](2026-11-01T15-58/summary.md) |
