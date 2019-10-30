import abc
from simulator.core.DtnCore import Simulable

class DtnAbstractDuctSelector(Simulable, metaclass=abc.ABCMeta):
    """ An abstract duct selector. """

    # Types of connections in the network
    _types = None

    def __init__(self, env, parent):
        super(DtnAbstractDuctSelector, self).__init__(env)
        self.parent = parent

    def reset(self):
        # Reset static variables
        self.__class__._types = None

    def initialize(self):
        # Initialize static variables only once
        if self.__class__._types: return

    def get_ducts(self, neighbor):
        # Get the ducts from the parent
        ducts = self.parent.ducts[neighbor]

        # If no ducts present in this node, throw error
        if len(ducts) == 0:
            raise ValueError(f'No outducts from {self.parent.nid} to {neighbor}')

        return ducts

    @abc.abstractmethod
    def select_duct(self, neighbor, bundle):
        pass