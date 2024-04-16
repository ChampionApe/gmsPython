import pandas as pd, pyDatabases
from pyDatabases import gpyDB, gpyDB_wheels, adj, adjMultiIndex
from gmsPython._mixedTools import concatMultiIndices

_ftype_inputs, _ftype_outputs = ('CES','CES_norm','MNL'), ('CET','CET_norm','MNL_out')
_scalePreserving = ('CES_norm','CET_norm','MNL','MNL_out')

def checkOrIgnore(d,k):
	return d[k] if k in d else k
def reverseDict(d):
	return {v:k for k,v in d.items()}

def trimNestingStructure(m, sparsity, maxIter = 10):
	""" Trim nesting structure in pandas multiindex 'm' with a 'sparsity' pattern on the inputs. NB: Only works on pure input-like trees """
	t = tree(name = 'test', tree = m.tolist())
	t.attrs_from_tree()
	nInputs = sparsity.to_frame(index=False).groupby('s').count().n
	oneInputSectors = nInputs[nInputs == 1]
	# Define new mapping for relevant sectors:
	mapOneInput = adjMultiIndex.applyMult(adj.rc_pd(t.get('output'), oneInputSectors), 
										  adj.rc_pd(sparsity, oneInputSectors).rename(['s','nn']))
	mMultipleGoods = adj.rc_pd(m, ('not', oneInputSectors))
	t = tree(name = 'test', tree = mMultipleGoods.to_list())
	t.attrs_from_tree()
	inputs = t.get('input')

	# 2. Remove inputs that are not used:
	noUse = adj.rc_pd(t.get('input'), ('not', sparsity))
	mMultipleGoods = adj.rc_pd(t.get('map'), ('not', adj.rc_pd(noUse, alias = {'n':'nn'})))

	# 2.A: Number of nodes for each parent node in the system:
	nNodes = mMultipleGoods.to_frame(index=False).groupby(['s','n']).count()

	# Start iteration checks
	i = 0
	t = tree(name = 'test', tree=mMultipleGoods.tolist())
	t.attrs_from_tree()
	inputs_i = t.get('input')
	while (min(nNodes['nn'])<=1) & (not inputs_i.difference(inputs).empty):
		i = i+1
		mMultipleGoods, nNodes, inputs_i = trim_ite(mMultipleGoods, nNodes)
		mMultipleGoods = adj.rc_pd(mMultipleGoods, ('not', inputs_i.difference(inputs).rename(['s','nn'])))
		if i==maxIter:
			raise StopIteration("Tree trimming did not converge")
	return mMultipleGoods.union(mapOneInput)

def trim_ite(m, nNodes):
	# 2B: Define mapping where knots have a single node:
	nodesOneChild = nNodes[nNodes['nn'] == 1].index
	mapOneNode = adj.rc_pd(m, nodesOneChild)
	# We make an exception if a combination (s, x) enters as both a knot and a branch. In this case, we cannot remove the parent node of 'x' (as we need this to maintain the tree structure)
	keepKnots = adj.rc_pd(mapOneNode.droplevel('nn').unique(), mapOneNode.droplevel('n').rename(['s','n']))
	nodesOneChild = nodesOneChild.difference(keepKnots)
	mapOneNode = adj.rc_pd(m, nodesOneChild)
	m = adj.rc_pd(m, ('not', nodesOneChild))
	# Apply map to change parent nodes
	mapNewNodes = adjMultiIndex.applyMult(m, mapOneNode.rename(['s','nn','new'])).droplevel('nn').rename(['s','n','nn'])
	m = adj.rc_pd(m, ('not', nodesOneChild.rename(['s','nn']))).union(mapNewNodes)
	# 2A: Return number of nodes for each one now:
	nNodes = m.to_frame(index = False).groupby(['s','n']).count()
	t = tree(name='test', tree = m.tolist())
	t.attrs_from_tree()
	return m, nNodes, t.get('input')

