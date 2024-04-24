from gmsPython.auxfuncs import *
_ftype_inputs, _ftype_outputs = ('CES','CES_norm','MNL'), ('CET','CET_norm','MNL_out')
_scalePreserving = ('CES_norm','CET_norm','MNL','MNL_out')

def checkOrIgnore(d,k):
	return d[k] if k in d else k
def reverseDict(d):
	return {v:k for k,v in d.items()}

class Tree:
	def __init__(self, name, tree = None, db = None, f = None,**ns):
		self.name = name
		self.db = noneInit(db,{})
		self.addFunctionandIO(f)
		self.scalePreserving = True if self.f in _scalePreserving else False
		self.ns = self.standardNamespace | ns
		self.tree = noneInit(tree,[])

	@property
	def standardNamespace(self):
		return {k: f'{self.name}_{k}' for k in ('map','knot','branch','input','output','int')}

	def addFunctionandIO(self,f):
		self.f = 'CES' if f is None else f
		self.io = 'input' if self.f in _ftype_inputs else 'output' 

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

	def attrsFromTree_input(self):
		self['map'] = pd.MultiIndex.from_tuples(self.tree, names = ['s', 'n','nn'])
		self['knot'] = self.get('map').droplevel('nn').unique()
		self['branch'] = self.get('map').droplevel('n').unique().rename(['s','n'])
		self['n'] = self.get('knot').union(self.get('branch')).droplevel('s').unique()
		self['s'] = self.get('map').get_level_values('s').unique()
		self['input'] = self.get('branch').difference(self.get('knot'))
		self['output'] = self.get('knot').difference(self.get('branch'))
		self['int'] = (self.get('branch').union(self.get('knot'))).difference(self.get('input').union(self.get('output')))

	def attrsFromTree_output(self):
		self['map'] = pd.MultiIndex.from_tuples(self.tree, names = ['s', 'n','nn'])
		self['knot'] = self.get('map').droplevel('n').rename(['s','n']).unique()
		self['branch'] = self.get('map').droplevel('nn').unique()
		self['n'] = self.get('knot').union(self.get('branch')).droplevel('s').unique()
		self['s'] = self.get('map').get_level_values('s').unique()
		self['input'] = self.get('knot').difference(self.get('branch'))
		self['output'] = self.get('branch').difference(self.get('knot'))
		self['int'] = (self.get('branch').union(self.get('knot'))).difference(self.get('input').union(self.get('output')))

	def __call__(self):
		getattr(self, f'attrsFromTree_{self.io}')()
		return self

class TreeFromData(Tree):
	def __init__(self,workbook,sheet,name=None,f=None,**ns):
		""" Workbook, sheet has to be supplied"""
		if type(workbook) is str:
			workbook = gpyDB.DbFromExcel.simpleLoad(workbook)
		super().__init__(sheet if name is None else name, db = gpyDB.DbFromExcel.var(workbook[sheet]),f=f,**ns)
		self.tree = self['mu'].index.to_list()

class AggTree:
	def __init__(self,name="",trees=None, ws = None, **ns):
		self.name=name
		self.ns = self.standardNamespace | ns
		self.trees = noneInit(trees,{})
		self.prune = ('n','nn','nnn','s','input','output','int') 
		self.db = gpyDB.GpyDB(ws = ws, alias=[(self.n('n'),self.n('nn')), (self.n('n'),self.n('nnn'))], name = self.name)

	@property
	def standardNamespace(self):
		return {k:k for k in ('n','nn','nnn','s')} | {k: f'{self.name}_{k}' for k in ('map','int','input','output','map_spinp','map_spout','knout','kninp','spinp','spout')}

	def n(self,item,local=None):
		return self.ns[item] if local is None else self.trees[local].ns[item]

	def get(self,item,local=None):
		return self.db[self.n(item,local=local)].vals

	def __setitem__(self,item,value):
		self.db[self.n(item)] = value

	def __call__(self,namespace=None):
		[tree() for tree in self.trees.values()]; 
		self.attrsFromTrees()
		self.adjustTrees()
		[self.addDbAndPrune(tree) for tree in self.trees.values()];
		self.namespace = namespace
		if namespace:
			gpyDB.AggDB.updSetElements(self.db,self.n('n'),namespace)
		return self

	def addDbAndPrune(self,tree):
		[self.db.aom_gpy(s) for name,s in tree.db.items() if checkOrIgnore(reverseDict(tree.ns), name) not in self.prune];

	def attrsFromTrees(self):
		self['n'] = pd.Index(set.union(*[set(tree.get('n')) for tree in self.trees.values()]), name = self.n('n'))
		self['s'] = pd.Index(set.union(*[set(tree.get('s')) for tree in self.trees.values()]), name = self.n('s'))
		self['map'] = concatMultiIndices([tree.get('map') for tree in self.trees.values()])
		self['map_spinp'] = concatMultiIndices([tree.get('map') for tree in self.trees.values() if tree.scalePreserving and tree.io == 'input'], names = self.get('map').names)
		self['map_spout'] = concatMultiIndices([tree.get('map') for tree in self.trees.values() if tree.scalePreserving and tree.io == 'output'], names = self.get('map').names)
		self['knout'] = concatMultiIndices([tree.get('knot') for tree in self.trees.values() if tree.io == 'output'],  names=[self.n('s'),self.n('n')])
		self['kninp'] = concatMultiIndices([tree.get('knot') for tree in self.trees.values() if tree.io == 'input'],  names=[self.n('s'),self.n('n')])
		self['spout'] = self.get('map_spout').droplevel(self.n('nn')).unique()
		self['spinp'] = self.get('map_spinp').droplevel(self.n('n')).unique().rename([self.n('s'),self.n('n')])
		inputs = set.union(*[set(tree.get('input')) for tree in self.trees.values()])
		outputs= set.union(*[set(tree.get('output')) for tree in self.trees.values()])
		ints = set.union(*[set(tree.get('int')) for tree in self.trees.values()])
		self['input'] = pd.MultiIndex.from_tuples(inputs-outputs,names = [self.n('s'),self.n('n')])
		self['output']= pd.MultiIndex.from_tuples(outputs-inputs,names = [self.n('s'),self.n('n')])
		self['int'] = pd.MultiIndex.from_tuples((inputs.intersection(outputs)).union(ints), names = [self.n('s'),self.n('n')])		

	def adjustTrees(self):
		[getattr(self, f'adjustTree_{tree.io}')(tree) for tree in self.trees.values()];

	def adjustTree_input(self,tree):
		[tree.ns.__setitem__(k,f'{tree.name}_{k}') for k in ('knot_o','knot_no','branch2o','branch2no')];
		tree['knot_o'] = tree.get('knot').intersection(self.get('output'))
		tree['knot_no'] = tree.get('knot').difference(self.get('output'))
		tree['branch2o'] = pyDatabases.adj.rc_pd(tree['map'], self.get('output')).droplevel(self.n('n')).rename([self.n('s'),self.n('n')])
		tree['branch2no'] = pyDatabases.adj.rc_pd(tree['map'], ('not', self.get('output'))).droplevel(self.n('n')).rename([self.n('s'),self.n('n')])

	def adjustTree_output(self,tree):
		[tree.ns.__setitem__(k,f'{tree.name}_{k}') for k in ('branch_o','branch_no')];
		tree['branch_o'] = tree.get('branch').intersection(self.get('output'))
		tree['branch_no'] = tree.get('branch').difference(tree.get('branch_o'))

