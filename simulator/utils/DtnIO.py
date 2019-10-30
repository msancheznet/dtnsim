import ast
from copy import deepcopy
from lxml import etree
import networkx as nx
import numpy as np
from operator import itemgetter
import pandas as pd
from collections import defaultdict
import json
from pathlib import Path
import os
from warnings import warn, catch_warnings, simplefilter
from simulator.utils.DtnUtils import load_class_dynamically

# ============================================================================================================
# === FUNCTIONS TO PROCESS CONTACT PLAN FOR A SCHEDULED CONNECTION
# ============================================================================================================

def prepare_contact_plan(orig, dest, cp):
    """ Prepare a contact plan for a connection by filtering out not relevant contacts

        :param orig: Name of the origin node
        :param dest: Name of the destination node
        :param cp:   Contact plan in dataframe format
        :return:     Filtered contact plan as a dataframe
    """
    # Initialize variables
    db = cp.copy(deep=True)

    # Get a copy of the contact plan for this contact
    cp = db.loc[(db.orig == orig) & (db.dest == dest)].copy()

    # If no range intervals are found, invert orig, dest since connection is assumed
    # to be symmetric
    if cp.empty: cp = db.loc[(db.orig == dest) & (db.dest == orig)]

    # If no range intervals are available at this point, exit
    if cp.empty: return

    # Sort range intervals
    cp = cp.sort_values(by=['tstart', 'tend'])

    # Compute the delta in time between gate openings and closings
    if cp.shape[0] != 1:
        cp['dtstart'] = np.insert(cp.tstart.iloc[1:].values - cp.tend.iloc[0:-1].values,
                                  0, cp.tstart.iloc[0])
    else:
        cp['dtstart'] = cp.tstart.iloc[0]

    # Drop rows with no duration
    cp = cp[cp.duration != 0.0]

    # Warn the user if something might be wrong
    if any(cp.dtstart < 0): warn(f'{orig}-{dest}: Check range intervals, dtstart < 0')
    if any(cp.dtstart < 0): warn(f'{orig}-{dest}: Check range intervals, duration < 0')

    return cp

# ============================================================================================================
# === FUNCTIONS TO PROCESS SCENARIO FILE
# ============================================================================================================

def load_traffic_file(file, as_dict=True):
    # Read data from file
    with open(file, 'r') as f: data = f.read()
    lines = data.split('\n')
    headers = lines[0].split('\t')

    # Discard columns that we are not interested in
    elim = ['ID', 'Links 2::Name', 'Type ID', 'Link Type Data 3::Security Requirement Result',
            'Link Type Data 3::Essential', 'First Interval State(s) & State Change Times (UTC):',
            'Links 2::Passthrough Parent ID', 'Links 2::TF Direct to DSH',
            'Links 2::TF Direct to Earth', 'Links 2::TF Direct to Relay']
    pos = [headers.index(h) for h in headers if h not in elim]

    # Construct data
    records = [itemgetter(*pos)(l.split('\t')) for l in lines[1:] if l]
    data = []

    for i, record in enumerate(records):
        d = {}
        d['RowID'] = int(i)
        d['Activity'] = record[0]
        d['LinkID'] = int(record[1])
        d['TransElementName'] = record[2]
        d['PassthroughConnectionID'] = int(record[3]) if record[3] != '' else -1
        d['ReceiveElementName'] = record[4]
        d['Latency'] = record[5]
        d['DataType'] = record[6]
        d['StartTime'] = pd.Timestamp(record[7]).replace(year=2034)
        d['EndTime'] = pd.Timestamp(record[8]).replace(year=2034)
        d['DataRate'] = 1e6*float(record[9])    # Transform to bps
        d['DutyCycle'] = float(record[10])
        d['Duration'] = float(record[11])
        data.append(d)

    # Initialize variables
    df = pd.DataFrame.from_dict(data).set_index(['LinkID', 'PassthroughConnectionID'])
    data = []
    processed = set()

    # Iterate over flows and decide which ones are critical
    for link_id, new_df in df.groupby(level=0):
        # Get the passthrough connection ID
        pid = new_df.index.get_level_values(1).values
        assert np.all(pid == pid[0]), 'All passthrough connections ID should be equal. Check:\n{}'.format(new_df)
        pid = pid[0]

        # Skip if already processed. Otherwise mark this combo (link_id, pid) as processed
        if (link_id, pid) in processed: continue
        else: processed.add((link_id, pid))

        # If the passthrough connection ID is null, then this is not critical
        if pid == -1:
            new_data = new_df.copy(deep=True)
            new_data['Critical'] = False
            data.append(new_data)
            continue

        # Otherwise, you need to see which flows are critical and which are not. Get the
        # complimentary flows
        other_df = df.loc[pid, link_id]

        # The dataframe with more rows has to contain the non-critical data
        if new_df.shape[0] > other_df.shape[0]:
            df1, df2 = other_df, new_df
        elif new_df.shape[0] < other_df.shape[0]:
            df1, df2 = new_df, other_df
        else:
            # If new_df and other_df are have the same data types, then they are critical
            df1, df2 = new_df, None

        # Process critical flows
        df1 = df1.copy(deep=True)
        df1['Critical'] = True
        data.append(df1)

        # Process non-critical flows if necessary
        if df2 is not None:
            df2 = df2.copy(deep=True)
            df2['Critical'] = False
            data.append(df2)

        # Mark the other_df also as processed
        processed.add((pid, link_id))

    # Return data as a dictionary
    df = pd.concat(data).reset_index(drop=True)

    return df.to_dict(orient='index') if as_dict else df

