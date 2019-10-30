from contextlib import contextmanager
from copy import  deepcopy
from cProfile import Profile
from datetime import datetime as dt
import inspect
from itertools import chain
import numbers
import numpy as np
import os
import pickle
import pandas as pd
from pstats import Stats
import time
import sys
from warnings import warn as python_warn

def warn(*args, **kwargs):
    python_warn(args[0].format(*args[1:]), **kwargs)

def timeit(fun, *args, **kwargs):
    from simulator.utils.time_utils import sec2hms
    tic = time.time()
    res = fun(*args, **kwargs)
    dt  = sec2hms(time.time()-tic)
    disp('Time elapsed: {} seconds'.format(dt))
    return res

def profileit(fun, *args, **kwargs):
    pr = Profile()
    pr.enable()
    res = fun(*args, **kwargs)
    pr.disable()
    ps = Stats(pr).sort_stats('tottime')
    #ps = Stats(pr).sort_stats('cumtime')
    ps.print_stats()
    return res, ps

def def_val(kwargs, vname, def_val=None, pop=False):
    if pop is False:
        return kwargs[vname] if vname in kwargs else def_val
    else:
        return kwargs.pop(vname, def_val)

def disp(*args, **kwargs):
    verbose = def_val(kwargs, 'verbose', True)
    if verbose is False:
        return
    if len(args) == 1:
        print(args[0])      # Print without arguments
    else:
        s, sargs = args[0], args[1:]
        print(s.format(*sargs))
    sys.stdout.flush()

def is_numeric(obj):
    return isinstance(obj, numbers.Number)

def is_list(obj):
    return isinstance(obj, (list, tuple))

def is_dict(obj):
    return isinstance(obj, dict)

def is_string(obj):
    return isinstance(obj, basestring) if sys.version_info <= (3, 0) else isinstance(obj, str)

def is_matrix(x):
    return (len(x.shape) > 1 and x.shape[1] > 1)

def is_column(x):
    return (len(x.shape) > 1 and x.shape[1] == 1)

def is_row(x):
    return len(x.shape) == 1

def is_pandas(x):
    return isinstance(x, (pd.DataFrame, pd.Series))

def is_dataframe(x):
    return isinstance(x, pd.DataFrame)

def is_series(x):
    return isinstance(x, pd.Series)

def new_iterable(obj):
    return obj if is_list(obj) else (obj,)

def new_array(obj):
    return obj.values if is_pandas(obj) else np.array(obj)

def new_dataframe(*args, **kwargs):
    # Check inputs
    assert len(args)==1, 'Only one argument allowed'
    
    # Initialize variables
    vals = args[0]
    
    # Special cases
    if is_dataframe(vals):
        return vals
    if is_series(vals):
        return vals.to_frame(name=kwargs.pop('name', None))
    
    # See http://pbpython.com/pandas-list-dict.html
    if is_dict(vals):
        return pd.DataFrame.from_dict(vals, **kwargs)
    elif is_list(vals):
        if is_dict(vals[0]):
            return pd.DataFrame(vals, **kwargs)
        elif is_list(vals[0][1]):
            return pd.DataFrame.from_items(vals, **kwargs)
        else:
            return pd.DataFrame.from_records(vals, **kwargs)
        
    raise TypeError('Cannot construct a pandas data frame using the constructor with type {}'.format(type(vals)))
                

def exists(obj, mode='var', var=None):
    """ Check if object exists as variable, file, directory or any of the above

        .. Warning:: In Spyder you might need to call exists('var', var=locals())
                     for this function to work.
    """
    if mode == 'var':
        return _exists_var(obj, var)
    elif mode == 'dir':
        return _exists_dir(obj)
    elif mode == 'file':
        return _exists_file(obj)
    elif mode == 'system':
        return _exists_system(obj)
    elif mode == 'any':
        return _exists_var(obj) & _exists_system(obj)
    else:
        raise ValueError('Mode {} is not recognized. Options are "var", "dir", "file", "system", "any"')

