"""Spec-coherence evaluation: does the shipped subject still conform to the
approved OpenSpec package that authorized it?

Stdlib-only. Advisory mode in the thin slice. No network, no secrets by
default. See openspec/changes/devgate-spec-coherence-service/design.md v2.

Decision-contract markers live on the implementing modules (result.py,
__main__.py), never on this docstring-only package initializer.
"""
