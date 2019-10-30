from abc import ABCMeta, abstractmethod
from simulator.core.DtnCore import Simulable

class DtnAbstractEndpoint(Simulable, metaclass=ABCMeta):

    def __init__(self, env, parent):
        super().__init__(env)

        # Store the parent DtnNode
        self.parent = parent

    @property
    def is_alive(self):
        return self.parent.is_alive

    @abstractmethod
    def initialize(self, *args, **kwargs):
        pass

    @abstractmethod
    def put(self, *args, **kwargs):
        pass