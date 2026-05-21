# Compliance Assistant — Feature Spec: Application Modes

## Overview

The compliance assistant supports three distinct modes of operation, each tailored to a different researcher workflow. The user selects their mode at the start of a session.

---

## Mode Selection

| Story | Description |
|-------|-------------|
| **US-0.1** | As a researcher, I can choose Co-Author, Review, or Adapt mode when I launch the app so the agent matches my workflow. |
| **US-0.2** | As a researcher, I can switch modes mid-session if I change my mind about how I want to work. |

---

## Mode 1: Co-Author (Guided Walkthrough)

> **Target user:** Less experienced researchers, first-time IRB submitters, or anyone starting from a study narrative / grant proposal.

The agent fills the form section-by-section based on uploaded documents, with mandatory researcher review at each step.

| Story | Description |
|-------|-------------|
| **US-1.1** | As a researcher, I can upload my study document and the agent starts filling the form one section at a time. |
| **US-1.2** | As a researcher, I review each section before the agent moves to the next — the agent explicitly asks me to confirm. |
| **US-1.3** | As a researcher, I can edit any field the agent filled before approving the section. |
| **US-1.4** | As a researcher, if the agent is missing info for a field, it asks me a specific question rather than guessing. |
| **US-1.5** | As a researcher, if a question is too nuanced for the agent, it tells me to contact the IRB office and drafts a summary I can email them. |
| **US-1.6** | As a researcher, I can see exactly why the agent filled a field a certain way (reasoning + sources in the activity drawer). |

---

## Mode 2: Review (Expert Researcher)

> **Target user:** Experienced researchers who are comfortable with IRB forms and prefer to write responses themselves.

The researcher fills out the form. The agent reviews it and flags issues by severity.

| Story | Description |
|-------|-------------|
| **US-2.1** | As a researcher, I can fill out the form myself (or upload a draft) without the agent auto-filling anything. |
| **US-2.2** | As a researcher, I can ask the agent to review my form when I'm ready. |
| **US-2.3** | As a researcher, I see a summary of flagged issues categorized as major (must fix) or minor (recommended). |
| **US-2.4** | As a researcher, I walk through flags one at a time — the agent explains the issue and suggests a fix. |
| **US-2.5** | As a researcher, I can ask the agent questions about specific fields (e.g., "Does this count as multi-site?") and it references past submissions. |
| **US-2.6** | As a researcher, no field is modified unless I explicitly approve the change. |

---

## Mode 3: Adapt (Resubmission / Amendment)

> **Target user:** Researchers adapting a previously approved submission for a new site, population, or study period.

The agent pre-fills from a previous submission and identifies what needs updating.

| Story | Description |
|-------|-------------|
| **US-3.1** | As a researcher, I can upload or select a previous IRB submission as my starting point. |
| **US-3.2** | As a researcher, I see the form pre-filled from my previous submission. |
| **US-3.3** | As a researcher, the agent identifies fields that obviously need updating (dates, site names, personnel) and asks me about them. |
| **US-3.4** | As a researcher, I can see old values alongside new ones so I know what changed. |
| **US-3.5** | As a researcher, fields that carry over unchanged are flagged for a quick confirmation, not a full re-review. |

---

## Cross-Cutting (All Modes)

These apply regardless of which mode the researcher selects.

| Story | Description |
|-------|-------------|
| **US-X.1** | As a researcher, the agent never infers or extrapolates beyond what I've explicitly stated — it asks instead. |
| **US-X.2** | As a researcher, I can see all agent reasoning, tool calls, and data sources in the activity drawer. |
| **US-X.3** | As a researcher, when the agent references past submissions, results are filtered by department or study type for relevance. |
| **US-X.4** | As a researcher, the agent catches common committee flags (missing consent info, no sample size, etc.) regardless of mode. |
| **US-X.5** | As a researcher, if the agent can't resolve an issue, it drafts a summary email to the IRB office for me. |
