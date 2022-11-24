import os, gams, pandas as pd, numpy as np, pickle, pyDatabases
from pyDatabases import gpy, GpyDB, gpyDB, OrdSet, adjMultiIndexDB, adjMultiIndex
from pyDatabases.gpyDB_wheels import read, robust, adj, aggregateDB

def concatMultiIndices(l, names = None):
	if l:
		return pd.MultiIndex.from_frame(pd.concat([i.to_frame() for i in l]))
	elif len(names)==1:
		return pd.Index([], name = names[0])
	elif len(names)>1:
		return pd.MultiIndex.from_tuples([],names=names)

def stackIndices(l, names = None):
	return pd.MultiIndex.from_tuples(np.hstack([i.values for i in l]), names = pyDatabases.noneInit(names, l[0].names)) if isinstance(l[0], pd.MultiIndex) else pd.Index(np.hstack([i.values for i in l]), name = pyDatabases.noneInit(names,l[0].name))

