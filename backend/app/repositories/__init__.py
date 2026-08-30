"""Repository layer: the only place that talks SQL.

Milestone 1 ships the actor repository. Later milestones add graph and task
repositories behind their own interfaces (see the phase plan in README.md).
"""
from .actors import ActorRepository, ActorRow

__all__ = ["ActorRepository", "ActorRow"]
