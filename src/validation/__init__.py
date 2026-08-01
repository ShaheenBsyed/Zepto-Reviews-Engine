"""
src.validation — insight quality assurance (Phase 6).

Modules:
  - faithfulness.py    : RAGAS / LLM-as-judge faithfulness scoring per insight
  - coverage.py        : Checks all 8 research questions have a corresponding insight
  - contradiction.py   : Pairwise LLM comparison to detect contradictory claims
  - spot_check.py      : Utilities for human reviewer spot-check workflow
  - eval_report.py     : Aggregates scores into outputs/eval_report.json
  - pipeline.py        : Phase 6 orchestrator
"""

from src.validation.faithfulness import FaithfulnessScorer
from src.validation.coverage import CoverageChecker
from src.validation.contradiction import ContradictionDetector
from src.validation.spot_check import SpotCheckManager
from src.validation.eval_report import EvalReportBuilder
from src.validation.pipeline import ValidationPipeline

__all__ = [
    "FaithfulnessScorer",
    "CoverageChecker",
    "ContradictionDetector",
    "SpotCheckManager",
    "EvalReportBuilder",
    "ValidationPipeline",
]
