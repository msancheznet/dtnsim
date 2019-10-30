import abc
import pandas as pd
from pathlib import Path

class DtnAbstractReport(object, metaclass=abc.ABCMeta):

    """ Alias name for this report. When saved, this alias will be
        used as the name of the report.
    """
    _alias = None

    def __init__(self, env):
        # Store the simulation environment
        self.env = env

        # File to store the data
        dir  = env.config['globals'].outdir
        file = env.config['globals'].outfile
        self.file = dir/file

        # Other variables
        self.writer = None  # Set it to export to .xlsx
        self.store  = None  # Set it to export to .h5

        # Cache with the collected data
        self.cache = None

    def __get__(self, item):
        # If you are not calling ``collect_data``, just do the
        # normal thing
        if item != 'collect_data': return getattr(self, item)

        # If you are calling ``collect_data``, do it and set
        # the cached value automatically
        self.cache = self.collect_data()

        # Return the cached value
        return self.cache

    @property
    def alias(self):
        alias = self.__class__._alias
        if not alias: raise ValueError(str(self) + 'does not have an alias')
        return alias

    @property
    def data(self):
        # If the cached value is available, use it
        if self.cache: return self.cache

        # Collect the data and return it
        return self.collect_data()

    @abc.abstractmethod
    def collect_data(self):
        """ Collect the data that needs to be exported by this report
            :return: pd.DataFrame: Data frame to be exported
        """
        pass

    def export_to(self, extension):
        # Get format
        format = extension.replace('.', '')

        # Collect data into data frame
        df = self.collect_data()

        # Trigger the right exporter
        exec(f'self.export_to_{format}(df)', locals(), globals())

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return f'<{self.__class__.__name__}>'

def concat_dfs(data, new_col_names):
    """ Consolidate a dictionary of data frames into one data frame

        :param dict data: {a: df for a, b: df for b}
        :param str/tuple new_col_names: The name for the column [a, b, ...] or columns
        :return: Data frame with numeric index
    """
    # If data is empty, return empty data frame
    if not data: return pd.DataFrame()

    # If new_col_names is not iterable, convert it
    if not isinstance(new_col_names, (list, tuple)):
        new_col_names = [new_col_names]

    # Get data frames to concatenate
    to_concat = {k: df for k, df in data.items() if not df.empty}

    # If no data to concatenate, return empty
    if len(to_concat) == 0: return pd.DataFrame()

    # Concatenate the data frames
    df = pd.concat(to_concat).reset_index(level=0)

    # If the data frame is empty, return
    if df.empty: return pd.DataFrame()

    # Create the mapper to rename the columns
    mapper = {f'level_{i}': col_name for i, col_name in enumerate(new_col_names)}

    # Rename the new column
    df.rename(mapper, axis=1, inplace=True)

    return df