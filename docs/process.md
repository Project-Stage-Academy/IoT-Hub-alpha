# Development Process and Workflow

This document outlines the operational standards for the IoT Catalog Hub project. 
It ensures that every task is well-defined before work begins and meets high-quality standards 
before it is considered finished. All tasks and PRs are tracked via the **GitHub Project Board** 
linked here: [Project Board](https://github.com/orgs/Project-Stage-Academy/projects/22)

---

## 1. Definition of Ready (DoR)

A User Story or task can be moved from **Backlog** to **Sprint Backlog** only if it meets the following criteria:

* **Clear Description:** The "What" and "Why" of the task are well-understood.
* **Acceptance Criteria (AC):** There is a list of measurable conditions that the feature must satisfy.
* **Dependencies:** Any external dependencies (e.g., API from another team, infrastructure) are identified and available.
* **Estimation:** The task has been reviewed and estimated by the team.
* **GitHub Project Board Card:** The task exists on the board and is in **Backlog/Ready** column.

---

## 2. Definition of Done (DoD)

A task is considered **Done** only when all the following technical and quality requirements are met:

### Code & Quality
- [ ] **Formatting:** Code is formatted using `black`.
- [ ] **Linting:** `flake8` checks pass with zero errors.
- [ ] **Logic:** The implementation satisfies all defined Acceptance Criteria (AC).

### Testing
- [ ] **Unit Tests:** New and existing tests pass using `pytest`.
- [ ] **Coverage:** Core logic is covered by automated tests.

### Infrastructure & Environment
- [ ] **Docker:** The feature is validated to run correctly within the `docker compose` environment.
- [ ] **CI Pipeline:** The GitHub Actions (or equivalent CI) status is "green" (passing).

### Documentation & Review
- [ ] **Documentation:** Relevant README files, `/docs`, or API specifications are updated.
- [ ] **Code Review:** The Pull Request (PR) has received at least **one approval** from a Lead or Mentor.
- [ ] **Issue Linking:** The PR is linked to the corresponding GitHub Issue/User Story.
- [ ] **Project Board Update:** The GitHub Project board card is moved to **Done** column.

---

## 3. Pull Request (PR) Policy

To maintain a clean and stable repository, we follow these rules:

1. **Branching:** Always create a new branch from `main`. Use the format: `task-number-short-description` (e.g., `task-9-team-structure`).
2. **Small PRs:** Keep PRs focused. It is better to have three small PRs than one massive one.
3. **Reviewers Assignment:** When creating a Pull Request, you must tag at least **2 colleagues** and mentor as reviewers to ensure a thorough review and cross-team knowledge sharing.
4. **No Direct Commits:** Committing directly to `main` is strictly prohibited.
5. **Squash and Merge:** We prefer "Squash and Merge" to keep the `main` branch history clean and linear.
6. **PR Template:** Always use the `.github/PULL_REQUEST_TEMPLATE.md` to ensure checklist compliance.

---

## 4. Additional Notes

- **Sprint Planning:** The mentor sends Epics with corresponding tasks before the start of each sprint. The team selects which tasks to work on.  
- **Blockers:** Any issues or blockers are discussed in the team’s Discord chat or voice channel.  
- **Cross-Team Communication:** Since the internship team is split into two sub-teams, it is important to synchronize critical changes between sub-teams to avoid duplication of work.
