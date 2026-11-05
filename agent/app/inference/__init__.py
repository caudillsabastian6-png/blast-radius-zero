"""Inference adapters. Per the Challenge 1 rules, the ONLY real adapter is
Vultr Serverless Inference. The mock adapter exists for offline local tests
and key-less demo dry-runs; it performs no network calls at all."""

from .base import InferenceClient, InferenceError
from .mock import MockInferenceClient, demo_script_for
from .vultr import VultrServerlessClient

__all__ = [
    "InferenceClient",
    "InferenceError",
    "MockInferenceClient",
    "VultrServerlessClient",
    "demo_script_for",
]
