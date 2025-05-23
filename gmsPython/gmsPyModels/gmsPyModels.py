from gmsPython.auxfuncs import *
import os, pickle
# from pyDatabases import noneInit
from pyDatabases.gpyDB import GpyDB
from gmsPython.gmsWrite.gmsWrite import StdArgs, FromDB
from gmsPython.gamY.gamY import Precompiler
from gmsPython.gmsPy.gmsPy import jTerms

def checkAttr(obj, attr, default = None):
	return getattr(obj, attr) if hasattr(obj, attr) else default

class Model:
	""" Simple shell for models defined with namespaces, databases, compiler etc.."""
	def __init__(self, name = None, ns = None, database = None, compiler = None, asModule = False, **kwargs):
		self.db = noneInit(database, GpyDB(**kwargs))
		self.name = name
		self.compiler = noneInit(compiler, Precompiler())
		self.j = jTerms(self.compiler)
		self.ns = noneInit(ns, {})
		self.m = {}
		self.cps = {} # checkpoints
		self.asModule = asModule
		self.dropattrs = ['cps','job','out_db'] # what attributes are dropped in exports

	### 0: Properties/customized methods
	@classmethod
	def load(cls, filename):
		with open(filename, "rb") as f:
			return pickle.load(f)
	@property
	def ws(self):
		return self.db.ws
	@property
	def work_folder(self):
		return self.db.work_folder
	@property
	def data_folder(self):
		return self.db.data_folder

	def makePropertyDynamic(self, key, value = None):
		""" create dynamic property out of "static" one """
		self.addProperty(key, noneInit(value, getattr(self, key)))

	def addProperty(self, key, value):
		""" default dynamic property method """
		setattr(self, f'_{key}', value)
		setattr(type(self), key, property(fget = lambda self: getattr(self, f'_{key}'), fset = lambda self, value: setattr(self, f'_{key}', value)))

	def __getstate__(self):
		if not self.asModule:
			self._loadDbFrom = os.path.join(self.data_folder, self.db.name)
			self.db.export()
		return {key:value for key,value in self.__dict__.items() if key not in (self.dropattrs+['db'])}
		
	def __setstate__(self,dict_):
		""" Don't include ws. Don't include db. """
		self.__dict__ = dict_
		if not self.asModule:
			self.db = GpyDB(dict_['_loadDbFrom'])
			for m in self.m.values():
				if isinstance(m, Model):
					m.db = self.db

	def export(self, name = None, repo = None):
		name = self.name if name is None else name
		repo = self.data_folder if repo is None else repo
		with open(os.path.join(repo,name), "wb") as file:
			pickle.dump(self, file)

	### 1. Navigate symbols
	def n(self, item, m = None):
		try:
			return getattr(self, f'n_{m.__class__.__name__}')(item, m)
		except KeyError:
			return item
	def n_NoneType(self, item, m):
		return self.ns[item]
	def n_str(self, item, m):
		return self.m[m].n(item)
	def n_tuple(self, item, m):
		return self.m[m[0]].n(item, m = m[1])
	def g(self, item, m = None):
		return self.db[self.n(item, m = m)]
	def get(self, item, m = None):
		return self.db(self.n(item, m = m))

	### 2: Modules
	def addModule(self, m, **kwargs):
		if isinstance(m, Model):
			self.m[m.name] = m
			self.m[m.name].asModule = True
		else:
			self.m[m.name] = Module(**kwargs)

	def attrFromM(self, attr):
		""" Get attributes from self.m modules """
		return {k:v for d in (getattr(m,attr)(m=m.name) if hasattr(m,attr) else {} for m in self.m.values()) for k,v in d.items()}


class Module:
	def __init__(self, name = None, ns = None, **kwargs):
		self.name, self.ns = name, noneInit(ns, {})
		[setattr(self, k,v) for k,v in kwargs.items()];

	def n(self, item, m = None):
		try:
			return self.ns[item] if m is None else self.m[m].n(item)
		except KeyError:
			return item

