from simulator.reports.DtnAbstractReport import DtnAbstractReport
import pandas as pd

class DtnRoutingCallsReport(DtnAbstractReport):
    """ Collects the number of times the routing procedures in all nodes
        have been executed.
    """
    _alias = 'routing_calls'

    def collect_data(self):
        # Get the battery state for all nodes
        calls = {nid: node.router.counter for nid, node in self.env.nodes.items()}

        # Create the dataframe
        df = pd.DataFrame.from_dict(calls, orient='index')
        df.columns = ['NumRoutingCalls']

        return df