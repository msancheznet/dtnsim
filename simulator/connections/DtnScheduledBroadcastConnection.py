"""
# ==================================================================================
# Author: Marc Sanchez Net
# Date:   03/14/2019
# Copyright (c) 2019, Jet Propulsion Laboratory.
# ==================================================================================
"""

from collections import defaultdict
from copy import deepcopy
import numpy as np
from simulator.connections.DtnAbstractConnection import DtnAbstractConnection, TransmissionError
from uuid import uuid1
from warnings import warn

from simulator.core.DtnSemaphore import DtnSemaphore

# Dictionary with all broadcast connection instances
# {origin: DtnScheduledBroadcastConnection}
_instances = {}

class DtnScheduledBroadcastConnection(DtnAbstractConnection):
    """ A scheduled connection that, if in view at the same time, propagates data to one or
        multiple destinations.

        This class manages internally all connections from an origin to one or multiple
        destinations. Therefore, it re-implements __new__ to return an already existing
        instance if you request an already existing broadcast connection
    """
    def __new__(cls, env, cid, orig, *args):
        # If you have an instance for this origin already,
        # return it
        if orig in _instances: return _instances[orig]

        # Create new instance
        instance = super().__new__(cls)

        # Store new instance
        _instances[orig] = instance

        return instance

    def __init__(self, env, cid, orig, dest, props):
        # Call parent constructor
        super(DtnScheduledBroadcastConnection, self).__init__(env, cid, orig, dest, props)

        # You need a semaphore per potential neighbor
        self.active = {n: False for n in env.nodes}

        # Map of messages in transit {dest: set(uuid1, uuid2, ...)}
        self.in_transit = defaultdict(set)

        # Flags to only initialize once
        self.initialized = False
        self.initialized_contacts = False

    def initialize(self, **kwargs):
        # If this connection is already running, skip
        if self.initialized: return

        # Call parent initializer
        super(DtnScheduledBroadcastConnection, self).initialize()

        # Mark as initialized
        self.initialized = True

    def initialize_contacts_and_ranges(self):
        # If this connection is already running, skip
        if self.initialized_contacts: return

        # Call parent
        super(DtnScheduledBroadcastConnection, self).initialize_contacts_and_ranges()

        # Initialize variables
        db = self.mobility_model.contacts_df

        # Get a copy of the contact plan for this contact
        cp = db.loc[db.orig == self.orig.nid].copy()

        # If no range intervals are found, invert orig, dest since connection is assumed
        # to be symmetric
        if cp.empty:
            cp = db.loc[db.dest == self.orig.nid]
            cp.rename({'orig':'dest', 'dest':'orig'}, axis=1, inplace=True)

        # If no range intervals are available at this point, exit
        if cp.empty: return

        # Sort range intervals
        cp = cp.sort_values(by=['tstart', 'tend'])

        # Drop rows with no duration
        self.contact_plan = cp[cp.duration != 0.0]

        # Create the broadcast intervals
        self.process_broacast_opportunities()

        # Mark the connection as initialized
        self.initialized_contacts = True

    def process_broacast_opportunities(self):
        # Initialize variables
        time      = []
        contacts  = []

        # Transform for fast processing
        df = self.contact_plan.copy().to_dict(orient='list')
        df['index'] = self.contact_plan.index.tolist()

        # Create list of with the cids active at any point in time
        while not np.isnan(df['tstart']).all() or not np.isnan(df['tend']).all():
            # Get the index for the next contact start. Catch the case where
            # you are just processing contact ends
            try:
                ts_idx = np.nanargmin(df['tstart'])
            except ValueError:
                ts_idx = np.nan

            # Get the index for the next contact end
            te_idx = np.nanargmin(df['tend'])

            # Grab the list of current contacts in view
            inview = set() if len(contacts) == 0 else deepcopy(contacts[-1])

            # Next event is contact end
            if np.isnan(ts_idx) or df['tstart'][ts_idx] > df['tend'][te_idx]:
                # Next event is a contact end
                time.append(df['tend'][te_idx])

                # Remove the contact that ends
                contacts.append(inview - {df['index'][te_idx]})

                # Set this event to NaN
                df['tend'][te_idx] = np.nan
                continue

            # Record the event time
            time.append(df['tstart'][ts_idx])

            # Add a new entry
            contacts.append(inview | {df['index'][ts_idx]})

            # Set this event to NaN
            df['tstart'][ts_idx] = np.nan

        # Initialize variables
        prev_t = -1
        to_remove = np.zeros(len(time), dtype=bool)

        # Figure out where duplicates are located
        for i, t in enumerate(time):
            if t > prev_t:
                prev_t = t
                continue
            to_remove[i - 1] = True

        # Eliminate duplicates
        self.time     = np.array(time)[~to_remove]
        self.contacts = np.array(contacts)[~to_remove]

        # If empty, issue warnings
        if len(self.time) != len(self.contacts):
            warn(f'Broadcast connection for {self.orig.nid} is wrong')
        if len(self.time) == 0:
            warn(f'Broadcast connection for {self.orig.nid} is empty')

    def run(self):
        # If you do not have a destination, return
        if len(self.time) == 0: yield self.env.exit()

        # If no contact information is available, return
        if len(self.contacts) == 0: yield self.env.exit()

        # Iterate over list of active contacts
        for t, cts in zip(self.time, self.contacts):
            # Wait until the next event
            yield self.env.timeout(max(0.0, t-self.t))

            # If at this point in time no one is in view, close
            if len(cts) == 0:
                self.current_contacts = {}
                self.current_dests    = {}
                self.in_transit       = defaultdict(set)
                self.close_connection()
                continue

            # Store current contacts
            self.current_contacts = cts
            self.current_dests    = {self.contact_plan.dest[cid] for cid in cts}

            # Eliminate all messages that were still in transit. This happens because
            # a message might not be completely delivered before the state of the
            # connection changes. See ``self.tx_to_neighbor``
            ended = set(self.in_transit.keys()) - self.current_dests
            for dest in ended:
                self.in_transit[dest] = set()

            # Open the connection
            self.open_connection()

    def set_contact_properties(self):
        # Initialize variables
        cp = self.contact_plan

        # Save connection properties
        self.prop_delay = {cp.dest[cid]: cp.range[cid] for cid in self.current_contacts}

    def do_transmit(self, peer_duct, message, BER, direction):
        # Hack to transform this function to a generator
        yield self.env.timeout(0)

        # Initialize variables
        valid_ducts = []

        # If the peer duct's parent is not the list of current destinations, then this message
        # is effectively lost since all routers will discard it.
        if peer_duct.parent.nid not in self.current_dests:
            self.lost.append(message)

        # Find all ducts where this message should be delivered
        for dest in self.current_dests:
            # Get the ducts for this destination towards this node
            ducts = self.env.nodes[dest].ducts[self.orig.nid]

            # If more than one duct, throw error. This is not allowed because you
            # don't have a criteria to choose between them
            if len(ducts) > 1:
                raise RuntimeError('Only one duct allowed in DtnScheduledBroadcastConnection')

            # Get the duct id
            duct_id = list(ducts.keys())[0]

            # Get another peer duct
            peer_duct2 = ducts[duct_id]['induct'] if direction == 'fwd' else ducts[duct_id]['outduct']

            # Add duct to list of valid ducts
            valid_ducts.append(peer_duct2)

        # Log start of transmission
        self.disp('{} starts being propagated', message)

        # Monitor the start of transmission
        self.monitor_tx_start(message)

        # Create a new UUID for this message
        m_uuid = uuid1()

        # Put the messages in transit
        for duct in valid_ducts:
            self.in_transit[duct.parent.nid].add(m_uuid)
            self.env.process(self.tx_to_neighbor(m_uuid, message, duct, BER, direction))

    def tx_to_neighbor(self, m_uuid, message, duct, BER, direction):
        # The duct's parent is the destination of this connection.
        # (duct.neighbor == self.orig)
        dest = duct.parent.nid

        # Do the actual transmission (This is a blocking call)
        try:
            yield from self.propagate(message, dest=dest)
        except TransmissionError:
            pass

        # If the uuid is not in the in-transit map, this message got lost
        if m_uuid not in self.in_transit[dest]:
            self.lost.append(message)
            return

        # Monitor end of transmission
        self.monitor_tx_end(message)

        # Remove the record for this message
        self.in_transit[dest].remove(m_uuid)

        # Create copy
        message = deepcopy(message)

        # Decide if message has error
        MER = (1 - (1 - BER) ** message.num_bits)
        if MER > 0: message.has_errors = (np.random.random() < MER)

        # Put the message in the destination node
        # Note: This is a non-blocking call since que in_queue
        # of a duct has infinite capacity
        if direction == 'fwd':
            duct.send(message)
        elif direction == 'ack':
            duct.ack(message)
        else:
            raise ValueError('Direction can only be "fwd" or "ack"')

    def transmission_error(self, message):
        err = '\n****** Cannot send message while connection is closed ******\n'
        err += 't={:.3f}:\tPropagation delay for connection ({}, {}) is None\n'.format(self.t, self.orig, self.dest)
        err += '\n' + repr(message) + '\n'
        err += 'Range interval table:\n'
        err += str(self.contact_plan)
        raise TransmissionError(err)