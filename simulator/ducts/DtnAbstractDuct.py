import abc
from simulator.core.DtnCore import Simulable
from simulator.core.DtnQueue import DtnQueue

class DtnAbstractDuct(Simulable, metaclass=abc.ABCMeta):
    """ An abstract duct. It operates 2 queues:

        1) in_queue: Queue where all bundles to be sent are placed.
        2) to_limbo: Queue where bundles that fail to be sent by the
                     convergence layer are placed. The ``fail_manager``
                     function in this class takes them an puts them in
                     the node's limbo queue for re-routing.
    """
    duct_type = None

    def __init__(self, env, name, parent, neighbor):
        super(DtnAbstractDuct, self).__init__(env)
        self.base_name = name        # See network architecture file (xml)
        self.parent    = parent      # DtnNode
        self.neighbor  = neighbor    # A string with the name of the neighbor
        self.monitor   = self.env.monitor

        # Connection through which data is sent
        #self.conn = env.connections[parent.nid, neighbor]

        # Add the queue for the convergence layer. DTN does not control it and
        # therefore it is assumed to be plain FIFO
        self.in_queue = DtnQueue(env)

        # Queue to store messages that were not successfully sent by the duct
        # and thus must be sent to the node's limbo
        self.to_limbo = DtnQueue(self.env)

        # Queue to store messages that were successfully sent by the duct
        self.success_queue = DtnQueue(self.env)

    def initialize(self, peer, **kwargs):
        # Peer duct (for an outduct it is an induct and vice versa)
        self.peer = peer

        # Activate the process for this convergence layer
        self.env.process(self.run())

        # Run the fail manager that returns bundles that failed to be sent for
        # re-routers
        self.env.process(self.fail_manager())

        # Run the success manager
        self.env.process(self.success_manager())

    @property
    def is_alive(self):
        return self.parent.is_alive

    @abc.abstractmethod
    def total_datarate(self, dest):
        pass

    @property
    def transmit_mode(self):
        return 'fwd' if self.duct_type == 'outduct' else 'ack'

    @property
    def name(self):
        return '{} {} ({}-{})'.format(self.__class__.__name__, self.base_name,
                                      self.parent.nid, self.neighbor)

    @property
    def stored(self):
        return self.in_queue.stored

    @property
    @abc.abstractmethod
    def radios(self):
        """ Returns a dictionary with the radios for this duct """
        pass

    def send(self, message):
        """ Pass a message to the duct for transmission
            This is a non-blocking call.
        """
        self.env.process(self.do_send(message))

    def do_send(self, message):
        # Add to the queue
        self.disp('{} delivered to {}', message, self.__class__.__name__)
        yield from self.in_queue.put(message)

    @abc.abstractmethod
    def run(self):
        pass

    def ack(self, message):
        """ This is called by a DtnConnection if you transmit something an specify direction
            equals "ack". It is more general than LTP, it is a generic mechanism to communicate
            "backwards" between two ducts (from rx's induct to tx's outduct) and no go through
            the in_queue (that takes message from the upper layer)
        """
        self.env.process(self.do_ack(message))

    def do_ack(self, message):
        """ A duct, by default should not be able to perform ack. See DtnOutductLTP for an example
            of implementation
        """
        # Fake yield to ensure this is a coroutine
        yield self.env.timeout(0)

        # This is not allowed unless this function is re-implemented
        # See DtnOutductLTP and DtnInductLTP for an example of how to use it
        raise RuntimeError('You cannot ACK in this convergence layer')

    def notify_success(self, message):
        self.env.process(self.do_notify_success(message))

    def do_notify_success(self, message):
        yield from self.success_queue.put(message)

    def success_manager(self):
        while self.is_alive:
            # Wait for a block that was successfully transmitted
            # Do nothing in the default implementation. Just here to
            # prevent the queue from filling indefinitely
            yield from self.success_queue.get()

    @abc.abstractmethod
    def radio_error(self, message):
        """ This function signals an LTP session that it needs to terminate because an error
            has occurred in the radio. The ``fail_manager`` will then be responsible to put
            the corresponding bundles to the node's limbo.
        """
        pass

    def fail_manager(self):
        while self.is_alive:
            # Wait for a block that was not successfully transmitted
            # by an LTP session
            bundle = yield from self.to_limbo.get()

            # Get the cid that needs to be excluded. This is not very neat, but
            # essentially reaches into the current DtnNeighborManager for this
            # neighbor and pulls the contact id
            cid = self.parent.queues[self.neighbor].current_cid

            # Send to node's limbo for re-routers
            self.parent.limbo(bundle, cid)