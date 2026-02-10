# Identified Problems

**Date:** 2026-02-09 19:49:28
**Topic:** math_fractions

## Overview

| # | Problem | Severity | Root Cause |
|---|---------|----------|------------|
| 1 | Incomplete topic coverage — comparing and adding fractions never addressed | critical | `rigid_study_plan` |
| 2 | Session ends abruptly without closure | major | `other` |
| 3 | Repetitive question structure without increasing difficulty | major | `turn_level_processing` |
| 4 | Failure to adapt to student's demonstrated mastery | major | `turn_level_processing` |
| 5 | Common misconceptions never probed or addressed | minor | `prompt_quality` |

---

## Root Cause Distribution

- **turn_level_processing**: 2 problem(s)
- **rigid_study_plan**: 1 problem(s)
- **other**: 1 problem(s)
- **prompt_quality**: 1 problem(s)

---

## Detailed Problems

### 1. Incomplete topic coverage — comparing and adding fractions never addressed

- **Severity:** CRITICAL
- **Turns:** [0, 1, 2, 3]
- **Root Cause:** `rigid_study_plan`

**Description:** The learning objectives include comparing fractions with the same denominator and adding fractions with the same denominator, but the entire session only covers basic fraction identification. The student demonstrates mastery of naming fractions quickly, yet the tutor continues with near-identical identification problems instead of advancing.

**Evidence:**
> imagine you have a chocolate bar broken into 8 equal pieces, and you eat 5 of them. What fraction of the chocolate bar did you eat?

**Suggested Fix:** Make the study plan more adaptive — allow lingering on difficult concepts and skipping ahead when understood.

### 2. Session ends abruptly without closure

- **Severity:** MAJOR
- **Turns:** [3]
- **Root Cause:** `other`

**Description:** The conversation simply stops after the student's third correct answer. There's no summary of learning, no transition to harder material, and no closing. The session feels incomplete.

**Evidence:**
> Okay so 8 pieces total so that's the bottom number and I ate 5 so... **5/8**!

### 3. Repetitive question structure without increasing difficulty

- **Severity:** MAJOR
- **Turns:** [1, 2, 3]
- **Root Cause:** `turn_level_processing`

**Description:** All three practice questions follow the exact same pattern: a food item is divided into N pieces, you take M of them, write the fraction. The cognitive demand doesn't increase, and the student clearly doesn't need more practice at this level.

**Evidence:**
> imagine you have a chocolate bar broken into 8 equal pieces, and you eat 5 of them. What fraction of the chocolate bar did you eat?

**Suggested Fix:** Add session-level narrative tracking so each turn decision considers the broader conversation trajectory.

### 4. Failure to adapt to student's demonstrated mastery

- **Severity:** MAJOR
- **Turns:** [2, 3]
- **Root Cause:** `turn_level_processing`

**Description:** The student correctly answers immediately and even articulates the reasoning in their own words ('the bottom number is how many slices total and top is what I took'). A skilled tutor would recognize this mastery and move to comparing or adding fractions rather than repeating the same type of problem.

**Evidence:**
> You explained that perfectly! 😊... So here's a fun one for you: imagine you have a chocolate bar broken into 8 equal pieces

**Suggested Fix:** Add session-level narrative tracking so each turn decision considers the broader conversation trajectory.

### 5. Common misconceptions never probed or addressed

- **Severity:** MINOR
- **Turns:** [0, 1, 2, 3]
- **Root Cause:** `prompt_quality`

**Description:** The curriculum identifies important misconceptions (e.g., larger denominator means larger fraction, 1/4 > 1/2 because 4 > 2), but the tutor never tests for or addresses these. Probing for misconceptions would be more valuable than repeating easy identification problems.

**Suggested Fix:** Review and improve the relevant agent prompts for clarity, specificity, and natural language generation.
