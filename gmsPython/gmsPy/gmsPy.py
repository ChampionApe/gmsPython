from ._gmsPy import *
from pyDatabases import gpyDB, gpyDB_wheels
from dreamtools.gamY import Precompiler
import pickle, gams, os
gmspyStandardOrder =  ('Root','Functions','Declare','Blocks','Fix','Unfix','Model','Solve')

# Auxiliary functions:
def arg2string(x,t=None):
	if t == 'file':
		with open(x,"r") as f:
			return f.read()
	elif isinstance(t,Precompiler):
		return t(as_string=x) if isinstance(x,str) else t(**x)
	elif t == 'gamY':
		return Precompiler(x)()
	elif isinstance(x,str):
		return x

def sortedArgs(args, order = gmspyStandardOrder):
	return {k:v for d in ({kk:vv for kk,vv in args.items() if kk.endswith(o)} for o in order) for k,v in d.items()}

def mergeDictAttrs(l,attr,sort=False):
	return sortedArgs({k:v for d in l for k,v in getattr(d,attr).items()},order=sort) if sort else {k:v for d in l for k,v in getattr(d,attr).items()}

def merge2dbs(main,other_i,residual=True):
	d = other_i.partition_db()
	gpyDB_wheels.robust.robust_merge_dbs(main.db, d['non_var'],priority='second')
	gpyDB_wheels.robust.robust_merge_dbs(main.db, d['var_endo'],priority='second')
	gpyDB_wheels.robust.robust_merge_dbs(main.db, d['var_exo'],priority='first')
	if residual:
		gpyDB_wheels.robust.robust_merge_dbs(main.db, d['residual'],priority='first')

def mergeDbs(main,other,residual=True):
	[merge2dbs(main,other_i,residual=residual) for other_i in other];
	return main.db

def mergeOrdSets(l,attr,state):
	return OrdSet([x for y in l for x in y.try_state(state)[attr]])

def attrFromState(s,attr,state):
	return s[attr] if state not in s.try_state(state) else s.try_state(state)[attr] 

def mergeStates_k(main, other, l, k, mergeArgs = False, order=gmspyStandardOrder):
	d = {'name': main.name+'_'+k, 'g_endo': mergeOrdSets(l,'g_endo',k), 'g_exo': mergeOrdSets(l,'g_exo',k),'blocks':mergeOrdSets(l,'blocks',k), 'solve': main.try_state(k)['solve']}
	return d | {'args': {}, 'text': {}} if mergeArgs is False else d | {'args': sortedArgs({key:value for di in [attrFromState(other_i,'args',k) for other_i in l] for key,value in di.items()},order=order),
											 'text': sortedArgs({key:value for di in [attrFromState(other_i,'text',k) for other_i in l] for key,value in di.items()},order=order)}

def mergeStates(main,other,l,mergeArgs=False,order=None):
	order = gmspyStandardOrder if order is None else order
	return {k: mergeStates_k(main,other,l,k,mergeArgs=mergeArgs,order=order) for other_i in l for k in other_i.states}

def mergeGmsSettings(main,other,order=None,residual=True,addStates=False):
	l = [main]+other
	[main.__setattr__(k,v) for k,v in {k: mergeDictAttrs(l,k) for k in ('macros','locals')}.items()]
	mergeCompile(main.Compile,[i.Compile for i in other])
	main.states = mergeStates(main, other,l,order=order)
	main.Compile.run()
	mergeDbs(main,other,residual=residual)
	return main

