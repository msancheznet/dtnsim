#import matplotlib as mpl
from simulator.utils.basic_utils import is_string, is_list, Table, new_array, def_val
from simulator.utils.math_utils import find_consecutive
import numpy as np
import pandas as pd
import sys
if sys.version_info[0] < 3: 
    from StringIO import StringIO
else:
    from io import StringIO
    long = int
import warnings

def sec2hms(seconds):
    """ Convert seconds to readable hour:minute:sec format 

        :param float seconds: Seconds

        :return str: The nicely formatted string
    """
    if seconds == float('inf'):
        return "Inf"

    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return "%dh:%02dm:%02ds" % (h, m, s)

def time2float(t, t0):
    return pd.to_timedelta(t-t0)/np.timedelta64(1,'s')
    # return mpl.dates.date2num(x)

def float2time(t, t0):
    tt = t0 + pd.to_timedelta(t, unit='s')
    return np.array([pd.Timestamp(t) for t in tt])
    # return mpl.dates.num2date(t)

def str2time(t, infer=True, fmt='%Y-%m-%d %H:%M:%S', microsec=False, tz=False):
    """ Convert a string time format to a pandas Timestamp

        See https://docs.python.org/2/library/datetime.html#strftime-strptime-behavior for conversion
    """
    fmt = fmt + '.%f' if microsec is True else fmt
    if infer is True:
        t = pd.to_datetime(t, infer_datetime_format=True)
    else:
        t = pd.to_datetime(t, format=fmt)
    return t.tz_localize(None) if tz is False else t
    #return datetime.strptime(t, fmt)

def time2str(t, fmt='%Y-%m-%d %H:%M:%S', microsec=False):
    """ Convert a pandas Timestamp to a string

        See https://docs.python.org/2/library/datetime.html#strftime-strptime-behavior for conversion
    """
    fmt = fmt + '.%f' if microsec is True else fmt
    return t.strftime(fmt)
    #return t.strftime(fmt)

def union_time_intervals(tstart, tend):
    # Boundary case
    if len(tstart) == 0 and len(tend) == 0:
        return tstart, tend

    # Initialize variables
    N  = np.size(tstart, 0)
    t0 = np.min([np.min(tstart), np.min(tend)])

    # Convert to time to numeric values
    ts, te = time2float(tstart, t0), time2float(tend, t0)

    # Sort values
    x = np.append(ts, te)
    p = np.argsort(x)
    t = x[p]

    # Work magic based on Matlab's `union_sets_intervals`
    z      = np.cumsum(np.bincount(np.arange(2*N), weights=2*((p+1)<=N)-1))
    z1     = np.append(0, z[0:-1])
    ts, te = t[(z1==0)&(z>0)], t[(z1>0)&(z==0)]

    # Transform back to time
    return float2time(ts, t0), float2time(te, t0)

def join_timetables(*args, **kwargs):
    """ Join timetables ensuring that a single time axis is shared. By default
        missing values are filled with the previous value

        .. warning:: If two dataframes have the same column name, then this function
                     fails.
    """
    # Set default values
    how    = 'outer' if 'how' not in kwargs else kwargs['how']
    method = 'ffill' if 'method' not in kwargs else kwargs['method']
    
    # Initialize variables
    args = list(args)
    df  = args.pop(0)
    
    # Join the tables 
    for table in args:
        timeline  = df.index.join(table.index, how=how)
        new_df    = df.reindex(index=timeline, method=method)
        new_table = table.reindex(index=timeline, method=method)
        df        = new_df.join(new_table, how=how)

    # Check if series and convert to data frame
    if isinstance(df, pd.Series):
        df = df.to_frame()
        
    return df

