from .DtnAbstractParser import DtnAbstractParser
from enum import Enum
from pydantic import PositiveInt, PositiveFloat
import sys
from typing import List, Optional, Set, Union

class RouterMode(str, Enum):
    FAST = 'fast'
    SLOW = 'slow'

class RouterAlgorithm(str, Enum):
    CGR = 'cgr'
    BFS = 'bfs'

class DtnLookupRouterParser(DtnAbstractParser):
    """ Validator for YAML configuration parameters of DtnCGRouter """
    # Excel file containing routes
    routes: str

    # Router mode
    mode: RouterMode = RouterMode.FAST

    # If True, all routes will be recomputed even if they there is a
    # route file provided
    recompute_routes: bool = False

    # Excluded routes specified as a list
    # Example: [['MOC', 'PSH', 'MCC'], ['MCC', 'MRO', 'MCC']]
    excluded_routes: Optional[List[List[str]]] = None

    # Maximum number of hops a valid route can have
    max_relay_hops: PositiveInt = sys.maxsize

    # Number of cores to use during the computation of the routes
    num_cores: PositiveInt = 1

    # Maximum number of neighbors to send a critical bundle.
    # e.g. if a node has 10 neighbors and ``max_crit=2``, then only the
    # two best neighbors will be used
    max_crit: Optional[int] = None

    # List of nodes that can be used as relays
    relays: Union[Set[str], List[str], str] = set()

    # Maximum speed of any node in the system in [miles/sec]
    # Based on latest SABR specification
    max_speed: PositiveFloat = 125

    # Algorithm to use for route computation.
    algorithm: RouterAlgorithm = RouterAlgorithm.BFS