def _exists_var(obj, variables):
    """ See if the object exists in the caller namespace

        .. Warning:: Does not work in Spyder
    """
    if variables is None: 
        frame = inspect.currentframe()
        try:
            return (obj in frame.f_back.f_locals)
        finally:
            del frame
    else:
        return (obj in variables)

def _exists_dir(obj):
    return os.path.isdir(os.path.abspath(obj))

def _exists_file(obj):
    return os.path.isfile(os.path.abspath(obj))

def _exists_system(obj):
    return os.path.exists(os.path.abspath(obj))

def save(obj, file, mode=None, time_tag=False):
    # Add time tag to file name
    if time_tag is True:
        file = file + ' - ' + dt.today().strftime('%m-%d-%Y %H:%M:%S')

    # If no mode is defined, infer it
    if mode is None:
        if isinstance(obj, (pd.DataFrame, pd.Series)):
            mode = 'dataframe'
        else:
            mode = 'pickle'

    # Initialize variables
    fname = os.path.abspath(file)

    # Save routine depending on mode
    if mode.lower() == 'pickle':
        with open(fname + '.rs', 'wb') as f:
            pickle.dump(obj, f)
    elif mode.lower() == 'dataframe':
        obj.to_excel(fname + '.xlsx')
    elif mode.lower() == 'csv':
        obj.to_csv(fname + '.csv')
    else:
        raise ValueError('Save mode {} is not available. Only "pickle", "dataframe" and "csv" are available'.format(mode))

def read(file, **kwargs):
    # Read options and initialize variables
    dtype = kwargs.pop('dtype', None)
    fname = os.path.abspath(file)

    # Get extension of the file
    filename, file_extension = os.path.splitext(file)

    # Set default read mode if possible
    if dtype is None:
        if file_extension.lower() == '.xls' or file_extension.lower() == '.xlsx':
            dtype = 'dataframe'
        elif file_extension.lower() == '.csv':
            dtype = 'csv'
        elif file_extension.lower() == '.json':
            dtype = 'json'

    # Special cases
    if dtype is not None:
        if dtype.lower() == 'dataframe':
            return pd.read_excel(fname, **kwargs)
        elif dtype.lower() == 'csv':
            return pd.read_csv(fname, **kwargs)
        elif dtype.lower() == 'json':
            return pd.read_json(fname, **kwargs)

    # Basic pickle read
    objects = []
    with open(fname, "rb") as openfile:
        while True:
            try:
                objects.append(pickle.load(openfile))
            except EOFError:
                break

    # Depack if possible and return
    return objects[0] if len(objects) == 1 else objects

@contextmanager
def hdf5_store(store_path, mode='r', compress=True):
    """ Write/Read an HDF5 store to import/export pandas tables
    
        :param str store_path: The absolute path for the store.
        :param char mode: 'r' for read (default), 'w' for write, 'a' for append
                          (default mode is 'r')
    
        Example 1: with('./store.h5', mode='r') as store:
                      df = store['/dataframe'] 
                      
        Example 2: with('./store.h5', mode='w') as store:
                      store['/dataframe'] = df
    """
    # If mode is neither read nor write
    if mode not in ['r', 'w', 'a']: 
        raise ValueError("'mode' must be 'r' or 'w' or 'a'")
    
    # If a store exists already and we are in write mode, delete it
    if mode == 'w' and os.path.exists(store_path): 
        os.remove(store_path)
        
    # If we are in read/append mode and the store does not exist, raise error
    if mode in ['r', 'a'] and not os.path.exists(store_path):
        raise FileExistsError('File {} not present in disk'.format(store_path))
    
    # Create new store
    store = pd.HDFStore(store_path) if not compress else pd.HDFStore(store_path, complib='zlib', complevel=9)

    # Yield the store
    yield store
    
    # Close the store
    store.close()

