from pyDatabases import gpy, OrdSet, noneInit
import re

# Four main types of methods: 
#	1. Default options e.g. for options, root components, and gamY functions.
#	2. writeGpy: A method that writes gams-like text from gpy symbols.
# 	3. write_from_db: A method that declares and read in sets, parameters, variables by reading a database.
# 	4. 	Default components: methods for writing a number of standad components used in GmsModels.
#	5. Loop, update, solve, store.

# -------------------------------------- 1: Default options -------------------------------------- #
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


# -------------------------------------- 2 : writeGpy -------------------------------------- #
def writeGpy(s=None, c=None, alias=None, lag=None, l="",**kwargs):
	alias = noneInit(alias,{})
	if s.type == 'set':
		return s.name+condition(c=c) if s.name not in alias else alias[s.name]+condition(c=c)
	elif s.type in ('subset','mapping'):
		return s.name+gmsdomains(s,alias=alias,lag=lag)+condition(c=c)
	elif s.type =='variable':
		return s.name+l+gmsdomains(s,alias=alias,lag=lag)+condition(c=c)
	elif s.type == 'scalar_variable':
		return s.name+l+condition(c=c)
	elif s.type == 'parameter':
		return s.name+gmsdomains(s,alias=alias,lag=lag)+condition(c=c)
	elif s.type == 'scalar_parameter':
		return s.name+condition(c=c)

def condition(c=None):
	return '' if c is None else f"$({point(c)})"

def point(vi):
	if isinstance(vi, gpy):
		return writeGpy(vi)
	elif isinstance(vi,dict):
		return writeGpy(**vi)
	elif isinstance(vi,tuple):
		return write_tuple(vi)
	elif isinstance(vi,str):
		return vi

def write_tuple(tup):
	if tup[0] == 'not':
		return f"( not ({point(tup[1])}))"
	else:
		return f"({f' {tup[0]} '.join([point(vi) for vi in tup[1]])})"

def gmsdomains(s,alias=None,lag=None):
	return list2string([noneInit(alias,{}).get(item,item)+str(noneInit(lag,{}).get(item,'')) for item in s.domains])

def list2string(list_):
	return '[{x}]'.format(x=','.join(list_)) if list_ else ''


# -------------------------------------- 3 : Declare symbols from db -------------------------------------- #
def writeDeclare(db, types = None, exceptions = None, exceptions_load = None, gdx = None, onmuli=True):
	return ''.join([getattr(_writeFromDb, f"write{k}")(db=db, exceptions=exceptions, exceptions_load=exceptions_load, gdx = gdx, onmuli=onmuli)
			for k in noneInit(types, ['Sets','Alias','SetsOther','SetsLoad','Parameters','ParametersLoad','Variables','VariablesLoad'])])

def writeAux(start,end,itersym,joinby='\n\t'):
	return start+joinby+joinby.join(itersym)+'\n'+end+'\n\n' if bool(itersym) else ''

class _writeFromDb:
	@staticmethod
	def writeSets(db=None,exceptions=None,**kwargs):
		return writeAux('sets',';',[writeGpy(s=db[s]) for s in (OrdSet(db.getTypes('set'))-OrdSet(db.get('alias_map2'))-noneInit(exceptions,OrdSet()))])
	@staticmethod
	def writeAlias(db=None,exceptions=None,**kwargs):
		return ''.join(['alias({x},{y});\n'.format(x=k,y=','.join(list(v))) for k,v in db.alias_dict.items() if k not in noneInit(exceptions,[])])+'\n'
	@staticmethod
	def writeSetsOther(db=None,exceptions=None,**kwargs):
		return writeAux('sets',';',[writeGpy(s=db[s]) for s in (OrdSet(db.getTypes(('subset','mapping')))-noneInit(exceptions,OrdSet()))])
	@staticmethod
	def writeSetsLoad(db=None,gdx=None,onmulti=True,exceptions_load=None,**kwargs):
		itersym = ['$load '+s for s in (OrdSet(db.getTypes(['set']))-OrdSet(db.get('alias_map2'))-noneInit(exceptions_load,OrdSet()))]+['$load '+s for s in (OrdSet(db.getTypes(['subset','mapping']))-noneInit(exceptions_load,OrdSet()))];
		start = '$GDXIN '+gdx+'\n'+'$onMulti' if onmulti else '$GDXIN '+gdx
		end   = '$GDXIN\n' +'$offMulti;' if onmulti else '$GDXIN;'
		return writeAux(start,end,itersym,joinby='\n')
	@staticmethod
	def writeParameters(db=None,exceptions=None,**kwargs):
		return writeAux('parameters',';',[writeGpy(s=db[s]) for s in (OrdSet(db.getTypes(('scalar_parameter','parameter')))-noneInit(exceptions,OrdSet()))])
	
	def writeParametersLoad(db=None,gdx=None,onmulti=True,exceptions_load=None,**kwargs):
		itersym = ['$load '+s for s in (OrdSet(db.getTypes(('scalar_parameter','parameter')))-noneInit(exceptions_load,OrdSet()))];
		start = '$GDXIN '+gdx+'\n'+'$onMulti' if onmulti else '$GDXIN '+gdx
		end   = '$GDXIN\n' +'$offMulti;' if onmulti else '$GDXIN;'
		return writeAux(start,end,itersym,joinby='\n')
	@staticmethod
	def writeVariables(db=None,exceptions=None,**kwargs):
		return writeAux('variables',';',[writeGpy(s=db[s]) for s in (OrdSet(db.getTypes(('scalar_variable','variable')))-noneInit(exceptions,OrdSet()))])
	@staticmethod
	def writeVariablesLoad(db=None,gdx=None,onmulti=True,exceptions_load=None,**kwargs):
		itersym = ['$load '+s for s in (OrdSet(db.getTypes(('scalar_variable','variable')))-noneInit(exceptions_load,OrdSet()))];
		start = '$GDXIN '+gdx+'\n'+'$onMulti' if onmulti else '$GDXIN '+gdx
		end   = '$GDXIN\n' +'$offMulti;' if onmulti else '$GDXIN;'
		return writeAux(start,end,itersym,joinby='\n')

