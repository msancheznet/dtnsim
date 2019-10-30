"""
# ==================================================================================
# Author: Marc Sanchez Net
# Date:   03/25/2019
# Copyright (c) 2019, Jet Propulsion Laboratory.
# ==================================================================================
"""

import abc
from copy import deepcopy
import numpy as np

from simulator.routers.DtnAbstractRouter import DtnAbstractRouter, RtRecord
from simulator.routers.nwc_opportunistic import find_route_energy_estimate

class NwcAbstractRouter(DtnAbstractRouter):

    def initialize(self):
        # Get the contact plan
        self.cp  = self.parent.mobility_model.contacts_df.copy()
        self.cp2 = self.prepare_contact_plan()

        # Get static state info for all nodes
        #self.state = {nid: {'energy_usage_tx':  node.P_radio,
        #                    'energy_usage_rx':  node.P_radio,
        #                    'battery_capacity': node.battery,
        #                    'battery_level':    node.battery,
        #                    'data': []}
        #              for nid, node in self.env.nodes.items()}
        self.state = {}
        self.state['node']             = np.array(list(self.env.nodes))
        self.state['energy_usage_tx']  = np.array([node.P_radio for node in self.env.nodes.values()])
        self.state['energy_usage_rx']  = np.array([node.P_radio for node in self.env.nodes.values()])
        self.state['battery_capacity'] = np.array([node.battery for node in self.env.nodes.values()])
        self.state['battery_level']    = np.array([node.battery for node in self.env.nodes.values()])

        # Hard-code the preferred path
        #self.preferred_path = ['node_4', 'node_3', 'node_2', 'node_1', 'base_station']
        self.preferred_path = [f'node_{i}' for i in range(10,0,-1)]
        self.preferred_path.append('base_station')

    def find_routes(self, bundle, first_time, **kwargs):
        # Increase counter
        self.counter += 1

        # Get the state information for all nodes
        for nid, node in self.env.nodes.items():
            idx = self.state['node'] == nid
            self.state['battery_level'][idx] = node.battery
            #self.state[nid]['battery_level'] = node.battery

        # Call routing function
        try:
            selected, contact_id, _ = self.find_best_route(bundle, first_time, **kwargs)
        except:
            selected = None

        # If none selected, return
        if selected is None: return 'limbo', None

        # Create routing record
        try:
            con = self.cp.xs(contact_id).to_dict()
        except:
            pass
        con['cid'] = contact_id
        route = {'EAT': np.inf,
                 'contacts': (contact_id,),
                 'dest': bundle.dest,
                 'limit_cid': contact_id,
                 'nhops': 1,
                 'orig': self.parent.nid,
                 'route': [selected],
                 'tend': con['tend'],
                 'tstart': con['tstart']}
        rec   = RtRecord(bundle=bundle, contact=con, route=route, priority=0, neighbor=selected)

        return [rec], []

    @abc.abstractmethod
    def find_best_route(self, bundle, first_contact, **kwargs):
        pass

    def prepare_contact_plan(self):
        '''cp2 = self.cp.rename({'tstart':'time_start',
                              'tend': 'time_end',
                              'rate': 'bandwidth',
                              'orig': 'origin',
                              'dest': 'destination',
                              'range': 'latency',
                              }, axis=1)

        tmp = cp2.to_dict(orient='index')

        for k, v in tmp.items():
            v['cid'] = k

        return list(tmp.values())'''
        cp2 = {c: self.cp.loc[:,c].values for c in self.cp}
        cp2['cid'] = np.arange(self.cp.shape[0], dtype=int)

        return cp2






