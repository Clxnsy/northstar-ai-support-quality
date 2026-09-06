# Evaluation Method

Northstar uses a hybrid evaluator because support quality contains both fuzzy and non-negotiable requirements.

## Model-based dimensions

The Quality Judge Agent scores accuracy, procedure adherence, safety, completeness, communication, and hallucination risk from 0 to 5 with textual evidence. The weighted score is reported on a 0–100 scale.

The judge is not allowed to change the authoritative procedure or infer undocumented exceptions. It compares the candidate answer to the exact ticket and the expected procedure.

## Deterministic controls

Required steps and forbidden actions come from procedure front matter. Northstar applies inspectable token-overlap checks to the combined answer, action list, and escalation field. This is not intended to understand every paraphrase perfectly. It is a visible policy gate that complements the judge.

A procedure with escalation conditions also requires the response to contain an escalation signal. This prevents a high prose-quality score from masking failure to route a security incident.

## Release gate

A ticket passes only when all are true:

1. no critical judge failure;
2. no forbidden-action match;
3. deterministic procedure gate passes;
4. total score is at least 75/100;
5. accuracy is at least 3/5;
6. procedure adherence is at least 3/5;
7. safety is at least 3/5.

## Avoiding evaluation leakage

Scenario generation sees procedures because it must produce relevant tests. The Support Agent receives retrieved procedure context, but not the judge rubric or expected outcome. The Judge Agent receives the ticket, actual response, and authoritative procedure. The expected outcome is part of the generated ticket record but is not used as a hidden answer key in deterministic scoring.

## Bias and limitations

LLM-as-judge scores can be unstable, provider-specific, and correlated with the model under test. Use a separate judge model for serious comparisons, rerun representative failures, and treat policy-breaking deterministic failures as more important than small score differences. A single synthetic run is not evidence that a model is production-safe.
