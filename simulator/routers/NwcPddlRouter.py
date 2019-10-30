"""
# ==================================================================================
# Author: Marc Sanchez Net
# Date:   03/25/2019
# Copyright (c) 2019, Jet Propulsion Laboratory.
# ==================================================================================
"""

from simulator.routers.NwcAbstractOpportunisticRouter import NwcAbstractRouter
from simulator.routers.nwc_pddl_router import find_route_pddl

class NwcPddlRouter(NwcAbstractRouter):

    def find_best_route(self, bundle, first_contact, **kwargs):
        # Call routing function
        return find_route_pddl(bundle_size=bundle.data_vol/1e6,
                                      contact_plan=self.cp2,
                                      current_time=self.t,
                                      nodes_state=self.state,
                                      source=self.parent.nid,
                                      target=bundle.dest,
                                      preferred_path=self.preferred_path)

    def prepare_contact_plan(self):
        plan = super().prepare_contact_plan()

        for contact in plan:
            contact['bandwidth'] /= 1e6

        return plan



