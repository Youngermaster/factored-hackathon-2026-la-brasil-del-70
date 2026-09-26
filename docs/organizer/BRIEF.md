# Organizer brief (summary)

This file summarizes the Factored AI & Data Hackathon 2026 problem statement and kickoff deck. The original PDFs stay outside git (the data dictionary PDF contains credentials). Where this summary and the originals differ, the originals win.

## Timeline

| Date | Milestone |
|---|---|
| 2026-09-25 | Challenge launch |
| 2026-10-05 | Submissions close |
| 2026-10-15 | Finalists announced |
| 2026-10-16 | Award ceremony |

Prizes: 6,000 / 3,000 / 1,000 USD, plus interviews with the Factored engineering and talent team.

## The challenge

Build a working AI-first customer-service system for a real-world banking environment. The kickoff deck puts it bluntly: build a customer-service system, not a chatbot. The system must:

- understand complex customer interactions,
- use data and tools securely,
- complete appropriate service workflows,
- involve human agents when needed.

Choose one focused workflow and demonstrate it end to end. Examples:

- account or payment inquiries,
- card-service support,
- transaction-dispute intake,
- credit-product information and eligibility.

These are examples, not separate tracks. Depth, demonstrated behavior, and engineering judgment determine the score. Implementing more workflows does not earn a bonus.

**Required demonstration cases:**
- a normal resolution path,
- an ambiguous or unsupported request,
- a case requiring human intervention.

**Languages:** demonstrate interactions in Spanish and Portuguese, and report limitations in the supplied data or language coverage.

**Expected behavior:** Understand, Decide, Act, Verify, Escalate. The key idea from the deck is that AI should not be autonomous just because it can be.

**Minimum requirements:**
- Maintain conversational context.
- Clarify ambiguous requests.
- Retrieve trusted information.
- Use tools securely.
- Execute appropriate workflows.
- Verify that actions actually happened.
- Know when not to act.
- Hand off to a human when needed.

**The three expected outcomes by case type:**

| Case | Expected handling |
|---|---|
| Normal | Policy-compliant automated resolution, verified account queries, authorized self-service transactions |
| Ambiguous or unsupported | Clarifying questions, or safe policy abstention for missing parameters or unsupported requests |
| Human-required | Structured handoff that transfers verified facts and open questions without dumping raw transcripts |

## What the solution should demonstrate

1. **A problem supported by data.** Analyze contact reasons, demand patterns, data quality, and operational constraints. Use this evidence to prioritize the workflow and define the intended customer and business outcomes.
2. **A functioning AI system.**
   - Maintain relevant context and clarify ambiguity.
   - Ground factual responses in permitted account, transaction, or policy information.
   - Use tools when they serve the workflow.
   - Report only actions whose outcomes the system has verified.
3. **Controlled automation.**
   - Define which requests the system can answer, which actions require confirmation, and when it must abstain or transfer.
   - Enforce permissions and policy outside model-generated prose.
   - Give the human agent the request, verified facts, actions taken, supporting evidence, and unresolved questions.
4. **Sound data and ML practice.**
   - Build repeatable data preparation with contracts, quality checks, lineage, and an update or freshness policy.
   - Evaluate at least one learned component against an appropriate baseline.
   - Use valid labels or relevance judgments and prevent leakage.
   - Justify representations, metrics, thresholds, and evaluation splits.
5. **Measured quality and failure handling.**
   - Evaluate on held-out cases, including: incorrect or missing data, expired sessions, unauthorized access attempts, prompt injection, tool failures, and multilingual ambiguity.
   - Report successful outcomes, unsafe outcomes, handoff behavior, latency, and cost, with sample sizes and limitations.
6. **A credible route to operation.**
   - Demonstrate tracing, bounded retries, safe fallback, and a reproducible setup.
   - Explain capacity limits, monitoring, access controls, data retention, and the remaining deployment work.
   - Base explanations on sources, policy rules, and execution records. Hidden model chain-of-thought is not an audit artifact.

## Architecture freedom

Conventional ML, pretrained language models, retrieval, deterministic workflows, agents, or a justified combination are all allowed. None of the following is mandatory:

- training a new model,
- multiple agents,
- a tool-count target,
- streaming,
- demand forecasting,
- a dashboard.

Every team is assessed on data engineering and AI/ML rigor. A pretrained or retrieval-based solution shows these through:

- component selection,
- relevance or intent labels,
- representations,
- leakage prevention,
- held-out evaluation,
- error analysis.

Use batch, incremental, or streaming processing according to the supplied inputs and the workflow's latency and freshness needs. Incremental file delivery does not by itself require streaming. If only static data is supplied, demonstrate update correctness with a clearly labeled test fixture.

