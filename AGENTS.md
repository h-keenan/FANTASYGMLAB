# DynastyGM repository delivery contract

Unless a task explicitly requires human product approval, completed repository
work must be delivered rather than left on a feature branch.

Agents must:

1. Branch from the latest `origin/main`.
2. Implement only the requested scope.
3. Run the required focused, full-suite, compile, diff, and safety validation.
4. Push the branch.
5. Open a pull request against `main`.
6. Repair failing checks and merge conflicts.
7. Mark the pull request ready for review.
8. Enable auto-merge using the repository-supported merge method.
9. Remain active until the pull request merges or a genuine blocker is documented.
10. Report the final merge SHA.

A missing local browser connection is not, by itself, a valid reason to leave a
pull request in draft. UI changes use the deterministic GitHub Actions browser
workflow in `.github/workflows/ci.yml`.

A pull request may remain draft only for:

- unresolved product ambiguity;
- a security or data-integrity risk;
- unrecoverable failing tests;
- an evidenced visual defect;
- a required external secret or service that cannot be safely simulated.

Add the `human-approval-required` label only when the task explicitly requires
human product approval. The trusted delivery workflow will not automatically
ready or merge a pull request carrying that label.
