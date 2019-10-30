import abc
from simulator.core.DtnSegments import LtpCancelSessionSegment
from .DtnAbstractDuct import DtnAbstractDuct

class DtnAbstractDuctLTP(DtnAbstractDuct, metaclass=abc.ABCMeta):
    """ Abstract LTP duct. It is subclassed by both DtnOutductLTP and DtnInductLTP
        to provide the following necessary common functionality:

        1) Requirement to re-implement ``initialize_ltp_session``, ``finalize_ltp_session``
           and ``run_ltp_session``.
        2) A radio to send data through a connection. The type of radio is configurable by
           the user through the .yaml file.
        3) A ``fail_manager`` that will redirect bundles that are not successfully delivered
           by the radio to the DTN node limbo for re-rerouting

        The core concept of LTP is a **session**, i.e. a process that will take care of sending a block
        of bundles from the outduct to induct. All re-tx required for a given block are handled by
        the same session. At any point in time, there can be any number of LTP sessions active
        since the underlying link can have long delays and therefore you do not want to wait for a session
        to end before starting another one.

        The LTP outduct creates a new session every time a new block of bundles is created. In contrast,
        an LTP induct creates a new session every time a new LTP Data Segment with a session_id not recognized
        is received. At the outduct, a session ends when all the data has been sent. At the induct, a session
        ends when the RA for the last RS has been received.

        Critical to this process is having unique session ids. For this purpose, we utilize the hash function
        available in Python. Note that this could result in non-unique ids due to possible hash collisions. This
        is mitigated by using the hash of the hex of the memory address of the block if a hash collision
        is detected. If that method fails, then an exception is raised.
    """
    def __init__(self, env, name, parent, neighbor):
        # Call parent constructor
        super(DtnAbstractDuctLTP, self).__init__(env, name, parent, neighbor)

        # Counter for session ids
        self.sid_counter = 0

        # Input queues for each LTP session
        # NOTE: to know if a session is active, check if an ltp_queue exists
        self.ltp_queues = {}

        # The radio for this duct
        self.radio = None

    def initialize(self, peer, *args, radio='', **kwargs):
        # Call parent initialization
        super(DtnAbstractDuctLTP, self).initialize(peer, **kwargs)

        # Get the set of radios this duct can use
        self.radio = self.parent.available_radios[radio]

    def get_session_id(self, block):
        # First attempt
        sid = hash(block)
        if sid not in self.ltp_queues: return sid

        # Second attempt
        sid = hash(hex(id(block)))
        if sid not in self.ltp_queues: return sid

        # Raise an exception
        raise RuntimeError('Cannot create unique session_id at LTP duct {}'.format(self.name))

    def is_session(self, session_id):
        return session_id in self.ltp_queues

    def total_datarate(self, dest):
        return self.radio.datarate

    @property
    def radios(self):
        return {'radio': self.radio}

    @property
    def num_sessions(self):
        """ Returns the number of LTP session active """
        return len(self.ltp_queues)

    @property
    def ltp_sessions(self):
        """ List the current active LTP sessions """
        return tuple(self.ltp_queues.keys())

    @abc.abstractmethod
    def run_ltp_session(self, *args, **kwargs):
        pass

    @abc.abstractmethod
    def initialize_ltp_session(self, *args, **kwargs):
        pass

    @abc.abstractmethod
    def finalize_ltp_session(self, *args, **kwargs):
        pass

    def success_manager(self):
        while self.is_alive:
            # Wait for a block that was successfully transmitted
            bundle = yield from self.success_queue.get()

            # If the parent does not have a success queue, i.e. it is
            # a node, you are done. This is admittedly not very neat,
            # but necessary to make ParallelLTP work
            if not hasattr(self.parent, 'success_queue'): continue

            # Put in the parent's queue
            yield from self.parent.success_queue.put(bundle)

    def radio_error(self, message):
        """ Called from ``DtnAbstractRadio`` to signal that an error
            has occurred during the transmission of a message.

            :param Message message: The message that cause the error
        """
        # Get session id
        sid = message.session_id

        # Send a signal to cancel the LTP session
        self.cancel_ltp_session(sid)

    def fail_manager(self):
        while self.is_alive:
            # Wait for a block that was not successfully transmitted
            # by an LTP session
            bundle = yield from self.to_limbo.get()

            # If the parent does not have a success queue, i.e. it is
            # a node, you are done. This is admittedly not very neat,
            # but necessary to make ParallelLTP work
            if not hasattr(self.parent, 'success_queue'): continue

            # Put in the parent's queue
            yield from self.parent.to_limbo.put(bundle)

    def cancel_ltp_session(self, session_id):
        """ When a radio error occurs, cancel the LTP session that was
            involved in the transmission of this block. This will be caught
            by the ``run_ltp_session`` in ``DtnOutductLTP`` and ``DtnInductLTP``.

            :param session_id: Session to cancel
        """
        self.env.process(self.do_cancel_ltp_session(session_id))

    def do_cancel_ltp_session(self, session_id):
        # Create a Cancel Session Segment to close this LTP session
        cancel = LtpCancelSessionSegment(session_id)

        # Put this in the queue of segments for this session
        # Use expedited priority so that it gets executed immediately
        yield from self.ltp_queues[session_id].put(cancel, 0)