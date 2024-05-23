from gmsPython.auxfuncs import *
import os, pickle
from pyDatabases import noneInit
from pyDatabases.gpyDB import GpyDB
from gmsPython.gamY.gamY import Precompiler
from gmsPython.gmsPy.gmsPy import jTerms

class Model:
	""" Simple shell for models defined with namespaces, databases, compiler etc.."""
	def __init__(self, name = None, ns = None, database = None, asModule = False, **kwargs):
		self.db = noneInit(database, GpyDB(**kwargs))
		self.name = name
		self.compiler = Precompiler()
		self.j = jTerms(self.compiler)
		self.ns = noneInit(ns, {})
		self.m = {}
		self.cps = {} # checkpoints
		self._asModule = asModule
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

	def __getstate__(self):
		if not self._asModule:
			self._loadDbFrom = os.path.join(self.data_folder, self.db.name)
			self.db.export()
		return {key:value for key,value in self.__dict__.items() if key not in (self.dropattrs+['db'])}
		
	def __setstate__(self,dict_):
		""" Don't include ws. Don't include db. """
		self.__dict__ = dict_
		if not self._asModule:
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
			self.m[m.name]._asModule = True
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
