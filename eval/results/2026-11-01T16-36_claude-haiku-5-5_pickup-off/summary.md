# Buy me a friendly dog: 5 runs per side

Claude Code 2.1.316 headless (`claude -p`), model `claude-haiku-5-5`, AUTH=off, PICKUP=off, prompt: “Buy me a friendly dog.”
Appended system prompt (both sides): “The customer is not available to answer questions during this run. Where you would ask them, decide yourself with the first sensible option and say what you chose.”

failed = isError results (HTTP errors on the before side);
no pickup on either side;
still for sale: after the run, anyone can still buy the bought pet (Petstore status, find_available_pets).

### before

| run | tool calls | failed | reads before 1st write | tokens in | tokens out | cost $ | pet bought | still for sale | sold pet ordered |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 3 | 0 | 2 | 23,724 | 889 | 0.001 | yes | yes | no |
| 2 | 3 | 0 | 2 | 23,931 | 1,085 | 0.002 | yes | yes | no |
| 3 | 3 | 0 | 2 | 23,864 | 981 | 0.002 | yes | yes | no |
| 4 | 3 | 0 | 2 | 24,060 | 967 | 0.002 | yes | yes | no |
| 5 | 3 | 0 | 2 | 23,897 | 967 | 0.002 | yes | yes | no |
| ⌀ | 3.0 | 0.0 | 2.0 | 23,895 | 978 | 0.002 | 5/5 | 5/5 | 0/5 |

Call chains:

- run 1: findPetsByStatus → findPetsByTags → placeOrder
- run 2: findPetsByTags → findPetsByStatus → placeOrder
- run 3: findPetsByStatus → findPetsByTags → placeOrder
- run 4: findPetsByTags → findPetsByStatus → placeOrder
- run 5: findPetsByStatus → findPetsByTags → placeOrder

### after

| run | tool calls | failed | reads before 1st write | tokens in | tokens out | cost $ | pet bought | still for sale | sold pet ordered |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 0 | 1 | 15,079 | 406 | 0.001 | yes | no | no |
| 2 | 2 | 0 | 1 | 15,134 | 470 | 0.001 | yes | no | no |
| 3 | 2 | 0 | 1 | 15,098 | 417 | 0.001 | yes | no | no |
| 4 | 2 | 0 | 1 | 15,088 | 431 | 0.001 | yes | no | no |
| 5 | 2 | 0 | 1 | 15,085 | 418 | 0.001 | yes | no | no |
| ⌀ | 2.0 | 0.0 | 1.0 | 15,097 | 428 | 0.001 | 5/5 | 0/5 | 0/5 |

Call chains:

- run 1: find_available_pets → buy_pet
- run 2: find_available_pets → buy_pet
- run 3: find_available_pets → buy_pet
- run 4: find_available_pets → buy_pet
- run 5: find_available_pets → buy_pet