def setxor_time(ts, te, tstart, tend):
    """ Perform a setxor operations given a list of events in an
        initial and final start time

        :param datetime/timestamp/string ts: Start of time. If string is provided, conversion to datetime will be attempted
        :param datetime/timestamp/string te: End of time. If string is provided, conversion to datetime will be attempted
        :param list tstart: List of interval start times
        :param list tend: List of interval end times

        Example: ts = 01-01-2000 00:00:00
                 te = 01-02-2000 00:00:00
                 tstart = [01-01-2000 01:00:00, 01-01-2000 12:00:00]    # E.g. Start of occultation period
                 tend   = [01-01-2000 02:00:00, 01-01-2000 13:00:00]    # E.g. End of occultation period

                 t1 = [01-01-2000 00:00:00, 01-01-2000 02:00:00, 01-01-2000 13:00:00]   # E.g. start of visibility period
                 t2 = [01-01-2000 01:00:00, 01-01-2000 12:00:00, 01-02-2000 00:00:00]   # E.g. end of visibility period
    """
    # Format inputs if necessary
    ts = str2time(ts) if is_string(ts) else ts
    te = str2time(te) if is_string(te) else te
    tstart, tend = new_array(tstart), new_array(tend)

    # Handle boundary case
    if len(tstart) == 0 and len(tend) == 0:
        return pd.Series([ts]), pd.Series([te])

    # Compute setxor using long values for the datetimes
    t1 = np.append(ts.value, tend.astype(long))
    t2 = np.append(tstart.astype(long), te.value)

    # Filter intervals with zero duration
    idx = (t2-t1 > 0)
    t1  = pd.to_datetime(t1[idx], unit='ns', infer_datetime_format=True)
    t2  = pd.to_datetime(t2[idx], unit='ns', infer_datetime_format=True)
    
    return t1, t2

def timeint2ts(timeint, ts=None, te=None, dt=1.0, on=True, off=False, name='ts'):
    """ Convert a table of time intervals to its time series representation.
        During a time within any timeint, the value of parameter 'on' will be
        specified (and 'off' otherwise)

        :param list/tuple/dataframe timeint: Time intervals. If ([ts1,ts2,...], [te1, te2, ...]) is provided, it is converted to data frame automatically
        :param te: Start time of the time series (default is None)
        :param ts: End time of the time series (default is None)
        :param float dt: Time series delta time in seconds (default is 1.0)
        :param on: Value to use during a time interval (default is True)
        :param off: Value to use outside time intervals (default is False)
        :param str name: Name of the time series (default is 'ts')

        :return pandas.DataFrame: Index has pd.Timestamp, first column has on/off
    """
    # Build the Data Frame with time intervals if necessary
    if is_list(timeint):
        assert len(timeint[0]) == len(timeint[1]), 'Timeint must contain two list of same dimension. Now {} is not {}'.format(len(timeint[0]), len(timeint[1]))
        if len(timeint[0]) == 0:
            timeint = pd.DataFrame(data={'tstart':[], 'tend':[]})
        else:
            istart, iend = zip(*timeint)
            istart  = pd.to_datetime(istart, infer_datetime_format=True) if is_string(istart[0]) else istart
            iend    = pd.to_datetime(iend, infer_datetime_format=True) if is_string(iend[0]) else iend
            timeint = pd.DataFrame(data={'tstart':istart, 'tend':iend})

    # Check boundary cases
    if timeint.empty and (None in [te, ts, dt]):
        raise RuntimeError('Timeint is empty and no ts={} and te={}. Cannot generate a time series with this information')

    # If empty, just create a time series with all on periods
    if timeint.empty:
        t  = pd.date_range(start=ts, end=te, freq=pd.DateOffset(seconds=dt))
        df = pd.DataFrame(data={name:[True]*len(t), 'By':['N/A']*len(t)}, index=t)
        return df

    # Overlap time intervals
    tstart, tend = union_time_intervals(timeint.tstart, timeint.tend)

    # Find the delta time required if necessary
    if dt is None:
        dt1 = np.min(timeint.tend-timeint.tstart)
        dt2 = pd.Timedelta(np.min(timeint.tstart[1:].values-timeint.tend[0:-1].values))
        dt  = min(dt1, dt2)/np.timedelta64(1,'s')

    # Select the start and end times for the time series
    ts = min(tstart) if ts is None else pd.to_datetime(ts, infer_datetime_format=True)
    te = max(tend)   if te is None else pd.to_datetime(te, infer_datetime_format=True)

    # Create time axis and new dataframe
    t  = pd.date_range(start=ts, end=te, freq=pd.DateOffset(seconds=dt))
    df = pd.DataFrame(data={name:[off]*len(t)}, index=t)

    # Loop over all events
    for t1, t2 in zip(tstart, tend):
        idx = (df.index >= t1) & (df.index <= t2)
        df.loc[idx, name] = on

    return df

