# memory.rules.md
- Always call get_rules and get_governance_policies before injecting any rule or policy into a prompt.
- Treat only {decision, rule, plan, review} as auto-injectable; others require explicit confirmation.
- Keep retrieval budgets: maxTokensPerItem<=300, totalTokenBudget<=1200 unless task explicitly raises limits.
- After each significant change, call save_diff with a concise, meaningful description.
- On errors, log_error and reference the eventual fix in a follow-up decision memory.
