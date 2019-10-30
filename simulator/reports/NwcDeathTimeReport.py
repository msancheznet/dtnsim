import pandas as pd
from simulator.reports.DtnAbstractReport import DtnAbstractReport

class NwcDeathTimeReport(DtnAbstractReport):

    _alias = 'death_time'

    def collect_data(self):
        # Get the battery state for all nodes
        death = {nid: node.death_time for nid, node in self.env.nodes.items()}

        # Create the dataframe
        df = pd.DataFrame.from_dict(death, orient='index')
        df.columns = ['DeathTime']

        return df