# Agentic AI Business Analytics Copilot

Work in numbered phases. Verify the normal entry point and update docs/PROGRESS.md and docs/PHASE_LOG.md with actual results before advancing. Use Python 3.12 and Node 24.

Analytics must come from parameterized, allowlisted SQLite queries. Keep generation and ingestion separate from read-only runtime access. Preserve reporting semantics in data/metadata. Demo mode requires no credentials. Treat questions, model outputs, and data as untrusted. Never log secrets or raw questions. Keep credentials server-side. Do not push, publish, or deploy without explicit user authorization.

Run Python tests from the root and frontend checks from frontend/. Keep dependencies locked, data simulated and reproducible, and benchmark truth independent of runtime queries.