## Data and execution boundaries

- Use only organizer-approved data and permitted external resources. Identify which inputs are real, de-identified, synthetic, or team-generated. Follow the published data-use terms.
- Do not include private customer records, credentials, or restricted data in public submissions or external model requests.
- Sandbox services and mock banking tools are acceptable when their contracts and limitations are documented.
- Demonstrate authentication with a trusted test session or identity service. A national ID or customer number alone does not prove identity.
- Enforce access to each customer's records, and action permissions, in the service or tool layer.
- **Credit workflows:** separate conversation handling, predictive risk estimates, and eligibility policy. Use approved rules or a clearly labeled synthetic policy service. The conversational model must not invent eligibility rules or approve credit. Show explanations, uncertainty, and review paths.
- No live lending decisions or movement of money is required or authorized.

## Evaluation evidence

- Compare the baseline and the proposed system on the same held-out workload.
- Report the number and mix of cases, label quality, model and prompt versions, and repeated-run variability.
- Include failures in the results.
- If a model judges answers, document its rubric and validate a sample against human or deterministic judgments.

**Outcome definitions to distinguish:**

- **Safe automated resolution:** an eligible case reaches the correct, policy-compliant outcome without human intervention. Report the rate over all in-scope test cases, plus the share of cases on which automation was attempted.
- **Containment:** a case ends without transfer. Containment alone does not demonstrate that the problem was solved.
- **Escalation quality:** cases that require escalation are transferred correctly and include useful handoff context. Report both missed and unnecessary transfers where labels permit.
- **Unsafe outcomes:** unauthorized disclosures or actions, or materially incorrect outcomes, reported with counts and denominators. Zero observed failures in a small test set does not establish zero risk.
- **Operating efficiency:** end-to-end p50/p95 latency, and cost per attempted case and per successful automated resolution. State the workload, sample size, and cost assumptions. Use "not defined" when there are no successful resolutions.

Compare service outcomes by language and by authorized customer segments, state small-sample limitations, and investigate disparities. Label offline measurements, simulations, and projected business savings separately. Do not describe an offline comparison as a measured production improvement.

## Kickoff deck emphasis

**Technical rigor:**
- data contracts with strict schema enforcement,
- deterministic, reproducible preparation,
- grounded relevance judgments and ground truth,
- strict train/eval isolation,
- realistic held-out splits,
- a learned component benchmarked against a baseline.

**Key metrics:** safe automated resolution, unsafe outcomes, cost efficiency.

**Technical deliverables:**

| Deliverable | What it means |
|---|---|
| Data-backed baseline | Justify workflow selection using reproducible logs |
| Grounded AI core | Ground every response in verified records |
| Controlled automation | Enforce action permissions beyond model prompts |
| Data and ML discipline | Repeatable pipelines with strict schema contracts |
| Measured failures | Stress-test held-out cases against injection |
| Route to operation | Deterministic setup with audit execution logs |

**Suggested tasks by discipline:**

| Discipline | Suggested tasks |
|---|---|
| AI | Production backend and structured JSON handoffs |
| ML | LLM/RAG orchestration and prompt-injection defense |
| Data engineering | Strong ETL/ELT pipeline and customer record isolation |
| Data analysis | Demand patterns and cost-per-resolution ROI |

**Make it a real service:**

| Area | Expectations |
|---|---|
| Observability | Tracing, execution records, monitoring |
| Reliability | Bounded retries, safe fallback, tool-failure handling |
| Security | Authentication, access controls, data retention |
| Reproducibility | Setup instructions, versioning, repeatable evaluation |

Be honest about what is missing: capacity limits, data limitations, language coverage, deployment work, and remaining risks.

**Evaluation criteria (deck).** First and foremost, the solution should work. Judged areas:
- overall project rationale and documentation,
- AI engineering (backend, frontend, deployment),
- data analytics (data quality and relevant insights),
- data engineering (extraction and transformation),
- machine learning (model selection, optimization, implementation, tracking).

**Final takeaway from the deck:** build something that works, prove that it works, and know when it should not act. Then show what it would take to make it real.

## Submission requirements

1. A public GitHub repository named `factored-hackathon-2026-[team name]`.
2. A link to where the tool is deployed.
3. A 4 to 6 slide presentation about the tool.
4. A short, mandatory video pitch demonstrating the working solution and explaining the core architectural decisions.

Send everything to `hackathon.admin@factored.ai`. Any language or tools may be used. Resources mentioned by the organizers: Microsoft Azure, Snowflake, AWS, Databricks.
