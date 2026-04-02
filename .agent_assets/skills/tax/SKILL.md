---
name: tax
description: Extract structured Chinese tax calculation requests for deterministic processing.
---

# Tax

Use this skill when the user wants to calculate a tax amount.

## Responsibilities

- Identify whether the user asks for VAT or corporate income tax
- Identify whether the taxpayer is a small-scale VAT taxpayer or a small low-profit enterprise
- Extract the calculation amount and whether it is tax-inclusive
- Call the `calculate_tax` tool with the extracted arguments

## Tool Guidance

- Use `calculate_tax`, do not directly compute the final tax only in free text
- Provide:
  - `tax_type`:
    - `vat`
    - `corporate_income_tax`
  - `taxpayer_type`:
    - `small_scale_vat_taxpayer`
    - `small_low_profit_enterprise`
  - `amount`
  - `includes_tax`
  - `description`

## Rules

- `amount` must be numeric and positive
- Set `includes_tax=true` only when the user explicitly says the amount is tax-inclusive
- If the user does not explicitly mention tax-inclusive pricing, default `includes_tax=false`
- If the user is not asking for tax calculation, do not force a tax result
- After the tool returns, summarize the result in concise Chinese