class AggTreeFromData(AggTree):
	def __init__(self,file_path,read_trees=None,name="",**ns):
		""" read_trees are passed to tree_from_data """
		super().__init__(name=name,**ns)
		wb = gpyDB.DbFromExcel.simpleLoad(file_path)
		if read_trees is None:
			read_trees = {sheet: {} for sheet in gpyDB.DbFromExcel.sheetnames_from_wb(wb)}
		self.trees = {t.name: t for t in (TreeFromData(wb,k,**v) for k,v in read_trees.items())}

def trimNestingStructure(m, sparsity, maxIter = 10):
	""" Trim nesting structure in pandas multiindex 'm' with a 'sparsity' pattern on the inputs. NB: Only works on pure input-like trees """
	t = Tree(name = 'test', tree = m.tolist())()
	nInputs = sparsity.to_frame(index=False).groupby('s').count().n
	oneInputSectors = nInputs[nInputs == 1]
	# Define new mapping for relevant sectors:
	mapOneInput = pyDatabases.adjMultiIndex.applyMult(pyDatabases.adj.rc_pd(t.get('output'), oneInputSectors), 
													  pyDatabases.adj.rc_pd(sparsity, oneInputSectors).rename(['s','nn']))
	mMultipleGoods = pyDatabases.adj.rc_pd(m, ('not', oneInputSectors))
	t = Tree(name = 'test', tree = mMultipleGoods.to_list())()
	inputs = t.get('input')

	# 2. Remove inputs that are not used:
	noUse = pyDatabases.adj.rc_pd(t.get('input'), ('not', sparsity))
	mMultipleGoods = pyDatabases.adj.rc_pd(t.get('map'), ('not', pyDatabases.adj.rc_pd(noUse, alias = {'n':'nn'})))

	# 2.A: Number of nodes for each parent node in the system:
	nNodes = mMultipleGoods.to_frame(index=False).groupby(['s','n']).count()

	# Start iteration checks
	i = 0
	t = Tree(name = 'test', tree=mMultipleGoods.tolist())()
	inputs_i = t.get('input')
	while (min(nNodes['nn'])<=1) & (not inputs_i.difference(inputs).empty):
		i = i+1
		mMultipleGoods, nNodes, inputs_i = trim_ite(mMultipleGoods, nNodes)
		mMultipleGoods = pyDatabases.adj.rc_pd(mMultipleGoods, ('not', inputs_i.difference(inputs).rename(['s','nn'])))
		if i==maxIter:
			raise StopIteration("Tree trimming did not converge")
	return mMultipleGoods.union(mapOneInput)

def trim_ite(m, nNodes):
	# 2B: Define mapping where knots have a single node:
	nodesOneChild = nNodes[nNodes['nn'] == 1].index
	mapOneNode = pyDatabases.adj.rc_pd(m, nodesOneChild)
	# We make an exception if a combination (s, x) enters as both a knot and a branch. In this case, we cannot remove the parent node of 'x' (as we need this to maintain the tree structure)
	keepKnots = pyDatabases.adj.rc_pd(mapOneNode.droplevel('nn').unique(), mapOneNode.droplevel('n').rename(['s','n']))
	nodesOneChild = nodesOneChild.difference(keepKnots)
	mapOneNode = pyDatabases.adj.rc_pd(m, nodesOneChild)
	m = pyDatabases.adj.rc_pd(m, ('not', nodesOneChild))
	# Apply map to change parent nodes
	mapNewNodes = pyDatabases.adjMultiIndex.applyMult(m, mapOneNode.rename(['s','nn','new'])).droplevel('nn').rename(['s','n','nn'])
	m = pyDatabases.adj.rc_pd(m, ('not', nodesOneChild.rename(['s','nn']))).union(mapNewNodes)
	# 2A: Return number of nodes for each one now:
	nNodes = m.to_frame(index = False).groupby(['s','n']).count()
	t = Tree(name='test', tree = m.tolist())()
	return m, nNodes, t.get('input')