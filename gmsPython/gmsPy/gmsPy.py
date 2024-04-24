from gmsPython.auxfuncs import *
from pyDatabases import OrdSet, noneInit
from copy import deepcopy
from gmsPython.gmsWrite.gmsWrite import Syms

# class metaGroup(Group):
# 	def __init__(self, name, groups = None):
# 		super().__init__()
# 		self.groups = noneInit(groups, {})

# 	@property
# 	def groupsCopy(self):
# 		return {k: deepcopy(v) for k,v in self.groups.items()}

# 	def __call__(self):
# 		for g in self.groups.values():
# 			g()

# 	def getVariablesFromMetaGroup(self, metaGroup):
# 		""" metaGroup = iterator of strings referring to existing group names """
# 		return OrdSet.union(*[OrdSet(self.groups[g].conditions) for g in metaGroup])

# 	def metaGroup(self,db,gs='all'):
# 		if isinstance(gs,Group):
# 			return gs
# 		elif gs == 'all':
# 			return Group('metagroup',g=self.groups.values())()
# 		else:
# 			return Group('metagroup',g=gs)()

# 	def fixGroupsText(self,db,gs):
# 		metagroup = self.metaGroup(db,gs=gs)
# 		return self.fixGroupText(db,metagroup)

# 	def fixGroupText(self,db,g):
# 		return "\n".join([f"{gmsWrite.writeGpy(db[k],c=v,l='.fx')} = {gmsWrite.writeGpy(db[k],l='.l')};" for k,v in g.conditions.items()])

# 	def unfixGroupsText(self,db,gs):
# 		metagroup = self.metaGroup(db,gs=gs)
# 		return self.unfixGroupText(db,metagroup)

# 	def unfixGroupText(self,db,g):
# 		return "\n".join([f"{gmsWrite.writeGpy(db[k],c=v,l='.lo')} = -inf;\n{gmsWrite.writeGpy(db[k],c=v,l='.up')} = inf;" for k,v in g.conditions.items()])

class Group:
	def __init__(self,name, v=None, g=None, sub_v=None, sub_g=None):
		self.name = name
		self.v = noneInit(v,[])
		self.g = OrdSet(noneInit(g,[]))
		self.sub_v = noneInit(sub_v,[])
		self.sub_g = OrdSet(noneInit(sub_g,[]))
		self.out = {}
		self.out_neg = {}

	def n(self, k):
		return OrdSet([v.name for v in k])

	def __call__(self):
		partition = OrdSet.partition(self.n(self.g), self.n(self.sub_g)) # tuple with p[0] = overlap, p[1] = only in first, p[2] only in second
		gs = OrdSet([g for g in self.g if g.name in partition[1]])
		sub_gs = OrdSet([g for g in self.sub_g if g.name in partition[2]])
		[self.add(x) for x in self.v]
		[self.addGroup(g) for g in gs];
		[self.checkIfNone_out(name) for name in self.out];
		[self.sub(x) for x in self.sub_v];
		[self.subGroup(g) for g in sub_gs];
		[self.checkIfNone_out_neg(name) for name in list(self.out_neg)];
		[self.removeIte(name,conds) for name,conds in self.out_neg.items()];
		return self

	def fix(self, db = None):
		return "\n".join([self.fixVar(name, self.conditions, db = db) for name in self.out])
	def unfix(self, db = None):
		return "\n".join([self.unfixVar(name, self.conditions, db = db) for name in self.out])
	def fixVar(self, name, c, db = None):
		return f"{self.writeVar(name, c, db = db, l = 'fx')} = {self.writeVar(name, c, db = db, l = '.l')};"
	def unfixVar(self, name, c, db = None):
		return f"{self.writeVar(name, c, db = db, l='.lo')} = -inf;\n{self.writeVar(name, c, db = db, l = 'up')} = inf;"
	def writeVar(self, name, c, db = None, **kwargs):
		return getattr(self, f'writeVar_{db.__class__.__name__}')(name, db, c, **kwargs)
	def writeVar_NoneType(self, name, db, c, **kwargs):
		return Syms.str_var(name, c = c[name], **kwargs)
	def writeVar_GpyDB(self, name, db, c, **kwargs):
		return Syms.gpy(db[name], c = c[name], **kwargs)
	def add(self, x):
		return getattr(self, f'add_{x.__class__.__name__}')(x)
	def add_tuple(self, tup):
		self.add_(tup[0], tup[1])
	def add_str(self, name):
		self.add_(name, None)
	def add_(self, name, condition):
		if name not in self.out:
			self.out[name] = [condition]
		elif condition not in self.out[name]:
			self.out[name] += [condition]
	def addIte(self, name, conds):
		if name not in self.out:
			self.out[name] = conds
		else:
			self.out[name] += [c for c in conds if c not in self.out[name]]
	def addGroup(self, g):
		[self.addIte(k,v) for k,v in g.conditions.items()];

	def sub(self, x):
		return getattr(self, f'sub_{x.__class__.__name__}')(x)
	def sub_tuple(self, tup):
		self.sub_(tup[0], tup[1])
	def sub_str(self, name):
		self.sub_(name, None)
	def sub_(self, name, condition):
		if name not in self.out_neg:
			self.out_neg[name] = [condition]
		elif condition not in self.out_neg[name]:
			self.out_neg[name] += [condition]
	def subIte(self, name, conds):
		if name not in self.out_neg:
			self.out_neg[name] = conds
		else:
			self.out_neg[name] += [c for c in conds if c not in self.out_neg[name]]
	def subGroup(self, g):
		[self.subIte(k,v) for k,v in g.conditions.items()];

	def checkIfNone_out(self, name):
		if None in self.out[name]:
			self.out[name] = [None]
	def checkIfNone_out_neg(self, name):
		if None in self.out_neg[name]:
			if name in self.out:
				self.out.__delitem__(name)
			self.out_neg.__delitem__(name)

	def conditionVar(self,name):
		if None in self.out[name]:
			return self.conditionsFromSub(name) if name in self.out_neg else None
		else:
			return ('and', [self.conditionsFromAdd(name), self.conditionsFromSub(name)]) if name in self.out_neg else self.conditionsFromAdd(name)
	def conditionsFromAdd(self, name):
		return ('or', self.out[name]) if len(self.out[name])>1 else self.out[name][0]
	def conditionsFromSub(self, name):
		return ('not', self.out_neg[name][0]) if len(self.out_neg[name]) == 1 else ('not', ('or', self.out_neg[name]))
	@property
	def conditions(self):
		return {name: self.conditionVar(name) for name in self.out}
	def removeIte(self,name,conds):
		""" For the variable 'name', remove all conditions 'conds' from self.out and then self.out_neg"""
		if name in self.out:
			condition_overlap = [c for c in conds if c in self.out[name]]
			self.out[name] = [c for c in self.out[name] if c not in condition_overlap]
			self.out_neg[name] = [c for c in self.out_neg[name] if c not in condition_overlap]
