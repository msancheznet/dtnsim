from simulator.ducts.DtnAbstractDuct import DtnAbstractDuct

class DtnInductBasic(DtnAbstractDuct):
    duct_type = 'induct'

    def __init__(self, env, name, parent, neighbor):
        super(DtnInductBasic, self).__init__(env, name, parent, neighbor)

    def initialize(self, peer, radio='', **kwargs):
        # Call the parent initializer
        super(DtnInductBasic, self).initialize(peer)

        # Find the data rate of the radio. This is just boilerplate at in this
        # duct since the radio object does not do anything. But in more complex
        # ducts, the radio object is used extensively.
        self.datarate = self.parent.available_radios[radio].datarate

    @property
    def total_datarate(self):
        return self.datarate

    @property
    def radios(self):
        return {}

    def radio_error(self, message):
        pass

    def run(self):
        while self.is_alive:
            # Wait until there is something to transmit
            bundle = yield from self.in_queue.get()

            # Deliver to DTN node for routers
            self.parent.forward(bundle)

    def __str__(self):
        return "<BasicInduct {}-{}>".format(self.parent.nid, self.neighbor)

    def __repr__(self):
        return str(self)