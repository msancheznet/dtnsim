import abc
import numpy as np
import pandas as pd
from simulator.core.DtnCore import Simulable, TimeCounter
from simulator.core.DtnSemaphore import DtnSemaphore

class DtnAbstractConnection(Simulable, metaclass=abc.ABCMeta):
    def __init__(self, env, cid, orig, dest, props):
        """ Initialize a DtnAbstractConnection

            :param DtnSimEnvironment env: Simulation environment
            :param str cid: Connection id as specified in the YAML file (not in the contact plan)
            :param str orig: Id of origin node
            :param str dest: Id of destination node
            :param dict props: Properties of this connection type
        """
        super(DtnAbstractConnection, self).__init__(env)

        # Set connection props
        self.type    = env.config['network'].connections[cid].type
        self.props   = props
        self.monitor = self.env.monitor

        # Connect to origin and destination
        self.orig = self.env.nodes[orig]
        self.dest = self.env.nodes[dest]

        # Lock that indicates when this connection is closed
        self.active = False

        # Propagation delay
        self.prop_delay = None

        # List of messages that are lost
        self.lost = []

        # Monitor when data departs
        self.sent = {}

    @property
    def cid(self):
        return '-'.join((self.orig.nid, self.dest.nid))

    @property
    def total_datarate(self):
        return sum(d['outduct'].total_datarate(self.dest.nid) for d in self.ducts.values())

    def list_lost(self):
        return pd.DataFrame([b.to_dict() for b in self.lost]) \
                             if self.monitor else pd.DataFrame()

    def list_sent(self):
        return pd.DataFrame.from_dict(self.sent, orient='index').reset_index()

    def initialize(self, start_connection=True):
        # Fill out the ducts structure. This is used to compute the total
        # date rate across all outducts, which in turn limits the rate of
        # data coming out of the queue (see ``total_datarate``)
        self.ducts = {d: self.orig.ducts[self.dest.nid][d] for d in self.config[self.type].ducts}

        # Run the connection, i.e. make it open/close
        # at the appropriate times
        if start_connection:
            self.env.process(self.run())

    def initialize_contacts_and_ranges(self):
        # Find the mobility model to use
        self.mobility_model = self.env.mobility_models[self.props.mobility_model]

    @abc.abstractmethod
    def run(self, *args, **kwargs):
        pass

    def open_connection(self, *args, **kwargs):
        # Set the properties of this contact
        self.set_contact_properties(*args, **kwargs)

        # Turn the active semaphore green to open the connection
        self.active = True

    def close_connection(self, *args, **kwargs):
        # Turn the active semaphore red
        self.active = False

    @abc.abstractmethod
    def set_contact_properties(self, *args, **kwargs):
        pass

    def transmit(self, peer_duct, message, BER, direction='fwd'):
        # If the connection is not active, return. This will effectively
        # drop the message here
        if self.active == False:
            self.lost.append(message)
            return

        # This will be a non-blocking call since a connection can propagate
        # multiple messages at the same time.
        self.env.process(self.do_transmit(peer_duct, message, BER, direction))

    def do_transmit(self, peer_duct, message, BER, direction):
        # Monitor the start of transmission
        self.monitor_tx_start(message)

        # Do the actual transmission (This is a blocking call)
        try:
            yield from self.propagate(message)
        except TransmissionError:
            # Log transmission failure
            self.disp('{} does not reach destination. Connection is closed while propagating', message)

            # Store lost message
            self.lost.append(message)

            # Finish transmission here if error
            return

        # Get message error probability and check that it is a valid number
        MER = (1 - (1 - BER) ** message.num_bits)

        # Add errors if necessary according to connection BER
        if MER > 0: message.has_errors = (np.random.random() < MER)

        # Monitor end of transmission
        self.monitor_tx_end(message)

        # Put the message in the destination node
        # Note: This is a non-blocking call since que in_queue
        # of a duct has infinite capacity
        if direction == 'fwd':
            peer_duct.send(message)
        elif direction == 'ack':
            peer_duct.ack(message)
        else:
            raise ValueError('Direction can only be "fwd" or "ack"')

    def propagate(self, message, dest=None):
        """ Simulate propagation delay """
        # If no destination, use the stored one
        if dest is None: dest = self.dest.nid

        # Increase the message propagation delay
        message.prop_delay += self.prop_delay[dest]

        # Wait the propagation time
        yield self.env.timeout(self.prop_delay[dest])

    def transmission_error(self, message):
        err = f'\n****** Transmission error at {self} ******\n'
        err += '\n' + repr(message) + '\n'
        raise TransmissionError(err)

    def monitor_tx_start(self, message):
        self.sent[str(message.mid)] = {'departure': self.t, 'dv': message.num_bits, 'type': message.__class__.__name__}

    def monitor_tx_end(self, message):
        self.sent[str(message.mid)]['arrival'] = self.t

    def __repr__(self):
        return '<{}: {}-{} ({})>'.format(self.__class__.__name__, self.orig.nid,
                                         self.dest.nid, self.type)

class TransmissionError(RuntimeError):
    pass