from .DtnAbstractMobilityModel import DtnAbstractMobilityModel
import pandas as pd
from simulator.utils.DtnIO import load_ezmonte_data

class DtnScheduledMobilityModel(DtnAbstractMobilityModel):

    def __init__(self, env, props):
        # Call parent constructor
        super(DtnScheduledMobilityModel, self).__init__(env, props)

        # Initialize paths
        indir = self.config['globals'].indir
        self.contact_file = indir / self.props.contacts
        self.ranges_file = indir / self.props.ranges

    def initialize(self, *args, **kwargs):
        # Load data from ezmonte
        print('Loading contact plan and range intervals')
        cp, ri = load_ezmonte_data(self.contact_file, self.ranges_file, self.epoch)

        # Compute the data rate for every link
        dr = [(*cid, conn.total_datarate) for cid, conn in self.env.connections.items()]
        dr = pd.DataFrame.from_records(dr, columns=('orig', 'dest', 'rate')).set_index(['orig', 'dest'])

        # Merge the data rate information into the contact plan and compute a contact capacity
        cp = pd.merge(cp, dr, how='left', left_on=('orig', 'dest'), right_index=True)
        cp['capacity'] = (cp.tend - cp.tstart) * cp.rate

        # Check validity of generated contact plan
        if (cp.tstart < 0).any() or (cp.tend < 0).any():
            raise ValueError('Contact plan cannot have contacts starting or ending before 0 sec.'
                             'This is most likely caused by a mismatch between the contact/range file'
                             'and the simulation epoch.')
        if (cp.rate < 0).any():
            raise ValueError('Contact plan cannot have a contact with a data rate < 0')
        if (cp.range < 0).any():
            raise ValueError('Contact plan cannot have a contact with a range  < 0')

        # Store dataframes
        self.contacts_df = cp
        self.ranges_df = ri