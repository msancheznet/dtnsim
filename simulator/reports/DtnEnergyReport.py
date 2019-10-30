import pandas as pd
from simulator.reports.DtnAbstractReport import DtnAbstractReport

class DtnEnergyReport(DtnAbstractReport):

    _alias = 'energy'

    def collect_data(self):
        # Initialize variables
        data = []

        # Iterate through all nodes
        for nid, node in self.env.nodes.items():
            # Iterate over all ducts to a given neighbor
            for neighbor, ducts in node.ducts.items():
                # Iterate over all ducts
                for duct_id, duct in ducts.items():
                    # Get the radios for this duct. Note that only
                    # the outduct consumes energy
                    radios = duct['outduct'].radios

                    # If no radios are defined, continue
                    if not radios: continue

                    # Create record
                    data.extend((nid, neighbor, duct_id, rid, radio.energy)
                                 for rid, radio in radios.items())

        # Create data frame
        df = pd.DataFrame(data, columns=('node', 'neighbor', 'duct',
                                         'radio', 'energy_J'))

        # Return data
        return df