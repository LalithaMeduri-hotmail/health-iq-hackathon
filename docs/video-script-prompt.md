---
title: Health IQ Demo Video Generation Prompt
description: Master prompt and scene-by-scene script for generating a walkthrough video that explains every Health IQ feature.
author: Health IQ Hackathon Team
ms.date: 2026-09-10
ms.topic: reference
keywords:
  - health iq
  - demo video
  - product walkthrough
  - prompt engineering
estimated_reading_time: 8
---

## Purpose

This document gives you a ready-to-use prompt for generating a product walkthrough video for Health IQ. The master prompt is a condensed, tool-ready version (under 1000 characters) for text-to-video generators that enforce a prompt-length cap. The detailed scene breakdown that follows expands the same six chapters into a full narration script for a longer cut (about 4 minutes), for use with a human narrator, a screen-recording brief, or an AI voiceover tool without a character limit. Both map one-to-one with the six features documented in [docs/lld](lld/1-low-level-design-overview.md), so either version explains every capability in the product.

## Master Prompt

Copy the block below into your video generation tool of choice (for example Sora, Runway, or Pictory). It is kept under 1000 characters to fit the prompt-length limits most text-to-video tools enforce.

```text
Create a 90-second demo video for Health IQ, an AI health companion app. Style: clean
light-blue UI screen recording, calm narrator, soft zooms on key numbers, minimal corporate
music. Open with title card: Health IQ - Understand Your Health, Together With Your Doctor,
and disclaimer: informational only, not a diagnosis or prescription. Show six chapters: (1)
Upload a prescription, extract medicine details, reveal generic alternatives with savings,
marked doctor-approval-required. (2) Upload a lab report, reveal health score, system cards,
and a specialist suggestion. (3) Compare two reports with a trend chart and improved,
worsened, or unchanged tags. (4) Generate an allergen-safe multi-day meal plan from report
findings. (5) Build a doctor-review PDF with approval controls and a secure 24-hour share
link. (6) Show a safety-reviewed badge on every response. Close with the tagline and
disclaimer repeated. Ground visuals in the real product UI; invent nothing.
```

## Scene Breakdown

Use these six chapters as the shot list for the longer, 4-minute narrated cut. Each chapter corresponds to one feature and includes the on-screen action, narration script, and key visuals to capture.

### Chapter 1: Prescription and Medicine Analyzer (0:10-0:55)

On-screen action: Upload a prescription photo on the Prescription Analyzer screen, show OCR extracting medicine name, dosage, and frequency, then reveal generic and cheaper alternatives with savings percentage and source date.

Narration:

"Health IQ starts by making sense of a prescription. Upload a photo of a prescription or a
tablet strip, and the app extracts the medicine name, strength, dosage, and frequency
automatically. Every low-confidence reading is flagged for you to confirm, so nothing is
guessed silently. Health IQ then surfaces generic and lower-cost alternatives that match the
exact active ingredient, strength, and form, each with an estimated savings percentage and a
source date. Every suggestion is marked as requiring doctor approval, because Health IQ never
changes a therapy on its own."

Key visuals: upload dropzone, OCR confidence badges, alternatives table with savings percentage, "doctor approval required" tag.

### Chapter 2: Health Profile and Specialist Advisor (0:55-1:40)

On-screen action: Upload a lab report, show the visual health snapshot (health score, organ or system cards, abnormal flags), then show the specialist suggestion with rationale.

Narration:

"Next, upload a lab report and Health IQ turns it into a visual health snapshot. Parameters
are normalized against reference ranges and organized into system cards with clear risk chips,
alongside an overall health score you can track over time. When something falls outside the
normal range, Health IQ suggests which type of specialist to talk to next, with plain-language
reasoning. It never names a disease or predicts urgency. It only points you toward the right
conversation with a professional."

Key visuals: health score gauge, system cards with color-coded chips, specialist suggestion card with rationale text.

### Chapter 3: Report Comparison Engine (1:40-2:15)

On-screen action: Select two reports (old versus current), show the parameter-by-parameter comparison table and trend chart.

Narration:

"Health IQ also compares reports over time. Pick any two lab reports and the app aligns every
shared parameter, classifying each one as improved, worsened, unchanged, or newly abnormal. A
trend chart visualizes the direction of change, and a plain-language summary explains what the
movement means, always grounded in reference ranges. The classification itself is calculated
deterministically, so the same two reports always produce the same result."

Key visuals: side-by-side report selector, comparison table with change badges, trend line chart.

### Chapter 4: AI Meal Planner (2:15-2:55)

On-screen action: Set preferences (allergies, cuisine, budget, goals), generate a multi-day meal plan, highlight allergen blocking.

Narration:

"Based on your latest report findings and personal preferences, Health IQ generates a
multi-day meal plan. Tell it your allergies, preferred cuisine, budget, and health goals, and
it builds condition-aware suggestions, such as lower glycemic index options when glucose is
elevated. Every recommendation is grounded in nutrition guidance with a cited source, allergens
are hard-blocked, and the app never prescribes supplement dosing or calorie targets. It is
general guidance, always meant to complement, not replace, professional advice."

Key visuals: preference form, generated day-by-day meal cards, allergen-safe badge, source citations.

### Chapter 5: Doctor-Review PDF and Secure Share (2:55-3:30)

On-screen action: Generate a doctor-review PDF from an analyzed prescription, show the structured sections and approval controls, then create and open a secure share link.

Narration:

"Every analysis can be turned into a structured, doctor-review PDF, framed as an approval
request rather than a prescription change. It includes confidence scores, source provenance,
and approve, modify, or reject controls for your doctor to sign off on. From there, Health IQ
issues a secure, time-bound share link, valid for 24 hours and fully revocable, so you can send
your results to a doctor without exposing your account."

Key visuals: PDF preview scrolling through sections, approval controls, share link generation dialog, expiry countdown.

### Chapter 6: Safety Reviewer, Every Step of the Way (3:30-4:00)

On-screen action: Show a subtle "safety checked" badge appearing on a response, briefly explain the mandatory safety pipeline.

Narration:

"Behind every feature in Health IQ sits a mandatory safety review. Before any answer reaches
you, a dedicated safety reviewer checks it against strict rules: no diagnosis, no prescribing,
no unverified claims. If a response cannot pass, it is blocked rather than shown. Health IQ is
built to inform and support your conversations with healthcare professionals, never to replace
them."

Key visuals: safety badge/checkmark overlay, disclaimer banner, closing title card with tagline and disclaimer.

## Narrator Voice and Tone Guidance

* Calm, confident, and warm, similar to a trusted clinician explaining a tool to a patient.
* Avoid superlatives such as "revolutionary" or "life-changing".
* Pause briefly after each disclaimer so it registers with viewers.
* Pronounce "Health IQ" consistently as two words, not an acronym.

## Reusable Short-Form Prompt

Use this shorter prompt if you only need a 60-second highlight reel for social media.

```text
Create a 60-second highlight video for "Health IQ", an AI health companion app. Show four
quick cuts in this order: (1) uploading a prescription and revealing cheaper medicine
alternatives with savings percentage, (2) a lab report becoming a visual health score with
system cards, (3) two reports compared side by side with a trend chart, (4) a personalized
meal plan with allergen-safe badges. End with the tagline "Health IQ - Understand Your Health,
Together With Your Doctor" and the disclaimer "Not a substitute for professional medical
advice." Keep pacing fast, upbeat but not clinical-sounding music, and clean on-screen captions
naming each feature as it appears.
```
