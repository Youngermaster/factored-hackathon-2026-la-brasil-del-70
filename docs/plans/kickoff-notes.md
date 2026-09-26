# Factored 2026 Hackathon Kick Off - Alignment & Strategy Meeting Notes

## 1. Executive Summary

The **Factored 2026 Hackathon Kick Off** internal alignment meeting brought together the project team (**Miguel (Project Manager/Developer)**, **Young**, **David (Fonseca)**, and **Julián**) to establish the strategy, architecture, and timeline for their entry. The team's primary objective is to build a production-ready, agentic banking system that goes beyond a standard chatbot by integrating tool execution, microservice orchestration, relational database management, and human-in-the-loop escalation. The call focused on translating the hackathon organizers' challenge criteria into an actionable build plan, defining the technical stack, establishing GitHub-centered documentation workflows, and locking down core banking modules. The ultimate outcome is to deliver a fully functional, production-deployed system within the strict 10-day competition window.

---

## 2. Key Hackathon Rules & Technical Constraints

* **Challenge Requirements:** 
  * Develop an agentic banking solution capable of processing end-to-end customer workflows across four core domains: **Accounts & Payments**, **Credit Cards**, **Claims & Disputes**, and **Product Information**.
  * The solution must **not** be a static, prompt-only chatbot; it must actively execute backend tools, query databases, verify actions, and escalate complex cases to human review.
* **Technical Stack Guidelines:**
  * **Frontend:** Web UI (React) and potential WhatsApp messaging interface.
  * **Backend & API:** Python (FastAPI/Flask microservices) for API handling and agent orchestration.
  * **Database:** PostgreSQL relational database to match the structured schema provided by organizers.
  * **Documentation & Diagrams:** Markdown formatted with Mermaid.js (`.mmd`) visual system and sequence diagrams.
  * **Optional Feature:** Brainstormed potential Coinbase X402 payment protocol integration for crypto transaction status tracking.
* **Constraints & Evaluation Criteria:**
  * **Production Readiness:** Organizers heavily prioritize functional, production-deployed applications over overly complex non-functional designs.
  * **Observability & Governance:** System must demonstrate structured workflows, clear decision logging, responsible AI guardrails, and error handling.
  * **Dataset Usage:** Relational banking dataset provided directly by hackathon organizers.
  * **Time Constraint:** 10-day build timeframe from kickoff to submission.

---

## 3. Action Items & Ownership Matrix

| Action Item / Task | Assigned Owner / Speaker | Due Date / Deadline | Status / Context |
| :--- | :--- | :--- | :--- |
| **Make GitHub Repository Private & Invite Team** (~16:54) | Young | Immediate | **Completed**; invited David (Fonseca), Julián, and Miguel (Project Manager/Developer) during the call. |
| **Upload Initial Code & Docs to Repo `/docs`** (~16:18) | Young | Today | **In Progress**; uploading initial codebase, documentation, and repository folder structure. |
| **Create Architecture & Decision Doc PR** (~15:18) | Miguel (Project Manager/Developer) | Today / Tomorrow | **Scheduled**; will draft PR on GitHub detailing meeting agreements and module breakdowns. |
| **Review & Commit Feedback on Decision Doc PR** (~15:35) | All Team Members (Julián, David (Fonseca), Young, Miguel (Project Manager/Developer)) | Today / Tomorrow | **Pending** creation of PR; team will review and submit commits/comments. |
| **Document Technical Stack & Framework Specs** (~18:20) | Young & Miguel (Project Manager/Developer) | Today / Tomorrow | **Scheduled**; detailing React, Python API, and PostgreSQL setup in `/docs`. |
| **Dataset Analysis & Upload Small Datasets to Repo** (~19:35) | Julián & David (Fonseca) | Today Afternoon | **In Progress**; analyzing relational dataset and uploading small datasets directly to the repository. |

---

## 4. Critical Timeline & Key Deadlines

* **Official Hackathon Kickoff:** Held by organizers on Friday prior to this team call (~07:15).
* **Total Hackathon Duration:** 10 days total (~19:58).
* **Internal Idea & Scope Lock Deadline:** Today afternoon/evening (~19:35, ~25:35).
* **Internal Decision Doc PR Review Deadline:** Between today and tomorrow (~15:40).
* **Coding Start Date:** Immediate upon scope lock.
* **Office Hours:** Not specified in recording.
* **Code Freeze:** Not specified in recording.
* **Final Submission Deadline:** Not specified in recording.
* **Pitch / Presentation Date:** Not specified in recording.
* **Award Ceremony:** Not specified in recording.

---

## 5. Team & Support Structures

* **Team Members:** Miguel (Project Manager/Developer), Young (Technical Lead/Architecture), David (Fonseca) (Developer/Analyst), Julián (Developer/Analyst).
* **Primary Communication & Code Channels:**
  * **GitHub Repository:** Central hub for source code, pull requests, Markdown decision docs, and Mermaid diagrams. Repository set to **Private**.
  * **WhatsApp:** Team messaging channel for quick syncs and data sharing.
* **AI Context Pipeline:** All meeting recordings and transcripts are being ingested by AI tools to auto-generate structured notes, pull requests, and documentation commits so that automated coding agents retain full repository context.
* **Mentor & Coach Assignments:** Not specified in recording.
* **Official Hackathon Support Channels (Slack/Discord):** Not specified in recording.

---

## 6. Highlights & Q&A Summary

* **Q: Is the goal of this challenge to build a simple banking chatbot?**
  * **A:** No. Miguel (Project Manager/Developer) clarified that the hackathon organizers explicitly stated in Friday's kickoff that simple chatbots will not win. The solution must be an integrated agentic system capable of intent classification, tool calling, transaction execution, verification, and human escalation.

* **Q: How will our team differentiate our solution if every team is building a banking system?**
  * **A:** David (Fonseca) raised concerns about standing out. The team agreed that core execution and production deployment matter most. Differentiating ideas proposed included automated fraud/AML detection, biometric transaction approval flows, an interactive guided walkthrough in the frontend UI for judges, and potential crypto payment tracking via Coinbase X402.

* **Q: What database architecture should be used for the dataset?**
  * **A:** Young confirmed that the dataset provided by the organizers is strictly relational. Therefore, the team selected PostgreSQL over NoSQL or graph databases.

* **Q: How should system workflows and evaluation criteria be presented to judges?**
  * **A:** The team decided to embed Mermaid.js visual diagrams directly into the Markdown documentation (`/docs`) and build an interactive setup wizard in the React frontend. This wizard will guide judges through testing mock credentials, triggering transactions, and observing automated fallback mechanisms.