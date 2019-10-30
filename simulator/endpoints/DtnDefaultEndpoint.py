from .DtnAbstractEndpoint import DtnAbstractEndpoint

class DtnDefaultEndpoint(DtnAbstractEndpoint):

    def __init__(self, env, parent):
        # Call parent constructor
        super().__init__(env, parent)

    def __len__(self):
        return len(self.data)

    def __bool__(self):
        return bool(self.data)

    def __iter__(self):
        return iter(self.data)

    def initialize(self):
        # All bundles will live in this list
        self.data = []

    def put(self, item):
        # If node is dead, skip
        if not self.is_alive:
            return

        # Store in list
        self.data.append(item)