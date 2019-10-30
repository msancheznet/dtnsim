from simulator.utils.basic_utils import *
import numpy as np
import pandas as pd
from operator import itemgetter
from itertools import groupby

def rmse(x, y):
    x, y = new_array(x), new_array(y)
    return np.sqrt(np.mean((x-y)**2))

def row_norm(mat):
    """ Compute the norm of a set of vectors, each of which is the row of a 
        numpy matrix.

        :param matrix mat: The matrix that contains the vectors
        :return array: The norm of each row
    """
    mat = mat.values if is_pandas(mat) else np.array(mat)
    return np.sum(np.abs(mat)**2,axis=-1)**(1./2)

def row_dot(mat1, mat2):
    """ Compute dot product for a set of vectors, each of which is the row
        of a numpy matrix

        :param matrix mat1: The matrix that contains one set of vectors
        :param matrix mat2: The matrix that contains the other set of vectors
        :return array: The dot of the rows
    """
    mat1 = mat1.values if is_pandas(mat1) else np.array(mat1)
    mat2 = mat2.values if is_pandas(mat2) else np.array(mat2)
    return np.einsum('ij,ij->i', mat1, mat2)

def row_angle(mat1, mat2, units='deg'):
    angle = np.arccos(row_dot(mat1, mat2)/(row_norm(mat1)*row_norm(mat2)))
    if units == 'rad':
        return angle
    elif units == 'deg':
        return np.rad2deg(angle)
    else:
        raise ValueError('Units {} for an angle are not valid. Choices are deg or rad')
        
def group_consecutives(vals, just_ends=False):
    """Return list of consecutive lists of numbers from vals (number list).
       From: https://stackoverflow.com/questions/2154249/identify-groups-of-continuous-numbers-in-a-list
       
       :param list/tuple/np.array vals:
       :param bool just_ends: Default is False, see examples
    
       Example 1: vals = [2, 3, 4, 5, 12, 13, 14, 15, 16, 17]
                  res  = group_consecutives(vals)
                  res  = [(2, 3, 4, 5), (12, 13, 14, 15, 16, 17)]
                  
       Example 2: vals = [2, 3, 4, 5, 12, 13, 14, 15, 16, 17]
                  res  = group_consecutives(vals, just_ends=True)
                  res  = [(2, 5), (12, 17)]
    """
    if just_ends: 
        def f(g):
            group = list(map(itemgetter(1), g))
            return (group[0], group[-1])
    else: f = lambda g: tuple(map(itemgetter(1), g))
    
    return [f(g) for k, g in groupby(enumerate(vals), lambda x: x[0]-x[1])]

def find_consecutive(vals, val=None):
    """ Find indices of consecutive occurences of ``val`` within the array
        vals. Indices are always inclusive. If ``val`` is not provided, then
       all values present in array are returned 

        Example 1: vals = [1,1,2,2,2,1,1]
                    val  = 1
                    find_consecutive(vals, val) = [[0,1],[5,6]]
                    
       Example 2: vals = [1,1,2,2,2,1,1]
                  find_consecutive(vals) = {1: [[0,1],[5,6]], 2: [[2, 4]]}

        :param np.array/pd.DataFrame/pd.Series vals: Array of values
        :param val: Value to search for
       :return np.array or dict of np.arrays
    """
    # Check inputs
    vals = vals.values if is_pandas(vals) else vals
    vals = vals.transpose()[0] if is_column(vals) else vals
   
    # If val is provided, just use it
    if val is not None: return _find_consecutive(vals, val)
    
    # Find all possible vals
    return {val: _find_consecutive(vals, val) for val in np.unique(vals)}
    
def _find_consecutive(vals, val):
    """ See ``find_consecutive``    """
    # Work magic
    isval   = np.concatenate(([False], np.equal(vals, val).view(np.int8), [False]))
    absdiff = np.abs(np.diff(isval))
    ranges  = np.where(absdiff == 1)[0].reshape(-1, 2)
    ranges[:,1] = ranges[:,1]-1

    return ranges.tolist()
    
