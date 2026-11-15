# Deployment architecture

November 14, 2026. The persistent VM runtime is merged. The swarm runner and
past.dev adapter are in PR #3 and have been deployed to an isolated VM directory
for live validation. Each run has its own artifacts and memory scope.

```mermaid
flowchart LR
    subgraph LOCAL["LOCAL MACHINE"]
        direction TB
        CONTROL["Deployment / launch scripts"]
        EXPORT["Retrieved evidence + reports"]
    end
    subgraph AZURE["AZURE WINDOWS VM · chemsep-01"]
        direction TB
        SCHEDULE["Windows Scheduled Task"]
        RUNNER["Python runner<br/>Single agent OR 3-agent swarm"]
        ENV["Design environment + checker<br/>Shared SolveService + cache"]
        CHEMSEP["ChemSep executable<br/>One solver worker"]
        MEMORY["past.dev adapter<br/>Publish · await ingestion · retrieve"]
        FILES["Run artifacts<br/>Designs · results · timing · usage"]
        SCHEDULE --> RUNNER
        RUNNER --> ENV --> CHEMSEP
        RUNNER --> MEMORY
        RUNNER --> FILES
    end
    subgraph EXTERNAL["EXTERNAL SERVICES"]
        direction TB
        MODELS["OpenAI Responses API"]
        PAST["Hosted past.dev API<br/>Separate audience per run"]
    end
    CONTROL -->|"Azure Run Command<br/>deploy / launch / inspect"| SCHEDULE
    FILES -->|"Explicit evidence export"| EXPORT
    RUNNER -->|"HTTPS"| MODELS
    MEMORY -->|"HTTPS"| PAST
```

The single-agent runner is `scripts/run_vm_agent.py`. The swarm runner is
`scripts/run_swarm.py`, using `sepdesign/swarm.py` and
`sepdesign/swarm_memory.py`. Both use `agents/llm_agent.py` for model calls.
The swarm creates separate design environments and ledgers for each agent,
sharing one simulator service/cache. Model proposals run concurrently; all
submissions are evaluated and published before the next round retrieves memory.
There is no coordinator model.

Credentials are read from a restricted VM env file. Only SYSTEM and
Administrators have file access. Source bundles and exported evidence exclude
credentials. past.dev uses TLS certificate verification with Windows native trust.

The older Luna/Sol pilots run the model loop locally and invoke Azure for each
submission. The persistent runtime removes that per-submission transport;
Azure commands are still used for setup and evidence retrieval.

Existing pilot HTML includes interactive flowsheet replay. Persistent and swarm
artifacts retain evidence but still need integration with the same report format.
See `results/azure-runtime/sol-five-call/` for the completed real five-call timing
test. Live swarm evidence is recorded separately; deployment alone is not success.