class tree:
	def __init__(self, name, tree = None, io = None, db = None, f = None,**ns):
		self.name = name
		self.db = pyDatabases.noneInit(db,{})
		self.addFunctionandIO(f,io)
		self.scalePreserving = True if self.f in _scalePreserving else False
		self.ns = {k:v if k not in ns else ns[k] for k,v in self.standardNamespace.items()}
		self.tree = pyDatabases.noneInit(tree,[])

	@property
	def standardNamespace(self):
		return {k: k+'_'+self.name for k in ('map','knot','branch','input','output','int')}

	def addFunctionandIO(self,f,io):
		if f:
			self.f = f
			if io is None:
				self.io = 'input' if self.f in _ftype_inputs else 'output'
			else:
				self.io = io
		else:
			self.io = 'input' if io is None else io
			self.f = 'CES' if self.io == 'input' else 'CET'

	def __getitem__(self,item):
		try:
			return self.db[self.ns[item]]
		except KeyError:
			return self.db[item]

	def __setitem__(self,item,value):
		try:
			self.db[self.ns[item]] = gpyDB.gpy(value,**{'name': self.ns[item]})
		except KeyError:
			self.db[item] = gpyDB.gpy(value,**{'name': item})

	def get(self,item):
		return self[item].vals

	def attrs_from_tree(self):
		self['map'] = pd.MultiIndex.from_tuples(self.tree, names = ['s', 'n','nn'])
		self['knot'] = self.get('map').droplevel('nn').unique() if self.io == 'input' else self.get('map').droplevel('n').rename(['s','n']).unique()
		self['branch'] = self.get('map').droplevel('n').unique().rename(['s','n']) if self.io == 'input' else self.get('map').droplevel('nn').unique()
		self['n'] = self.get('knot').union(self.get('branch')).droplevel('s').unique()
		self['s'] = self.get('map').get_level_values('s').unique()
		self['input'] = self.get('branch').difference(self.get('knot')) if self.io == 'input' else self.get('knot').difference(self.get('branch'))
		self['output'] = self.get('branch').difference(self.get('knot')) if self.io == 'output' else self.get('knot').difference(self.get('branch'))
		self['int'] = (self.get('branch').union(self.get('knot'))).difference(self.get('input').union(self.get('output')))

class tree_from_data(tree):
	def __init__(self,workbook,sheet,name=None,io=None,f=None,**ns):
		""" Workbook has to be supplied"""
		super().__init__(sheet if name is None else name, db = gpyDB_wheels.read.variables(workbook[sheet]),io=io,f=f,**ns)
		self.tree = self['mu'].index.to_list()

