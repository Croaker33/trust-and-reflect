# Trust and Reflect — prompts and rule lists

Supplementary artifacts for

> **Trust and Reflect: Process Critique and Confidence Auditing for Web
> Search Agents**, NLPIR 2026.

Everything here is the text and the constants the reported runs actually
consumed. The framework is prompt-only and training-free, so these two
directories are the whole of what a reader needs beyond the paper.

## `prompt/prompts.py`

| Constant | Module | Paper |
|---|---|---|
| `THOUGHT_PROMPT_CN`, `THOUGHT_FEW_SHOT_1_CN`, `THOUGHT_FEW_SHOT_3_CN` | Planning Agent | Sect. 3.2 |
| `SEARCH_TOOL_PROMPT_CN`, `SEARCH_TOOL_FEW_SHOT_1_CN`, `SEARCH_TOOL_FEW_SHOT_3_CN` | Searcher — query formulation | Sect. 3.1 |
| `SELECT_TOOL_PROMPT_CN`, `SELECT_TOOL_FEW_SHOT_1_CN`, `SELECT_TOOL_FEW_SHOT_3_CN` | Searcher — page selection | Sect. 3.1 |
| `SEARCHER_THOUGHT_PROMPT_CN`, `SEARCHER_THOUGHT_FEW_SHOT_1_CN`, `SEARCHER_THOUGHT_FEW_SHOT_3_CN` | Searcher — reasoning step | Sect. 3.1 |
| `SUMMARY_PROMPT_CN` | Final answer synthesis | Sect. 3.1 |
| `CRITIC_PROMPT_CN`, `CRITIC_FEW_SHOT_CN` | Critic Agent | Sect. 3.3 |
| `CONFIDENCE_PROMPT_CN`, `CONFIDENCE_FEW_SHOT_CN` | Confidence Analyzer, LLM layer | Sect. 3.4 |
| `ANSWER_DECOMPOSE_PROMPT`, `RESPONSE_DECOMPOSE_PROMPT` | Evaluation harness | Sect. 4.1 |

Each module's output schema is stated inside its own prompt, so the JSON
schemas are released with the templates rather than separately.

## `rules/`

The deterministic layer of the Confidence Analyzer (Sect. 3.4). Both files
carry the constants plus the scoring functions that read them, so a rule
report can be reproduced without re-deriving it from the paper's prose.

- **`domain_authority.py`** — the *source reliability* sub-score: two
  authoritative lists (domain suffixes, institutional keywords), the
  weak-source list, the tier-to-reliability map and the domain-diversity
  bonus.
- **`risk_flags.py`** — the conflict and uncertainty lexicons, the trigger
  condition of each of the seven risk flags, the retry-critical subset, both
  sets of risk-aware caps, the four sub-score weights, the rule/LLM fusion
  weights and the reporting and retry thresholds.

The keyword lists are curated for the Chinese-language web of the Web24
collection window. They are an implementation detail, not part of the
method: replacing them changes the rule layer's inputs but not the
architecture. Sect. 5 names their semi-automatic maintenance as future work.

## License

MIT — see [LICENSE](LICENSE).
