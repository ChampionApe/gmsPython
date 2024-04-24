import numpy as np, pandas as pd, pyDatabases
from pyDatabases import noneInit, gpyDB

def concatMultiIndices(l, names = None):
	if l:
		return pd.MultiIndex.from_frame(pd.concat([i.to_frame() for i in l]))
	elif len(names)==1:
		return pd.Index([], name = names[0])
	elif len(names)>1:
		return pd.MultiIndex.from_tuples([],names=names)

def stackIndices(l, names = None):
	return pd.MultiIndex.from_tuples(np.hstack([i.values for i in l]), names = noneInit(names, l[0].names)) if isinstance(l[0], pd.MultiIndex) else pd.Index(np.hstack([i.values for i in l]), name = noneInit(names,l[0].name))
