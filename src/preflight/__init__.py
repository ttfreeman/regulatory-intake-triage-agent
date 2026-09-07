"""Preflight Intake Analysis Assistant.

A lightweight, deterministic-by-default situational-awareness pass that runs
BEFORE the triage workflow. It profiles the dataset, flags data-quality
issues, detects likely duplicate/repeat-contact chains, flags prompt
injection and sensitive-data signals, clusters complaints by theme, and
(optionally, if Gemini is enabled) asks an LLM to narrate the findings.

This module never assigns a severity tier, contravention assessment, or
routing decision - those are the triage workflow's job (see src/classify.py,
src/router.py). Preflight only produces a review-priority forecast to help a
human decide where to look first.
"""