class GModel(Model):
	""" 'Model' class with some a lot of added structure """
	def __init__(self, defaultModel = 'model_B', **kwargs):
		super().__init__(**kwargs)
		self.defaultModel = defaultModel # backup model state

	def modelName(self, state = 'B', **kwargs):
		return '_'.join(['M',self.name,state])
	@property
	def dynamicProperties(self):
		return (n for n in self.__dict__ if n.startswith('_'))
	def initDynamicProperties(self):
		[self.addProperty(k[1:], getattr(self, k)) for k in self.dynamicProperties]
	def __setstate__(self,dict_):
		""" Don't include ws. Don't include db. """
		self.__dict__ = dict_
		if not self.asModule:
			self.db = GpyDB(dict_['_loadDbFrom'])
			for m in self.m.values():
				if isinstance(m, Model):
					m.db = self.db
		self.initDynamicProperties()


	# groups:
	@property
	def listGroups(self):
		return (n for n in dir(type(self)) if n.startswith('group_'))
	@property
	def listMetaGroups(self):
		return (n for n in dir(type(self)) if n.startswith('metaGroup_'))
	def initGroups(self):
		self.groups = {g.name: g for g in (getattr(self, k) for k in self.listGroups)}
		[grp() for grp in self.groups.values()]; # initialize groups
		metaGroups = {g.name: g for g in (getattr(self, k) for k in self.listMetaGroups)}
		[grp() for grp in metaGroups.values()]; # initialize metagroups
		self.groups.update(metaGroups)

	# model specs:
	@property
	def listModels(self):
		return (n for n in dir(type(self)) if n.startswith('model_'))

	@property
	def textBlocks(self):
		""" dict where values are written as text blocks used to define equations of the model """
		return {}

	def getModel(self, state = 'B', **kwargs):
		return getattr(self, f'model_{state}') if hasattr(self, f'model_{state}') else getattr(self,self.defaultModel)
	def defineModel(self, **kwargs):
		return f"""$Model {self.modelName(**kwargs)} {','.join(self.getModel(**kwargs))};"""

	# write methods
	def solveStatement(self, **kwargs):
		return f""" solve {self.modelName(**kwargs)} using CNS;"""

	def write_gamY(self, state = 'B'):
		return self.text+self.solveText(state = state)
	def write(self, state = 'B'):
		return self.compiler(self.write_gamY(state = state), has_read_file = False)

	def writeModel(self, n):
		return f"""$Model {n.replace('model', f'M_{self.name}',1)} {','.join(getattr(self,n))};"""
	@property
	def writeModels(self):
		return '\n'.join([self.writeModel(n) for n in self.listModels])

	@property
	def writeBlocks(self):
		return ''.join(self.textBlocks.values())
	@property
	def writeInit(self):
		return getattr(self,'textInit') if hasattr(self,'textInit') else ''
	@property
	def writeFuncs(self):
		return getattr(self,'textFuncs') if hasattr(self,'textFuncs') else ''

	def fixText(self, state ='B'):
		return self.groups[f'{self.name}_exo_{state}'].fix(db = self.db)
	def unfixText(self, state = 'B'):
		return self.groups[f'{self.name}_endo_{state}'].unfix(db = self.db)

	@property
	def text(self):
		return f"""
{StdArgs.root()}
{StdArgs.funcs()}
# DEFINE LOCAL FUNCTIONS/MACROS:
{self.writeFuncs}

# DECLARE SYMBOLS FROM DATABASE:
{FromDB.declare(self.db)}
# LOAD SYMBOLS FROM DATABASE:
{FromDB.load(self.db, gdx = self.db.name)}
# WRITE INIT STATEMENTS FROM MODULES:
{self.writeInit}

# WRITE BLOCKS OF EQUATIONS:
{self.writeBlocks}

# DEFINE MODELS:
{self.writeModels};
"""

	def solveText(self, **kwargs):
		return f"""
# Fix exogenous variables in state:
{self.fixText(**kwargs)}

# Unfix endogenous variables in state:
{self.unfixText(**kwargs)}

# solve:
{self.solveStatement(**kwargs)}
"""

	# Solve methods 
	def jSolve(self, n, state = 'B', loopName = 'i', ϕ = 1, solve = None, addJobOpt=None, runJobOpt=None):
		""" Solve model from scratch using the jTerms approach."""
		mainText = self.compiler(self.text, has_read_file = False)
		jModelStr = self.j.jModel(self.modelName(state=state), self.groups.values(), db = self.db, solve = noneInit(solve, self.solveStatement(state = state))) # create string that declares adjusted $j$-terms
		fixUnfix = self.j.group.fix()+self.unfixText(state=state)+self.j.solve
		loopSolve = self.j.jLoop(n, loopName = loopName, ϕ = ϕ)
		self.job = self.ws.add_job_from_string(mainText+jModelStr+fixUnfix+loopSolve, **noneInit(addJobOpt, {}))
		self.job.run(databases = self.db.database, **noneInit(runJobOpt, {}))
		return GpyDB(self.job.out_db, ws = self.ws)

	def solve(self, text = None, state = 'B', addJobOpt = None, runJobOpt = None):
		self.job = self.ws.add_job_from_string(noneInit(text, self.write(state = state)), **noneInit(addJobOpt, {}))
		self.job.run(databases = self.db.database, **noneInit(runJobOpt, {}))
		self.out_db = GpyDB(self.job.out_db, ws = self.ws)
		return self.out_db