def ts2timeint(ts, val=True, col=0):
    """ Convert a time series to time intervals. Only time intervals at value 'val'
        will be used.

        :param pandas.DataFrame/Series ts: Time series
        :param val: The value that marks time intervals under consideration (default is True)
        :return pandas.DataFrame: (tstart, tend)
    """
    # Check inputs
    ts = ts.to_frame(name='tmp') if isinstance(ts, pd.Series) else ts
    
    # Find column to be used to find the intervals
    if not isinstance(col, int):
        col = np.where(col == ts.columns)[0][0]
    
    # Select the values
    vals = ts.iloc[:,col].values 
    
    # Find sets of consecutive `val` in vals
    runs = find_consecutive(vals, val)
    ints = [(ts.index[run[0]], ts.index[run[1]]) for run in runs]

    # Format output
    return pd.DataFrame.from_records(ints, columns=['tstart', 'tend'])

def group_by_time(df, col, by='day', fun='max', args=(), kwargs={}, index='categories'):
    """ See <https://pandas.pydata.org/pandas-docs/stable/api.html#groupby>_ for the set of `fun` parameters
            available. Examples are: 'count', 'max', 'min', 'median', etc

        .. Tip:: Since Access inherits from TimeIntervalTable, the underlaying data format
                 is a `pandas.DataFrame`, not a `pandas.Series`. Consequently, only the groupby
                 functions of a generic GroupBy or DataFrameGroupBy are valid. Functions of SeriesGroupBy
                 are not allowed.
    """
    if col == 'index':
        t = df.index
    else:
        t = df.loc[:, col].dt

    if by.lower() in ['y', 'year']:
        group = df.groupby([t.year])
        group = getattr(group, fun)(*args, **kwargs)
        group.index.names = ['year']
    elif by.lower() in ['m', 'month']:
        group = df.groupby([t.year, t.month])
        group = getattr(group, fun)(*args, **kwargs)
        group.index.names = ['year', 'month']
    elif by.lower() in ['d', 'day']:
        group = df.groupby([t.year, t.month, t.day])
        group = getattr(group, fun)(*args, **kwargs)
        group.index.names = ['year', 'month', 'day']
    elif by.lower() in ['h', 'hour']:
        group = df.groupby([t.year, t.month, t.day, t.hour])
        group = getattr(group, fun)(*args, **kwargs)
        group.index.names = ['year', 'month', 'day', 'hour']
    elif by.lower() in ['m', 'min', 'minute']:
        group = df.groupby([t.year, t.month, t.day, t.hour, t.minute])
        group = getattr(group, fun)(*args, **kwargs)
        group.index.names = ['year', 'month', 'day', 'hour', 'min']
    elif by.lower() in ['s', 'sec', 'second']:
        group = df.groupby([t.year, t.month, t.day, t.hour, t.minute, t.second])
        group = getattr(group, fun)(*args, **kwargs)
        group.index.names = ['year', 'month', 'day', 'hour', 'min', 'sec']
    else:
        raise KeyError('Grouping can be by "year", "month", "day", "min" and "sec" only')

    # Choose index
    if index == 'categories':
        return group
    elif index == 'times':
        group.index = pd.DatetimeIndex([pd.Timestamp(*i) for i, _ in group.iterrows()])
        return group
    else:
        raise KeyError('Argument "index={}"" is not valid. Options are "categories" or "times"')