def show_progress(ind=None, s=None, i=None, N=None, t=None, msg=None, sep='\t - '):
    """ Show progress during a simulation or optimization

        :param object ind: The individual, architecture or design being evaluated
        :param object score: The score/metrics values for this individual
        :param int i: The index for this individual
        :param int N: The total number of individuals to evaluate
        :param float t: The elapsed seconds required to evaluate the individual
    """
    from simulator.utils.time_utils import sec2hms
    smsg, prefix = [], True

    # Add progress information
    if i is not None and N is not None:
        p = 100*((1.0*i+1)/N)
        smsg.append('({}/{} - {:.1f}%)'.format(i+1, N, p))
    elif i is not None:
        smsg.append('({})'.format(i+1))
    else:
        prefix = False

    # Add start message
    if msg is not None:
        smsg.append(msg)

    # Add individual information
    if ind is not None:
        smsg.append('Individual: {}'.format(ind))

    # Add score information
    if s is not None:
        smsg.append('Score: {}'.format(s))

    # Add time information
    if t is not None:
        smsg.append('Elapsed time: {}'.format(sec2hms(t)))

    # Display log message
    s = smsg[0] + ': ' + sep.join(smsg[1:]) if prefix is True else sep.join(smsg)
    disp(s)

class Counter(object):
    def __init__(self, start=-1):
        self.value = start

    def __next__(self):
        self.value += 1
        return self.value

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return '<Counter: {}>'.format(self.value)

class Timer(object):
    """ Timer object for Python. It can be used in two modes

        Mode 1:
            with Timer('Fun name'):
                # Run fun()

        Mode 2:
            for i in range(10):
                timer = Timer(N=10)
                val   = fun(i)
                timer.toc(ind=i, score=val, i=i)
    """
    def __init__(self, name=None, N=None):
        self._name = name
        self._tic  = time.time()
        self._N    = N

    def __enter__(self):
        self._tic = time.time()

    def __exit__(self, type, value, traceback):
        show_progress(msg=self._name, t=time.time() - self._tic)

    def toc(self, msg=None, ind=None, score=None, i=None):
        self._toc = time.time()
        dt = self._toc - self._tic
        show_progress(ind=ind, s=score, i=i, N=self._N, t=dt, msg=None)

class UniqueDict(dict):
    def __setitem__(self, k, v):
        if k in self.keys():
            raise ValueError("Key {} is already present".format(k))
        else:
            return super(UniqueDict, self).__setitem__(k, v)

    def __str__(self):
        return super(UniqueDict, self).__str__()

    def __repr__(self):
        return super(UniqueDict, self).__repr__()

