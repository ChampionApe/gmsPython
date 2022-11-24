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

def pname(v, name):
	return f"{v}_{name}"
def ssname(v,name):
	return f"{v}_{name}_ss"
def invpname(v, name):
	return v.rsplit('_'+name,1)[0]
def invssname(v,name):
	return v.rsplit('_'+name+'_ss',1)[0]

def gridDB(db0, dbT, name, n = 10, extractSol = None, db_name = 'grids', loop = 'l1', gridtype = 'linear', phi = 1, checkDiff = True, error = 1e-11, sort_index = True):
	db = GpyDB(ws = db0.ws, alias = db0.get('alias_'), **{'name': db_name})
	db[loop] = loop+'_'+pd.Index(range(1,n+1),name=loop).astype(str)
	db.updateDict = {}
	for var in set(db0.getTypes(['variable','parameter'])).intersection(set(dbT.getTypes(['variable','parameter']))):
		commonIndex = db0.get(var).index.intersection(dbT.get(var).index)
		v0,vT = adj.rc_pd(db0.get(var),commonIndex), adj.rc_pd(dbT.get(var),commonIndex)
		if checkDiff:
			commonIndex = vT[abs(v0-vT)>error].index
			v0,vT = adj.rc_pd(v0,commonIndex),adj.rc_pd(vT,commonIndex)
		if not vT.empty:
			db[ssname(var,name)] = commonIndex
			db[pname(var,name)] = gpy(adjMultiIndex.addGrid(v0,vT,db.get(loop),pname(var,name), gridtype=gridtype, phi=phi, sort_index = sort_index), **{'type':'parameter'})
			db.updateDict[var] = {'c': db[ssname(var,name)], 'par': pname(var,name)}
	for var in set(db0.getTypes(['scalar_variable','scalar_parameter'])).intersection(set(dbT.getTypes(['scalar_variable','scalar_parameter']))):
		if (not checkDiff) or (abs(db0.get(var)-dbT.get(var))>error):
			db[pname(var, name)] = gpy(adjMultiIndex.addGrid(db0.get(var),dbT.get(var),db.get(loop),pname(var, name),gridtype=gridtype,phi=phi),**{'type':'parameter'})
			db.updateDict[var] = {'c': None, 'par': pname(var,name)}
	db.updateSolDict = {'_'.join(['sol',var,name]): {'c': extractSol[var], 'var': var} for var in pyDatabases.noneInit(extractSol, {})}
	[db.__setitem__(k, gpy(pd.Series([], index = pd.MultiIndex.from_tuples([], names = db[loop].domains+db0[v['var']].domains), name = k), **{'type':'parameter'})) for k,v in db.updateSolDict.items()];
	aggregateDB.updateSets(db,clean_alias=True)
	db.merge_internal()
	return db
