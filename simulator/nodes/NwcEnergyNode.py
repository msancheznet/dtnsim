"""
# ==================================================================================
# Author: Marc Sanchez Net
# Date:   03/22/2019
# Copyright (c) 2019, Jet Propulsion Laboratory.
# ==================================================================================
"""

from simulator.nodes.DtnNode import DtnNode

class NwcEnergyNode(DtnNode):
    def initialize(self):
        # Call parent initializer
        super().initialize()

        # Initialize battery state
        self.battery = self.props.battery
        self.P_hotel = self.props.P_hotel
        self.P_radio = self.props.P_radio
        self.rate    = self.props.battery_rate

        # Indicates when a node dies because of battery
        self.death_time = -1

        # Start battery monitor
        self.env.process(self.battery_manager())

    @property
    def is_alive(self):
        # Check if this node is still alive
        alive = super().is_alive and self.battery > 0

        # Record death if necessary
        if not alive and self.death_time == -1:
            self.death_time = self.t

        return alive

    def battery_manager(self):
        # Initialize variables
        pwr = self.P_hotel

        # Do until this node dies
        while self.is_alive:
            # Wait for one second
            yield self.env.timeout(self.rate)

            # Decrease battery by drive and hotel load
            self.battery -= max(pwr*self.rate, 0)

    def limbo_manager(self):
        # Initialize variables
        self.num_bnd = {}
        dt = self.props.limbo_wait

        while self.is_alive:
            # Wait for a while
            yield self.env.timeout(dt)

            # Get everything from the queue
            items = yield from self.limbo_queue.get_all(check_empty=False)

            self.num_bnd[self.t] = len(items)

            # Put all items in the input queue
            for item in items:
                yield from self.in_queue.put(item)