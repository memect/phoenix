"""评估器模块"""

from .object import ObjectEvaluator, ObjectEvaluationResult
from .list_of_objects import ListOfObjectsEvaluator, ListOfObjectsEvaluationResult

__all__ = [
    "ObjectEvaluator",
    "ObjectEvaluationResult",
    "ListOfObjectsEvaluator",
    "ListOfObjectsEvaluationResult",
]