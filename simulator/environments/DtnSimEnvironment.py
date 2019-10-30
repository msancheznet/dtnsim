# -*- coding: utf-8 -*-

from simulator.environments.DtnAbstractSimEnvironment import SimEnvironment
import numpy as np
import pandas as pd
import os
from pathlib import Path
import random
from simulator.utils.DtnUtils import load_class_dynamically
from warnings import warn

class DtnSimEnviornment(SimEnvironment):

    def reset(self):
        for node in self.nodes.values(): node.reset(); del node
        for con in self.connections.values(): del con
        for mbm in self.mobility_models.values(): del mbm
        for rpt in self.all_results.values(): del rpt
        print(self.del_msg.format(os.getpid(), self.sim_id))

    def initialize(self):
        # De-pack useful global arguments
        self.epoch = self.config['scenario'].epoch
        self.seed  = self.config['scenario'].seed

        # Initialize logger
        self.initialize_logger()

        # Set the seed for the random numbers
        self.set_simulation_seed()

        # Variable to store all results
        self.all_results = {}

        # Create all nodes
        self.nodes = {}
        for nid, node in self.config['network'].nodes.items():
            # Initialize variables
            props = self.config[node.type]
            clazz = load_class_dynamically('simulator.nodes', getattr(props, 'class'))

            # Create node object
            self.nodes[nid] = clazz(self, nid, props)

        # Create all connections
        self.connections = {}
        for cid, con in self.config['network'].connections.items():
            # Initialize variables
            props = self.config[con.type]
            o, d  = con.origin, con.destination
            clazz = load_class_dynamically('simulator.connections', getattr(props, 'class'))

            # Create connections
            self.connections[o, d] = clazz(self, cid, o, d, props)
            self.connections[d, o] = clazz(self, cid, d, o, props)

        # Create the mobility model
        self.create_mobility_models()

        # Initialize all nodes. This can only be done after initializing the connections
        # because otherwise you can't know which ducts to create.
        for node in self.nodes.values(): node.initialize()

        # Initialize all ducts. This must be done after the initializing the
        # node because the radios must be up and running
        for node in self.nodes.values(): node.initialize_neighbors_and_ducts()

        # Initialize all connections. This must be done after initializing the ducts
        for o, d in self.connections:
            self.connections[o, d].initialize()
            self.connections[d, o].initialize()

        # Initialize all mobility models. This can only be done after initializing
        # the connections, since the mobility model might inherit info from them.
        self.initialize_mobility_models()

        # Complete connection initialization using info from mobility models
        for c in self.connections.values(): c.initialize_contacts_and_ranges()

        # Initialize all routers using info from mobility models. Also initialize
        # all endpoints using information from routers. Finally, initialize neighbor
        # manager with info from the mobility model
        for node in self.nodes.values():
            node.initialize_router()
            node.initialize_endpoints()
            node.initialize_neighbor_managers()

        # Flag the reports that need to be generated
        self.reports = self.config['reports'].reports

        # Show initialization message
        print(self.init_msg.format(os.getpid(), self.sim_id,
                                   self.config_file, self.seed))

    def create_mobility_models(self):
        # Initialize variables
        self.mobility_models = {}

        # Gather all models defined in YAML file
        models = {node.props.mobility_model for node in self.nodes.values()}
        models.update({c.props.mobility_model for c in self.connections.values()})
        models = models - {None}

        # Iterate over models to initialize
        for model in models:
            # Find properties of this mobility model
            props = self.config[model]

            # Initialize class
            clazz = load_class_dynamically('simulator.mobility_models', getattr(props, 'class'))
            self.mobility_models[model] = clazz(self, props)

    def initialize_mobility_models(self):
        for model in self.mobility_models.values():
            model.initialize()

    def set_simulation_seed(self):
        if self.seed is None: return
        np.random.seed(self.seed)
        random.seed(self.seed)

    def finalize_simulation(self, close_logger=True):
        # If the results are already available, return them
        if self.all_results: return self.all_results

        # Initialize variables
        self.all_results = {}

        # Collect all the reports
        for report in self.reports:
            # Create the report
            clazz  = load_class_dynamically('simulator.reports', report, report)
            report = clazz(self)

            # If this report already exists, raise error
            if report.alias in self.all_results:
                continue

            # Store the report
            self.all_results[report.alias] = report.data

        # Compose and return result
        return self.all_results

    def validate_simulation(self):
        # Format validation portion of log file
        self.new_log_section(title='VALIDATION RESULTS')

        # Get the simulation results
        self.finalize_simulation(close_logger=False)

        # Perform validation process
        error = self._validate_sent() | \
                self._validate_arrived() | \
                self._validate_dropped() | \
                self._validate_stored() | \
                self._validate_lost() | \
                self._validate_arrived_bundles() | \
                self._validate_standard_data_volume() | \
                self._validate_critical_data_volume() | \
                self._validate_expected_data_volume() | \
                self._validate_num_bundles_end()

        # Display warning if error detected
        #if error: warn('Simulation did not pass all tests. See log file for details')
        return (not error)

    def _validate_sent(self):
        # If the required report was not collected, skip
        if 'DtnSentBundlesReport' not in self.reports: return False

        # Perform check
        error = self.all_results['sent'].empty

        # Display error
        if error: self.error("No bundles were ever sent.", header=False)
        else:     self.log("Sent bundles test successfully passed.", header=False)
        self.new_line()

        return error

    def _validate_arrived(self):
        # If the required report was not collected, skip
        if 'DtnArrivedBundlesReport' not in self.reports: return False

        # Perform check
        error = self.all_results['arrived'].empty

        # Display error
        if error:
            self.error("No bundles were received at destination.", header=False)
        else:
            self.log("Received bundles test successfully passed.", header=False)
        self.new_line()

        return error

    def _validate_dropped(self):
        # If the required report was not collected, skip
        if 'DtnDroppedBundlesReport' not in self.reports: return False

        # Get report data
        dropped = self.all_results['dropped']

        # If no bundles dropped, pass test
        if dropped.empty:
            self.log("Dropped bundles test successfully passed.", header=False)
            self.new_line()
            return False

        # Find the non-critical data that was dropped
        v = dropped.loc[dropped.critical == False, :]
        self.error("'dropped' should be empty but holds:\n{}", v, header=False)
        self.new_line()

        return True

    def _validate_stored(self):
        # If the required report was not collected, skip
        if 'DtnStoredBundlesReport' not in self.reports: return False

        # Get report data
        stored = self.all_results['stored']

        # If stored is not empty, pass test
        if stored.empty:
            self.log("Stored bundles test successfully passed.", header=False)
            self.new_line()
            return False

        # If stored is not empty, then  error
        self.error("Some bundles are still stored in DTN nodes:\n{}", stored, header=False)
        self.new_line()

        return False

    def _validate_lost(self):
        # If the required report was not collected, skip
        if 'DtnConnLostBundlesReport' not in self.reports: return False

        # Get report data
        lost = self.all_results['lost']

        # If stored is not empty, pass test
        if lost.empty:
            self.log('Lost bundles test successfully passed.', header=False)
            self.new_line()
            return False

        # If stored is not empty, then  error
        self.error("'lost' should be empty by holds:\n{}", lost, header=False)
        self.new_line()

        return False

    def _validate_arrived_bundles(self):
        # If the required report was not collected, skip
        if 'DtnArrivedBundlesReport' not in self.reports or \
           'DtnSentBundlesReport' not in self.reports: return False

        # Get report data
        arrived = self.all_results['arrived']
        sent    = self.all_results['sent']

        # Get the list of bids that were transmitted
        s_bids = set(sent.index.get_level_values('bid')) if not sent.empty else set()

        # Get the list of bids that were received
        a_bids = set(arrived.bid) if not arrived.empty else set()

        # Perform check - See how many bids never arrived
        diff  = s_bids - a_bids
        error = bool(diff)

        # Display log message
        if error:
            self.error('Bundles {} do not arrive.', diff, header=False)
        else:
            self.log('All bundle Ids where accounted for.', header=False)
        self.new_line()

        return error

    def _validate_standard_data_volume(self):
        # If the required report was not collected, skip
        if 'DtnArrivedBundlesReport' not in self.reports or \
           'DtnSentBundlesReport' not in self.reports: return False

        # Get report data
        arrived = self.all_results['arrived']
        sent    = self.all_results['sent']

        # If nothing was sent or received, error
        if sent.empty or arrived.empty:
            self.error('Non-critical data volume test skipped')
            return False

        # Eliminate critical data
        sent    = sent.loc[sent.critical == False, :]
        arrived = arrived.loc[arrived.critical == False, :]

        # Compute transmitted and received data volume per flow
        tx_dv = sent.groupby(by='fid').data_vol.sum()
        rx_dv = arrived.groupby(by='fid').data_vol.sum()

        # Perform check. Inspired by numpy's "allclose" function
        atol, rtol = 1e-8, 1e-3
        ok = np.abs(tx_dv.subtract(rx_dv, fill_value=0.0).values) <= (atol + rtol * np.abs(tx_dv.values))
        error = not ok.ravel().all()

        # Check whether some flows had different transmitted and received data volume. If so, data is being lost during the simulation
        if error:
            self.error('The following non-critical flows received a data volume that is '
                       'different from the transmitted data volume:', header=False)
            dv = pd.concat([tx_dv, rx_dv], axis=1).fillna(value=0.0)
            dv.columns = ['TxDataVolume', 'RxDataVolume']
            self.log('{}', dv.loc[~ok.ravel(), :], header=False)
        else:
            self.log('Non-critical data volume test successfully passed.', header=False)
        self.new_line()

        return error

    def _validate_critical_data_volume(self):
        # If the required report was not collected, skip
        if 'DtnArrivedBundlesReport' not in self.reports or \
           'DtnSentBundlesReport' not in self.reports: return False

        # Get report data
        arrived = self.all_results['arrived']
        sent    = self.all_results['sent']

        # If nothing was sent or received, error
        if sent.empty or arrived.empty: self.error('Critical data volume test skipped'); return True

        # Eliminate non-critical data
        sent    = sent.loc[sent.critical == True, :]
        arrived = arrived.loc[arrived.critical == True, :]

        # Compute transmitted and received data volume per flow
        tx_dv = sent.groupby(by='fid').data_vol.sum()
        rx_dv = arrived.groupby(by='fid').data_vol.sum()

        # Compute the ration of rx_data_vol/tx_data_vol
        mult = 1.0 / tx_dv.divide(rx_dv, axis=0, fill_value=0.0)

        # Perform check.
        error = (mult < 1.0).any()

        # Display error message if necessary
        if error:
            self.error('The following critical flows did not receive all received data volume:', header=False)
            dv = pd.concat([tx_dv, rx_dv], axis=1)
            dv.columns = ['TxDataVolume', 'RxDataVolume']
            err_dv     = dv.loc[mult < 1.0, :].fillna(value=0.0)
            self.log('{}', err_dv, header=False)
        else:
            self.log('Critical data volume test successfully passed.', header=False)

        # Display informational message about critical data volume
        self.log('Informational data on critical data flows. Data volume multiplier:', header=False)
        data = {k: 'x{:.1f}'.format(v) for k, v in mult.to_dict().items()}
        data = pd.DataFrame.from_dict(data, orient='index').rename(columns={0:'Multiplier'})
        self.log('{}', data, header=False)
        self.new_line()

        return False

    def _validate_expected_data_volume(self):
        # If the required report was not collected, skip
        if 'DtnSentBundlesReport' not in self.reports: return False

        # Initialize variables
        dv1, dv2 = {}, {}

        # Iterate over all generators in the simulation
        for _, node in self.nodes.items():
            for gid, gen in node.generators.items():
                dv1[gid] = gen.predicted_data_vol()
                dv2[gid] = gen.generated_data_vol()

        # Compute the total data volume in [Tbit]
        tdv1 = sum(dv1.values())/1e12
        tdv2 = sum(dv2.values())/1e12

        # Perform check
        error = not np.isclose(tdv1, tdv2)

        # Display error message if necessary
        if error:
            self.error('The predicted data volume is {:.6f}Tbit')
            self.error('The generated data volume is {:.6f}Tbit')
            self.error('They should match. Differences in flows are as follows:')
            self.error('Predicted: {}'.format(dv1))
            self.error('Predicted: {}'.format(dv2))
        else:
            self.log('Expected data volume test successfully passed.', header=False)

        # Finish test
        self.new_line()

        return error

    def _validate_num_bundles_end(self):
        # If the required report was not collected, skip
        if 'DtnArrivedBundlesReport' not in self.reports or \
           'DtnSentBundlesReport' not in self.reports or \
           'DtnConnLostBundlesReport' not in self.reports or \
           'DtnDroppedBundlesReport' not in self.reports or \
           'DtnStoredBundlesReport' not in self.reports: return False

        # Get report data
        arrived = self.all_results['arrived']
        dropped = self.all_results['dropped']
        stored  = self.all_results['stored']
        sent    = self.all_results['sent']
        lost    = self.all_results['lost']

        # Compute number of bundles
        n1 = sent.shape[0]

        # Compute number of bundles that arrive, are dropped, lost or stored
        n2 = arrived.shape[0] + dropped.shape[0] + \
             lost.shape[0] + stored.shape[0]

        # Perform check (because of bundle fragmentation and critical routers
        # policy, the number of bundles at end will almost certainly be larger
        # that the number of bundles sent)
        error = n1 > n2

        # Display error message if necessary
        if error:
            self.error('{:.0f} bundles were sent, but {:.0f} bundles were either dropped,'
                       'arrived, lost or stored. Where are the rest?', n1, n2, header=False)
        else:
            self.log('"Num. bundles at end" test successfully passed.', header=False)
        self.new_line()

        return error

    def __str__(self):
        return f'<DtnSimEnvironment t={self.now}>'