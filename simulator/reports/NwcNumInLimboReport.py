import pandas as pd
from simulator.reports.DtnAbstractReport import DtnAbstractReport

class NwcNumInLimboReport(DtnAbstractReport):

    _alias = 'num_in_limbo'

    def collect_data(self):
        # Get the number of bundles that were in the limbo as a function of time
        in_limbo = {nid: node.num_bnd for nid, node in self.env.nodes.items()}

        # Create data frame
        df = pd.DataFrame(in_limbo)

        return df