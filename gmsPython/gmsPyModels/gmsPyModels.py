from gmsPython.auxfuncs import *
from pyDatabases import noneInit
from pyDatabases.gpyDB import GpyDB
from gmsPython.gamY.gamY import Precompiler
from gmsPython.gmsPy.gmsPy import jTerms

class Model:
	""" Simple shell for models defined with namespaces, databases, compiler etc.."""
	def __init__(self, name = None, ns = None, database = None, **kwargs):
		self.db = noneInit(database, GpyDB(**kwargs))
		self.name = name
		self.compiler = Precompiler()
		self.j = jTerms(self.compiler)
		self.ns = noneInit(ns, {})
		self.m = {}
		self.cps = {} # checkpoints

	### 0: Properties/customized methods
	@property
	def ws(self):
		return self.db.ws
	@property
	def work_folder(self):
		return self.db.work_folder

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
		if isinstance(m, type(self)):
			self.m[m.name] = m
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
