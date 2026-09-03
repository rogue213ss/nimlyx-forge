# Production Engineering Rule — Brutal Phase Validation

This project must NOT advance phases based solely on implementation completion or passing unit tests.
Every phase must pass a mandatory BRUTAL VALIDATION GATE before it is considered complete.
The goal is not to prove that the software works. The goal is to actively prove that the software continues to behave correctly when things go wrong.

## Core Rule
A phase is only COMPLETE when all of the following have been validated:
1. Happy path
2. Boundary conditions
3. Invalid input
4. Missing data
5. Malformed data
6. External service failure
7. Partial failure
8. Duplicate execution
9. Retry behavior
10. Database integrity
11. State-machine integrity
12. Crash/restart recovery
13. Idempotency
14. Provenance correctness
15. Security-sensitive behavior
16. Performance under realistic load
17. Regression against every previous phase

Do not mark a phase complete if any critical category is untested.

## Required Phase Report
At the end of every phase, produce a report containing:
1. Implementation Summary
2. Automated Tests
3. Failure Injection
4. Idempotency
5. Database Integrity
6. State Machine Audit
7. Crash Recovery
8. External-Service Validation
9. Real-World Validation
10. Data Provenance Audit
11. Security Audit
12. Performance Validation
13. Regression Testing
14. Adversarial Testing
15. Acceptance Criteria

## Final Principle
This is a production system. Treat every phase as guilty until proven correct.
The workflow is:
`BUILD → BREAK → OBSERVE → FIX → BREAK AGAIN → VERIFY → REGRESSION → ACCEPT`
Passing tests is evidence. It is not proof. The system should earn the right to move to the next phase.