class TimeTable(Table):
    def __init__(self, *args, **kwargs):
        super(TimeTable, self).__init__(*args, **kwargs)

    def __str__(self):
        return 'TimeTable'
    
    def __repr__(self):
        msg  = 'TimeTable\n'
        msg += str(self.df)
        return msg

    def __deepcopy__(self, memo):
        """ You can't call self.copy() here. If you did, and created a subclass
            you would enter an infinite loop
        """
        new_table = super(TimeTable, self).copy()
        return TimeTable(new_table.df)
            
    def copy(self):
        new_table = super(TimeTable, self).copy()
        return TimeTable(new_table.df)

    def save(self, *args, **kwargs):
        file = args[0] + '.csv',
        self.df.to_csv(file, **kwargs)

    @classmethod
    def read(cls, *args, **kwargs):
        # Set default values
        if 'index_col' not in kwargs:
            kwargs['index_col'] = 0
        if 'parse_dates' not in kwargs:
            kwargs['parse_dates'] = [0]
        mode = def_val(kwargs, 'mode', 'file', pop=True)

        if mode.lower() == 'file':
            file_name    = args[0] + '.csv'
            new_table    = cls.__new__(cls)
            new_table.df = pd.read_csv(file_name, **kwargs)
        elif mode.lower() == 'string':
            string_io    = StringIO(args[0])
            new_table    = cls.__new__(cls)
            new_table.df = pd.read_csv(string_io, **kwargs)
        else:
            raise KeyError('Invalid mode for TimeTable.read. Value provided = {}. Options valid are "file", "string"'.format(mode))
        return new_table

    def export(self, *args, **kwargs):
        file = args[0] + '.xlsx'
        self.df.to_excel(file, **kwargs)

    @property
    def tstart(self):
        return self.df.index[0]

    @property
    def tend(self):
        return self.df.index[-1]

    def group(self, by='day', fun='max', args=(), kwargs={}, index='categories'):
        """ See <https://pandas.pydata.org/pandas-docs/stable/api.html#groupby>_ for the set of `fun` parameters
            available. Examples are: 'count', 'max', 'min', 'median', etc

            .. Tip:: Since Access inherits from TimeIntervalTable, the underlaying data format
                     is a `pandas.DataFrame`, not a `pandas.Series`. Consequently, only the groupby
                     functions of a generic GroupBy or DataFrameGroupBy are valid. Functions of SeriesGroupBy
                     are not allowed.
        """
        return group_by_time(self.df, 'index', by=by, fun=fun, args=args, kwargs=kwargs, index=index)

