from gmsPython.auxfuncs import *
from pyDatabases import gpyDB, OrdSet, noneInit

default_user_functions = """
# User defined functions:
$FUNCTION SolveEmptyNLP({name})
variable randomnameobj;  
randomnameobj.L = 0;

EQUATION E_EmptyNLPObj;
E_EmptyNLPObj..    randomnameobj  =E=  0;

Model M_SolveEmptyNLP /
E_EmptyNLPObj, {name}
/;
solve M_SolveEmptyNLP using NLP min randomnameobj;
$ENDFUNCTION
"""

default_options_root = {'SYSOUT': 'OFF', 'SOLPRINT': 'OFF', 'LIMROW': '0', 'LIMCOL': '0', 'DECIMALS': '6'}

def list2str(l):
	return '[{x}]'.format(x=','.join(l)) if l else ''
def lagIdx(lag, item):
	return lag.get(item,'') if isinstance(lag, dict) else lag
def eq_(k,v):
	return f'{k}={v}'

def writeOptions(**options):
	return ', '.join([eq_(k,v) for k,v in (default_options_root | options).items()])

class StdArgs:
	@staticmethod
	def root(**options):
		return f"""
$SETLOCAL qmark ";
OPTION {writeOptions(**options)};
"""
	@staticmethod
	def funcs(**kwargs):
		return default_user_functions

class Syms:
	@staticmethod
	def str_var(s = None, c = None, l = "", **kwargs):
		""" Simple writing method where s is a string"""
		domains = Syms.str_getDomains(s)
		return s.rpartition(domains)[0]+l+domains+Syms.gpyCondition(c) if domains else s+l+Syms.gpyCondition(c)

	@staticmethod
	def str_getDomains(text):
		return text[text.find('['):text.find(']')+1] if '[' in text else ''
	@staticmethod
	def gpy(s = None, c = None, alias = None, lag = None, l = ""):
		return getattr(Syms, f'gpy_{s.type}')(s = s, c = c, alias = noneInit(alias, {}), lag = noneInit(lag, {}), l = l)
	@staticmethod
	def gpy_set(s = None, c = None, alias = None, **kwargs):
		return s.name + Syms.gpyCondition(c = c) if s.name not in alias else alias[s.name]+Syms.gpyCondition(c = c)
	@staticmethod
	def gpy_subset(s = None, c = None, alias = None, lag = None, **kwargs):
		return s.name+Syms.gpyDomains(s, alias, lag)+Syms.gpyCondition(c)
	@staticmethod
	def gpy_map(**kwargs):
		return Syms.gpy_subset(**kwargs)
	@staticmethod
	def gpy_var(s = None, c = None, alias = None, lag = None, l = "", **kwargs):
		return s.name+l+Syms.gpyDomains(s, alias, lag)+Syms.gpyCondition(c)
	@staticmethod
	def gpy_par(s = None, c = None, alias = None, lag = None, **kwargs):
		return s.name+Syms.gpyDomains(s, alias = alias, lag = lag)+Syms.gpyCondition(c)
	@staticmethod
	def gpy_scalarVar(s = None, c = None, l = "", **kwargs):
		return s.name+l+Syms.gpyCondition(c)
	@staticmethod
	def gpy_scalarPar(s = None, c = None, **kwargs):
		return s.name+Syms.gpyCondition(c)
	@staticmethod
	def gpyDomains(s, alias = None, lag = None):
		return list2str([noneInit(alias, {}).get(item,item) + str(lagIdx(noneInit(lag, {}), item)) for item in s.domains])
	@staticmethod
	def gpyCondition(c):
		return '' if c is None else f"$({Syms.point(c)})"
	@staticmethod
	def point(vi):
		return getattr(Syms, f'point_{vi.__class__.__name__}')(vi)
	@staticmethod
	def point_gpy(vi):
		return Syms.gpy(vi)
	@staticmethod
	def point_dict(vi):
		return Syms.gpy(**vi)
	@staticmethod
	def point_str(vi):
		return vi
	@staticmethod
	def point_list(vi, k = ''):
		return f'{k}'.join([Syms.point(vi) for vi in vi])
	@staticmethod
	def point_tuple(tup):
		if tup[0] == 'not':
			return f"( not ({Syms.point(tup[1])}))" 
		else:
			return f"({f' {tup[0]} '.join([Syms.point(vi) for vi in tup[1]])})"

def strBlock(start, itersym, joinby='\n\t', end = ';'):
	return start+joinby+joinby.join(itersym)+'\n'+end+'\n\n' if bool(itersym) else ''
def loadSyntax(gdx, onmulti = True):
	return '$GDXIN '+gdx+'\n'+'$onMulti' if onmulti else '$GDXIN '+gdx, '$GDXIN\n' +'$offMulti;' if onmulti else '$GDXIN;'

class FromDB:
	@staticmethod
	def declare(db, exceptions = None):
		return ''.join([getattr(FromDB, f'decl{k}')(db, exceptions=exceptions) for k in ('Sets','Pars','Vars')])
	@staticmethod
	def load(db, gdx = None, onmulti=True, exceptions_load=None):
		return ''.join([getattr(FromDB, f'load{k}')(db, gdx = gdx, onmulti=onmulti, exceptions_load=None) for k in ('Sets','Pars','Vars')])
	@staticmethod
	def declSets(db, exceptions = None):
		return FromDB.declSets_(db, exceptions = exceptions)+FromDB.declAlias(db, exceptions = exceptions)+FromDB.declSetsOther(db, exceptions = exceptions)
	@staticmethod
	def declSets_(db, exceptions = None):
		return strBlock('sets', [Syms.gpy(db[s]) for s in OrdSet(db.getTypes(['set']))-OrdSet(exceptions)])
	@staticmethod
	def declAlias(db, exceptions = None):
		return ''.join(['alias({x},{y});\n'.format(x=k,y=','.join(list(v))) for k,v in db.aliasDict.items() if k not in noneInit(exceptions, [])])+'\n'
	@staticmethod
	def declSetsOther(db, exceptions=None):
		return strBlock('sets', [Syms.gpy(db[s]) for s in OrdSet(db.getTypes(['subset','map']))-OrdSet(exceptions)])
	@staticmethod
	def declPars(db, exceptions = None):
		return strBlock('parameters', [Syms.gpy(db[s]) for s in OrdSet(db.getTypes(['par','scalarPar']))-OrdSet(exceptions)])
	@staticmethod
	def declVars(db, exceptions = None):
		return strBlock('variables', [Syms.gpy(db[s]) for s in OrdSet(db.getTypes(['var','scalarVar']))-OrdSet(exceptions)])

	@staticmethod
	def loadSyms(db, getTypes, gdx = None, onmulti=True, exceptions_load=None):
		itersym = [f"$load {s}" for s in OrdSet(getTypes)-OrdSet(exceptions_load)]
		start, end = loadSyntax(gdx, onmulti=onmulti)
		return strBlock(start, itersym, joinby = '\n', end = end)
	@staticmethod
	def loadSets(db, gdx = None, **kwargs):
		return FromDB.loadSyms(db, list(db.getTypes(['set']))+list(db.getTypes(['subset','map'])), gdx =gdx, **kwargs)
	@staticmethod
	def loadPars(db, gdx = None, **kwargs):
		return FromDB.loadSyms(db, db.getTypes(['par','scalarPar']), gdx = gdx, **kwargs)
	@staticmethod
	def loadVars(db, gdx = None, **kwargs):
		return FromDB.loadSyms(db, db.getTypes(['var','scalarVar']), gdx = gdx, **kwargs)		


