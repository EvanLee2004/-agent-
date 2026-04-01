# IFRS Skill for AI Coding Agents

A comprehensive IFRS (International Financial Reporting Standards) skill that gives AI agents expert-level knowledge of all current IFRS and IAS standards. Works with Claude Code, Codex CLI, Gemini CLI, Cursor, and any agent supporting the [Agent Skills](https://agentskills.io) specification.

## What It Does

- **Accounting Guidance** — Answer any IFRS question with paragraph-level citations
- **Compliance & Audit Support** — Generate disclosure checklists, gap analyses, and audit memos
- **GAAP-to-IFRS Transition** — Framework-agnostic transition planning with IFRS 1 procedures
- **Audience Adaptation** — Adjusts depth for professionals (with citations) or learners (plain language)
- **Currency Verification** — Automatically checks web for latest effective dates and amendments

## Coverage

| Content | Details |
|---------|---------|
| **Standards** | All 40 active standards (IFRS 1-17, IAS 1-41) with scope, core principles, key rules, disclosure requirements, common pitfalls, and cross-references |
| **Workflows** | 7 step-by-step procedures: Revenue (IFRS 15), Leases (IFRS 16), Impairment (IAS 36), Financial Instruments (IFRS 9), First-Time Adoption (IFRS 1), Deferred Tax (IAS 12), Business Combinations (IFRS 3) |
| **Templates** | 5 structured formats: Disclosure checklist, Gap analysis, Audit memo, Management representation letter, Accounting policy summary |
| **Transition** | 10 common difference areas, 3-phase project plan, IFRS 1 exemption framework, IT/system guidance, deferred tax implications |
| **Interpretations** | Key IFRICs referenced in context (IFRIC 12, 21, 22, 23, and others) |

## Installation

### Claude Code
```bash
# Clone to your skills directory
git clone https://github.com/ramyatrouny/ifrs-skill.git ~/.claude/skills/ifrs

# Or copy manually
cp -r ifrs/ ~/.claude/skills/ifrs/
```

### Codex CLI
```bash
git clone https://github.com/ramyatrouny/ifrs-skill.git ~/.codex/skills/ifrs
```

### Other Agents
Copy the `ifrs/` folder to your agent's skills directory. The skill follows the [agentskills.io specification](https://agentskills.io/specification).

## File Structure

```
ifrs/
  SKILL.md                  # Entry point (lightweight hub, ~300 words)
  standards-reference.md    # All 40 IFRS/IAS standards (207KB)
  workflows.md              # 7 step-by-step procedures (78KB)
  compliance-templates.md   # 5 structured output templates (37KB)
  transition-guide.md       # GAAP-to-IFRS transition guide (37KB)
```

## How It Works

1. User asks an IFRS question
2. `SKILL.md` loads and detects: task type, audience level, output format
3. Agent reads the relevant supporting file(s) on demand
4. Response adapts: professional (with citations) or learner (plain language)

## Example Queries

- "How should we recognize revenue for a bundled software deal under IFRS 15?"
- "Run a disclosure completeness check for our IFRS 16 lease notes"
- "We're transitioning from local GAAP to IFRS — walk me through the process"
- "Explain the expected credit loss model to someone new to IFRS 9"
- "Prepare an audit memo for this business combination under IFRS 3"

## Contributing

Contributions are welcome! Areas where help is needed:
- Additional workflows (IFRS 17 Insurance, IFRS 2 Share-based Payment)
- Jurisdiction-specific adoption guides
- Additional compliance templates
- Translations

## License

MIT

## Disclaimer

This skill provides technical guidance based on IFRS as issued by the IASB. It does not replace professional judgment. Consult qualified professionals for specific accounting decisions. Always refer to the full text of relevant standards and any jurisdiction-specific modifications.
