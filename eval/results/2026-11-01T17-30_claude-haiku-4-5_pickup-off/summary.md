# Buy me a friendly dog: 5 runs per side

Claude Code 2.1.316 headless (`claude -p`), model `claude-haiku-4-5`, AUTH=off, PICKUP=off, prompt: “Buy me a friendly dog.”
Appended system prompt (both sides): “The customer is not available to answer questions during this run. Where you would ask them, decide yourself with the first sensible option and say what you chose.”

failed = isError results (HTTP errors on the before side);
no pickup on either side;
still for sale: after the run, anyone can still buy the bought pet (Petstore status, find_available_pets).

### before

| run | tool calls | failed | reads before 1st write | tokens in | tokens out | cost $ | pet bought | still for sale | sold pet ordered |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 2 | 0 | 31,337 | 810 | 0.028 | no | no | no |
| 2 | 1 | 0 | 0 | 20,464 | 628 | 0.015 | no | no | no |
| 3 | 1 | 0 | 0 | 20,497 | 645 | 0.015 | no | no | no |
| 4 | 2 | 1 | 0 | 31,243 | 767 | 0.018 | no | no | no |
| 5 | 2 | 1 | 0 | 31,321 | 895 | 0.018 | no | no | no |
| ⌀ | 1.6 | 0.8 | 0.0 | 26,972 | 749 | 0.019 | 0/5 | 0/5 | 0/5 |

Call chains:

- run 1: addPet → addPet
- run 2: addPet
- run 3: addPet
- run 4: addPet → addPet
- run 5: addPet → addPet

### after

| run | tool calls | failed | reads before 1st write | tokens in | tokens out | cost $ | pet bought | still for sale | sold pet ordered |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 0 | 1 | 24,919 | 431 | 0.021 | yes | no | no |
| 2 | 2 | 0 | 1 | 24,973 | 492 | 0.021 | yes | no | no |
| 3 | 2 | 0 | 1 | 24,909 | 423 | 0.021 | yes | no | no |
| 4 | 2 | 0 | 1 | 24,851 | 371 | 0.021 | yes | no | no |
| 5 | 2 | 0 | 1 | 24,819 | 357 | 0.020 | yes | no | no |
| ⌀ | 2.0 | 0.0 | 1.0 | 24,894 | 415 | 0.021 | 5/5 | 0/5 | 0/5 |

Call chains:

- run 1: find_available_pets → buy_pet
- run 2: find_available_pets → buy_pet
- run 3: find_available_pets → buy_pet
- run 4: find_available_pets → buy_pet
- run 5: find_available_pets → buy_pet
