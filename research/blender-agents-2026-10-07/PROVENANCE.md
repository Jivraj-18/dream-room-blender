# Research artifacts and boundaries

The active constraint is **no payments**. All operating proposals use local models and existing hardware. Paid-provider rates and published paid experiments are reference evidence only.

- `REPORT.md`: synthesis, prior-work comparison, provisional capability boundaries, free architecture and evaluation proposal.
- `sources.csv`: 42 reviewed sources, evidence types, scope, caveats and snapshot paths where available.
- `rates.csv`: five dated **reference-only** API rate rows. Not a deployment configuration or spending authorization.
- `pilot_tasks.csv`: twelve proposed task specifications. No fixtures or results have been generated.
- `event-template.json`: unexecuted telemetry template. Every unknown usage/result field is null; zero payment budget is a policy, not a fabricated measurement.
- `repo-pins.json`: commits observed during repository review. They were not installed or executed.
- `source-manifest.json`: hashes and sizes of downloaded snapshots. A hash verifies snapshot integrity, not truth of a source's claim.
- `sources/`: selected README/code snapshots, public Reddit responses and retrieved pages. Repository source snapshots are research references, not part of an implemented harness.

Public research used `rdt search/read`, authenticated `gh` read/search calls, official documentation, paper HTML and direct `curl` fetching. No Reddit/GitHub messages were posted. No paid-model inference or mesh-generation requests were issued.

Reddit queries included Blender MCP, failure/limitation/topology terms, and vision-feedback/self-correction terms. Broad searches returned unrelated material too. Only specifically cited relevant posts support the report; the search snapshots are not a representative dataset. Selected threads were read with bounded comment counts, so this is not exhaustive comment coverage. Demo videos and submitted scene files were not audited.

The photo-benchmark article had sixteen models when fetched, although its Reddit announcement title said fourteen. New native-CLI entries used a later brief; API-equivalent subscription estimates differ from charged API costs. The report preserves those distinctions rather than treating the figures as a controlled harness ranking.

Local probes found Claude Code 2.1.289, Codex 0.160.1, Antigravity CLI 1.0.16, Ollama 0.18.2 and approximately 16 GB RAM. Ollama listed only `neural-chat:latest`. NVIDIA-SMI could not communicate with the driver. Blender was initially absent from PATH; the user subsequently requested installation. Official Blender 5.2.2 LTS was installed in `.tools/blender/` with a workspace launcher, its official checksum was verified, and creation/save/CPU Cycles render/reopen tests passed. This is separate from running the proposed agent benchmark.

Documentation establishes local-model integration routes, but their actual compatibility with a chosen coder/vision model has not been tested. No vision checkpoint was downloaded. Any benchmark would need a fresh Blender, endpoint, image and tool-call preflight.

Telemetry normalization rules:

1. Preserve raw usage fields, request IDs, endpoint identity and version.
2. Record either final request totals or their increments. Do not sum streaming cumulative updates repeatedly.
3. Treat cache-read/write and reasoning fields as subsets or disjoint categories according to each adapter's actual semantics.
4. Missing usage, cache or thinking fields are unknown, not zero.
5. Separate measured resource usage, metered charges, API-equivalent estimates and explicit labor/energy assumptions.
6. Count local model and Blender work even though no service payment is made.
7. Keep all failed attempts and rejected candidates in campaign accounting.

This is a targeted review and proposed protocol, not a systematic novelty review or an executed modeling study.

Publication note: Raw third-party research snapshots remain in the original workspace. The source index, review notes and snapshot hashes are published; local_snapshot paths in sources.csv refer to that original workspace.
