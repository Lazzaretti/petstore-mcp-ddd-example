# Buy me a friendly dog: 5 runs per side

Claude Code 2.1.316 headless (`claude -p`), model `claude-opus-5-5`, AUTH=off, PICKUP=off, prompt: “Buy me a friendly dog.”
Appended system prompt (both sides): “The customer is not available to answer questions during this run. Where you would ask them, decide yourself with the first sensible option and say what you chose.”

failed = isError results (HTTP errors on the before side);
no pickup on either side;
still for sale: after the run, anyone can still buy the bought pet (Petstore status, find_available_pets).

### before

| run | tool calls | failed | reads before 1st write | tokens in | tokens out | cost $ | pet bought | still for sale | sold pet ordered |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 3 | 0 | 2 | 20,900 | 576 | 0.041 | yes | yes | no |
| 2 | 2 | 0 | 1 | 20,145 | 492 | 0.036 | yes | yes | no |
| 3 | 3 | 0 | 2 | 20,820 | 582 | 0.040 | yes | yes | no |
| 4 | 3 | 0 | 2 | 20,922 | 624 | 0.042 | yes | yes | no |
| 5 | 3 | 0 | 2 | 20,860 | 599 | 0.041 | yes | yes | no |
| ⌀ | 2.8 | 0.0 | 1.8 | 20,729 | 575 | 0.040 | 5/5 | 5/5 | 0/5 |

Call chains:

- run 1: findPetsByStatus → findPetsByTags → placeOrder
- run 2: findPetsByStatus → placeOrder
- run 3: findPetsByStatus → findPetsByTags → placeOrder
- run 4: findPetsByStatus → findPetsByTags → placeOrder
- run 5: findPetsByStatus → findPetsByTags → placeOrder

### after

| run | tool calls | failed | reads before 1st write | tokens in | tokens out | cost $ | pet bought | still for sale | sold pet ordered |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 3 | 0 | 1 | 17,066 | 384 | 0.046 | yes | no | no |
| 2 | 3 | 0 | 1 | 17,085 | 410 | 0.033 | yes | no | no |
| 3 | 2 | 0 | 1 | 12,599 | 320 | 0.030 | yes | no | no |
| 4 | 2 | 0 | 1 | 12,588 | 328 | 0.030 | yes | no | no |
| 5 | 2 | 0 | 1 | 12,604 | 326 | 0.030 | yes | no | no |
| ⌀ | 2.4 | 0.0 | 1.0 | 14,388 | 354 | 0.034 | 5/5 | 0/5 | 0/5 |

Call chains:

- run 1: find_available_pets → buy_pet → my_purchases
- run 2: find_available_pets → buy_pet → my_purchases
- run 3: find_available_pets → buy_pet
- run 4: find_available_pets → buy_pet
- run 5: find_available_pets → buy_pet
