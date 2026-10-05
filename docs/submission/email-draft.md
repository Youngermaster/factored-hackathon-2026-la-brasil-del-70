# Submission email (draft, not sent)

A draft for the human to send from the team's own account after the checklist in [SUBMISSION.md](SUBMISSION.md) is done. No session sends it. Replace every angle-bracket placeholder; the numbers below quote [results.md](../evaluation/results.md) and must not change unless the evaluation is rerun and republished.

To: `hackathon.admin@factored.ai`
Subject: Factored AI & Data Hackathon 2026 submission: La Brasil del 70

```text
Hello Factored team,

We are submitting La Brasil del 70's project for the Factored AI & Data Hackathon 2026.

Repository (public): https://github.com/Youngermaster/factored-hackathon-2026-la-brasil-del-70
Deployed demo: https://la-brasil-del-70.westus2.cloudapp.azure.com   (demo mode: pick a profile on the sign-in page; the one-time code is shown on screen, and /demo lists the messages to try)
Slides (PDF, the six main slides): <link, or attached>
Video pitch (under 3:00): <link>

What it is: an AI-first customer-service system for a synthetic Latin American bank. Customers chat in Spanish or Portuguese about four workflows on one engine: account and payment inquiries, card support with a protective card block, transaction-dispute intake and status, and credit-product information with an indicative result from a clearly labeled synthetic eligibility service. The language model understands; deterministic code, driven by a versioned policy pack, decides; every write is confirmed, stepped up, and read back before it is reported; and every turn leaves an execution record. There are no lending decisions and no money movement.

Evaluation (simulated, offline, on the hosted model azure/gpt-4.1-mini; 304 held-out cases in the four workflows): safe automated resolution 185/304 (61%, 95% interval 55 to 66) against 141/304 for a menu and rules baseline and 69/304 for a naive LLM agent, with 1/304 graded unsafe outcomes for the proposed system (a confirmed, step-up-verified second write the scenario did not expect) against 92/304 for the naive agent. Per workflow, account inquiry and card support tie the baseline. The README and docs/evaluation/results.md report every workflow separately, with denominators, and LIMITATIONS.md states what we cannot claim.

Where to start: README.md, then docs/submission/brief-traceability.md, which maps every requirement of the brief to code, tests, and evidence.

Team: Juan Young (technical lead), Miguel Correa, David Fonseca, Julián Valencia.

Thank you,
<name>
La Brasil del 70
```
