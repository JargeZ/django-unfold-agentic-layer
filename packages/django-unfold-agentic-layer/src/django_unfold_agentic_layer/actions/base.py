from abc import ABC, abstractmethod


class BaseLogicAction(ABC):
    @abstractmethod
    def execute(self): ...
