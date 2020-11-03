import sys
import traceback
import copy
from pprint import pprint
import pandas as pd
import time

from falx.table.language import (HOLE, Node, Table, Select, Unite, Filter, Separate, Spread, 
	Gather, GroupSummary, CumSum, Mutate, MutateCustom)
from falx.table import enum_strategies
from falx.table import abstract_eval
from falx.utils.synth_utils import remove_duplicate_columns, check_table_inclusion, t_or_l_inclusion, align_table_schema, prlog, fit_progs_into_abstraction, prtime, matches_sketch, to_sketch


abstract_combinators = {
	"select": lambda q: Select(q, cols=HOLE),
	"unite": lambda q: Unite(q, col1=HOLE, col2=HOLE),
	"filter": lambda q: Filter(q, col_index=HOLE, op=HOLE, const=HOLE),
	"separate": lambda q: Separate(q, col_index=HOLE),
	"spread": lambda q: Spread(q, key=HOLE, val=HOLE),
	"gather": lambda q: Gather(q, value_columns=HOLE),
	"group_sum": lambda q: GroupSummary(q, group_cols=HOLE, aggr_col=HOLE, aggr_func=HOLE),
	"cumsum": lambda q: CumSum(q, target=HOLE),
	"mutate": lambda q: Mutate(q, col1=HOLE, op=HOLE, col2=HOLE),
	"mutate_custom": lambda q: MutateCustom(q, col=HOLE, op=HOLE, const=HOLE), 
}

wild_card = "??"

global attempt_count
attempt_count = 0

global candidate_programs_cache
candidate_programs_cache = None

global known_programs
known_programs = []

#59
#[[('gather', [{}]), ('separate', [{}])], [('gather', [{'5', '1'}]), ('separate', [{}]), ('spread', [{}, {}])]]

#46
# known_programs = [[('gather', [{'3'}])], [('separate', [{'0'}]), ('gather', [{'2'}])]]

# 56
# known_programs = [[('gather', [{'10'}])]]

#37
# known_programs = [
# [('gather', [{'2'}]), ('mutate', [{}, {'-'}, {}])],
# [('mutate', [{'5'}, {'-'}, {'2'}]), ('gather', [{'2'}])]]
# known_programs = [
# [('gather', [{'2'}]), ('mutate', [{}, {'-'}, {}])],
# [('mutate', [{'5'}, {'-'}, {'2'}]), ('gather', [{'2'}])]
# [('mutate', [{'5'}, {'-'}, {'2'}])],
# [('gather', [{'1', '3', '4'}]), ('group_sum', [{'0'}, {'4'}, {'sum'}])],
# [('gather', [{}]), ('mutate', [{}, {'-'}, {}])],
# [('cumsum', [{}]), ('mutate', [{'5'}, {'-'}, {'2'}])],
# [('mutate', [{'5'}, {'-'}, {'2'}]), ('gather', [{}])],
# [('mutate', [{'5'}, {'-'}, {'2'}]), ('cumsum', [{}])]]


#21 or something
# known_programs = [[('gather', [{'3'}])],
# [('select', [{'0', '1', '3'}]), ('gather', [{}])],
# [('gather', [{'3'}]), ('select', [{'0', '1'}])],
# [('gather', [{}]), ('gather', [{}])],
# [('gather', [{'3'}]), ('cumsum', [{}])],
# [('gather', [{'3'}]), ('mutate', [{}, {}, {}])],
# [('cumsum', [{}]), ('gather', [{'3'}])],
# [('mutate', [{}, {}, {}]), ('gather', [{'3'}])]]

def update_tree_value(node, path, new_val):
	"""from a given ast node, locate the refence to the arg,
	   and update the value"""
	for k in path:
		node = node["children"][k]
	node["value"] = new_val

def get_node(node, path):
	for k in path:
		node = node["children"][k]
	return node

with open("/Users/peter/Documents/UCSB/falx/falx/output/peterlogs/interfacelog.txt", 'w') as f:
	f.write("synthesizer loaded\n")