# -------------------------------------- 4: Default components	-------------------------------------- #
def auxdict2equal(k,v):
	return k+'='+v

def writeRoot(**kwargs):
	return f"""$ONEOLCOM
$EOLCOM #
$SETLOCAL qmark ";
OPTION {', '.join([auxdict2equal(k,v) for k,v in (default_options_root | kwargs).items()])};
"""

def writeFunctions(precompiler,macros,f=None):
	""" Read functions from text; """
	f = default_user_functions if f is None else f
	funcs = {k:v for k,v in functions_from_str(f).items() if k not in precompiler.user_functions}
	macrs = {k:v for k,v in macros_from_str(f).items() if k not in macros}
	return '\n'.join([v for v in list(funcs.values())+list(macrs.values())])

def writeModel(name, blocks):
	return f"$Model {name} {', '.join(blocks)};\n" if blocks else ""

def writeSolve(solve=None,name=None):
	return f"""solve {name} using CNS;""" if solve is None else solve


# -------------------------------------- 5: Loop, update, solve, store	-------------------------------------- #
def loopText(text, domains, c = None):
	return f"loop({domains}{condition(c=c)},\n\t{text}\n);"

def updateFromGridDB(db0, db, name, updateDict):
	return ';\n\t'.join([f"{writeGpy(db0[k], c=v['c'], l = '.fx')} = {writeGpy(db[v['par']])}" for k,v in updateDict.items()])+';' if updateDict else ""

def updateSolFromGridDB(db0, db, name, updateSolDict):
	return ';\n\t'.join([f"{writeGpy( db[k], c=v['c'], l = '.fx')} = {writeGpy(db0[v['var']], l = '.l')}" for k,v in updateSolDict.items()])+';' if updateSolDict else ""

def declareFromGridDB(db0, db):
	return writeDeclare(db, exceptions=OrdSet(db0.symbols), exceptions_load = OrdSet(db0.symbols)+OrdSet([k for k in db.symbols if k.startswith('sol_')]), gdx = f"""%{db.name}%""")

def loopUpdateSolve(loop, name, db, db0, updateDict, updateSolDict = None, loopConditional = None, solve = None, model = None):
	text = updateFromGridDB(db0, db, name, updateDict)+'\n\t'+writeSolve(solve=solve, name = model)+'\n\t'+updateSolFromGridDB(db0,db,name,noneInit(updateSolDict,{}))
	return declareFromGridDB(db0,db)+loopText(text, loop, c = loopConditional)


#### A few regex functions:
def macros_from_str(string):
	a = re.findall(r"^.*?\$MACRO(.*?)\n",string,re.IGNORECASE | re.DOTALL | re.MULTILINE)
	b = ['$MACRO' + a[i] for i in range(len(a))]
	return {macro_name_from_str(b[i]): b[i] for i in range(len(b))}
	
def functions_from_str(string):
	a = re.findall(r"^.*?\$FUNCTION(.*?)\$ENDFUNCTION.*?$",string,re.IGNORECASE | re.DOTALL | re.MULTILINE)
	b = ['$FUNCTION' + a[i] + '$ENDFUNCTION' for i in range(len(a))]
	return {function_name_from_str(b[i]): b[i] for i in range(len(b))}
	
def blocks_from_str(string):
	a = re.findall(r"^.*?\$BLOCK(.*?)\$ENDBLOCK.*?$",string,re.IGNORECASE | re.DOTALL | re.MULTILINE)
	if a:
		return [block_name_from_str('$BLOCK'+a[i] +'$ENDBLOCK') for i in range(len(a))]
	else:
		return []
def groups_from_str(string):
	a = re.findall(r"^.*?\$GROUP(.*?)\;.*?$",string,re.IGNORECASE | re.DOTALL | re.MULTILINE)
	if a:
		return [group_name_from_str('$GROUP'+a[i] +';') for i in range(len(a))]
	else:
		return []

def macro_name_from_str(string):
	return re.search(r"^.*?\$MACRO(.*?)\(",string,re.IGNORECASE | re.DOTALL | re.MULTILINE).group(1).strip()
def function_name_from_str(string):
	return re.search(r"^.*?\$FUNCTION(.*?)\(.*?",string,re.IGNORECASE | re.DOTALL | re.MULTILINE).group(1).strip()
def block_name_from_str(string):
	return re.search(r"^.*?\$BLOCK\s(.*?)\s.*?",string,re.IGNORECASE | re.DOTALL | re.MULTILINE).group(1).strip()		
def group_name_from_str(string):
	return re.search(r"^.*?\$GROUP\s(.*?)\s.*?",string,re.IGNORECASE | re.DOTALL | re.MULTILINE).group(1).strip()		
