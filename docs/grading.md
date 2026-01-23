# Grading Rubric and Quality Criteria

This document defines the evaluation framework for the internship project. Performance is assessed based on each completed User Story and summarized during weekly checkpoints.

Scores are indicative and may be used qualitatively during weekly checkpoints.
Numerical grading is applied only at defined evaluation milestones.


## 1. Score Distribution by Category

Each task/User Story is evaluated on a 100-point scale, distributed as follows:

| Category | Weight | Evaluation Criteria |
| :--- | :--- | :--- |
| **Functionality** | 40 pts | Compliance with Acceptance Criteria (AC), bug-free logic. |
| **Code Quality** | 20 pts | Adherence to `black` and `flake8` standards, clean code principles. |
| **Testing** | 15 pts | Presence of unit tests (`pytest`), coverage of edge cases. |
| **CI/CD & Infra** | 10 pts | Correct Docker configuration, green CI pipelines. |
| **Documentation** | 10 pts | README updates, clear code comments, API documentation. |
| **Demo & Reports** | 5 pts | Presentation quality during demos, timely weekly reports. |

---

## 2. Detailed Rubric Breakdown

### Functionality (40 pts)
* **30-40 pts:** All AC met; feature works as expected without errors.
* **15-29 pts:** Core logic works, but some secondary AC are missed or minor bugs exist.
* **0-14 pts:** The feature fails to perform its primary function.

### Code Quality (20 pts)
* **15-20 pts:** Clean, readable code; fully formatted with `black`; zero `flake8` warnings.
* **5-14 pts:** Minor issues with variable naming or structure; partial formatting.
* **0-4 pts:** Hard-to-read code; significant duplication (DRY principle violated).

### Testing (15 pts)
* **10-15 pts:** Tests cover both "happy path" and "failure" scenarios.
* **1-9 pts:** Minimal testing provided (e.g., only basic success cases).
* **0 pts:** No tests provided.

---

## 3. Pass/Fail Thresholds

Final progress is calculated as the average score across all assigned tasks:

* **90 - 100:** **Excellence**. Recommended for internship completion with distinction.
* **70 - 89:** **Pass**. Successful completion of the program.
* **Below 70:** **Fail**. Requires additional improvement or reassessment.

## 4. Weekly Checkpoints (Formative Evaluation)

During weekly checkpoints, mentors provide qualitative feedback mapped to the rubric
categories (Functionality, Code Quality, Testing, etc.) without assigning final scores.

The rubric serves as a reference to:
- highlight strengths and gaps,
- track progress over time,
- align expectations before final evaluation.
