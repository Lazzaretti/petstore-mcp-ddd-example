# Buy me a friendly dog: 5 runs per side

Claude Code 2.1.316 headless (`claude -p`), model `claude-haiku-5-5`, AUTH=off, prompt: “Buy me a friendly dog.”
Appended system prompt (both sides): “The customer is not available to answer questions during this run. Where you would ask them, decide yourself with the first sensible option and say what you chose.”

probing = reads before the first write; failed = isError results (HTTP errors on the before side);
pickup: the before API has no pickup, so it is always no there;
still on offer: after the run, anyone can still buy the bought pet (Petstore status, find_available_pets).

### before

| run | tool calls | failed | probing | tokens in | tokens out | cost $ | pet bought | pickup | still on offer | sold pet ordered |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 3 | 0 | 2 | 23,802 | 850 | 0.002 | yes | no | yes | no |
| 2 | 3 | 0 | 2 | 23,889 | 981 | 0.002 | yes | no | yes | no |
| 3 | 3 | 0 | 2 | 23,823 | 944 | 0.002 | yes | no | yes | no |
| 4 | 3 | 0 | 2 | 23,736 | 934 | 0.002 | yes | no | yes | no |
| 5 | 3 | 0 | 2 | 23,875 | 941 | 0.002 | yes | no | yes | no |
| ⌀ | 3.0 | 0.0 | 2.0 | 23,825 | 930 | 0.002 | 5/5 | 0/5 | 5/5 | 0/5 |

Call chains:

- run 1: findPetsByStatus → findPetsByTags → placeOrder
- run 2: findPetsByStatus → findPetsByTags → placeOrder
- run 3: findPetsByStatus → findPetsByTags → placeOrder
- run 4: findPetsByTags → findPetsByStatus → placeOrder
- run 5: findPetsByTags → findPetsByStatus → placeOrder

### after

| run | tool calls | failed | probing | tokens in | tokens out | cost $ | pet bought | pickup | still on offer | sold pet ordered |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 3 | 0 | 1 | 22,818 | 662 | 0.002 | yes | yes | no | no |
| 2 | 3 | 0 | 1 | 22,943 | 688 | 0.001 | yes | yes | no | no |
| 3 | 3 | 0 | 1 | 22,823 | 637 | 0.001 | yes | yes | no | no |
| 4 | 3 | 0 | 1 | 22,803 | 650 | 0.001 | yes | yes | no | no |
| 5 | 3 | 0 | 1 | 22,953 | 691 | 0.001 | yes | yes | no | no |
| ⌀ | 3.0 | 0.0 | 1.0 | 22,868 | 666 | 0.001 | 5/5 | 5/5 | 0/5 | 0/5 |

Call chains:

- run 1: find_available_pets → buy_pet → schedule_pickup
- run 2: find_available_pets → buy_pet → schedule_pickup
- run 3: find_available_pets → buy_pet → schedule_pickup
- run 4: find_available_pets → buy_pet → schedule_pickup
- run 5: find_available_pets → buy_pet → schedule_pickup
