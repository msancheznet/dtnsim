"""
# ==================================================================================
# Author: Marc Sanchez Net
# Date:   03/18/2019
# Copyright (c) 2019, Jet Propulsion Laboratory.
# ==================================================================================
"""
from pathlib import Path
import pandas as pd

from simulator.core.DtnBundle import Bundle
from simulator.generators.DtnAbstractGenerator import DtnAbstractGenerator

class AgcPacketGenerator(DtnAbstractGenerator):

    def initialize(self):
        # Get generator properties
        sat_id    = self.parent.nid.replace('s', 'Sat')
        path      = Path(self.props.params['globals']['indir'])
        self.file = path/Path(self.props.file.format(sat_id))

        # Get bundle properties
        self.data_type  = self.props.data_type
        self.bundle_sz  = self.props.bundle_size
        self.bundle_TTL = self.props.bundle_TTL
        self.critical   = self.props.critical
        self.until      = self.props.until

        # Get origin for all bundles
        self.orig = self.parent.nid

        # Import data
        try:
            self.df = pd.read_csv(self.file, sep='\s+', index_col=False)
        except:
            pass

        # Set the packet id as the index
        self.df.set_index('DataPacket_ID', drop=True, inplace=True)

        # Run generator
        self.env.process(self.run())

    def run(self):
        # If no data, skip
        if self.df.empty: yield self.env.exit()

        # Get name of satellites
        dests = [s.replace('s','Sat') for s in self.env.nodes.keys()]

        # Iterate and create bundles
        for pid, row in self.df.iterrows():
            # Wait until the next event
            yield self.env.timeout(max(0.0, row['Time[s]'] - self.t))

            # Figure out to which sats you need to send a copy
            # WARNING: Ignore priorities for now
            for dest in dests:
                # Get the priority level
                priority = row[dest]

                # If priority == -1, it means skip. If priority == 0, it
                # means this is the source satellite
                if priority == -1 or priority == 0:
                    continue

                # Undo name transformation
                dest = dest.replace('Sat', 's')

                # Only send if you are supposed to
                if self.t >= self.until:
                    continue

                # Compute packet data vol. This is added in case Ames specifies
                # packets per region.
                if 'Extra' in row:
                    data_vol = self.bundle_sz*row['Extra']
                else:
                    data_vol = self.bundle_sz

                # Create a new bundle and record it
                new_bundle = Bundle(self.env, self.orig, dest, self.data_type,
                                    data_vol, self.bundle_TTL, self.critical,
                                    fid=(self.orig, dest, self.fid, -1, -1),
                                    TTL=self.get_bundle_TTL(priority), priority=priority)

                # Monitor the new bundle creation
                self.monitor_new_bundle(new_bundle)

                # Log the new bundle creation
                self.disp('{} is created at node {}', new_bundle, self.parent.nid)

                # Schedule routers of bundle
                self.parent.forward(new_bundle)

    def get_bundle_TTL(self, priority):
        # 100 min TTL by Sreeja's output
        return 100*60

    def predicted_data_vol(self):
        # THIS IS INCORRECT!
        return self.df.shape[0]*self.bundle_sz

