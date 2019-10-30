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
        flows = generate_bundles(traffic, id2alias, min_bundle_size=float(self.props.min_bundle_size),
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

# ============================================================================================================
# === TESTING OF TRAFFIC GENERATION
# ============================================================================================================

# Define test inputs
data_path    = '..\Scenario 2 - Data' + os.sep
network_file = data_path + 'Scenario 2 - Topology.xml'
traffic_file = data_path + 'Phobos Scenario 2-1 - Trials.scenario'

def test_traffic_generation(N=100):
    from simulator.utils.basic_utils import Timer
    from simulator.utils.time_utils import sec2hms
    from collections import Counter
    from simulator.utils.DtnIO import load_network_file, load_traffic_file

    # Initialize variables
    network = load_network_file(network_file)
    traffic = load_traffic_file(traffic_file)
    numbnd  = []
    empty   = []

    # Generate generators multiple times
    for i in range(N):
        timer = Timer(N=N)
        flows = generate_bundles(deepcopy(traffic), network)
        numbnd.append({fid: len(flow['Bundles']) for fid, flow in flows.items()})
        empty.append({fid for fid, flow in flows.items() if len(flow['Bundles']) == 0})
        timer.toc(i=i)

    # Format generators
    traffic = pd.DataFrame(traffic).transpose()
    traffic = traffic[['RowID', 'Activity', 'TransElementName', 'ReceiveElementName', 'StartTime',
                       'EndTime', 'Critical', 'DataType', 'Latency', 'DataRate', 'DutyCycle', 'Duration']]

    # Get bundle size
    bundles = {fid: flow['BundleSize']/1e6 for fid, flow in flows.items()}
    bundles = pd.DataFrame(bundles.values(), index=bundles.keys(), columns=['BundleSize[Mbit]'])

    # Count number of trials in which a flow generted no bundle
    empty   = Counter(x for xs in empty for x in xs)
    empty   = pd.DataFrame(empty, index=[1]).transpose()
    empty.columns = ['NoBundles']
    empty_pctg    = 100.0*empty/N
    empty_pctg.columns = ['NoBundles[%]']

    # Count the number of trials in which a flow generated at least one bundle
    non_empty = N - empty
    non_empty.columns  = ['YesBundles']

    # Compute the expected number of bundles. NOTE: THIS IS INCORRECT AS IT DOES NOT
    # TAKE INTO ACCOUNT THE DURATION OF PERIODS
    expected_non_empty = np.minimum((traffic.DutyCycle*N), N).to_frame('ExpYesBundle')
    diff   = (non_empty.iloc[:,0] - expected_non_empty.iloc[:,0]).to_frame('Diff')

    # Compute statistics oin the number of bundles generated per experiment
    numbnd = pd.DataFrame(numbnd).transpose()
    numbnd.columns = ['Exp{}'.format(i) for i in numbnd.columns]
    mean   = numbnd.mean(axis=1).to_frame('Mean')
    median = numbnd.median(axis=1).to_frame('Median')
    std    = numbnd.std(axis=1).to_frame('Std')

    # Compute and format Ton and Toff for the generators generation process
    Toff   = ((1/traffic.DutyCycle-1)*traffic.Duration).apply(lambda x: sec2hms(x)).to_frame('Toff')
    traffic.Duration = traffic.Duration.apply(lambda x: sec2hms(x))

    # Compute the amount of data volume that was not sampled
    dv1 = ((traffic.EndTime - traffic.StartTime) / np.timedelta64(1, 's'))*traffic.DutyCycle*traffic.DataRate
    dv2 = (bundles.loc[:, 'BundleSize[Mbit]'])*median.Median

    # Compose the final result table
    result = pd.concat([traffic, Toff, bundles, dv1.to_frame('ExpDataVol'), dv2.to_frame('MedianDataVol'),
                        expected_non_empty, non_empty, diff, empty, empty_pctg, mean, median, std, numbnd], axis=1)
    result.loc[pd.isnull(result.NoBundles), 'NoBundles'] = 0.0
    result.loc[pd.isnull(result.YesBundles), 'YesBundles'] = N
    idx = pd.isnull(result.Diff)
    result.loc[idx, 'Diff'] = np.abs(N-expected_non_empty.loc[idx, 'ExpYesBundle'])
    result = result.sort_values(by=['Diff'], ascending=False)

    # Check that the data flows never sampled do not exceed 10% of total data volume in simulation
    idx = result.NoBundles == N
    dv2 = ((result.EndTime[idx]-result.StartTime[idx])/np.timedelta64(1, 's'))*result.DutyCycle[idx]*result.DataRate[idx]
    pctg_sampled = 100*dv2.sum()/dv1.sum()
    if pctg_sampled >= 10: warn('Error: The total data volume sampled differs by more than 10% from the expected data volume for this scenario')
    print('{}\% of data volume was never sampled in the {} scenarios'.format(pctg_sampled, N))

    # Calculate statistics on total data volume sent in [Mbit]
    dv = numbnd.multiply(bundles.loc[:, 'BundleSize[Mbit]'], axis='index').sum()
    avg_dv, std_dv = dv.mean(), dv.std()

    return result, pctg_sampled, avg_dv, std_dv

def run_traffic_generation_experiments(i, Nmin=1, Nmax=1000, Ndelta=50):
    vals, mean_dv, std_dv = {}, {}, {}
    for n in range(Nmin, Nmax, Ndelta):
        _, vals[n], mean_dv[n], std_dv[n] = test_traffic_generation(N=n)
    df1 = pd.DataFrame(vals.values(), index=vals.keys(), columns=['MissedDataVol'])
    df2 = pd.DataFrame(mean_dv.values(), index=mean_dv.keys(), columns=['MeanDataVol'])
    df3 = pd.DataFrame(std_dv.values(), index=std_dv.keys(), columns=['StdDataVol'])
    return pd.concat([df1, df2, df3], axis=1)

def traffic_generation_stats():
    from multiprocessing import Pool
    pool = Pool(processes=5)
    dfs  = pool.map(run_traffic_generation_experiments, range(100))
    pool.close()
    pool.join()
    for i, df in enumerate(dfs): df['eid'] = i
    return pd.concat(dfs, axis=0)

if __name__ == '__main__':
    # Simple test
    result, pctg_sampled = test_traffic_generation(N=2)
    
    # Advanced test
    #result.to_excel('Bundle Generation.xlsx')
    #exp = traffic_generation_stats()