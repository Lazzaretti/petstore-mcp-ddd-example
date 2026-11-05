# Buy me a friendly dog: 5 runs per side

Claude Code 2.1.316 headless (`claude -p`), model `claude-opus-5-5`, AUTH=off, prompt: “Buy me a friendly dog.”
Appended system prompt (both sides): “The customer is not available to answer questions during this run. Where you would ask them, decide yourself with the first sensible option and say what you chose.”

probing = reads before the first write; failed = isError results (HTTP errors on the before side);
pickup: the before API has no pickup, so it is always no there;
still on offer: after the run, anyone can still buy the bought pet (Petstore status, find_available_pets).

### before

| run | tool calls | failed | probing | tokens in | tokens out | cost $ | pet bought | pickup | still on offer | sold pet ordered |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 4 | 0 | 2 | 28,299 | 667 | 0.045 | yes | no | yes | no |
| 2 | 2 | 0 | 1 | 20,162 | 506 | 0.036 | yes | no | yes | no |
| 3 | 3 | 0 | 2 | 20,871 | 611 | 0.041 | yes | no | yes | no |
| 4 | 2 | 0 | 1 | 20,176 | 563 | 0.037 | yes | no | yes | no |
| 5 | 2 | 0 | 1 | 20,133 | 501 | 0.036 | yes | no | yes | no |
| ⌀ | 2.6 | 0.0 | 1.4 | 21,928 | 570 | 0.039 | 5/5 | 0/5 | 5/5 | 0/5 |

Call chains:

- run 1: findPetsByStatus → findPetsByTags → placeOrder → getPetById
- run 2: findPetsByStatus → placeOrder
- run 3: findPetsByStatus → findPetsByTags → placeOrder
- run 4: findPetsByStatus → placeOrder
- run 5: findPetsByStatus → placeOrder

### after

| run | tool calls | failed | probing | tokens in | tokens out | cost $ | pet bought | pickup | still on offer | sold pet ordered |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 3 | 0 | 1 | 19,471 | 640 | 0.044 | yes | yes | no | no |
| 2 | 3 | 0 | 1 | 19,348 | 568 | 0.042 | yes | yes | no | no |
| 3 | 3 | 0 | 1 | 19,334 | 543 | 0.041 | yes | yes | no | no |
| 4 | 3 | 0 | 1 | 19,427 | 576 | 0.042 | yes | yes | no | no |
| 5 | 3 | 0 | 1 | 19,304 | 548 | 0.041 | yes | yes | no | no |
| ⌀ | 3.0 | 0.0 | 1.0 | 19,377 | 575 | 0.042 | 5/5 | 5/5 | 0/5 | 0/5 |

Call chains:

- run 1: find_available_pets → buy_pet → schedule_pickup
- run 2: find_available_pets → buy_pet → schedule_pickup
- run 3: find_available_pets → buy_pet → schedule_pickup
- run 4: find_available_pets → buy_pet → schedule_pickup
- run 5: find_available_pets → buy_pet → schedule_pickup