class Table(object):
    def __init__(self, *args, **kwargs):
        self.df = new_dataframe(*args, **kwargs)

    @property
    def empty(self):
        return self.df.empty
            
    def __getitem__(self, item):
        val = self.df.__getitem__(item)
        if is_pandas(val):
            return Table(val)
        else:
            return val 
    
    def __setitem__(self, item, val):
        self.df.__setitem__(item, val)
        
    def __delitem__(self, item):
        self.df.__delitem__(item)
        
    def __getattr__(self, item):
        return self.__dict__['df'].__getattr__(item)

    def __iter__(self):
        return self.df.iterrows()

    def __contains__(self, val):
        return (val in self.df)
    
    def __bool__(self):
        return (not self.df.empty)

    def __add__(self, val):
        assert is_numeric(val), '+ operation with table is only defined with numbers. Tried to add {}'.format(val)
        new_df = self.df.__add__(val)
        return self.__class__(new_df)

    def __radd__(self, val):
        assert is_numeric(val), '+ operation with table is only defined with numbers. Tried to add {}'.format(val)
        new_df = self.df.__radd__(val)
        return self.__class__(new_df)

    def __sub__(self, val):
        assert is_numeric(val), '- operation with table is only defined with numbers. Tried to substract {}'.format(val)
        new_df = self.df.__sub__(val)
        return self.__class__(new_df)

    def __rsub__(self, val):
        assert is_numeric(val), '- operation with table is only defined with numbers. Tried to substract {}'.format(val)
        new_df = self.df.__rsub__(val)
        return self.__class__(new_df)

    def __mul__(self, val):
        assert is_numeric(val), '* operation with table is only defined with numbers. Tried to multiply by {}'.format(val)
        new_df = self.df.__mul__(val)
        return self.__class__(new_df)

    def __rmul__(self, val):
        assert is_numeric(val), '* operation with table is only defined with numbers. Tried to multiply by {}'.format(val)
        new_df = self.df.__rmul__(val)
        return self.__class__(new_df)

    def __div__(self, val):
        assert is_numeric(val), '/ operation with table is only defined with numbers. Tried to divide by {}'.format(val)
        new_df = self.df.__div__(val)
        return self.__class__(new_df)

    def __rdiv__(self, val):
        assert is_numeric(val), '/ operation with table is only defined with numbers. Tried to divide by {}'.format(val)
        new_df = self.df.__rdiv__(val)
        return self.__class__(new_df)
    
    def __str__(self):
        return 'Table'
    
    def __repr__(self):
        msg  = 'Table\n'
        msg += str(self.df)
        return msg

    def __deepcopy__(self, memo):
        cls     = self.__class__
        new_obj = cls.__new__(cls)

        # Add the new access to memo to avoid excess copying in case the object itself is
        # referneces from its member    
        # See https://stackoverflow.com/questions/1500718/what-is-the-right-way-to-override-the-copy-deepcopy-operations-on-an-object-in-p/1500887#1500887
        memo[id(self)] = new_obj

        # Copy all attributes
        for k, v in self.__dict__.iteritems():
            if k == 'df':
                setattr(new_obj, 'df', self.df.copy(deep=True))
            else:
                setattr(new_obj, k, deepcopy(v, memo))
        
        return new_obj

    def copy(self):
        return self.__class__(self.df.copy(deep=True))

    @classmethod
    def load(cls, *args, **kwargs):
        """ Read from excel.
            
            :param args: Name of Excel file (only one argument allowed)
            :param kwargs: See https://pandas.pydata.org/pandas-docs/stable/generated/pandas.read_excel.html
        """
        return cls(pd.read_excel(args[0], **kwargs))

    def export(self, filename, **kwargs):
        """ For list of kwargs, see https://pandas.pydata.org/pandas-docs/stable/generated/pandas.DataFrame.to_excel.html
        """
        # Get the filepath
        fname, ext = os.path.splitext(filename)
        ext = '.xlsx' if ext == '' else ext
        filepath = os.path.abspath(fname + ext)

        # Create the excel writer
        self.df.to_excel(filepath, **kwargs)    
            

    def flatten(self):
        df = self.df.reset_index()
        return self.__class__(df)

    def replace(self, *args, **kwargs):
        """ Replace a value in the entire table
            
            :param old_val: Value to find and replace
            :param new_val: Value to replace old_val with
            
            For kwargs, see https://pandas.pydata.org/pandas-docs/stable/generated/pandas.DataFrame.replace.html
        """
        new_df = self.df.replace(to_replace=args[0], value=args[1])
        return self.__class__(new_df)

    def delete_col(self, col_name):
        if col_name in self.columns:
            del self.df[col_name]
        return self

    def rename_col(self, old_name, new_name):
        assert old_name in self.df.columns, 'Column {} not present in this Table'.format(old_name)
        new_cols = [(new_name if col == old_name else col)for col in self.df.columns]
        self.df.columns = new_cols
        return self

    def sort_columns(self, cols):
        self.df = self.df[cols]
        return self

    def sort_rows(self, *args, **kwargs):
        """ Sort rows of this table. For options see http://pandas.pydata.org/pandas-docs/version/0.19.2/generated/pandas.DataFrame.sort_values.html#pandas.DataFrame.sort_values.
        """
        reset_index = def_val(kwargs, 'reset_index', def_val=True, pop=True)
        df = self.df.sort_values(*args, **kwargs)
        if reset_index is True:
            self.df = df.reset_index(drop=True)
        else:
            self.df = df
        return self

    def sort_index(self, **kwargs):
        """ Sort index of table. For options see https://pandas.pydata.org/pandas-docs/stable/generated/pandas.DataFrame.sort_index.html
        """
        self.df = self.df.sort_index(**kwargs)
        return self

    def unique(self, *args, **kwargs):
        # Initialize variables
        mode = def_val(kwargs, 'mode', def_val='column')
        data = self.df.loc[:, args]

        if mode.lower() == 'column':
            data = data.drop_duplicates()
        elif mode.lower() == 'combined':
            data = pd.unique(data.values.ravel())
        else:
            raise KeyError('Mode {} is not valid. Options are "column" and "combined"'.format(mode))

        return self.__class__(data)

    def to_row_list(self, index=True):
        """ Get a list of tuples, where each tuple is a row

            :param bool index: If true, the first element of each tuple is the index.
                               Otherwise the index is ignored.
        """
        if index is True:
            return [tuple(chain([k], list(r))) for k, r in self]
        else:
            return [tuple(r) for _, r in self]

    def to_col_list(self, index=True):
        raise NotImplementedError

    def to_row_dict(self):
        """ Get a dictionary where the key is the index and the value is the row """
        vals = self.to_row_list()
        return dict(zip(self.df.index.values, vals))

    def to_col_dict(self, index=True):
        """ Get a dictionary where the key is the column header and the value is the column.
            
            :param bool index: If true, the first tuple corresponds to the index.
        """
        d = self.df.to_dict(orient='list')
        d['index'] = self.df.index.values
        return d

