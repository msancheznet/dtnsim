# -*- coding: utf-8 -*-

from simulator.ducts.DtnAbstractDuct import DtnAbstractDuct

class DtnOutductBasic(DtnAbstractDuct):
    duct_type = 'outduct'

    def __init__(self, env, name, parent, neighbor):
        super(DtnOutductBasic, self).__init__(env, name, parent, neighbor)

    def initialize(self, peer, radio='', **kwargs):
        # Call the parent initializer
        super(DtnOutductBasic, self).initialize(peer)

        # Get all the connections for this duct
        self.outcons = {d: self.env.connections[o, d] for o, d in
                           self.env.connections if o == self.parent.nid}

        # Get the radio
        self.radio = self.parent.available_radios[radio]

    def total_datarate(self, dest):
        return self.radio.datarate

    @property
    def radios(self):
        return {}

    def radio_error(self, message):
        pass

    def run(self):
        """ Send through a BasicRadio that is shared by all outducts """
        while self.is_alive:
            # Wait until there is something to transmit
            message = yield from self.in_queue.get()

            # Log ready to transmit
            self.disp('{} starts transmission', message)

            # Send through radio
            self.radio.put(self.neighbor, message, self.peer, self.transmit_mode)

            # Notify the success of this message
            self.notify_success(message)

            # Log exit of convergence layer
            self.disp('{} ends transmission (no propagation delay yet)', message)
        
    def deprecated_run(self):
        """ DEPRECATED! DOES NOT USE A RADIO AS A SHARED RESOURCE! """
        # Get the relevant connection
        conn = self.outcons[self.neighbor]

        while self.is_alive:
            # Wait until there is something to transmit
            message = yield from self.in_queue.get()
            
            # Log ready to transmit
            self.disp('{} starts transmission', message)

            # Transmit the bundle
            while True:
                # Wait while bundle is being transmitted
                yield self.env.timeout(message.num_bits/self.datarate)  # UNCOMMENT FOR SIMULATION

                # If the connection has ended by now, then wait for next contact
                # to this neighbor. When it starts, you have to retransmit, hence the while.
                # NOTE: This model a bundle that does not have time to exit at the convergence layer.
                #       I assume that it will be re-transmitted, as if there was an ARQ mechanism or similar.
                if conn.active.is_red: yield conn.active.green; continue

                # If you reach this point then the bundle has been transmitted while the connection
                # is active, so you can exit the loop
                break
            
            # Transmit the message through an error-less connection.
            # This is a non-blocking call since the bundle is out in transit
            conn.transmit(self.peer, message, 0.0)

            # Notify the success of this message
            self.notify_success(message)

            # Log exit of convergence layer
            self.disp('{} ends transmission (no propagation delay yet)', message)

    def __str__(self):
        return "<BasicOutduct {}-{}>".format(self.parent.nid, self.neighbor)

    def __repr__(self):
        return str(self)