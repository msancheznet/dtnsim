# -*- coding: utf-8 -*-

import numpy as np
from simulator.connections.DtnAbstractConnection import DtnAbstractConnection, TransmissionError
from simulator.utils.DtnIO import prepare_contact_plan

class DtnScheduledConnection(DtnAbstractConnection):
    """ A connection propagates a data unit from a transmitting node to a receiving
        node. It implements the following functionality:

        1) Initialization method to set connection properties such as propagation
        2) A non-blocking transmit method, since multiple data units can be sent at
           the same time.
        3) A propagation time manager that sets the state of the connection (green vs.
           red as a function of the contact plan).

        .. Tip:: A convergence layer that wants to transmit using a DtnConnection must first
                 do ``yield self.conn.active.green`` to ensure the connection is open (see
                 ``DtnOutductBasic`` as an example.
        .. Tip:: A DtnConnection operates using ``messages`` instead of bundles. This is
                 because you could propagate LTP segments, or IP packets.
    """
    def __init__(self, env, cid, orig, dest, props):
        """ Initialize a DtnScheduleConnection

            :param DtnSimEnvironment env: Simulation environment
            :param str cid: Connection id as specified in the YAML file (not in the contact plan)
            :param str orig: Id of origin node
            :param str dest: Id of destination node
            :param dict props: Properties of this connection type
        """
        # Call parent constructor
        super(DtnScheduledConnection, self).__init__(env, cid, orig, dest, props)

        # Current contact id as specified in the contact plan
        self.contact_id = None

        # Contact plan for this connection
        self.contact_plan = None

    def initialize_contacts_and_ranges(self):
        # Call parent
        super().initialize_contacts_and_ranges()

        # Prepare the contact plan
        self.contact_plan = prepare_contact_plan(self.orig.nid,
                                                 self.dest.nid,
                                                 self.mobility_model.contacts_df)

    def run(self):
        # If no contact plan available, exit
        if self.contact_plan is None: yield self.env.exit()

        # If contact plan has not valid entries, exit
        if self.contact_plan.empty: yield self.env.exit()

        # Iterate over range intervals
        for cid, row in self.contact_plan.iterrows():
            # Wait until the contact starts
            yield self.env.timeout(max(0.0, row['dtstart']))

            # Open the connection
            self.open_connection(row['range'])

            # Wait until the contact ends
            yield self.env.timeout(row['duration'])

            # Close the connection
            self.close_connection()

    def set_contact_properties(self, prop):
        ''' Set properties of the current contact. '''
        self.prop_delay = {self.dest.nid: prop}

    def transmission_error(self, message):
        err = '\n****** Cannot send message while connection is closed ******\n'
        err += 't={:.3f}:\tPropagation delay for connection ({}, {}) is None\n'.format(self.t, self.orig, self.dest)
        err += '\n' + repr(message) + '\n'
        err += 'Range interval table:\n'
        err += str(self.contact_plan)
        raise TransmissionError(err)

