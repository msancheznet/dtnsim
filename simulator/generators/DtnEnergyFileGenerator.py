"""
# ==================================================================================
# Author: Marc Sanchez Net
# Date:   03/22/2019
# Copyright (c) 2019, Jet Propulsion Laboratory.
# ==================================================================================
"""

from simulator.generators.DtnFileGenerator import DtnFileGenerator

class DtnEnergyFileGenerator(DtnFileGenerator):

    def initialize(self):
        # Initialize variables
        self.on_power = self.props.on_power
        self.on_time  = self.props.on_power

        # Call parent initializer
        super().initialize()

    def new_bundle(self, dest):
        # Account for energy lost
        self.parent.battery -= self.on_power*self.on_time

        # Return parent
        return super().new_bundle(dest)