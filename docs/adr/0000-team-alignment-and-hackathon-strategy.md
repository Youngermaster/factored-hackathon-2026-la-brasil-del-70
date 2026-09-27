# ADR 0000: Agentic Banking Architecture, Core Tech Stack & Team Alignment

* **Status:** Proposed
* **Date:** 2026-09-27
* **Deciders:**
  * Miguel (Project Manager / Developer)
  * Young (Technical Lead / Developer)
  * David (Fonseca) (Developer)
  * Julián (Developer)

---

## 1. Context & Problem Statement

The Factored 2026 Hackathon challenge requires building an end-to-end banking solution covering four core functional domains: **Accounts & Payments**, **Credit Cards**, **Claims & Disputes**, and **Product Information**.

The competition organizers explicitly noted during kickoff that basic, prompt-only chatbots will not meet evaluation standards. The solution must operate as a production-ready agentic system capable of executing backend tools, querying structured relational data, verifying user intents, logging decision paths, and providing human-in-the-loop escalation paths for complex or high-risk cases.

---

## 2. Team Ownership & Responsibilities

To maintain high development velocity across human developers and automated coding agents during the 10-day build window, team roles are defined as follows:

* **Miguel (Project Manager / Developer):** Overall project management, drafting Architecture Decision Records (ADRs) and pull requests, backend development, and alignment on challenge criteria.
* **Young (Technical Lead / Developer):** Repository setup, core architecture, initial code and documentation uploads, technical stack specifications, and agent integration.
* **Julián & David (Fonseca) (Developers):** Relational dataset analysis, data extraction, uploading small working datasets to `/data` in the repository, and defining schema requirements.

  > **Note (Young, 2026-09-27):** Datasets will not be uploaded to `data/`. That folder is gitignored and holds each person's local download of the full dataset (`make data-download`). The committed samples live in `data_platform/sample/`: a small linked sample that runs the whole pipeline offline, and a `preview/` folder with about ten example rows per table. Both are regenerated with `make data-sample`; see `data_platform/sample/README.md`.

---

## 3. Decision Drivers

* **Production Readiness:** Organizers heavily weight functional, deployed software over conceptual designs.
* **Relational Schema:** The hackathon dataset provided by organizers is strictly relational.
* **Observability & Governance:** The agent must log decisions, handle errors gracefully, and maintain responsible AI guardrails.
* **Timeline:** Strict 10-day build window from kickoff to final submission.

---

## 4. Considered Options

* **Backend Framework:** Python (FastAPI / Flask) vs. Node.js (TypeScript)
* **Database Engine:** PostgreSQL vs. NoSQL / Vector-only Store
* **Frontend Interface:** React Web Application vs. Mobile-only / CLI

---

## 5. Decision Outcome

**Chosen Option:** A microservice-oriented Python backend paired with PostgreSQL and a React Web UI.

### Architecture Specifications

1. **Backend & Agent Orchestration (Python / FastAPI or Flask):**
   * Handles intent classification, tool execution, and microservice orchestration.
   * Manages agent routing, guardrails, and human escalation workflows.

   > **Note (Young, 2026-09-27):** The backend uses FastAPI (not Flask), as a single service organized in hexagonal layers; see ADR 0002 and `services/api/README.md`.

2. **Database Layer (PostgreSQL):**
   * Stores customer accounts, transaction histories, and dispute logs to align with the organizers' relational dataset.

3. **Frontend & Interaction Layer (React):**
   * Provides a web interface with an interactive setup wizard to guide judges through credential testing, transaction triggers, and automated fallback pathways.
   * Explores potential secondary integration via WhatsApp messaging.

4. **Documentation & Visual Modeling (Mermaid.js):**
   * Sequence and system architecture diagrams maintained directly in Markdown using `.mmd` files within `/docs`.

---

## 6. Consequences

### Positive Impact

* Fully satisfies the organizers' criteria for real backend execution and database interaction over static chat prompts.
* Leverages existing team proficiency in Python and relational data modeling for rapid development within the 10-day deadline.
* Simplifies judge evaluation via a structured frontend walkthrough.

### Pros & Cons of Selected Stack

* **Python + PostgreSQL (Selected):**
  * *Pros:* Directly supports the provided relational dataset; fast iteration for agent tools and microservice APIs.
  * *Cons:* Requires rigorous API integration testing to ensure stable agent tool calls under competition conditions.
* **NoSQL / Unstructured Database (Rejected):**
  * *Pros:* High flexibility for arbitrary chat logs.
  * *Cons:* Poor fit for the structured relational banking schema provided by organizers.

### Risks & Mitigations

* **Risk:** Scope creep across four banking domains within a short development cycle.
* **Mitigation:** Strict feature lock by the end of Day 1; priority focused on bulletproof core execution over non-essential features.

---

## 7. Next Steps & Pending Dependencies

* **Prerequisite:** Julián and David (Fonseca) complete the analysis of the relational banking dataset and upload small working datasets to `/data` in the repository.

  > **Note (Young, 2026-09-27):** As above, samples go to `data_platform/sample/`, never to `data/`.
* **Trigger for Next ADR:** Once dataset analysis is finalized by Julián and David, open **`docs/adr/0002-relational-database-schema-and-domain-tools.md`** (or the next available ADR index) to formalize:
  1. The exact database table definitions and schema mapping in PostgreSQL.
  2. The specific API tools and endpoints exposed to the agent for the four core banking domains.
  3. Differentiating technical features (e.g., automated fraud detection, biometric approval flows, or judge walkthrough setup).
