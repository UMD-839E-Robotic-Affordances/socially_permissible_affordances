# Themes for the model's "why" answers

Note: `dataset_with_whys.json` was built from the dataset as it was before the review was finished (120 scenarios), so it no longer matches `dataset.json` (143 scenarios). Regenerate it after a new `--why` run.

`dataset_with_whys.json` (repo root, next to `dataset.json`) is a clone of the dataset with a `whys` entry per scenario
and prompt type. Each entry has the model's follow-up reply (`factors`, `reason`) plus the labels below. The whys come from
`rq1/results/deprecated/rq1_results_claude-haiku-5-5_low_877e10d.json` (Haiku 5.5, effort low, `--why`).

The labels were assigned by hand (by Claude, reading each reason). Each reason was labeled from its text, with the
prompt type visible but without the gold label, the model's answer field or correctness shown, and all labels were set
before any analysis. Some scenarios were already familiar from earlier in the session, so the labeling is not perfectly
blind. They are one rater's judgment, not a validated coding scheme; no second rater has checked them.

Two independent systems. Each reason gets one value from each.

## 1. Theme: what kind of consideration the verdict rests on (one primary, optional `also`)

The primary theme is the consideration the reason ties its verdict to most directly. `also` lists other themes the reason
clearly uses.

| Theme | The reason argues from... | Typical wording |
|---|---|---|
| `outcome` | what the action would cause: harm, damage, loss, risk, waste, or disruption to someone | "risks breaking", "would disrupt", "wastes time" |
| `entitlement` | who may decide: ownership, consent, authorization, explicit instructions, a person's private sphere or wishes | "without their permission", "explicitly asked" |
| `convention` | rules and norms: laws, posted or written rules, licenses, etiquette, fairness, honesty, cultural or setting expectations | "violates the posted rule", "unwritten norm" |
| `fit` | means and ends: whether the tool, method or agent suits the task (intended use, capability, available alternative, efficiency, timing of steps) | "wrong tool", "a better option is available" |
| `no_objection` | the absence of a problem: an ordinary use, a legitimate goal, nothing at stake; used to justify acceptance | "no ownership conflict", "reasonable, low-impact use" |

Decision rules: harm to a person's interests counts as `outcome`; the person's say over their things counts as
`entitlement`. Sentimental loss counts as `outcome`. An impersonal rule counts as `convention`; a person's instruction counts
as `entitlement`. Tie-breaker: the clause the verdict is explicitly tied to.

## 2. Framing: how the reasoning is structured

| Framing | Meaning |
|---|---|
| `one_sided` | gives reasons only for its verdict |
| `weighed` | names a consideration that cuts the other way ("even though", "regardless of", "though") and says why it does not prevail |
| `undetermined` | says the answer depends on a missing fact or cannot be determined from the scenario |

## Counts (570 whys, 114 scenarios x 5 prompt types)

Themes: outcome 195, entitlement 153, convention 107, fit 78, no_objection 37. Framing: one_sided 443, weighed 92,
undetermined 35. Whys with an `also` theme: 353.

Caveats: the five prompt types give near-duplicate reasons for the same scenario, so the 570 labels are not independent
(114 scenarios is the real sample size); the themes depend partly on the scenario, not only on the model's reasoning.