# ============================================================================================================
# === FUNCTIONS TO PROCESS THE NETWORK ARCHITECTURE FILE
# ============================================================================================================

def load_network_file(filepath, alias=None):
    # Initialize variables
    root    = etree.parse(filepath).getroot()
    net     = nx.DiGraph()

    # Add all nodes
    for node in root.findall('node'):
        attribs = {'state': None}
        attribs.update(node.attrib)
        attribs['relay'] = attribs['relay'].lower() == 'true'
        net.add_node(node.get('id'), **attribs)

    # Load all the connection definitions
    #con_def = {c.get('type'): c.attrib for c in root.findall('connection_def')}
    con_def = {c.get('id'): {d.get('id'): d.attrib for d in c.findall('duct')}
                              for c in root.findall('connection_def')}

    # Add all connections with an initial weight of 1, and merging the properties from con_def
    for c in root.findall('connection'):
        attribs = deepcopy(c.attrib)
        attribs['weight'] = 1
        attribs['ducts']  = con_def[attribs['type']]
        #attribs.update(con_def[attribs['type']])
        net.add_edge(c.get('origin'), c.get('destination'), **attribs)
        net.add_edge(c.get('destination'), c.get('origin'), **attribs)

    # Check that the map "alias" been properly defined
    if alias:
        diff = set(net.nodes())-set(alias.keys())
        assert (not bool(diff)), 'Alias map is incorrect, check {}'.format(diff)

    return net

# ============================================================================================================
# === FUNCTIONS TO PROCESS EZMONTE VISIBILITY OUTPUT
# ============================================================================================================

def norm_time(t, t0): return (t - t0) / np.timedelta64(1, 's')

def load_ezmonte_data(contact_file, ranges_file, t0):
    # Load contacts and range intervals
    if contact_file.suffix == '.xlsx':
        cp = pd.read_excel(contact_file, index_col=0)
        ri = pd.read_excel(ranges_file, index_col=0)
    elif contact_file.suffix == '.csv':
        converters = {'tstart': lambda x: pd.to_datetime(x),
                      'tend': lambda x: pd.to_datetime(x)}
        cp = pd.read_csv(contact_file, sep=',', index_col=0, converters=converters)
        ri = pd.read_csv(ranges_file, sep=',', index_col=0, converters=converters)
    elif contact_file.suffix == '.h5':
        cp = pd.read_excel(contact_file)
        ri = pd.read_excel(ranges_file)
    else:
        raise IOError('Contact plan can only be .h5, .xlsx or .csv')

    # Merge tables
    cp = pd.merge(cp, ri.loc[:, ['cid', 'range']], left_index=True, right_on='cid')
    cp = cp.set_index('cid')

    # Transform everything to relative timing
    cp.tstart = norm_time(cp.tstart, t0)
    cp.tend   = norm_time(cp.tend, t0)
    ri.tstart = norm_time(ri.tstart, t0)
    ri.tend   = norm_time(ri.tend, t0)

    return cp, ri

def load_route_schedule_file(routes_file, t0):
    # Load route schedule
    converter  = lambda x: ast.literal_eval(x)
    converters = {'route': converter, 'contacts': converter}
    if routes_file.suffix == '.xlsx':
        routes = pd.read_excel(routes_file, converters=converters)
    elif routes_file.suffix == '.csv':
        routes = pd.read_csv(routes_file, sep=',', index_col=0, converters=converters)

    # Check if any datetimes need to be normalized
    if routes.select_dtypes(include=['datetime64']).empty == False:
        routes.time   = norm_time(routes.time, t0)
        routes.EAT    = norm_time(routes.EAT, t0)
        routes.tstart = norm_time(routes.tstart, t0)
        routes.tend   = norm_time(routes.tend, t0)

    return routes

