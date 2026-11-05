# Buy me a friendly dog: 5 runs per side

Claude Code 2.1.316 headless (`claude -p`), model `claude-haiku-4-5`, AUTH=off, prompt: “Buy me a friendly dog.”
Appended system prompt (both sides): “The customer is not available to answer questions during this run. Where you would ask them, decide yourself with the first sensible option and say what you chose.”

probing = reads before the first write; failed = isError results (HTTP errors on the before side);
pickup: the before API has no pickup, so it is always no there;
still on offer: after the run, anyone can still buy the bought pet (Petstore status, find_available_pets).

### before

| run | tool calls | failed | probing | tokens in | tokens out | cost $ | pet bought | pickup | still on offer | sold pet ordered |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 0 | 0 | 31,219 | 803 | 0.028 | no | no | no | no |
| 2 | 2 | 1 | 0 | 31,235 | 715 | 0.017 | no | no | no | no |
| 3 | 0 | 0 | 0 | 9,941 | 523 | 0.013 | no | no | no | no |
| 4 | 0 | 0 | 0 | 9,941 | 426 | 0.012 | no | no | no | no |
| 5 | 0 | 0 | 0 | 9,943 | 415 | 0.012 | no | no | no | no |
| ⌀ | 0.8 | 0.2 | 0.0 | 18,456 | 576 | 0.016 | 0/5 | 0/5 | 0/5 | 0/5 |

Call chains:

- run 1: addPet → placeOrder
- run 2: addPet → addPet
- run 3: (no tool calls)
- run 4: (no tool calls)
- run 5: (no tool calls)

### after

| run | tool calls | failed | probing | tokens in | tokens out | cost $ | pet bought | pickup | still on offer | sold pet ordered |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 3 | 0 | 1 | 35,545 | 769 | 0.026 | yes | yes | no | no |
| 2 | 3 | 0 | 1 | 35,416 | 666 | 0.025 | yes | yes | no | no |
| 3 | 3 | 0 | 1 | 35,682 | 900 | 0.027 | yes | yes | no | no |
| 4 | 3 | 0 | 1 | 35,572 | 802 | 0.026 | yes | yes | no | no |
| 5 | 3 | 0 | 1 | 35,534 | 723 | 0.025 | yes | yes | no | no |
| ⌀ | 3.0 | 0.0 | 1.0 | 35,550 | 772 | 0.026 | 5/5 | 5/5 | 0/5 | 0/5 |

Call chains:

- run 1: find_available_pets → buy_pet → schedule_pickup
- run 2: find_available_pets → buy_pet → schedule_pickup
- run 3: find_available_pets → buy_pet → schedule_pickup
- run 4: find_available_pets → buy_pet → schedule_pickup
- run 5: find_available_pets → buy_pet → schedule_pickup
