# -*- coding: utf-8 -*-

import os
from collections import defaultdict
from copy import deepcopy
from warnings import warn

import numpy as np
import pandas as pd
from pathlib import Path
from simulator.core.DtnBundle import Bundle
from simulator.utils.DtnIO import load_traffic_file
from simulator.utils.DtnUtils import shift_traffic
from simulator.generators.DtnAbstractGenerator import DtnAbstractGenerator

# ============================================================================================================
# === DEFINE LATENCY CATEGORIES - THESE ARE CONSTANT
# ============================================================================================================

# Define latency
lat = np.array([[60, np.nan, np.nan],
                [60, np.nan, np.nan],
                [60, np.nan, 3600],
                [60,    60, np.nan],
                [60,   900,  21600],
                [60,   300,   3600],
                [60,   300, np.nan],
                [60,    60, np.nan],
                [60,   900,  21600],
                [60,   900,  21600],
                [60,   900,  21600],
                [60,   300, np.nan]])
lat = pd.DataFrame(data=1.0*lat, columns=['seconds','minutes','hours'],
                   index=['voice','biomedical','caution and warning','command and teleoperation',
                          'file','health and status','nav type 1 products','nav type 2 message',
                          'pao hd video','sci hd video','science','sd video'])

# ============================================================================================================
# === FUNCTIONS TO CREATE TWO STATE MARKOV PROCESS AND BUNDLE GENERATION TIMES
# ============================================================================================================

def two_state_markov_process(Tmin, Tmax, DutyCycle, Ton):
    # Initialize variables
    Tstart = 0
    Tend   = Tmax - Tmin
    Toff   = ((1 / DutyCycle) - 1) * Ton
    K      = 10
    ok     = False

    while not ok:
        # Initialize variables
        Ns = int(np.ceil(0.5*K*(Tend-Tstart)/(Ton + Toff)))

        # Handle special case where duty cycle is 1
        if DutyCycle == 1:
            state, times = True, Tend
        else:
            state   = np.random.uniform() < DutyCycle
            on_dur  = np.random.exponential(scale=Ton,  size=Ns)
            off_dur = np.random.exponential(scale=Toff, size=Ns)

            times = np.zeros(2*Ns)
            if state == True:
                times[0::2] = on_dur
                times[1::2] = off_dur
            else:
                times[0::2] = off_dur
                times[1::2] = on_dur

        # Finalize the process generated
        times =  np.insert(np.cumsum(times), 0, 0)
        states = np.zeros_like(times, dtype=bool)
        states[0::2] = state
        states[1::2] = not state

        # Validate the sequence
        if times[-1] >= Tend: ok = True
        else: K += 1

    # Trim end of generated sequence to match Tend
    times[times > Tend] = Tend
    idx = np.argmax(times == Tend)+1
    if idx != 0 and DutyCycle != 1.0 and idx != len(times):
        times  = times[0:idx]
        states = states[0:idx]

    # Shift times to Tmin, Tmax
    times += Tmin

    return times, states

def generate_markov_bundles(BS, Rb, Lat, Tmin, Tmax, DutyCycle, Ton):
    # Generate Markov intervals
    times, states = two_state_markov_process(Tmin, Tmax, DutyCycle, Ton)

    # Initial processing entry. If initial state is OFF, skip it
    ini = (states[0] == False)

    # Initialize variables
    t     = []
    buf   = 0
    state = True

    # Iterate over periods
    for i in range(ini, len(states)-1):
        # Handle OFF state only if buffer is not empty
        if state == False and buf != 0:
            # t_ref indicates the time at which the last bundle was sent. If no
            # bundles were ever sent, assume 0.
            t_ref = 0 if len(t) == 0 else t[-1]

            # If waiting for the start of the ON period will make you exceed
            # the latency requirement, send a bundle with half data half padding.
            while t_ref + Lat < times[i+1] and buf >= BS:
                t_ref = max(t_ref, times[i]) + Lat
                t.append(t)
                buf -= BS

        # Handle ON state
        if state == True:
            dv    = buf + Rb * (times[i+1] - times[i])
            N_bnd = int(np.floor(dv / BS))
            t_bnd = times[i] + np.arange(1,N_bnd+1)*(BS / Rb)
            if len(t_bnd) > 0: t_bnd -= buf/Rb
            t_bnd = t_bnd[t_bnd <= times[i+1]]
            t.extend(t_bnd)
            buf = dv - N_bnd * BS

        # Switch state
        state = not state

    # Add one last bundle add the end of t to transmit all unaccounted data.
    # Note that this bundle might have some padding data
    if buf > 0:
        t_ref = times[-1] if len(t) == 0 else t[-1]
        if states[-1] == False:
            t.append(t_ref + Lat)
        else:
            t.append(max(t_ref, times[-1])+Lat)
        buf = 0

    # return times at which a bundle is delivered, and the amount of data left at the end
    return t, buf

