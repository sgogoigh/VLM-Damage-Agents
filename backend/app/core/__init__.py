"""Standalone port of the Multi-Modal Evidence Review pipeline.

Self-contained: nothing here imports the sibling ``code/`` package. The public
entry point is ``run_pipeline`` (orchestrator), backed by the closed output
contract in ``contract`` and the provider registry in ``llm``.
"""
