# ADR 0000: Agentic Banking Architecture, Core Tech Stack & Team Alignment

* **Status:** Proposed
* **Date:** 2026-09-27
* **Deciders:** 
  * Miguel (Project Manager / Developer)[span_0](start_span)[span_0](end_span)
  * Young (Technical Lead / Developer)[span_1](start_span)[span_1](end_span)
  * David (Fonseca) (Developer)[span_2](start_span)[span_2](end_span)
  * Julián (Developer)[span_3](start_span)[span_3](end_span)

---

## 1. Context & Problem Statement

The Factored 2026 Hackathon challenge requires building an end-to-end banking solution covering four core functional domains: **Accounts & Payments**, **Credit Cards**, **Claims & Disputes**, and **Product Information**[span_4](start_span)[span_4](end_span). 

The competition organizers explicitly noted during kickoff that basic, prompt-only chatbots will not meet evaluation standards[span_5](start_span)[span_5](end_span). The solution must operate as a production-ready agentic system capable of executing backend tools, querying structured relational data, verifying user intents, logging decision paths, and providing human-in-the-loop escalation paths for complex or high-risk cases[span_6](start_span)[span_6](end_span).

---

## 2. Team Ownership & Responsibilities

To maintain high development velocity across human developers and automated coding agents during the 10-day build window, team roles are defined as follows[span_7](start_span)[span_7](end_span):

* **Miguel (Project Manager / Developer):** Overall project management, drafting Architecture Decision Records (ADRs) and pull requests, backend development, and alignment on challenge criteria[span_8](start_span)[span_8](end_span).
* **Young (Technical Lead / Developer):** Repository setup, core architecture, initial code and documentation uploads, technical stack specifications, and agent integration[span_9](start_span)[span_9](end_span).
* **Julián & David (Fonseca) (Developers):** Relational dataset analysis, data extraction, uploading small working datasets to `/data` in the repository, and defining schema requirements[span_10](start_span)[span_10](end_span).

---

## 3. Decision Drivers

* **Production Readiness:** Organizers heavily weight functional, deployed software over conceptual designs[span_11](start_span)[span_11](end_span).
* **Relational Schema:** The hackathon dataset provided by organizers is strictly relational[span_12](start_span)[span_12](end_span).
* **Observability & Governance:** The agent must log decisions, handle errors gracefully, and maintain responsible AI guardrails[span_13](start_span)[span_13](end_span).
* **Timeline:** Strict 10-day build window from kickoff to final submission[span_14](start_span)[span_14](end_span).

---

## 4. Considered Options

* **Backend Framework:** Python (FastAPI / Flask) vs. Node.js (TypeScript)[span_15](start_span)[span_15](end_span)
* **Database Engine:** PostgreSQL vs. NoSQL / Vector-only Store[span_16](start_span)[span_16](end_span)
* **Frontend Interface:** React Web Application vs. Mobile-only / CLI[span_17](start_span)[span_17](end_span)

---

## 5. Decision Outcome

**Chosen Option:** A microservice-oriented Python backend paired with PostgreSQL and a React Web UI[span_18](start_span)[span_18](end_span).

### Architecture Specifications

1. **Backend & Agent Orchestration (Python / FastAPI or Flask):**
   * Handles intent classification, tool execution, and microservice orchestration[span_19](start_span)[span_19](end_span).
   * Manages agent routing, guardrails, and human escalation workflows[span_20](start_span)[span_20](end_span).

2. **Database Layer (PostgreSQL):**
   * Stores customer accounts, transaction histories, and dispute logs to align with the organizers' relational dataset[span_21](start_span)[span_21](end_span).

3. **Frontend & Interaction Layer (React):**
   * Provides a web interface with an interactive setup wizard to guide judges through credential testing, transaction triggers, and automated fallback pathways[span_22](start_span)[span_22](end_span).
   * Explores potential secondary integration via WhatsApp messaging[span_23](start_span)[span_23](end_span).

4. **Documentation & Visual Modeling (Mermaid.js):**
   * Sequence and system architecture diagrams maintained directly in Markdown using `.mmd` files within `/docs`[span_24](start_span)[span_24](end_span).

---

## 6. Consequences

### Positive Impact
* Fully satisfies the organizers' criteria for real backend execution and database interaction over static chat prompts[span_25](start_span)[span_25](end_span).
* Leverages existing team proficiency in Python and relational data modeling for rapid development within the 10-day deadline[span_26](start_span)[span_26](end_span).
* Simplifies judge evaluation via a structured frontend walkthrough[span_27](start_span)[span_27](end_span).

### Pros & Cons of Selected Stack

* **Python + PostgreSQL (Selected):**
  * *Pros:* Directly supports the provided relational dataset; fast iteration for agent tools and microservice APIs[span_28](start_span)[span_28](end_span).
  * *Cons:* Requires rigorous API integration testing to ensure stable agent tool calls under competition conditions[span_29](start_span)[span_29](end_span).
* **NoSQL / Unstructured Database (Rejected):**
  * *Pros:* High flexibility for arbitrary chat logs.
  * *Cons:* Poor fit for the structured relational banking schema provided by organizers[span_30](start_span)[span_30](end_span).

### Risks & Mitigations
* **Risk:** Scope creep across four banking domains within a short development cycle[span_31](start_span)[span_31](end_span).
* **Mitigation:** Strict feature lock by the end of Day 1; priority focused on bulletproof core execution over non-essential features[span_32](start_span)[span_32](end_span).

---

## 7. Next Steps & Pending Dependencies

* **Prerequisite:** Julián and David (Fonseca) complete the analysis of the relational banking dataset and upload small working datasets to `/data` in the repository[span_33](start_span)[span_33](end_span).
* **Trigger for Next ADR:** Once dataset analysis is finalized by Julián and David, open **`docs/adr/0002-relational-database-schema-and-domain-tools.md`** (or the next available ADR index) to formalize:
  1. The exact database table definitions and schema mapping in PostgreSQL[span_34](start_span)[span_34](end_span).
  2. The specific API tools and endpoints exposed to the agent for the four core banking domains[span_35](start_span)[span_35](end_span).
  3. Differentiating technical features (e.g., automated fraud detection, biometric approval flows, or judge walkthrough setup)[span_36](start_span)[span_36](end_span).
