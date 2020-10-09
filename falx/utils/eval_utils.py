import sys

from io import StringIO 
import json
import numpy as np
from timeit import default_timer as timer
import subprocess
import copy
import random


from falx.symbolic import SymTable

def sample_symbolic_table(symtable, config, strategy="diversity"):
    """given a symbolic table, sample a smaller symbolic table that is contained by it
    Args:
        symtable: the input symbolic table
        p_abs: proportion of a demonstration(s if E) which is made symbolic
        num_samples: number of demonstrations to sample from
    Returns:
        the output table sample
    """
    p_abs = config["p_abs"]
    if "E" in p_abs:
        p_abs = p_abs.split("E")[0]
        changeEveryRow = True
    else:
        changeEveryRow = False
    p_abs = float(p_abs)

    size = config["num_samples"]
    if size > len(symtable.values):
        size = len(symtable.values)

    if strategy == "uniform":
        chosen_indices = np.random.choice(list(range(len(symtable.values))), size, replace=False)
    elif strategy == "diversity":
        indices = set(range(len(symtable.values)))
        chosen_indices = set()
        for i in range(size):
            pool = indices - chosen_indices
            candidate_size = min([20, len(pool)])
            candidates = np.random.choice(list(pool), size=candidate_size, replace=False)
            index = pick_diverse_candidate_index(candidates, chosen_indices, symtable.values)
            chosen_indices.add(index)

    sample_values = [symtable.values[i] for i in chosen_indices]

    total_abstracted = 0.0
    for row in sample_values:
        if changeEveryRow: total_abstracted = 0.0
        keys = list(row.keys())
        random.shuffle(keys)
        for k in keys:
            if total_abstracted >= p_abs:
                break
            row[k] = wildcard
            total_abstracted += (1.0/len(keys))

    mandatory_presence = {v:False for v in config["mandatory"]}
    for row in sample_values:
        for k in keys:
            for val in config["mandatory"]:
                if row[k] == val or row[k] == str(val):
                    mandatory_presence[val] = True

    for val in config["mandatory"]:
        if not mandatory_presence[val]:
            return  sample_symbolic_table(symtable, config, strategy=strategy)

    symtable_sample = SymTable(sample_values)
    return symtable_sample


def pick_diverse_candidate_index(candidate_indices, chosen_indices, full_table):
    """according to current_chosen_row_indices and the full table, 
       choose the best candidate that maximize """
    keys = list(full_table[0].keys())
    cardinality = [len(set([r[key] for r in full_table])) for key in keys]
    def card_score_func(card_1, card_2):
        if card_1 == 1 and card_2 > 1:
            return 0
        return 1
    scores = []
    for x in candidate_indices:
        temp_card = [len(set([full_table[i][key] for i in list(chosen_indices) + [x]])) for key in keys]
        score = sum([card_score_func(temp_card[i], cardinality[i]) for i in range(len(keys))])
        scores.append(score)
    return candidate_indices[np.argmax(scores)]

def convert_sym_data(sym_data, config):
    true_output = None
    if config["num_samples"] != None:
        print("sampling from the full output...")
        true_output_view = sym_data.instantiate()
        true_output = []
        for row in true_output_view:
            true_output.append(copy.deepcopy(row))
        print(true_output)
        sym_data = sample_symbolic_table(sym_data, config)
        return sym_data, true_output
    else:
        return sym_data, None

def remove_demonstrations(inst, wildcard = '??'):
    r_count = 0
    r_set = {}
    c_count = 0
    c_set = {}
    for r,i in zip(inst,range(len(inst))):
        for k,v in r.items():
            if v == wildcard:
                c_set[k] = True
                r_set[i] = True
    for k in c_set:
        c_count += 1
    for r in r_set:
        r_count += 1
    if r_count < len(inst):
        return [r for r,i in zip(inst,range(len(inst))) if i not in r_set]
    else:
        keys = list(c_set.keys())
        random.shuffle(keys)
        return [{k:v for (k,v) in r.items() if k not in c_set} for r in inst]
        #newinst = [{k:v for (k,v) in r.items() if k!=keys[0]} for r in inst]
        #res = remove_demonstrations(newinst)
        return res
