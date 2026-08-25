"""Bizro credit-agent — Credit Readiness Report generation.

Consumes transaction data ONLY through the shared schema (server/schema.md) via a
read-only mirrored model layer; never imports voice/vision pipeline code or server
code (AGENTS.md §1). Server entrypoint: credit_agent.report.generate_report.
"""
