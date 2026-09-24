# Research workflow

Pair each question with a development task through `modules.md`.

Research is relevant because model choice, temporal motion, conservative visibility and complete-path latency are unresolved and cannot be decided from the current code alone.

Start with an actionable question in `questions.md`. Define evidence and a falsifier before searching. Prefer original papers, official dataset/evaluator documentation, standards and official repositories. Search snippets are discovery only; inspect the underlying source. Cross-check material claims, record disagreement and uncertainty, then record sources in `evidence.md`, session findings in `research-log.md`, and significant claims in `claims.md`. Translate only validated findings into `implementation-impact.md`, a proposed ADR and an execution task. A decision changes only after its owner approves it. An experiment that contradicts a prior claim reopens its question.

Use FACT, ASSUMPTION, HYPOTHESIS, MEASURED RESULT, LITERATURE-BACKED CLAIM, DESIGN DECISION and UNKNOWN for narrative statements. The claim registry has its own category set: REQUIREMENT, OBSERVATION, HYPOTHESIS, MEASURED RESULT, LITERATURE FACT and ASSUMPTION. Mark failed or unrun validation NOT VERIFIED. Do not quote historical prototype evidence as Drishti performance.

Flow: question -> primary sources -> evidence -> claim -> decision -> task -> implementation -> test/experiment -> revised evidence. Inspect this folder before repeating research.
