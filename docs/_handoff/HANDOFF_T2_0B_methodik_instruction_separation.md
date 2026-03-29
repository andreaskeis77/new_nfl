# HANDOFF T2.0B Methodik Instruction Separation

Status: delivered and ready for local validation

Scope:
- codify the separation between **Einordnung** and **Aktion** in repo-facing
  method documents
- reduce operator ambiguity in future ChatGPT deliverables
- keep the bolt docs-only

Why this bolt exists:
- recent tranches showed that mixed explanation and action text creates
  unnecessary operator friction
- Andreas should not have to infer which part of a response is context and
  which part is an executable instruction
- this rule should live in repo documentation, not only in chat memory

What changes:
- `docs/DELIVERY_PROTOCOL.md` now requires a clear response structure with
  `Einordnung` and `Aktion`
- `docs/WORKING_AGREEMENT.md` now makes that separation part of the operational
  instruction format and anti-pattern list

Preferred next step after local validation:
- continue with the next small technical T2 bolt on top of the now clarified
  delivery and instruction conventions
