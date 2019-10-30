"""
# ==================================================================================
# Author: Marc Sanchez Net
# Date:   03/18/2019
# Copyright (c) 2019, Jet Propulsion Laboratory.
# ==================================================================================
"""

from simulator.routers.DtnCgrBasicRouter import DtnCgrBasicRouter

class AgcCgrRouter(DtnCgrBasicRouter):
    """ Router for the Agile Constellation study. This router does the following:
        1) To route, it uses the same algorithm as ``DtnCgrBasicRouter``
        2) It reads/modifies a bundle's AGC extension block

        The ACG extension block contains the ID of the expected destination for each
        hop
    """
    def find_routes(self, bundle, first_time, **kwargs):
        # If no AGC extension block, create empty one
        if 'AGC' not in bundle.eblocks:
            bundle.eblocks['AGC'] = self.parent.nid

        # If it is the first time that you are routing this and you received
        # this bundle erroneously (because of broadcasting), drop it
        if first_time and bundle.eblocks['AGC'] != self.parent.nid:
            return 'drop', None

        # Call parent router
        records_to_fwd, cids_to_exclude = super().find_routes(bundle, first_time, **kwargs)

        # If you do know how to route this, return
        if records_to_fwd is None: return None, None

        # Set the new value for the bundle's AGC extension block
        bundle.eblocks['AGC'] = records_to_fwd[0].contact['dest']

        return records_to_fwd, cids_to_exclude