def generate_bundles(traffic, id2alias, min_bundle_size=1024, max_bundle_size=8e9, lat_frac=0.5):
    # Get a map from node alias to ids
    alias2id = {v: k for k, v in id2alias.items()}

    # Get simulation start time
    t0 = min([flow['StartTime'] for _, flow in traffic.items()])

    # Iterate over flows
    for fid, flow in traffic.items():
        # Get the numeric latency
        flow['Latency'] = lat.loc[flow['DataType'].lower(), flow['Latency'].lower()]

        # Compute bundle size
        bundle_lat = flow['Latency']*min(lat_frac, flow['DutyCycle'])
        bundle_sz  = min(max(min_bundle_size, int(flow['DataRate']*bundle_lat)), max_bundle_size)

        # Get start and time for this flow
        Tmin = (flow['StartTime'] - t0).total_seconds()
        Tmax = (flow['EndTime'] - t0).total_seconds()

        # Generate bundles
        t, _ = generate_markov_bundles(bundle_sz, flow['DataRate'], flow['Latency'],
                                       Tmin, Tmax, flow['DutyCycle'], flow['Duration'])

        # Store the bundle times and size
        flow['Bundles']    = t
        flow['BundleSize'] = bundle_sz
        flow['fid']        = fid

        # Transform names of flows from alias to ids
        flow['Orig'] = alias2id[flow['TransElementName']]
        flow['Dest'] = alias2id[flow['ReceiveElementName']]

    return traffic

# ============================================================================================================
# === SIMULATION CLASS
# ============================================================================================================

class DtnMarkovBundleGenerator(DtnAbstractGenerator):
    _all_flows = None

    def __init__(self, env, parent, props):
        super().__init__(env, parent, props)
        
        # Initialize variables
        self.traffic_file = self.config['globals'].indir / props.file

    def reset(self):
        # Reset static variables
        super().reset()
        self.__class__._all_flows = None

    def initialize(self):
        # Setting static variables only once
        if not self.__class__._all_flows: self.load_flows()

        # Get flows for this generator
        self.flows = self.__class__._all_flows[self.parent.nid]

        # Iterate over all flows for this generator
        for _, flow in self.flows.items(): self.env.process(self.run(flow))

    def load_flows(self):
        # Load generators file
        traffic = shift_traffic(load_traffic_file(self.traffic_file), self.epoch)

        # Generate bundles
        id2alias = {nid: dd.alias for nid, dd in self.config['network'].nodes.items()}
        flows = generate_bundles(traffic, id2alias, min_bundle_size=int(self.props.min_bundle_size),
                                 max_bundle_size=float(self.props.max_bundle_size),
                                 lat_frac=float(self.props.latency_fraction))

        # Log bundle generation
        for fid, flow in flows.items():
            if len(flow['Bundles']) == 0:
                self.disp('Flow {}: No bundles generated', fid)
            else:
                self.disp('Flow {}: {} bundles generated between t={:.3f} and t={:.3f}', fid, len(flow['Bundles']),
                          min(flow['Bundles']), max(flow['Bundles']))

        # Create a dictionary of dictionaries or dictionary: {Node ID: {flow id: {flow props}}
        d = defaultdict(dict)
        for fid, flow in flows.items(): d[flow['Orig']][fid] = flow

        # Store all the flows generated
        self.__class__._all_flows = d
        
    def run(self, flow):
        # If no bundles, return
        if len(flow['Bundles']) == 0: return
        
        # Initialize variables
        bnd_dt = np.insert(np.diff(flow['Bundles']), 0, flow['Bundles'][0])

        # Iterate over bundle transmit times
        for dt in bnd_dt:
            # Wait until next time to transmit
            yield self.env.timeout(dt)

            # Create a new bundle and record it
            new_bundle = Bundle.from_flow(self.env, flow)

            # Monitor the new bundle creation
            self.monitor_new_bundle(new_bundle)

            # Log the new bundle creation
            self.disp('{} is created at node {}', new_bundle, self.parent.nid)

            # Schedule routers of bundle
            self.parent.forward(new_bundle)

    def predicted_data_vol(self):
        """ Predicted data volume in [bits] """
        return sum(f['DataRate']*((f['EndTime']-f['StartTime']).total_seconds())
                   for f in self.flows.values())