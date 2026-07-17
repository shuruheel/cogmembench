# Cognitive-substrate literature matrix

Verified: 2026-07-17. This matrix uses the linked paper, code, or dataset artifact—not a survey
name—as the unit of evidence. “No” means the released task does not make the capability a scored
requirement; it does not mean the associated system could never support it.

## Benchmark comparison

| Artifact | Verified release | Main scored capability | V,K belief | Decision-time evidence | Cascade repair + repaired reuse/action |
|---|---|---|---:|---:|---:|
| LongMemEval | [paper/code/data](https://github.com/xiaowu0162/LongMemEval) | Multi-session extraction, temporal reasoning, knowledge updates, abstention | No | Evidence locators, not decision receipts | No |
| MemoryAgentBench | [paper](https://arxiv.org/abs/2507.05257), [code/data](https://github.com/HUST-AI-HYZ/MemoryAgentBench) | Retrieval, test-time learning, long-range understanding, selective forgetting | No | No | Forgetting/update tasks, but no dependency cascade |
| MemoryArena | [paper/code/data portal](https://memoryarena.github.io/) | Interdependent multi-session memory-agent-environment tasks | No | No | Cross-session experience reuse and action, but no explicit cascade oracle |
| BEAM | [paper/code/data](https://github.com/mohammadtavakoli78/BEAM) | Long conversations to 10M tokens; ten abilities including contradiction, ordering, abstention | No | No | No |
| EvolMem | [paper](https://arxiv.org/abs/2601.03543), [release](https://github.com/shenye7436/EvolMem) | Cognitive dimensions across multi-session dialogue memory | No | No | No |
| EvoMemBench | [paper/code](https://github.com/DSAIL-Memory/EvoMemBench) | In/cross-episode and knowledge/execution memory; self-evolving perspective | No | No | Experience reuse and execution, without bitemporal cascade scoring |
| STALE | [paper](https://arxiv.org/abs/2605.06527) | Implicit invalidation, stale-premise resistance, downstream policy adaptation | No | No | Downstream adaptation, but no explicit derivation-DAG repair or provenance receipt |
| PM-Bench | [paper](https://arxiv.org/abs/2607.12385) | Delayed intentions in a simulated week | No | No | Prospective execution, not premise repair |
| EMemBench | [paper](https://arxiv.org/abs/2601.16690) | Trajectory-conditioned episodic questions in text/visual games | No | No | Interactive action, not cognitive-artifact repair |
| REMem | [paper](https://arxiv.org/abs/2602.13530), [code](https://github.com/intuit-ai-research/REMem) | Episodic recollection and multi-step reasoning | No | No | No explicit cascade invalidation |

## Closest systems and measurement approaches

| Artifact | Verified release | Relevant contribution | Boundary relative to CogMemBench |
|---|---|---|---|
| Zep/Graphiti | [paper](https://arxiv.org/abs/2501.13956), [code](https://github.com/getzep/graphiti) | Temporal KG, validity intervals, ingestion time, edge invalidation, hybrid retrieval; evaluated mainly on DMR/LongMemEval | Closest substrate semantics. The published evaluation does not jointly score decision-time receipts, dependency-DAG repair, and later action across controlled depth. |
| TOKI | [paper](https://arxiv.org/abs/2606.06240) | Bitemporal contradiction operators, isolation preconditions, provenance-preserving audit rows | Closest formal rival. It specifies write-time correctness and a small LoCoMo slice; it is not the cross-system, multi-family action/reuse benchmark proposed here. |
| Mem0 | [paper](https://arxiv.org/abs/2504.19413), [code/evals](https://github.com/mem0ai/mem0) | Extraction, consolidation, graph memory, retrieval quality, latency and token cost | Primarily conversational QA measurement; no V,K snapshot contract or dependency repair oracle. |
| MemGPT/Letta | [paper](https://arxiv.org/abs/2310.08560), [code](https://github.com/letta-ai/letta), [memory leaderboard](https://www.letta.com/blog/letta-leaderboard/) | Agent-managed memory tiers; read/write/update synthetic tasks | Strong active-memory control comparison, but no bitemporal audit/cascade benchmark. |
| A-MEM | [paper](https://arxiv.org/abs/2502.12110), [code](https://github.com/agiresearch/A-mem) | Zettelkasten-style note evolution and linking | Evaluates memory organization and QA, not decision-time provenance or recursive repair. |
| HippoRAG 2 | [code/paper links](https://github.com/osu-nlp-group/hipporag) | Hippocampal-indexing analogy, associative graph retrieval, sense-making and continual knowledge integration | Motivates a retrieval architecture; does not score substrate lifecycle correctness. CogMemBench therefore treats its cognitive analogy as related framing, not evidence that benchmark semantics are biologically faithful. |
| Cognee | [paper/code](https://github.com/topoteretes/cognee) | Graph/vector ingestion and reasoning; evaluated on knowledge-graph/LLM interface tasks | A system under test, not an existing benchmark for the five-way intersection. |
| Evidence tracing/provenance | [survey](https://arxiv.org/abs/2606.04990) | Claim/evidence/execution trace taxonomy and open benchmark gaps | Supports the receipt and lineage problem definition; does not itself supply a memory benchmark. |

## LoCoMo handling

LoCoMo’s [official release](https://github.com/snap-research/locomo) remains useful for
conversational recall and temporal QA comparisons. Its tiny ten-conversation corpus, heterogeneous
system-specific pipelines, and judge sensitivity make it unsuitable as CogMemBench’s publication
ground truth. A 2026 third-party audit reports answer-key and judge false-positive problems; that
audit is not yet a peer-reviewed replacement dataset, so this protocol records the dispute rather
than declaring the official artifact invalid. No primary CogMemBench endpoint is inherited from
LoCoMo.

## Novelty result

The search did not find a released benchmark that jointly requires all five of:

1. belief at valid time V under transaction-time knowledge K;
2. decision-time evidence support and exclusion of later evidence;
3. explicit downstream invalidation after a premise changes;
4. repaired conclusion reuse in later reasoning and environment action across controlled depth;
5. discrimination between faithful and post-hoc rationale receipts.

The claim is deliberately intersectional. CogMemBench does not claim novelty for temporal memory
(Zep/Graphiti, LongMemEval, STALE), bitemporal correctness (TOKI), action-based memory evaluation
(MemoryArena, EMemBench), recursive retrieval (REMem/HippoRAG), or provenance tracing in isolation.

## Re-check rule

Re-run this audit immediately before Gate 7. The field changed materially during implementation:
STALE, EvoMemBench, TOKI, and PM-Bench all appeared after the plan’s initial research framing.
Any new artifact covering the full intersection requires narrowing the novelty statement before
publication, not after results are known.