class TableList(UniqueDict):
    def __init__(self, *args, **kwargs):
        self.var_type = def_val(kwargs, 'var_type', def_val=object)
        super(TableList, self).__init__(*args)

    def __setitem__(self, item, value):
        self._check_type(value)
        super(TableList, self).__setitem__(item, value)

    def __iter__(self):
        return self.iteritems()

    def __str__(self):
        return str(self.keys())

    def keys(self):
        keys = super(TableList, self).keys()
        return sorted(keys)

    def _check_type(self, obj):
        assert isinstance(obj, self.var_type), 'Only {} objects can be added to {}. Tried to add {}'.format(self.var_type, self.__class__, type(obj))

    def to_table(self, idx_names):
        if bool(self) is False:
            index = pd.MultiIndex(levels=[[]]*len(idx_names), labels=[[]]*len(idx_names), names=idx_names)
            df = pd.DataFrame(index=index, columns=[''])
        else:
            d  = [table.df for table in self.values() if table.empty is False]
            df = pd.concat(d, axis=0, keys=self.keys())
            df.index.names = idx_names

        return Table(df)

    def export(self, *args, **kwargs):
        # Process inputs
        file = args[0] + '.xlsx'
        mode = def_val(kwargs, 'mode', 'single', pop=True)

        # Save everything
        if mode.lower() == 'single':
            df = self.to_table(**kwargs)
            df.to_excel(file)
        elif mode.lower() == 'multi':
            # Create a Pandas Excel writer using XlsxWriter as the engine.
            writer = pd.ExcelWriter(file, engine='xlsxwriter')

            # Export each access in a sheet
            for id, table in self:
                kwargs['sheet_name'] = str(id)
                table.df.to_excel(writer, **kwargs)

            # Save excel
            writer.save()
        else:
            raise KeyError('Export mode for {} can only be "single" or "multi". Value provided is {}'.format(self.__class__, mode))