#========================================================================
#=== EXPORT FUNCTIONS
#========================================================================

def export_dtn_results(config, env):
    # Get output file path
    file = config['globals'].outdir/config['globals'].outfile

    # Check that this extension is valid
    if file.suffix not in ['.h5', '.xlsx', '.csv']:
        print('ERROR Exporting. Extension {} not recognized. '
              'Options are ".xlsx", ".csv" and ".h5')
        return

    # Export depending on extension
    with catch_warnings():
        simplefilter('ignore')
        if   file.suffix == '.xlsx': _export_to_excel(file, env)
        elif file.suffix == '.csv':  _export_to_csv(file, env)
        elif file.suffix == '.h5':   _export_to_hdf5(file, env)

    # If no monitoring, skip the res
    if not config['globals'].export_monitor: return

    # Export monitor data to json file
    _export_to_json(file, env)

def _export_to_excel(file, env):
    # Create Excel writer
    writer = pd.ExcelWriter(str(file), engine='xlsxwriter')

    # Export all results
    for name, df in env.all_results.items():
        # Excel writer throws error if empty
        if df.empty: continue

        # Export
        df.to_excel(writer, sheet_name=name, merge_cells=False)

    # Close the Excel writer and write the file.
    writer.save()

def _export_to_csv(file, env):
    # Export all results
    for name, df in env.all_results.items():
        df.to_csv(file.with_name(f'{name}.csv'))

def _export_to_hdf5(file, env):
    # Open HDF5 store
    store = pd.HDFStore(str(file))

    # Export all results
    for name, df in env.all_results.items():
        # Make sure that the column names are unique
        # E.g.: [a b b c] --> [a b b1 c]
        s = df.columns.to_series()
        df.columns = s + s.groupby(s).cumcount().astype(str).replace({'0': ''})

        #Store the dataframe
        store[f'/{name}'] = df

    # Close store
    store.close()

def _export_to_json(file, env):
    # Initialize variables
    exp = defaultdict(dict)

    # Iterate over nodes
    for nid, node in env.nodes.items():
        for neighbor in node.neighbors:
            # Get the DtnPriorityQueue object
            q = node.queues[neighbor].queue.queue

            # Extract information from priority queues
            d = defaultdict(dict)
            for priority in q.priorities:
                pid = 'critical' if priority == 0 else 'standard'

                d[pid]['NumQueue'] = {}
                x, y = q.counters[priority].to_timeseries()
                d[pid]['NumQueue']['x'] = x.tolist()
                d[pid]['NumQueue']['y'] = y.tolist()

                d[pid]['Load'] = {}
                x, y = q.loads[priority].to_timeseries()
                d[pid]['Load']['x'] = x.tolist()
                d[pid]['Load']['y'] = y.tolist()

                d[pid]['BundleDelay'] = {}
                y = q.delays[priority]
                d[pid]['BundleDelay']['x'] = list(range(len(y)))
                d[pid]['BundleDelay']['y'] = np.array(y).tolist()

            # Extract information from outducts
            for band, ducts in node.ducts[neighbor].items():
                dd = defaultdict(lambda: defaultdict(dict))
                for duct, clyr in ducts.items():
                    x, y = clyr.in_queue.counter.to_timeseries()
                    dd[duct]['NumQueue']['x'] = x.tolist()
                    dd[duct]['NumQueue']['y'] = y.tolist()

                    y = clyr.in_queue.delay
                    dd[duct]['BundleDelay']['x'] = list(range(len(y)))
                    dd[duct]['BundleDelay']['y'] = np.array(y).tolist()
                d['ducts'][band] = dict(dd)

            # Store data for this node-neighbor pair
            exp[nid][neighbor] = dict(d)

    # Iterate over connections
    for cid, conn in env.connections.items():
        cid = '_'.join(cid)
        exp[cid]['InTransit'] = {}
        x, y = conn.counter.to_timeseries()
        exp[cid]['InTransit']['x'] = x.tolist()
        exp[cid]['InTransit']['y'] = y.tolist()

    # Dump to json file
    with open(file.with_name('monitor.json'), 'w') as f:
        json.dump(dict(exp), f)