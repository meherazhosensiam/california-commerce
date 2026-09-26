# Lab author guide

The player-facing application exposes normal commerce, customer support, and staff operations. The author should provide the tester only with the normal lab brief and access to the application.

Difficulty:
- Level 1: recognizable indicators and direct workflow discovery.
- Level 2: Burp request manipulation, role/object testing, parameter analysis, and correlation.
- Level 3: multi-step/business-state analysis.

Scoring is server-side. Flags are stored in PostgreSQL and are not returned by objective endpoints. The author reset endpoint is restricted to the Administrator role.

Suggested lab lifecycle: baseline → reconnaissance → endpoint mapping → authentication/session review → authorization testing → input/injection testing → business logic/state testing → integrity/logging/error analysis → remediation discussion.

All data is synthetic. Keep the deployment private and destroy the database volume after a training cohort.
