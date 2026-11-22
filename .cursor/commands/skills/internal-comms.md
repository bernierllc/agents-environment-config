---
name: "Internal Comms"
description: "A set of resources to help me write all kinds of internal communications, using the formats that my company likes to use. Claude should use this skill whenever asked to write some sort of internal communications (status reports, leadership updates, 3P updates, company newsletters, FAQs, incident reports, project updates, etc.)."
tags: "["skill", "internal-comms"]"
---

## When to use this skill
To write internal communications, use this skill for:
- 3P updates (Progress, Plans, Problems)
- Company newsletters
- FAQ responses
- Status reports
- Leadership updates
- Project updates
- Incident reports

## How to use this skill

To write any internal communication:

1. **Identify the communication type** from the request
2. **Load the appropriate guideline file** from the `examples/` directory:
    - `examples/3p-updates.md` - For Progress/Plans/Problems team updates
    - `examples/company-newsletter.md` - For company-wide newsletters
    - `examples/faq-answers.md` - For answering frequently asked questions
    - `examples/general-comms.md` - For anything else that doesn't explicitly match one of the above
3. **Follow the specific instructions** in that file for formatting, tone, and content gathering

If the communication type doesn't match any existing guideline, ask for clarification or more context about the desired format.

## Keywords
3P updates, company newsletter, company comms, weekly update, faqs, common questions, updates, internal comms

<!-- feedback-loop:begin -->
## Feedback

If the `feedback-loop` skill is installed, use it to improve this skill over time:

- When this skill's own instructions cause rework, a wrong default, a missed case or a needless
  pause, log it as it happens: subject `skill:internal-comms`, with the phase or section at fault and the
  concrete fix to these instructions.
- At the end of a run, check `skill:internal-comms`; if a review is due, make the feedback-loop offer.

If `feedback-loop` is not installed, ignore this section.
<!-- feedback-loop:end -->