class GmsSettings:
	# ---	0: Initialization	--- #
	def __init__(self,f=None,**kwargs):
		if f:
			with open(f,"rb") as file:
				self = pickle.load(file)
		else:
			[setattr(self,k,pyDatabases.dictInit(k,v,kwargs)) for k,v in self.simpleStdSettings.items()];
			self.Compile = pyDatabases.dictInit('Compile',Compile(groups=pyDatabases.dictInit('groups',None,kwargs)),kwargs) # If 'Compile' in kwargs, use this. Else, use 'groups' in kwargs to init.
			self.Precompiler = pyDatabases.dictInit('Precompiler',Precompiler(**self.Precompiler_options),kwargs) # If 'Precompiler' in kwargs use this. Else, use 'precompiler_options' to init.
			self.db = pyDatabases.dictInit('db',gpyDB.GpyDB(ws=pyDatabases.dictInit('ws',None,kwargs)), kwargs) # If 'db' in kwargs use this. Else, use 'ws' to init.
			self.states = pyDatabases.dictInit('states',{'B': self.standardInstance()},kwargs) # if 'states' in kwargs use this. Else, use std. instance.

	@property
	def simpleStdSettings(self):
		return {'name': 'name', 'macros': {},'locals':{},'mainDbName': None, 'state':'B','Precompiler_options':{'has_read_file':True}}

	def standardInstance(self,state='B'):
		return {'name': f"{self.name}_{state}", 'g_endo': OrdSet(), 'g_exo': OrdSet(), 'blocks': OrdSet(), 'solve': None, 'args': {}, 'text': {}}

	def __getitem__(self,item):
		try:
			return self.states[self.state][item]
		except KeyError:
			return getattr(self,item)

	def __setitem__(self,item,value):
		if item in ('g_endo','g_exo','blocks'):
			self.states[self.state][item] = OrdSet(value)
		else:
			self.states[self.state][item] = value

	def setstate(self,state=None):
		if state is None:
			self.state = list(self.states.keys())[0]
		elif state in self.states:
			self.state = state
		else:
			self.states[state] = self.standardInstance(state=state)
			self.state = state

	def try_state(self,state):
		return self.states[self.state] if state not in self.states else self.states[state]

	# ---	1: Subsetting	--- #
	def metagroup(self,g,db=None):
		""" g ∈ {'g_exo','g_endo'} """
		return self.Compile.metaGroup(self.db if db is None else db, gs=self[g].v)

	def var_ss(self,var,g,db=None):
		""" type(var) == str, type(g) == _GmsPy.Group"""
		db = self.db if db is None else db
		if db[var].type == 'scalar_variable':
			return db[var] if var in g.conditions else None
		else:
			return gpyDB_wheels.adj.rc_AdjGpy(db[var],c=g.conditions[var],pm=True) if var in g.conditions else None

	def db_ss(self,g,db=None):
		""" g ∈ {'g_exo','g_endo'} """
		g = self.metagroup(g,db=db)
		return {k:v for k,v in {s: self.var_ss(s,g,db=db) for s in g.conditions if s in gpyDB.symbols_db(db)}.items() if v is not None}

	def inferVarExoFromVarEndo(self, var_endo, db = None):
		db = pyDatabases.noneInit(db, self.db)
		return {k: db[k] if k not in var_endo else gpyDB_wheels.adj.rc_AdjGpy(db[k], ('not',var_endo)) for k in self.Compile.getVariablesFromMetaGroup(self['g_exo']) if k in gpyDB.symbols_db(db)}

	def partition_db(self,db=None,checkOverlap = False):
		db = self.db if db is None else db
		d = {'non_var': db.getTypes(('set','subset','mapping','parameter','scalar_parameter')), 'var_endo': self.db_ss('g_endo',db=db), 'var_exo': self.db_ss('g_exo',db=db)}
		if checkOverlap:
			d['var_exo'] = {k: v if k not in d['var_endo'] else gpyDB_wheels.adj.rc_AdjGpy(v, ('not',d['var_endo'][k])) for k,v in d['var_exo'].items()}
			# d['var_exo'] = self.inferVarExoFromVarEndo(d['var_endo'], db=db)
		d['residual'] = {k:v for k,v in db.getTypes(('scalar_variable','variable')).items() if k not in (list(d['var_endo'])+list(d['var_exo']))}
		return d

	# ---	2: Writing methods	--- #
	def reset_Precompiler(self):
		self.Precompiler = Precompiler(**(self.Precompiler_options | {'locals_': self.Precompiler.locals, 'user_functions': self.Precompiler.user_functions}))

	def write(self,check_root=True,reset=True):
		""" compile text from args. """
		if reset:
			self.reset_Precompiler()
		if check_root:
			self['args'] = self.check_root(self['args'])
		self['text'] = {k: arg2string(v,self.Precompiler) for k,v in self['args'].items()}
		return self['text']

	def writeSolveState(self, state):
		""" get the text needed to resolve state"""
		self.setstate(state)
		return '\n'.join({k: arg2string(v,self.Precompiler) for k,v in gmsWrite.standardRun(self, self.db).items()}.values())

	def check_root(self,args):
		return {'Root': gmsWrite.writeRoot()} | args if not (list(args.keys()))[0].endswith(('Root','Root.gms','Root.gmy','Root.txt')) else args

	def stdArgs(self,blocks='',functions=None,prefix=None,prefix_run=None,run=True):
		self.mainDbName = self.db.name
		return gmsWrite.standardArgs(self,self.db,f"""%{self.db.name}%""",blocks=blocks,functions=functions,run=run,prefix=self.name+'_' if prefix is None else prefix, prefix_run = self['name']+'_' if prefix_run is None else prefix_run)

	def sortedArgs(self, order = gmspyStandardOrder):
		return sortedArgs(self['args'],order=order)

