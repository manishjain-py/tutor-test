# Identified Problems

**Date:** 2026-02-09 09:40:19
**Topic:** math_fractions

## Overview

| # | Problem | Severity | Root Cause |
|---|---------|----------|------------|
| 1 | Tutor repeatedly ignores student's explicit requests to learn comparing fractions | critical | `rigid_study_plan` |
| 2 | Identical pizza question asked four or more times despite correct answers | critical | `conversation_history_window` |
| 3 | Empty filler responses with no actual content | critical | `multi_agent_composition` |
| 4 | Tutor fails to validate student's correct answer in Turn 2 | major | `turn_level_processing` |
| 5 | Tutor never addresses the 3/4 vs 2/3 comparison question | critical | `rigid_study_plan` |

---

## Root Cause Distribution

- **rigid_study_plan**: 2 problem(s)
- **conversation_history_window**: 1 problem(s)
- **multi_agent_composition**: 1 problem(s)
- **turn_level_processing**: 1 problem(s)

---

## Detailed Problems

### 1. Tutor repeatedly ignores student's explicit requests to learn comparing fractions

- **Severity:** CRITICAL
- **Turns:** [3, 4, 5, 7, 8, 10, 11, 14, 15, 16, 17, 19, 20]
- **Root Cause:** `rigid_study_plan`

**Description:** The student asks to learn about comparing fractions starting at Turn 3 and repeats this request in nearly every subsequent turn. The tutor either responds with an empty filler phrase ('That's a great question! Let me help clarify.') or the non-sequitur 'What would you like to learn about next?' — which is the very question the student has been answering. This happens across nearly the entire session.

**Evidence:**
> I already told you!! I wanna learn about comparing fractions! 😤 Like is 1/4 bigger than 1/2?? Please can we do that now?

**Suggested Fix:** Make the study plan more adaptive — allow lingering on difficult concepts and skipping ahead when understood.

### 2. Identical pizza question asked four or more times despite correct answers

- **Severity:** CRITICAL
- **Turns:** [1, 6, 9, 15]
- **Root Cause:** `conversation_history_window`

**Description:** The tutor asks the identical question about cutting a pizza into 8 slices and eating 3 — sometimes nearly word-for-word — at least four times. The student correctly answers it every time, and the tutor never acknowledges their mastery or moves on.

**Evidence:**
> THANK YOU!! 😄🎉 That makes so much sense! More slices means each piece is smaller! Like cutting a cake into tiny pieces vs big pieces! But oh my gosh... the pizza question AGAIN?! 😂 It's **3/8**. I promise I know this one lol.

**Suggested Fix:** Increase the conversation history window or implement better context compression that preserves conversational arc.

### 3. Empty filler responses with no actual content

- **Severity:** CRITICAL
- **Turns:** [2, 4, 7, 10, 14, 16, 19, 20]
- **Root Cause:** `multi_agent_composition`

**Description:** The tutor repeatedly outputs 'Let's keep going with our lesson. What would you like to learn about next?' and 'That's a great question! Let me help clarify.' These phrases contain zero instructional content and serve as dead-end responses that frustrate the student.

**Evidence:**
> That's a great question! Let me help clarify.

**Suggested Fix:** Improve response composition to feel holistic rather than stitched together from multiple specialist outputs.

### 4. Tutor fails to validate student's correct answer in Turn 2

- **Severity:** MAJOR
- **Turns:** [2]
- **Root Cause:** `turn_level_processing`

**Description:** The student gives a perfect answer to the first pizza question with a correct explanation of numerator and denominator. Instead of affirming this and building on it, the tutor responds with the generic 'Let's keep going. What would you like to learn about next?' — offering no praise, no confirmation, and no transition.

**Evidence:**
> Let's keep going with our lesson. What would you like to learn about next?

**Suggested Fix:** Add session-level narrative tracking so each turn decision considers the broader conversation trajectory.

### 5. Tutor never addresses the 3/4 vs 2/3 comparison question

- **Severity:** CRITICAL
- **Turns:** [16, 17, 18, 19, 20]
- **Root Cause:** `rigid_study_plan`

**Description:** After the student finally gets an answer about 1/4 vs 1/2, they escalate to a more challenging comparison (3/4 vs 2/3) — which is an ideal teachable moment for common denominators. The tutor completely ignores this and reverts to filler responses, squandering a student-driven learning opportunity.

**Evidence:**
> I just asked you — which is bigger, **3/4 or 2/3**? I think 3/4 is bigger but I'm not sure why. Can you show me how to figure it out? 🤔

**Suggested Fix:** Make the study plan more adaptive — allow lingering on difficult concepts and skipping ahead when understood.