def combvec(*args):
    """ Fast implementation of Matlab's combvec function in Python. In a nutshell:
    
        vals = combvec([1,2,3], [4,5,6])
        vals = [[1,4], [1,5], [1,6], ..., [3,4], [3,5], [3,6]]

        To use combvec, simply

        def eval_options(var1, var2, var3):
            for v1, v2, v3 in combvec(var1, var2, var3):
                ....
    
        .. Tip:: For Matlab, see `<https://www.mathworks.com/help/nnet/ref/combvec.html?searchHighlight=combvec&s_tid=doc_srchtitle>`_
        .. Tip:: Implementation is based on `<https://stackoverflow.com/questions/1208118/using-numpy-to-build-an-array-of-all-combinations-of-two-arrays>`_
    """
    N = len(args)
    args = [np.atleast_1d(arg) for arg in args]
    idxs = [range(len(arg)) for arg in args]
    opts = np.array(np.meshgrid(*idxs), dtype=int).T.reshape(-1,N)
    vals = [[args[i][o] for i, o in enumerate(opt)] for opt in opts]
    return vals

def prctile(vals, q=[50, 75, 95, 99, 100], axis=0):
    data  = vals.values if is_pandas(vals) else vals
    q     = new_iterable(q)
    stats = np.nanpercentile(data, q=q, axis=axis)

    if is_pandas(vals):
        df = pd.DataFrame(stats, index=q, columns=vals.columns)
    else:
        df = pd.DataFrame(stats, index=q)

    return df

def isinteger(x, rtol=1e-05, atol=1e-08, equal_nan=False):
    """ Check if value x is an integer. Rounding error can be circumvented
        See https://docs.scipy.org/doc/numpy-1.10.4/reference/generated/numpy.isclose.html
        See https://stackoverflow.com/questions/21583758/how-to-check-if-a-float-value-is-a-whole-number
    """
    return np.isclose(x, np.round(x).astype('int'))
    
def union_intervals(x, y, stacked=True):
    """ Union of numeric intervals.

        :param array x: Start time of the intervals
        :param array y: End time of the intervals
        :param bool stacked: Return as matrix

        .. code:: python

            >> union_intervals([1, 2, 15], [10, 11, 20])
            >> array([[ 1, 11],
                     [15, 20]])

            >> union_intervals([1, 2, 15], [10, 11, 20], stacked=False)
            >> (array([ 1, 15]), array([11, 20]))

        .. Danger:: The sorting algorithm used is "mergesort" because it is
                    the only one in numpy that is stable (see
                    https://docs.scipy.org/doc/numpy-1.14.0/reference/generated/numpy.sort.html)
                    Note that Matlab uses a stable version of "quicksort"
    """
    # Initialize variables
    N = len(x)

    # Sort values
    x = np.append(x, y)
    p = np.argsort(x, kind='mergesort')
    t = x[p]

    # Work magic based on Matlab's `union_sets_intervals`
    z    = np.cumsum(np.bincount(np.arange(2*N), weights=2*((p+1)<=N)-1))
    z1   = np.append(0, z[0:-1])
    x, y = t[(z1==0)&(z>0)], t[(z1>0)&(z==0)]
    
    # If no need to stack, return immediately
    if not stacked: return x, y

    return np.stack((x, y), axis=1)

def xor_intervals(lb, ub, int_s, int_e, do_union=True, sort=False):
    """ xor of numeric intervals

        :param num lb: Lower bound for the overall interval
        :param num ub: Upper bound for the overall interval
        :param list ints: List of lists/tuples with the intervals
        :param bool do_union: If False, then the union of ``ints`` is
                              not performed. Set it to False **only**
                              if you can guarantee that ``ints`` do
                              not overlap
        :param bool sort: Sort the intervals prior. If ``do_union`` is
                          True, then this has no effect as the union
                          process will do the sorting for you

        >> lb, ub = 0, 10
        >> ints   = [[2, 3], [5, 8]]
        >> int_s, int_e = zip(*ints)
        >> xor_intervals(lb, ub, ints_s, int_e)
           [(0, 2), (3, 5), (8, 10)]
    """
    # Preprocess the intervals if needed
    if do_union:
        # Compute the union of the intervals
        int_s, int_e = union_intervals(int_s, int_e, stacked=False)
    elif sort:
        # If sorting is needed, do it
        idx = np.argsort(int_s)
        int_s, int_e = int_s[idx], int_e[idx]

    # Compute xor
    sint = np.append(lb, int_e)
    eint = np.append(int_s, ub)

    # Filter any intervals with 0 duration and return
    idx = (eint-sint > 0)
    return list(zip(sint[idx], eint[idx]))