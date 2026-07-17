# External Adapter Kit

Updated: 2026-07-16

The adapter kit maps the canonical cognitive-v2 operation stream into records persisted inside
an external substrate. It is a walking-skeleton portability mechanism, not a claim that every
vendor natively implements the benchmark ontology.

## Evidence boundary

Every capability manifest declares one evidence mode:

- `native`: the substrate directly exposes the tested semantics.
- `mapped`: the adapter persists a reversible canonical representation inside the substrate.
- `sidecar`: required evidence exists only in harness memory or a separate harness database.

Sidecar evidence is inadmissible for substrate scoring. The mapped adapters reconstruct
snapshots and audit receipts exclusively from records read back from the external service. Local
caches are not part of the evaluation path.

Every run also declares `operating_mode`. `matched-budget` uses the protocol's fixed item and
read-context ceilings. `natural` uses adapter-specific settings frozen before execution and
reviewed through the vendor window; the chosen values are still explicit in the run manifest.
Natural and matched-budget rows are separate analysis cells and must never be silently pooled.

## Journal mapping

Agent-directed and oracle operations are stored as an immutable operation journal. Commit,
revision, relation, retrieval, and session-boundary records include the namespace and logical
clock. Snapshot and audit export replay records fetched from the service. Automatic observations
use the service's ordinary record path and retain the public event locator in remote metadata.

This gives all three systems a common, testable portability floor while keeping vendor-native
temporal extraction, graph relations, and lifecycle automation as separately reported features.

## Supported walking skeletons

### MindGraph

Uses public `/node`, `/reality/capture`, `/search`, `/nodes`, and `/nodes/delete` endpoints.
Reset is scoped by a trial-specific `agent_id`; the adapter never calls global `/clear`.

### Mem0 OSS

Uses the official self-hosted REST surface: `POST/GET/DELETE /memories` and `POST /search`.
Canonical journal writes set `infer=false`; automatic observations set `infer=true`. The trial
namespace is the Mem0 `user_id`.

### Zep Cloud

Uses Graph API v2 standalone graphs, verbatim episodes, episode-scoped graph search, recent
episode listing, and processed-state polling. Each trial owns a dedicated graph that is deleted
and recreated on reset.

### Cognee

Uses Cognee REST API v1 datasets, multipart data ingestion, blocking cognify, raw dataset-data
reads, and `CHUNKS_LEXICAL` search. Each trial owns a dedicated dataset. Exact canonical records
are wrapped inside the ingested text so snapshots and audits can be reconstructed from Cognee,
without a harness sidecar.

## Required audit

`validate-adapter-v2 --portability-audit` reports each capability as `present_correct`,
`present_incorrect`, `capability_absent`, or `infrastructure_failure`. It verifies idempotency,
bounded retrieval, dual-axis reconstruction, audit filtering, explicit usage fidelity, scoped
reset, and namespace isolation.

Official API references used for this mapping:

- Mem0 OSS REST API: https://docs.mem0.ai/open-source/features/rest-api
- Zep graph add/search/episodes: https://help.getzep.com/sdk-reference/graph/add-data,
  https://help.getzep.com/sdk-reference/graph/search, and
  https://help.getzep.com/sdk-reference/graph/episode/get-graph-episodes
- Graphiti OSS/MCP reference: https://github.com/getzep/graphiti
- Cognee REST API lifecycle: https://docs.cognee.ai/api-reference/introduction,
  https://docs.cognee.ai/cognee-cloud/functionality/dataset-management, and
  https://docs.cognee.ai/api-reference/search/search
