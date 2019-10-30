import pandas as pd
from .DtnAbstractParser import DtnAbstractParser
from pydantic import validator, PositiveFloat
from typing import Optional

class DtnScenarioParser(DtnAbstractParser):
    """ Validator for tag ``scenario in YAML configuration file """
    # Simulation epoch
    epoch : str = pd.Timestamp.now()

    # Simulation seed
    seed : Optional[int] = None

    # Last simulation instant (in simulation time)
    until: Optional[PositiveFloat] = None

    @validator('epoch')
    def str_epoch_to_timestamp(cls, v):
        return pd.Timestamp(v).tz_localize(None)
