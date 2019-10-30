from .DtnAbstractParser import DtnAbstractParser

class DtnEpidemicRouterParser(DtnAbstractParser):
    # Class type for the manager
    manager: str

    # Maximum buffer size for the opportunistic manager queue
    max_buffer_size: float = float('inf')