from gmsPython import gmsWrite, gmsPy
from . import gmsPyGlobals
import pyDatabases, pickle
from pyDatabases.gpyDB_wheels import robust

class GmsPython:
	""" standard gamspython models """
	def __init__(self,name=None,f=None,s=None,glob=None,m=None,ns=None,m_kwargs=None,s_kwargs=None,g_kwargs=None):
		if f is not None:
			with open(f, "rb") as file:
				self.__dict__ = pickle.load(file).__dict__
		else:
			self.s = gmsPy.GmsSettings(**(pyDatabases.noneInit(s_kwargs,{})|{'name':name})) if s is None else s
			self.ns = pyDatabases.noneInit(ns,{})
			self.m = {}
			self.initModules(pyDatabases.noneInit(m,[]),**pyDatabases.noneInit(m_kwargs,{}))
			self.InitGlobals(glob,g_kwargs)

	def initModules(self,m,submodule_kwargs=None,**m_kwargs):
		if any([isinstance(mi,GmsPython) for mi in m]):
			gmsPy.mergeGmsSettings(self.s,[mi.s for mi in m if isinstance(mi,GmsPython)],**m_kwargs)
		[self.addModule(mi,**pyDatabases.noneInit(submodule_kwargs,{})) for mi in m];

	def addModule(self,m,merge_s=False,adjust_db=True,**kwargs):
		if isinstance(m,GmsPython):
			if merge_s:
				gmsPy.mergeGmsSettings(self.s,[m.s],**kwargs)
			if adjust_db:
				m.s.db = self.s.db
			self.m[m.name] = m
		else:
			self.m[m.name] = Submodule(**kwargs)

	def InitGlobals(self, glob, g_kwargs):
		self.glob = getattr(gmsPyGlobals, glob)(kwargs_ns=self.ns,kwargs_vals=g_kwargs) if type(glob) is str else glob
		if self.glob:
			self.ns.update(self.glob.ns)
			[self.s.db.__setitem__(k,v) for k,v in self.glob.db.items()];

	# --- 		1: Interact w. namespace/database 		--- #
	def n(self, item, m=None):
		try:
			if m is None:
				return self.ns[item]
			elif type(m) is str:
				return self.m[m].n(item)
			else:
				return self.m[m[0]].n(item,m=m[1])
		except KeyError:
			return item

	def g(self, item, m=None):
		return self.s.db[self.n(item, m=m)]

	def get(self, item, m=None):
		return self.g(item, m=m).vals

	@property
	def name(self):
		return self.s.name

	# ---		2: Standard compile methods			---- #
	def compile(self,initDB=False,states_kwargs=None):
		self.compile_groups()
		self.compile_states(**pyDatabases.noneInit(states_kwargs,{}))
		if initDB:
			self.initDB()

	def compile_groups(self):
		self.s.Compile.groups.update(self.groups())
		self.s.Compile.run()
		return self.s.Compile.groups

	def compile_states(self,**kwargs):
		self.s.states.update(self.states(**kwargs))

	def states(self,compile_modules = True,order=None, mergeArgs = True):
		if compile_modules:
			[m.compile_states() for m in self.m.values() if hasattr(m,'compile_states')];
		other = [m.s for m in self.m.values() if hasattr(m,'s')]+[m for m in self.m.values() if hasattr(m,'states') and isinstance(m,Submodule)];
		return gmsPy.mergeStates(self.s, other, [self.s]+other, mergeArgs = mergeArgs, order=order)

	def initDB(self):
		for m in self.m.values():
			if hasattr(m,'initDB'):
				robust.robust_merge_dbs(self.s.db,m.initDB(m=m.name),priority='first')
	def groups(self):
		return self.getAttrFromModules('groups')

	def getAttrFromModules(self,attr):
		return {k:v for d in (getattr(m,attr)(m=m.name) if hasattr(m,attr) else {} for m in self.m.values()) for k,v in d.items()}

	# ---		3: Write and run methods		---- #
	def write(self, order = gmsPy.gmspyStandardOrder, kwargs=None, write_kwargs = None):
		self.s['args'].update(self.s.stdArgs(pyDatabases.noneInit(kwargs,{})))
		self.s['args'] = gmsPy.sortedArgs(self.s['args'], order = order)
		return self.s.write(**pyDatabases.noneInit(write_kwargs,{}))

	def run(self, model=None, db_str = None, exportdb = True, exportTo = None, ws = None, options = None, merge=True, mergeGdx = 'clear', options_add=None, options_run=None,**kwargs):
		if isinstance(model, gmsPy.GmsModel):
			return self.runModel(model, db_str=db_str, merge=merge, mergeGdx = mergeGdx, exportdb=exportdb,exportTo=exportTo,options_add=options_add, options_run=options_run)
		else:
			return self.runAndInitModel(db_str=db_str, merge=merge, mergeGdx = mergeGdx, exportdb=exportdb,exportTo=exportTo,ws=ws,options=options,options_add=options_add, options_run=options_run,**kwargs)

	def runAndInitModel(self, db_str=None, exportdb=True, exportTo=None, ws=None, options=None, merge=True, mergeGdx = 'clear', options_add=None, options_run = None, **kwargs):
		model = gmsPy.GmsModel(ws=ws,options=options,**kwargs)
		return self.runModel(model, db_str = db_str, merge=merge, mergeGdx = mergeGdx, exportdb=exportdb, exportTo = exportTo,options_add=options_add, options_run = options_run)

	def runModel(self,model,db_str=None, merge=True, mergeGdx = 'clear', exportdb=True, exportTo = None, options_add=None, options_run = None):
		model.addDB(self.s.db, db_str=db_str, merge=merge, mergeGdx = mergeGdx, exportdb=exportdb, exportTo=exportTo)
		model.run(run = '\n'.join(self.s['text'].values()), options_add=options_add, options_run = options_run)
		return model

	def sneakyCalib(self, dbTarget, cState = 'C', model=None, db_str = None, exportdb = True, exportTo = None, ws = None, options = None, options_add=None, options_run=None, loop_kwargs = None, **kwargs):
		""" Like sneaky solve, but changes state to 'C' """
		if model is None:
			model = gmsPy.GmsModel(ws = ws, options=options, **kwargs)
		options_run = {'checkpoint': model.ws.add_checkpoint()} | pyDatabases.noneInit(options_run, {})
		self.run(model = model, db_str = db_str, exportdb = exportdb, exportTo = exportTo, options_add=options_add, options_run=options_run) # solve baseline, add checkpoint
		cp = model.ws.add_checkpoint()
		model.run(run = self.s.writeSolveState(cState), options_add = {'checkpoint': options_run['checkpoint']}, options_run = {'checkpoint': cp}) # switch to calibration state, run from checkpoint, add new checkpint
		text, db = gmsWrite.SolveLoop(self.s, dbTarget, db0 = model.out_db, **pyDatabases.noneInit(loop_kwargs, {})) # run loop with exogenous variables gradually adjusted towards solution
		cp2 = model.ws.add_checkpoint()
		model.addDB(db)
		model.run(run=text, options_add = {'checkpoint': cp}, options_run = {'checkpoint': cp2})
		return model, cp2

	def sneakySolve(self, dbTarget, model=None, db_str = None, exportdb = True, exportTo = None, ws = None, options = None, options_add=None, options_run=None, loop_kwargs = None, **kwargs):
		""" Start from a feasible solution, and then sneak up on solution by adjusting exogenous values """
		if model is None:
			model = gmsPy.GmsModel(ws = ws, options=options, **kwargs)
		options_run = {'checkpoint': model.ws.add_checkpoint()} | pyDatabases.noneInit(options_run, {})
		self.run(model = model, db_str = db_str, exportdb = exportdb, exportTo = exportTo, options_add=options_add, options_run=options_run)
		text, db = gmsWrite.SolveLoop(self.s, dbTarget, db0 = model.out_db, **pyDatabases.noneInit(loop_kwargs, {}))
		cp = model.ws.add_checkpoint()
		model.addDB(db)
		model.run(run=text, options_add = {'checkpoint':options_run['checkpoint']}, options_run = {'checkpoint': cp})
		return model, cp

class Submodule:
	""" Simple submodule that is not defined by a GmsSettings instance. """
	def __init__(self, name = None, ns=None, **KeyAttrs):
		self.name, self.ns = name, pyDatabases.noneInit(ns,{})
		[setattr(self,k,v) for k,v in KeyAttrs.items()];

	def n(self,item,m=None):
		try:
			return self.ns[item] if m is None else self.m[m].n(item)
		except KeyError:
			return item

	def state(self,k):
		if hasattr(self,'states'):
			return self.states[k] if k in self.states else self.states[self.state]