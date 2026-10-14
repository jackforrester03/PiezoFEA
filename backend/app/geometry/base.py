"""Interface for dimension-specific interpreters of a Project."""

from typing import Protocol, TypeVar

from app.schema import Project

ModelT = TypeVar("ModelT", covariant=True)


class InterpreterError(ValueError):
    """The project cannot be represented by this interpreter (message is user-facing)."""


class Interpreter(Protocol[ModelT]):
    def interpret(self, project: Project) -> ModelT: ...
