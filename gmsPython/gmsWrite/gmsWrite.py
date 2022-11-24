from ._gmsWrite import *

def standardArgs(settings, db, gdx, blocks = None, functions = None, run = True, prefix = '', prefix_run = '', options=None):
	args = {'Root': writeRoot(**noneInit(options, {})), prefix+'Functions': writeFunctions(settings.Precompiler, settings.macros, f=functions), prefix+'Declare': writeDeclare(db, gdx=gdx), prefix+'Blocks': blocks}
	return {k:v for k,v in args.items() if v} | standardRun(settings, db, prefix=prefix_run) if run else {k:v for k,v in args.items() if v}

def standardRun(settings, db, prefix =''):
	return {prefix+'Fix': settings.Compile.fixGroupsText(db,settings['g_exo']), prefix+'Unfix': settings.Compile.unfixGroupsText(db,settings['g_endo']), 
			prefix+'Model': writeModel(settings['name'], settings['blocks']), prefix+'Solve': writeSolve(solve=settings['solve'],name=settings['name'])}

def SolveLoop(settings, dbT, db0 = None, name ='shock', subsetDB = True, loop = 'l1', solve=None, model=None, **kwargs):
	if subsetDB:
		x = settings.partition_db(db=dbT)
		dbT.series.database = (x['non_var'] | x['var_exo'])
	db = gridDB(noneInit(db0, settings.db), dbT, name, loop=loop,**kwargs)
	text = loopUpdateSolve(loop, name, db, settings.db, db.updateDict, updateSolDict = db.updateSolDict, solve = noneInit(solve, settings['solve']), model = noneInit(solve, settings['name']))
	return text, db