class aggTree:
	def __init__(self,name="",trees=None,**ns):
		self.name=name
		self.ns = {k:v if k not in ns else ns[k] for k,v in self.standardNamespace.items()}
		self.trees = pyDatabases.noneInit(trees,{})
		self.prune = ('n','nn','nnn','s','input','output','int')
		self.db = gpyDB.GpyDB(alias=pd.MultiIndex.from_tuples([(self.n('n'),self.n('nn')), (self.n('n'),self.n('nnn'))]),**{'name':self.name})

	@property
	def standardNamespace(self):
		return {k:k for k in ('n','nn','nnn','s')} | {k: k+'_'+self.name for k in ('map','int','input','output','map_spinp','map_spout','knout','kninp','spinp','spout')}

	def n(self,item,local=None):
		return self.ns[item] if local is None else self.trees[local].ns[item]

	def get(self,item,local=None):
		return self.db[self.n(item,local=local)].vals

	def __setitem__(self,item,value):
		self.db[self.n(item)] = value

	def __call__(self,namespace=None):
		[tree.attrs_from_tree() for tree in self.trees.values()];
		self.attrs_from_trees()
		self.adjust_trees()
		[self.add_db_prune(tree) for tree in self.trees.values()];
		self.namespace = namespace
		if namespace:
			gpyDB_wheels.aggregateDB.updateSetValues(self.db,self.n('n'),namespace)
		return self

	def add_db_prune(self,tree):
		[gpyDB.GpyDBs_AOM_Second(self.db,s) for name,s in tree.db.items() if checkOrIgnore(reverseDict(tree.ns),name) not in self.prune];

	def attrs_from_trees(self):
		self['n'] = pd.Index(set.union(*[set(tree.get('n')) for tree in self.trees.values()]), name = self.n('n'))
		self['s'] = pd.Index(set.union(*[set(tree.get('s')) for tree in self.trees.values()]), name = self.n('s'))
		self['map'] = concatMultiIndices([tree.get('map') for tree in self.trees.values()])
		self['map_spinp'] = concatMultiIndices([tree.get('map') for tree in self.trees.values() if tree.scalePreserving and tree.io == 'input'], names = self.get('map').names)
		self['map_spout'] = concatMultiIndices([tree.get('map') for tree in self.trees.values() if tree.scalePreserving and tree.io == 'output'], names = self.get('map').names)
		self['knout'] = concatMultiIndices([tree.get('knot') for tree in self.trees.values() if tree.io == 'output'],  names=[self.n('s'),self.n('n')])
		self['kninp'] = concatMultiIndices([tree.get('knot') for tree in self.trees.values() if tree.io == 'input'],  names=[self.n('s'),self.n('n')])
		self['spout'] = self.get('map_spinp').droplevel(self.n('nn')).unique()
		self['spinp'] = self.get('map_spout').droplevel(self.n('n')).unique().rename([self.n('s'),self.n('n')])
		inputs = set.union(*[set(tree.get('input')) for tree in self.trees.values()])
		outputs= set.union(*[set(tree.get('output')) for tree in self.trees.values()])
		ints = set.union(*[set(tree.get('int')) for tree in self.trees.values()])
		self['input'] = pd.MultiIndex.from_tuples(inputs-outputs,names = [self.n('s'),self.n('n')])
		self['output']= pd.MultiIndex.from_tuples(outputs-inputs,names = [self.n('s'),self.n('n')])
		self['int'] = pd.MultiIndex.from_tuples((inputs.intersection(outputs)).union(ints), names = [self.n('s'),self.n('n')])

	def adjust_trees(self):
		[self.adjust_tree_in(tree) for tree in self.trees.values() if tree.io == 'input'];
		[self.adjust_tree_out(tree) for tree in self.trees.values() if tree.io == 'output'];

	def adjust_tree_in(self,tree):
		tree.ns['knot_o'] = 'knot_o_'+tree.name
		tree.ns['knot_no'] = 'knot_no_'+tree.name
		tree.ns['branch2o'] = 'branch2o_'+tree.name
		tree.ns['branch2no']= 'branch2no_'+tree.name
		tree['knot_o'] = tree.get('knot').intersection(self.get('output'))
		tree['knot_no'] = tree.get('knot').difference(self.get('output'))
		tree['branch2o'] = gpyDB_wheels.adj.rc_pd(tree['map'], self.get('output')).droplevel(self.n('n')).rename([self.n('s'),self.n('n')])
		tree['branch2no'] = gpyDB_wheels.adj.rc_pd(tree['map'], ('not', self.get('output'))).droplevel(self.n('n')).rename([self.n('s'),self.n('n')])

	def adjust_tree_out(self,tree):
		tree.ns['branch_o'] = 'branch_o_'+tree.name
		tree.ns['branch_no'] = 'branch_no_'+tree.name
		tree['branch_o'] = tree.get('branch').intersection(self.get('output'))
		tree['branch_no'] = tree.get('branch').difference(tree.get('branch_o'))

class aggTree_from_data(aggTree):
	def __init__(self,file_path,read_trees=None,name="",**ns):
		""" read_trees are passed to tree_from_data """
		super().__init__(name=name,**ns)
		wb = gpyDB_wheels.read.simpleLoad(file_path)
		if read_trees is None:
			read_trees = {sheet: {} for sheet in gpyDB_wheels.read.sheetnames_from_wb(wb)}
		self.trees = {t.name: t for t in (tree_from_data(wb,k,**v) for k,v in read_trees.items())}
