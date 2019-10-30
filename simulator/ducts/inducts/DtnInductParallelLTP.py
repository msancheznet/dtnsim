from simulator.core.DtnQueue import DtnQueue
from simulator.ducts.DtnAbstractDuctParallelLTP import DtnAbstractDuctParallelLTP

class DtnInductParallelLTP(DtnAbstractDuctParallelLTP):
    """ This induct just receives bundles from multiple underlying LTP inducts.
        Any forwarding request is then handled by a special handler to ensure
        that only one copy of a bundle is delivered to the DtnNode class.

        Note 1: This duct does not use the ``run`` function like all others.
                Instead, everything happens in the ``forward`` function since
                this makes is compatible the underlying LTP inducts
        Note 2: If the a peer outduct cancels its transmission, then a handler
                will be left lingering. This would not be acceptable in real-life,
                and therefore some sort of timer would need to be used (or a network
                management functionality) but it is ok here since the simulation will
                still finish.
    """
    duct_type = 'induct'

    def __init__(self, env, name, parent, neighbor):
        # Call parent constructor
        super(DtnInductParallelLTP, self).__init__(env, name, parent, neighbor)

        # Initialize variables
        self.fwd_handlers = set()
        self.fwd_queues   = {}

    def run(self):
        # Fake yield to force coroutine. It is not needed
        yield self.env.timeout(0)

    def forward(self, bundle):
        self.env.process(self.do_forward(bundle))

    def do_forward(self, bundle):
        """ Send the bundle to the node for routing to the next node.
            Do not forward multiple copies of the same bundle.
        """
        # Get handler session id
        hid = bundle.mid

        # If this bundle does not have a handler, create it
        if hid not in self.fwd_handlers:
            self.initialize_fwd_handler(hid)

        # Add the bundle to queue for the appropriate handler
        yield from self.fwd_queues[hid].put(bundle)

    def initialize_fwd_handler(self, hid):
        self.fwd_handlers.add(hid)
        self.fwd_queues[hid] = DtnQueue(self.env)
        self.env.process(self.run_fwd_handler(hid))

    def finalize_fwd_handler(self, hid):
        self.fwd_handlers.remove(hid)
        self.fwd_queues.pop(hid)

    def run_fwd_handler(self, hid):
        # Initialize variables
        counter = 0

        while self.is_alive:
            # Get the next bundle for this handler
            bundle = yield from self.fwd_queues[hid].get()

            # Update the counter
            counter += 1

            # If it is the first time you see this bundle, forward it to node
            if counter == 1: self.parent.forward(bundle)

            # If you have seen this bundle as many times as LTP sessions, you are done
            if counter == self.num_engines: break

        # Tear down this handler
        self.finalize_fwd_handler(hid)
