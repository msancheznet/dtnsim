import pandas as pd

from .DtnAbstractMobilityModel import DtnAbstractMobilityModel
from simulator.utils.basic_utils import Counter

class DtnStaticMobilityModel(DtnAbstractMobilityModel):

    def __init__(self, env, props):
        # Call parent
        super(DtnStaticMobilityModel, self).__init__(env, props)

        # Propagation delay
        self.prop_delay = props.prop_delay

        # Variable to assign contact ID and make it unique
        self.cids = Counter()

    def new_cid(self):
        return next(self.cids)

    def initialize(self):
        # Create a fake contact plan based on the defined connections
        cp = [{'orig': o,
               'dest': d,
               'tstart': 0,
               'tend': float('inf'),
               'duration': float('inf'),
               'rate': c.total_datarate,
               'range': self.prop_delay} for (o,d), c in self.env.connections.items()]

        self.contacts_df = pd.DataFrame(cp)