class Synthesizer(object):

	def __init__(self, config=None):
		if config is None:
			self.config = {
				"operators": ["select", "unite", "filter", "separate", "spread", 
					"gather", "group_sum", "cumsum", "mutate", "mutate_custom"],
				"filer_op": [">", "<", "=="],
				"constants": [],
				"aggr_func": ["mean", "sum", "count"],
				"mutate_op": ["+", "-"],
				"gather_max_val_list_size": 3,
				"gather_max_key_list_size": 3
			}
		else:
			self.config = config

	def from_list_format(self, m):
		sketch = Table(0)
		for (op,args) in m:
			sketch = abstract_combinators[op](sketch)
		return sketch

	def enum_sketches(self, inputs, output, size, heur=True):
		start = time.time()
		size = 3
		"""enumerate program sketches up to the given size"""

		# check if output contains a new value 
		# (this decides if we should use ops that generates new vals)
		
		inp_val_set = set([v for t in inputs for r in t for k, v in r.items()] + [k for t in inputs for k in t[0]])
		out_val_set = set([v for r in output for k, v in r.items() if v != wild_card])
		new_vals = out_val_set - inp_val_set
		
		#if any([len(t[0]) < 4 for t in inputs]):
			# always consider new value operators for small tables (#column < 4)
		#	contain_new_val = True

		# check if there are seperators in column names
		sep_in_col_names = [key for t in inputs for key in t[0] if ('-' in key or '_' in key or '/' in key)]
		sep_in_content = [v for t in inputs for r in t for k, v in r.items() if (isinstance(v, str) and ('-' in v or '_' in v or '/' in v))]
		has_sep = (len(sep_in_col_names) > 0) or (len(sep_in_content) > 0)

		candidates = {}
		for level in range(0, size + 1):
			candidates[level] = []
			if level == 0:
				candidates[level] += [Table(data_id=i) for i in range(len(inputs))]
			else:
				for p in candidates[level - 1]:
					for op in abstract_combinators:
						#ignore operators that are not set
						if op not in self.config["operators"]:
							continue
						q = abstract_combinators[op](copy.copy(p))
						candidates[level].append(q)

		if heur:
			for level in range(0, size + 1):
				candidates[level] = [q for q in candidates[level] if not enum_strategies.disable_sketch(q, new_vals, has_sep)]
		prtime("sketch enumeration", time.time()-start)
		return candidates

	def pick_vars(self, ast, inputs):
		"""list paths to all holes in the given ast"""
		def get_paths_to_all_holes(node):
			results = []
			for i, child in enumerate(node["children"]):
				if child["type"] == "node":
					# try to find a variable to infer
					paths = get_paths_to_all_holes(child)
					for path in paths:
						results.append([i] + path)
				elif child["value"] == HOLE:
					# we find a variable to infer
					results.append([i])
			return results
		return get_paths_to_all_holes(ast)

	def infer_domain(self, ast, var_path, inputs):
		node = Node.load_from_dict(get_node(ast, var_path[:-1]))
		return node.infer_domain(arg_id=var_path[-1], inputs=inputs, config=self.config)

	def instantiate(self, ast, var_path, inputs):
		"""instantiate one hole in the program sketch"""
		domain = self.infer_domain(ast, var_path, inputs)
		candidates = []
		for val in domain:
			new_ast = copy.deepcopy(ast)
			update_tree_value(new_ast, var_path, val)
			candidates.append(new_ast)
		return candidates

	def instantiate_one_level(self, ast, inputs):
		"""generate program instantitated from the most recent level
			i.e., given an abstract program, it will enumerate all possible abstract programs that concretize
		"""
		var_paths = self.pick_vars(ast, inputs)

		# there is no variables to instantiate
		if var_paths == []:
			return [], []

		# find all variables at the innermost level
		innermost_level = max([len(p) for p in var_paths])
		target_vars = [p for p in var_paths if len(p) == innermost_level]

		recent_candidates = [ast]
		for var_path in target_vars:
			temp_candidates = []
			for partial_prog in recent_candidates:
				temp_candidates += self.instantiate(partial_prog, var_path, inputs)
			recent_candidates = temp_candidates

		# for c in recent_candidates:
		# 	nd = Node.load_from_dict(c)
		# 	print(f"{' | '}{nd.stmt_string()}")
		
		# this show how do we trace to the most recent program level
		concrete_program_level = innermost_level - 1

		return recent_candidates, concrete_program_level

	def iteratively_instantiate_and_print(self, p, inputs, level, print_programs=False):
		"""iteratively instantiate a program (for the purpose of debugging)"""
		#TODO: add this
		#if print_programs:
			#print(f"{'  '.join(['' for _ in range(level)])}{p.stmt_string()}")
		results = []
		if p.is_abstract():
			ast = p.to_dict()
			var_path = self.pick_vars(ast, inputs)[0]
			#domain = self.infer_domain(ast, path, inputs)
			candidates = self.instantiate(ast, var_path, inputs)
			for c in candidates:
				nd = Node.load_from_dict(c)
				results += self.iteratively_instantiate_and_print(nd, inputs, level + 1, print_programs)
			return results
		else:
			return [p]

	def iteratively_instantiate_with_premises_check(self, p, inputs, premise_chains, time_limit_sec=None):
		"""iteratively instantiate abstract programs w/ promise check """
		def instantiate_with_premises_check(p, inputs, premise_chains):
			start_inst = time.time()
			"""instantiate programs and then check each one of them against the premise """
			results = []
			if p.is_abstract():

				print(p.stmt_string())
				ast = p.to_dict()
				next_level_programs, level = self.instantiate_one_level(ast, inputs)

				for _ast in next_level_programs:
					start_match = time.time()
					listsketch = to_sketch(Node.load_from_dict(_ast))
					# print(to_sketch(Node.load_from_dict(_ast)))
					cont = False
					for q in known_programs:
						if matches_sketch(listsketch,q,strict=True):
							print("some of them can be skipped")
							cont = True
							break
					prtime("sketch_matching",time.time()-start_match)
					if cont:
						continue

					# force terminate if the remaining time is running out
					if time_limit_sec is not None and time.time() - start_time > time_limit_sec:
						return results

					premises_at_level = [[pm for pm in premise_chain if len(pm[1]) == level][0] for premise_chain in premise_chains]

					subquery_res = None
					for premise, subquery_path in premises_at_level:

						if subquery_res is None:
							# check if the subquery result contains the premise
							start = time.time()
							subquery_node = get_node(_ast, subquery_path)
							print("  {}".format(Node.load_from_dict(subquery_node).stmt_string()))
							subquery_res = Node.load_from_dict(subquery_node).eval(inputs)
							prtime("eval_in_instant",time.time()-start)
							#print(subquery_res)

						#print(subquery_res)
						if check_table_inclusion(premise.to_dict(orient="records"), subquery_res.to_dict(orient="records")):

							# debug
							# p = Node.load_from_dict(_ast)
							# if not p.is_abstract():
							# 	print(f"{' - '}{p.stmt_string()}")
							# 	print(subquery_res)
							# 	print(premise)
							# 	print( check_table_inclusion(premise.to_dict(orient="records"), subquery_res.to_dict(orient="records")))

							results.append(Node.load_from_dict(_ast))
							break
				prtime("instant2", time.time()-start_inst)
				return results
			else:
				prtime("instant2", time.time()-start_inst)
				return []

		print("time limit: {}".format(time_limit_sec))

		results = []
		if p.is_abstract():
			
			if time_limit_sec < 0:
				return []
			start_time = time.time()

			candidates = instantiate_with_premises_check(p, inputs, premise_chains)
			for _p in candidates:
				# if time_limit_sec is not None and time.time() - start_time > time_limit_sec:
				# 	return results
				remaining_time_limit = time_limit_sec - (time.time() - start_time) if time_limit_sec is not None else None
				results += self.iteratively_instantiate_with_premises_check(_p, inputs, premise_chains, remaining_time_limit)
			return results
		else:
			# handling concrete programs won't take long, allow them to proceed
			return [p]

	# def enumerative_all_programs(self, inputs, output, max_prog_size):
	# 	"""Given inputs and output, enumerate all programs in the search space """
	# 	all_sketches = self.enum_sketches(inputs, output, size=max_prog_size)
	# 	concrete_programs = []
	# 	for level, sketches in all_sketches.items():
	# 		for s in sketches:
	# 			concrete_programs += self.iteratively_instantiate_and_print(s, inputs, 1, True)
	# 	for p in concrete_programs:
	# 		try:
	# 			t = p.eval(inputs)
	# 			print(p.stmt_string())
	# 			print(t)
	# 		except Exception as e:
	# 			print(f"[error] {sys.exc_info()[0]} {e}")
	# 			tb = sys.exc_info()[2]
	# 			tb_info = ''.join(traceback.format_tb(tb))
	# 			print(tb_info)
	# 	print("----")
	# 	print(f"number of programs: {len(concrete_programs)}")

	def instantiate_programs_from_sketch(self, s, inputs, output, deduction=True):
		if not deduction:
			return self.iteratively_instantiate_and_print(s, inputs, 1) #TODO: figure out what this 1 does
		else:
			start = time.time()
			ast = s.to_dict()
			out_df = pd.DataFrame.from_dict(output)

			out_df = remove_duplicate_columns(out_df)
			prtime("conversion",time.time()-start)
			# all premise chains for the given ast
			start = time.time()
			premise_chains = abstract_eval.backward_eval(ast, out_df)
			prtime("backward_eval", time.time()-start)

			#TODO: figure out how the time limit works
			# remaining_time_limit = time_limit_sec - (time.time() - start_time) if time_limit_sec is not None else None
			return self.iteratively_instantiate_with_premises_check(s, inputs, premise_chains, 5000000000)



	def enumerative_synthesis(self, inputs, output, max_prog_size, time_limit_sec=None, solution_limit=None, true_output=None, lightweight=False, deduction=True,heuristics=False):
		
		prlog("the solution limit is: " + str(solution_limit),pr=True)

		if heuristics == "True":
			heuristics = True
		elif heuristics == "False":
			heuristics = False
		else:
			print("wrong heuristic input, should be the string True or the string False")
			exit(1)

		def encache(cands,k):
			global candidate_programs_cache

			if candidate_programs_cache is not None:
				prlog("OVERWRITING CACHE")
			candidate_programs_cache = (output, cands, k)
			return cands

		start_time = time.time()

		# if candidate_sketches_cache is not None:
		# 	(prevOutput, prevSketches) = candidate_programs_cache
		# 	if align_table_schema(prevOutput,output, boolean_result=True):
		# 		all_sketches = prevsketches

		all_sketches = self.enum_sketches(inputs, output, size=max_prog_size, heur=heuristics)
		candidates = []
		for level, sketches in all_sketches.items():
			# for incrementality
			# if min_prog_size > level:
			# 	continue
			for s in sketches:
				print(s.stmt_string())
				start = time.time()
				concrete_programs = self.instantiate_programs_from_sketch(s,inputs,output,deduction=deduction)
				prtime("instantiate", time.time()-start)
				start = time.time()
				for p in concrete_programs:
					try:
						t = p.eval(inputs)
						if align_table_schema(output, t.to_dict(orient="records")) != None:
							candidates.append(p)

					#TODO: is this necessary?
					except Exception as e:
						print(f"[error] {sys.exc_info()[0]} {e}")
						tb = sys.exc_info()[2]
						tb_info = ''.join(traceback.format_tb(tb))
						print(tb_info)
				prtime("check", time.time()-start)


		abstract_programs = fit_progs_into_abstraction(candidates)
		sketch_nodes = [self.from_list_format(p) for p in abstract_programs]

		prlog("\n\n no sketches left to try ....\n\n")
		encache(sketch_nodes,max_prog_size+1)
		return candidates


	# #todo: these optional args do almost nothing
	# def enumerative_search(self, inputs, output, max_prog_size, time_limit_sec=None, solution_limit=None, true_output=None):
	# 	"""Given inputs and output, enumerate all programs in the search space until 
	# 		find a solution p such that output ⊆ subseteq p(inputs)  """
	# 	if true_output != None:
	# 		prlog("True output is: " + str(true_output))

	# 	all_sketches = self.enum_sketches(inputs, output, size=max_prog_size)
	# 	candidates = []
	# 	prlog("true output:\n" + str(output) + "\n")
	# 	for level, sketches in all_sketches.items():
	# 		for s in sketches:
	# 			concrete_programs = self.iteratively_instantiate_and_print(s, inputs, 1)
	# 			prlog("\nSketch\n:" + str(s.to_dict())+"\n")
	# 			prlog("CONCRETE PROGRAMS:\n"+str(concrete_programs) + "\n")

	# 			for p in concrete_programs:
	# 				try:
	# 					t = p.eval(inputs)
	# 					temp = False
	# 					tempTrue = False
	# 					if align_table_schema(output, t.to_dict(orient="records")) != None:
	# 						temp = True
	# 						#used for evaluation, but not exploration
	# 						# if true_output != None:
	# 						# 	global attempt_count
	# 						# 	if align_table_schema(true_output,t.to_dict(orient="records"), boolean_result=True): #and align_table_schema(t.to_dict(orient="records"), true_output, boolean_result=True):
	# 						# 		print("# candidates before getting a good enough solution: " + str(attempt_count))
	# 						# 		tempTrue = True
	# 						# 		#return candidates
	# 						# 	else:
	# 						# 		attempt_count += 1

	# 						print(p.stmt_string())
	# 						print(t)
	# 						candidates.append(p)
	# 					prlog("sketch: " + str(s.to_dict()) + "\n")
	# 					prlog("program: " + str(p.to_dict()) + "\n")
	# 					if temp:
	# 						prlog("MATCH!\n")
	# 					if tempTrue:
	# 						prlog("CORRECT!\n")
	# 					prlog("candidate output:\n" + str(t) + "\n")
						
	# 				except Exception as e:
	# 					print(f"[error] {sys.exc_info()[0]} {e}")
	# 					tb = sys.exc_info()[2]
	# 					tb_info = ''.join(traceback.format_tb(tb))
	# 					print(tb_info)
	# 	print("----")
	# 	print(f"number of programs: {len(candidates)}")
	# 	return candidates

	# def enumerative_synthesis(self, inputs, output, max_prog_size, time_limit_sec=None, solution_limit=None, true_output=None, lightweight=False):
	# 	"""Given inputs and output, enumerate all programs with premise check until 
	# 		find a solution p such that output ⊆ subseteq p(inputs) """

	# 	prlog("the solution limit is: " + str(solution_limit),pr=True)

	# 	def encache(cands,k):
	# 		global candidate_programs_cache

	# 		if candidate_programs_cache is not None:
	# 			prlog("OVERWRITING CACHE")
	# 		candidate_programs_cache = (output, cands, k)
	# 		return cands

	# 	#incrementality
	# 	# global candidate_programs_cache
	# 	# min_prog_size = 0
	# 	# if candidate_programs_cache is not None:
	# 	# 	(prevOutput, prevCands,k) = candidate_programs_cache
	# 	# 	if align_table_schema(prevOutput,output, boolean_result=True):
	# 	# 		if lightweight:
	# 	# 			return [cand for cand in prevCands if align_table_schema(output,cand.eval(inputs).to_dict(orient="records"),boolean_result=True)]
	# 	# 		else:
	# 	# 			min_prog_size = k

	# 	start_time = time.time()

	# 	all_sketches = self.enum_sketches(inputs, output, size=max_prog_size)
	# 	candidates = []
	# 	for level, sketches in all_sketches.items():
	# 		# for incrementality
	# 		# if min_prog_size > level:
	# 		# 	continue
	# 		for s in sketches:
	# 			print(s.stmt_string())
	# 			ast = s.to_dict()
	# 			out_df = pd.DataFrame.from_dict(output)

	# 			out_df = remove_duplicate_columns(out_df)
	# 			# all premise chains for the given ast
	# 			premise_chains = abstract_eval.backward_eval(ast, out_df)

	# 			remaining_time_limit = time_limit_sec - (time.time() - start_time) if time_limit_sec is not None else None
	# 			programs = self.iteratively_instantiate_with_premises_check(s, inputs, premise_chains, remaining_time_limit)
				
	# 			for p in programs:
	# 				# check table consistensy
	# 				t = p.eval(inputs).to_dict(orient="records")
	# 				alignment_result = check_table_inclusion(output, t)
	# 				if alignment_result:
	# 					candidates.append(p)
	# 					# TODO: make this a flag (or, even better, separate it out somehow)
	# 					# if true_output != None:
	# 					# 	global attempt_count
	# 					# 	prlog("hello: attempt count is " + str(attempt_count) + "\n",pr=True)

	# 					# 	correct_table_trans = align_table_schema(true_output,t.to_dict(orient="records"), boolean_result=True)
	# 					# 	other_dir = align_table_schema(t.to_dict(orient="records"), true_output, boolean_result=True)
	# 					# 	# if correct_table_trans and not other_dir:
	# 					# 	# 	print("TRUE OUTPUT (length " + str(len(true_output)) + "): " + str(true_output))
	# 					# 	# 	print("P's OUTPUT (length " + str(len(t.to_dict(orient="records"))) + "): " + str(t.to_dict(orient="records")))
	# 					# 	if correct_table_trans and other_dir:
	# 					# 		prlog("# candidates before getting the correct solution: " + str(attempt_count), pr=True)
	# 					# 		prlog("\n about to return from synthesis ....\n",pr=True)
	# 					# 		return encache(candidates,level)
	# 					# 	else:
	# 					# 		attempt_count += 1
	# 					# 	prlog("hello: now attempt count is " + str(attempt_count) + "\n",pr=True)

	# 				#TODO: add this back in, make it more clear
	# 				# if solution_limit is not None and len(candidates) >= solution_limit:
	# 				# 	prlog("\n\n found " + str(len(candidates)) + " candidates ....\n\n")
	# 				# 	return encache(candidates,level)
				
	# 			# early return if the termination condition is met
	# 			# TODO: time_limit may be exceeded if the synthesizer is stuck on iteratively instantiation
	# 			# if time_limit_sec is not None and time.time() - start_time > time_limit_sec:
	# 			# 	prlog("\n\n ran out of time ....\n\n")
	# 			# 	return encache(candidates,level)
	# 		# TODO: give a flag for this
	# 		# if len(candidates) > 0:
	# 		# 	prlog("finished out level " + str(level) + " with candidates ...")
	# 		# 	return encache(candidates,level+1)

	# 	prlog("\n\n no sketches left to try ....\n\n")
	# 	return encache(candidates,max_prog_size+1)
