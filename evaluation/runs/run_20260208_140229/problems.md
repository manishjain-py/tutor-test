# Identified Problems

**Date:** 2026-02-08 14:09:53
**Topic:** math_fractions

## Overview

| # | Problem | Severity | Root Cause |
|---|---------|----------|------------|
| 1 | Tutor ignores the new 10-slice question and reverts to the old 3/8 problem | critical | `turn_level_processing` |
| 2 | Excessive repetition of the same 3/8 question and explanation | major | `rigid_study_plan` |
| 3 | Miscalibrated feedback: says the student is 'very close' when the answer is correct | minor | `prompt_quality` |
| 4 | Fails to deliver stated objectives (compare and add same-denominator fractions) | major | `rigid_study_plan` |
| 5 | Unnatural looping undermines session arc and student challenge level | major | `model_capability` |

---

## Root Cause Distribution

- **rigid_study_plan**: 2 problem(s)
- **turn_level_processing**: 1 problem(s)
- **prompt_quality**: 1 problem(s)
- **model_capability**: 1 problem(s)

---

## Detailed Problems

### 1. Tutor ignores the new 10-slice question and reverts to the old 3/8 problem

- **Severity:** CRITICAL
- **Turns:** [3]
- **Root Cause:** `turn_level_processing`

**Description:** After asking a new problem (10 slices, eat 4), the tutor responds as if the original 8-slice, eat-3 problem is still being solved, incorrectly marking the student wrong and re-asking the old question. This is a major breakdown in coherence and responsiveness.

**Evidence:**
> “Now you try: If a pizza is cut into **10 equal slices** and Maya eats **4 slices**, what fraction did she eat?” ... “Here, the pizza is cut into **8 equal slices**, and Maya ate **3 slices**, so the fraction she ate is **3/8** (not 4/10).”

**Suggested Fix:** Add session-level narrative tracking so each turn decision considers the broader conversation trajectory.

### 2. Excessive repetition of the same 3/8 question and explanation

- **Severity:** MAJOR
- **Turns:** [5, 6, 8]
- **Root Cause:** `rigid_study_plan`

**Description:** The tutor repeatedly asks the identical '8 slices, ate 3' question even after the student answers correctly multiple times, and repeats the numerator/denominator explanation nearly word-for-word. This wastes time and reduces learning progress.

**Evidence:**
> “Now answer this: **A pizza is cut into 8 equal slices. Maya eats 3 slices. What fraction of the pizza did Maya eat?**”

**Suggested Fix:** Make the study plan more adaptive — allow lingering on difficult concepts and skipping ahead when understood.

### 3. Miscalibrated feedback: says the student is 'very close' when the answer is correct

- **Severity:** MINOR
- **Turns:** [2]
- **Root Cause:** `prompt_quality`

**Description:** The student answers correctly (3/8), but the tutor begins with “You’re very close!” which signals partial correctness and can confuse or undermine confidence.

**Evidence:**
> “You’re very close! **For this pizza problem, 3/8 is correct** ...”

**Suggested Fix:** Review and improve the relevant agent prompts for clarity, specificity, and natural language generation.

### 4. Fails to deliver stated objectives (compare and add same-denominator fractions)

- **Severity:** MAJOR
- **Turns:** [0, 9]
- **Root Cause:** `rigid_study_plan`

**Description:** The tutor promises comparing and adding fractions but never transitions beyond defining fractions and identifying numerator/denominator. The session ends still repeating identification tasks.

**Evidence:**
> “You’ll learn what a fraction means, find the numerator and denominator, compare fractions with the same bottom number, and add them too.”

**Suggested Fix:** Make the study plan more adaptive — allow lingering on difficult concepts and skipping ahead when understood.

### 5. Unnatural looping undermines session arc and student challenge level

- **Severity:** MAJOR
- **Turns:** [6, 8]
- **Root Cause:** `model_capability`

**Description:** Even after the student demonstrates mastery (correctly defining fractions and identifying numerator/denominator), the tutor loops back to the same simplest question instead of extending difficulty (e.g., simplifying 4/10, comparing 3/8 vs 5/8, or adding 1/8+3/8).

**Evidence:**
> “Now try this: **A pizza is cut into 8 equal slices. Maya eats 3 slices. What fraction of the pizza did Maya eat?**”

**Suggested Fix:** This may be a model limitation. Consider testing with different models or adjusting temperature/sampling.
