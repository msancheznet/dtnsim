from simulator.core.DtnQueue import DtnQueue
from simulator.radios.DtnAbstractRadio import DtnAbstractRadio

class DtnBasicRadio(DtnAbstractRadio):

    def __init__(self, env, parent, shared=True):
        # Call parent constructor
        super(DtnBasicRadio, self).__init__(env, parent, shared)

        # Create input queue
        self.in_queue = DtnQueue(env)

    @property
    def stored(self):
        df = self.in_queue.stored
        df['where'] = 'radio'
        return df

    def initialize(self, rate=0, BER=0, J_bit=0, **kwargs):
        # Store configuration parameters
        self.datarate  = rate
        self.BER       = BER
        self.J_bit     = J_bit

        # Call parent initializer
        super(DtnBasicRadio, self).initialize()

    def do_put(self, neighbor, message, peer, direction):
        # Create item to send
        item = (neighbor, message, peer, direction)

        # Add it to the queue
        yield from self.in_queue.put(item)

    def run(self, **kwargs):
        while self.is_alive:
            # Get the next segment to transmit
            item = yield from self.in_queue.get()

            # Depack item
            neighbor, message, peer, direction = item

            # Get the connection to send this message through
            conn = self.outcons[neighbor]

            # Compute total transmission time
            Ttx = message.num_bits/self.datarate

            # Apply delay for radio to transmit entire segment
            yield self.env.timeout(Ttx)

            # Count the energy consumed
            self.energy += message.num_bits * self.J_bit

            # Transmit the message through the connection.
            self.send_through_connection(message, conn, peer, direction)

    def send_through_connection(self, message, conn, peer, direction):
        """ Send a message through a connection

            :param Message message: The message to send
            :param conn: The connection to send the message through
            :param peer: The peer duct that will receive the message
            :param str direction: 'fwd' vs. 'ack'. By default 'fwd', use 'ack'
                                  for the acknowledgement messages of protocols
                                  like LTP (from dest to origin).
        """
        # This is a non-blocking call since the bundle is out in transit
        conn.transmit(peer, message, self.BER, direction=direction)