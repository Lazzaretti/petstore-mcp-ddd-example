# petstore-mcp-ddd-example

> **Material for the talk** *Protocol Solved, Design Still Open: Domain-Driven Design for MCP Servers* by Fabrizio Lazzaretti, with input from Annegret Junker (KubeCon + CloudNativeCon North America 2026, Agentics Day, 9 Nov 2026). Slides and more: [lazzaretti.me/agentics26](https://lazzaretti.me/agentics26).
>
> A demo, not a product: built to show one idea and to reproduce the numbers on the slides.
>
> **Before you run anything:**
> - `petstore_before.py` (the wrapped API) sends its tool calls to the **public** Swagger Petstore (`petstore3.swagger.io`) by default: an agent using it creates and changes pets and orders there. To stay local, run `scripts/petstore-local.sh start` and set `PETSTORE_API_URL=http://localhost:8081/api/v3`. `eval.py` and the clips already use the local Petstore.
> - `eval.py` and the clip scripts run real Claude Code sessions with your login: they use your Claude plan or API credits (5 runs per side and model by default).
>
> **No open-source license:** published to read alongside the talk, all rights reserved. Third-party material and credits: [third-party/](third-party/README.md).

## The idea

Turning an API into an MCP server takes a few lines: one tool per endpoint. The agent then gets whatever the API has, and has to glue the steps together itself. This repo takes the classic [Swagger Petstore](https://petstore3.swagger.io) and builds it twice:

- **Before:** the Petstore's OpenAPI spec wrapped as one MCP server, one tool per endpoint (`petstore_before.py`, 19 tools).
- **After:** the same shop designed from its domain with Domain-Driven Design: three MCP servers, one per bounded context, with tools named and shaped after business actions (`petstore/`, 6 tools and 1 resource).

Then the same request goes to both: **"Buy me a friendly dog."**

On the before side the agent calls `placeOrder` and says it bought Rex. Rex is still for sale: in the Petstore API an order doesn't change the pet, and nothing tells the agent. Buying would need a second call that changes the pet's status (`updatePet`); the agent doesn't ask, it assumes the order is the purchase and never makes that call. An older, smaller model (Haiku 4.5) fails worse on the same tools: it never looks at the shop's pets, makes up a dog with `addPet`, overwrites Rex in some runs, and still reports success. On the after side the agent calls `buy_pet`, the server applies the shop's rules, and Rex is off sale. A second buy of Rex is refused with an error the agent can act on:

```
PetNotAvailable: Rex is already sold. Use find_available_pets for others.
```

The point: **designing the MCP surface from the domain gives the agent a better contract than wrapping the API.** The protocol is the same on both sides; only the design differs.

The after side comes from Domain-Driven Design: Domain Storytelling and EventStorming found four bounded contexts, and each context the agent needs became its own MCP server (Identity Management became the OAuth login, with no tools). The tools were then designed in business words on the Bounded Context Canvas and the [MCP Product Canvas](https://miro.com/miroverse/mcp-product-canvas/) ([canvases/](canvases/): the template and the one for the Pet Sales buyer); details in the talk.

## Watch it first

Real Claude Code sessions, recorded with [VHS](https://github.com/charmbracelet/vhs), 2× speed. Nothing is staged: the prompts are typed, everything else is the model.

| Before: the wrapped Petstore (22 s) | After: three domain servers (26 s) |
|---|---|
| [![Before clip](media/before-clip-poster.png)](media/before-clip.mp4) | [![After clip](media/after-clip-poster.png)](media/after-clip.mp4) |
| 1 "Buy me a friendly dog": `addPet` → `placeOrder`. The agent makes up a dog, "Buddy", and says: "Done! I've purchased a friendly dog for you named Buddy… Your order has been approved." 2 "Which friendly dogs are available?": Rex and Bello were in the shop all along, plus Buddy, "the one I just added for you". 3 "Did the order go through? Was the dog actually bought?": the order is "approved" but not complete, and Buddy is still for sale. | 1 "Buy me a friendly dog": `find_available_pets` → `buy_pet`. Claude Code asks for confirmation; the agent bought Rex and lists the free pickup slots. 2 "Tuesday 10 AM": `schedule_pickup`, confirmed again. 3 "Buy Rex for my sister too": Rex is gone, the agent offers Bello. |

Both clips use Claude Code 2.1.316 with Haiku 4.5, an older small model, and in both the customer answers (no extra system prompt). The same model invents a dog on the wrapped API and buys the right one through the domain servers. The answers vary from take to take; the evaluation below has the numbers.

## What it shows: the numbers

What the agent has to read, measured from what Claude Code 2.1.316 actually sends to the model (tool name, description, input schema, server instructions). Run `uv run python -m petstore.app tools` to print it.

| | Before | After | After, without pickup |
|---|---|---|---|
| MCP servers | 1 | 3 | 3 |
| Tools | 19 | 6 (+ 1 resource) | 5 (+ 1 resource) |
| Sent to the model (chars) | 7,509 | 2,578 | **1,850 (−75 %)** |
| Tokens (≈ chars ÷ 4) | ≈1,877 | ≈644 | ≈462 |

The original Petstore has no pickup, so "after, without pickup" (`PICKUP=off`) is the fair comparison: the same scope on both sides. Claude Code doesn't send titles, annotations, output schemas or `_meta` to the model; `host_request.py` captures the real request to check this.

**The evaluation** (`eval.py`, 1 Nov 2026): "Buy me a friendly dog." 5 times per side and model, headless Claude Code, the same four pets, Opus 5.5, Haiku 5.5 and Haiku 4.5, with and without pickup. What counts:

- **Before, "bought"** = `placeOrder` succeeded for a friendly dog on offer. **"Still for sale"** = the Petstore still lists that dog as available after the run.
- **After, "bought"** = an active purchase in Pet Handover, and the pet is off offer.

Results ([all runs](eval/results/combined.md)):

- **After side: 5 of 5 in all six run sets.** Every model finds a pet, buys it, schedules the pickup when there is one, and the pet is off sale. No failed calls, 2–3 calls per run.
- **Before side, Opus 5.5 and Haiku 5.5:** an order every time (`findPetsBy… → placeOrder`), and the pet stays for sale in 20 of 20 runs. Never a pickup.
- **Before side, Haiku 4.5: no seeded dog bought in 10 runs.** It made up a dog with `addPet` ("Buddy") instead of reading the shop, overwrote Rex (id 1) in 3 runs, and still reported success in most of the others.
- **Same scope (`PICKUP=off`):** about 30–37 % fewer input tokens per run with the current models.

Domain tools kept even an older, smaller model on the rules; endpoint tools left every model to improvise. These are small, indicative runs (5 per cell, Claude models only), not a benchmark.

## Setup

Two ways:

- **The dev container (recommended):** everything below runs in it, with all tools pinned. You need Docker (Docker Desktop or similar). In VS Code: install the *Dev Containers* extension, open this folder, *Dev Containers: Reopen in Container*. On the command line: `npx @devcontainers/cli up --workspace-folder .`, then `npx @devcontainers/cli exec --workspace-folder . bash`. The first build takes a few minutes; `.devcontainer/post-create.sh` installs and pins the tools.
- **On your machine:** Python 3.13 and [uv](https://docs.astral.sh/uv/) are enough for the quick start. For the login, the local Petstore and kind you also need Docker; for the clips and the evaluation, Claude Code.

**Claude Code in the container:** the container doesn't mount your `~/.claude`. Run `claude` once and sign in; if no browser opens, copy the login URL into your browser and paste the code back. The login lives in a Docker volume and survives rebuilds.

**Ports:** 8000 MCP servers, 8080 Keycloak, 8081 the local Petstore, 8082 kagent UI. VS Code forwards 8000 and 8080 with `requireLocalPort`, so Claude Code on your machine can use the servers in the container: the OAuth issuer and audience are `http://localhost:8000|8080`, so a busy port must fail instead of moving to another one.

The container has no outbound firewall, because kind, Keycloak and kagent pull images from many registries. To add one, see [Claude Code in dev containers](https://code.claude.com/docs/en/devcontainer).

## Try it

### Quick start (no Docker)

```bash
uv sync                                         # fastmcp 4.1.4 (pinned)
uv run pytest                                   # the rules and the MCP contracts (no Docker, no network)
uv run python -m petstore.app tools             # what the agent sees: before vs. after
uv run python -m petstore.app demo --pause      # 8 scripted scenes through MCP, no model
```

The `demo` scenes: find friendly dogs, buy Rex without a slot (the result lists free slots), schedule the pickup, Bob tries to buy Rex (`PetNotAvailable`), Alice's purchases, an expired reservation, too late to reschedule or cancel, Bob cancels Alice's purchase (`UnknownPurchase`).

### Connect Claude Code without a login

```bash
AUTH=off PETSTORE_CUSTOMER=alice uv run python -m petstore.app serve   # :8000, /discovery/mcp, /sales/mcp, /handover/mcp
```

Then add the three servers (`http://localhost:8000/discovery/mcp`, `/sales/mcp`, `/handover/mcp`) to your MCP host. `stage-after/` has a ready Claude Code config for port 8010 (`scripts/reset-after.sh` starts the app there with a fixed clock).

### With the login (OAuth, Keycloak)

This is the setup used on stage. It needs Docker for Keycloak.

1. `scripts/keycloak.sh start` (Keycloak 26.8.1, realm `petstore`, users `alice`/`alice-demo` and `bob`/`bob-demo`; admin console `admin`/`admin`; all local demo credentials), then `uv run python -m petstore.app serve`.
2. Check: `curl -si http://localhost:8000/sales/mcp -X POST | head -5` returns `401` with a `WWW-Authenticate` header pointing at `/.well-known/oauth-protected-resource/sales/mcp`.
3. `cd stage && claude`. Accept the three project MCP servers when asked.
4. Type `/mcp`, choose `petstore-sales`, *Authenticate*. The browser opens Keycloak: log in as `alice` (password `alice-demo`, local demo credentials).
5. Repeat for `petstore-discovery` and `petstore-handover`: each server has its own token audience, so a Pet Sales token doesn't open Pet Discovery.
6. If the login fails because Keycloak can't fetch Claude Code's client metadata (no internet), register a fixed client instead: `claude mcp add --transport http --client-id claude-code-petstore --callback-port 33419 petstore-sales http://localhost:8000/sales/mcp` (same for the other two), then `/mcp` again.

Everything runs on plain `http://localhost`: fine for development, not for production.

### Settings

| Setting | Default | What |
|---|---|---|
| `AUTH` | `on` | `off`: no OAuth, the customer comes from `PETSTORE_CUSTOMER` |
| `PETSTORE_CUSTOMER` | `alice` | the customer with `AUTH=off` (`alice` or `bob`) |
| `PICKUP` | `on` | `off`: the original Petstore's scope: no `schedule_pickup`, no pickup in results, schemas or policies, cancel any time |
| `PETSTORE_NOW` | real clock | fixed shop time (America/Denver), e.g. `2026-11-09T16:45` |
| `RESERVATION_HOLD` | `24h` | how long a reservation holds: `24h`, `30m`, `90s` |
| `PORT` | `8000` | |
| `KEYCLOAK_ISSUER` | `http://localhost:8080/realms/petstore` | |
| `PUBLIC_URL` | `http://localhost:8000` | base of the token audience `<PUBLIC_URL>/<context>/mcp` |
| `PETSTORE_API_URL` | public Petstore | where the before server's tool calls go |

Everything is in memory: restart to reset. The seed: 1 Rex (dog, friendly), 2 Mia (cat, indoor), 3 Bello (dog, puppy, friendly), 4 Max (dog, friendly, sold).

## Reproduce the talk's evidence

Needs Docker and Claude Code logged in.

```bash
scripts/petstore-local.sh start|stop|status      # swaggerapi/petstore3:1.0.29 on :8081, seeded with the four pets
uv run python eval.py run [--runs 5] [--side before|after|both] [--model claude-opus-5-5] [--pickup on|off]
uv run python eval.py combine                    # eval/results/combined.md: all runs in one table
uv run python host_request.py [--model claude-haiku-5-5]   # what Claude Code really sends to the model, per side
uv run python wire_trace.py [--url http://localhost:8000]  # the raw MCP messages (app running with AUTH=off)
media/render-before-clip.sh 1 3                  # the before clip, 3 takes (Haiku 4.5; MODEL=… for another)
media/render-after-clip.sh 1 3                   # the after clip, 3 takes
```

- `eval.py` resets the side before each run (fresh local Petstore, fresh app on port 8010) and writes `summary.md`, `runs.json` and the transcripts to `eval/results/<timestamp>/`.
- The clips are rendered from `media/before-clip.tape` and `media/after-clip.tape`. Each take resets the shop, starts Claude Code with only that side's servers (`stage-before/` or `stage-after/`, no CLAUDE.md) and types the prompts. `scripts/check_before_take.py` and `check_after_take.py` then read the transcript and the shop's state: the calls per prompt and what happened to Rex (`media/*-take<n>.json`).

### On Kubernetes: kagent on kind

The three servers can also be registered in [kagent](https://kagent.dev) on a kind cluster, tested with kagent 0.10.4. kagent can't do the OAuth login, so the app runs with `AUTH=off`. All three servers run in one process and pass events in memory; separate deployments per context (kmcp) and events over NATS are not built.

```bash
AUTH=off uv run python -m petstore.app serve &
scripts/kagent-kind.sh up      # kind cluster `petstore`, kagent 0.10.4 via Helm, three RemoteMCPServers
scripts/kagent-kind.sh ui      # http://localhost:8082 → View → "MCP & tools", filter "petstore"
scripts/kagent-kind.sh down    # deletes the cluster
```

The script expects the dev container: kind runs in its Docker-in-Docker, so the `RemoteMCPServer` URLs point at the kind network's gateway (the container), e.g. `http://172.19.0.1:8000`. Only kagent's controller and UI are installed (`k8s/kagent-values.yaml`); listing tools needs no LLM key.

![kagent's "MCP & tools" page: the three Petstore servers with their six tools](media/kagent-mcp-tools.png)

## Find your way around

```
petstore_before.py      before: 19 tools generated from petstore-openapi.json (Swagger Petstore 1.0.29)
petstore/               after: one module per bounded context
  discovery.py          Pet Discovery  → petstore-discovery
  sales.py              Pet Sales      → petstore-sales: the Pet aggregate, reservations, pickup calendar, policies
  handover.py           Pet Handover   → petstore-handover
  events.py             the events between the contexts (in memory)
  identity.py           the customer: from the OAuth token, or PETSTORE_CUSTOMER with AUTH=off
  app.py                mounts the three servers; modes serve, tools, demo
  numbers.py, demo.py   the numbers table and the scripted scenes
stage/                  Claude Code config for the live demo (OAuth, port 8000)
stage-before/, stage-after/   Claude Code configs for the clips and the evaluation
eval.py, eval/results/  the evaluation and all its runs
media/                  the clips, their tapes and per-take results
host_request.py, wire_trace.py   what the host sends to the model; what goes over the wire
tests/                  domain, contract and integration tests
canvases/               the MCP Product Canvas: the template and the one for the Pet Sales buyer
spikes/                 research notes (Keycloak, elicitation, kagent/kmcp): read, don't copy
k8s/, scripts/          kind + kagent, Keycloak, the local Petstore, resets
```

Contexts share only `events.py` and `identity.py`; there are no domain imports between contexts. The design behind it (domain story, EventStorming, context map, canvases) is in the talk.

### Tests

- **Domain** (`tests/test_sales*.py`, `test_discovery.py`, `test_handover.py`, `test_events.py`, `test_contexts.py`): the rules without MCP: aggregate, calendar and clock, events between contexts.
- **Contract** (`tests/test_contract*.py`, `test_numbers.py`, `test_app.py`): through MCP with FastMCP's in-memory client: tool list, parameters, output schemas, annotations, results, `next_step`, error texts, customer isolation.
- **Integration** (`uv run pytest -m integration`, `tests/integration/`): the running app over Streamable HTTP with Keycloak tokens, the before server against the local Petstore. They start what they need or skip with the reason.

`uv run ruff check . && uv run ruff format --check .` keeps the code clean.

## Learn more

- The talk: slides, canvases and the method at [lazzaretti.me/agentics26](https://lazzaretti.me/agentics26).
- [MCP specification 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28): tools, resources, authorization.
- [Bounded Context Canvas](https://github.com/ddd-crew/bounded-context-canvas) and [Context Mapping](https://github.com/ddd-crew/context-mapping) by ddd-crew.
- [SamplesDddMeetAi](https://github.com/Grinseteddy/SamplesDddMeetAi) by Annegret Junker: skills for EventStorming, context maps and Bounded Context Canvases.
- [MCP Product Canvas](https://miro.com/miroverse/mcp-product-canvas/) on Miroverse.

## License

None: © 2026 Fabrizio Lazzaretti, all rights reserved. You can read the code alongside the talk, but no license to reuse it is granted. `petstore-openapi.json` (Swagger Petstore, Apache 2.0) and the canvases have their own terms: [third-party/README.md](third-party/README.md).