class TimeIntervalTable(Table):
    def __init__(self, *args, **kwargs):
        super(TimeIntervalTable, self).__init__(*args, **kwargs)
        
        # Check that intervals are defined
        if 'tstart' not in self.df.columns:
            raise TypeError('TimeIntervalTable must contain a "tstart" column. It stores the time interval start')
        if 'tend' not in self.df.columns:
            raise TypeError('TimeIntervalTable must contain a "tend" column. It stores the time interval end')
            
        # Sort columns in nice format
        cols = list(self.columns.values)
        cols.remove('tstart')
        cols.remove('tend')
        new_cols = ['tstart', 'tend']
        new_cols.extend(cols)
        self.sort_columns(new_cols)

        # Construct the duration column
        try:
            self.df['dur'] = (self.tend-self.tstart).apply(lambda x: x.total_seconds())
        except:
            self.df['dur'] = self.tend-self.tstart
            
    def __add__(self, other):
        my_df  = self.copy().df
        ot_df  = other.copy().df
        new_df = pd.concat((my_df, ot_df), ignore_index=True)
        new_df.drop_duplicates(subset=['tstart', 'tend'], inplace=True)
        return TimeIntervalTable(new_df)
    
    def __or__(self, other):
        return self.__add__(other)
    
    def __mul__(self, other):
        ts = pd.concat((self.df.tstart, other.df.tstart), ignore_index=True)
        te = pd.concat((self.df.tend,   other.df.tend)  , ignore_index=True)
        ts, te = union_time_intervals(ts, te)
        return TimeIntervalTable({'tstart':ts, 'tend':te})
        
    def __and__(self, other):
        return self.__mul__(other)

    def __invert__(self):
        ts, te = min(self.tstart), max(self.tend)
        ts, te = setxor_time(ts, te, self.tstart, self.tend)
        return TimeIntervalTable({'tstart': ts, 'tend':te})
            
    def __str__(self):
        if self.df.empty:
            return 'TimeIntervalTable: Empty'
        else:
            return 'TimeIntervalTable: {} to {} ({})'.format(self.df.tstart.iloc[0], self.df.tend.iloc[-1], self.df.shape[0])
    
    def __repr__(self):
        msg  = 'TimeIntervalTable\n'
        msg += str(self.df)
        return msg

    def __deepcopy__(self, memo):
        """ You can't call self.copy() here. If you did, and created a subclass
            you would enter an infinite loop
        """
        new_table = super(TimeIntervalTable, self).copy()
        return TimeIntervalTable(new_table.df)
            
    def copy(self):
        new_table = super(TimeIntervalTable, self).copy()
        return TimeIntervalTable(new_table.df)
    
    def max(self):
        """ Return the time interval with longest duration """
        i = self.duration(units='sec').idxmax()
        return self.df.loc[i]
    
    def min(self):
        """ Return the time interval with shortest duration """
        i = self.duration(units='sec').idxmin()
        return self.df.loc[i]
    
    def duration(self, units=None): 
        if units == 'sec':
            return self.df.dur
        elif units == 'min':
            return self.df.dur/60.0
        elif units == 'h':
            return self.df.dur/3600.0
        elif units == 'd':
            return self.df.dur/86400.0
        elif units == 'str':
            return self.df.dur.apply(lambda x: sec2hms(x))
        else:
            return self.df.dur.apply(lambda x: pd.Timedelta(seconds=x))

    def group(self, by='day', fun='max', args=(), kwargs={}, index='times'):
        """ See <https://pandas.pydata.org/pandas-docs/stable/api.html#groupby>_ for the set of `fun` parameters
            available. Examples are: 'count', 'max', 'min', 'median', etc

            .. Tip:: Since Access inherits from TimeIntervalTable, the underlaying data format
                     is a `pandas.DataFrame`, not a `pandas.Series`. Consequently, only the groupby
                     functions of a generic GroupBy or DataFrameGroupBy are valid. Functions of SeriesGroupBy
                     are not allowed.
        """
        df = group_by_time(self.df, 'tstart', by=by, fun=fun, args=args, kwargs=kwargs, index=index)
        return TimeTable(df)
    
    def filter(self, t_min, t_max, include_edges=True):
        idx1 = (self.tstart >= t_min) & (self.tend <= t_max)
        if include_edges:
            idx2 = (self.tstart < t_min)  & (self.tend > t_min)
            idx3 = (self.tstart < t_max)  & (self.tend > t_max)
            idx1 = idx1 | idx2 | idx3
            
        df = self.df.loc[idx1, :]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            df['tstart'] = df['tstart'].clip(lower=t_min) # This throws warning even though it is the accepted way of doing it
            df['tend']   = df['tend'].clip(upper=t_max)
        return TimeIntervalTable(df)
    
    def shift(self, time_delta):
        self.df['tstart'] = self.df['tstart'] + time_delta
        self.df['tend']   = self.df['tend'] + time_delta
        return self