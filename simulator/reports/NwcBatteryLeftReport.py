import pandas as pd
from simulator.reports.DtnAbstractReport import DtnAbstractReport

class NwcBatteryLeftReport(DtnAbstractReport):

    _alias = 'battery_left'

    def collect_data(self):
        # Get the battery state for all nodes
        battery = {nid: node.battery for nid, node in self.env.nodes.items()}

        # Create the dataframe
        df = pd.DataFrame.from_dict(battery, orient='index')
        df.columns = ['battery']

        return df