class GmsModel:
	def __init__(self,ws=None,options=None,**kwargs):
		self.init_ws(ws)
		self.init_opt(**pyDatabases.noneInit(options,{}),**kwargs)

	def init_ws(self,ws):
		if isinstance(ws,gams.GamsWorkspace):
			self.ws = ws
		elif type(ws) is str:
			self.ws = gams.GamsWorkspace(working_directory=ws)
		elif ws is None:
			self.ws = gams.GamsWorkspace()
		else:
			raise TypeError(f"The GmsModel class cannot be initialized with ws type {type(ws)}")

	def write_options(self,options_string):
		with open(os.path.join(self.ws.working_directory,self.opt_name), "w") as f:
			f.write(options_string)

	def init_opt(self,opt=None,opt_file=None,opt_name=None,**kwargs):
		self.opt_name = opt_name if opt_name else "options.opt"
		if isinstance(opt,str):
			self.write_options(opt)
			self.opt = self.ws.add_options()
			self.opt.file = 1
		elif isinstance(opt, gams.GamsOptions):
			self.opt = opt
		elif opt_file:
			self.opt = self.ws.add_options(opt_file=opt_file)
			self.opt.file = 1
		else:
			self.opt = self.ws.add_options()
		[setattr(self.opt,key,value) for key,value in kwargs.items()];
		
	@property
	def work_folder(self):
		return self.ws.working_directory

	def run(self,run=None,runfile=None,options_add=None,options_run=None,db_as_gpy=True):
		self.add_job(run=run,runfile=runfile,options=options_add)
		self.run_job(options=options_run)
		self.out_db = gpyDB.GpyDB(db=self.job.out_db,ws=self.ws) if db_as_gpy else None

	def add_job(self,run=None, runfile = None, options=None):
		if run:
			self.job = self.ws.add_job_from_string(run,**pyDatabases.noneInit(options,{}))
		elif runfile:
			runfile = runfile if os.path.isabs(runfile) else os.path.join(self.work_folder,runfile)
			self.job = self.ws.add_job_from_file(runfile,**pyDatabases.noneInit(options,{}))

	def run_job(self,options=None):
		self.job.run(gams_options=self.opt,**pyDatabases.noneInit(options,{}))

	def addlocal(self,placeholder,local):
		self.opt.defines[placeholder] = local

	def addDB(self,db,db_str=None,merge=True,mergeGdx='clear',exportdb=True,exportTo=None):
		""" Add a GpyDB by specifying db_str or exportTo. Writes a gdx file + add it as a placeholder in the model. """
		db_str = os.path.join(db.work_folder if exportTo is None else exportTo,db.name) if db_str is None else db_str
		if merge:
			db.merge_internal(merge=mergeGdx)
		if exportdb:
			db.database.export(db_str)
		self.addlocal(db.name, db_str)
