import json
import itertools
import numpy as np

import pandas as pd
import networkx as nx
from os.path import commonprefix
import time
import re

# def find_abstraction(s1,s2):
#     pref = commonprefix([s1,s2])
#     post = commonprefix([s1[::-1],s2[::-1]])
#     s1mid = s1[len(pref):len(s1)-len(post)]
#     s2mid = s2[len(pref):len(s2)-len(post)]
#     for c in s1mid+s2mid:
#         if c not in ['(',')',',',' ','1','2','3','4','5','6','7','8','9','0','[',']','+','-']:
#             return None
#     return [pref,post]

def to_list_format(s):
    splitops = s.split(";")[1:]
    nonewvar = [ss.split("<-")[1].strip() for ss in splitops]
    divideopargs = [(ss.split("(",1)[0],ss.split("(",1)[1]) for ss in nonewvar]
    splitargs = [(op,re.split(r',\s*(?![^()]*\))', args[:-1])) for (op, args) in divideopargs]
    argstoset = [(op,[set([v.strip(") (") for v in arg.split(",")]) for arg in args][1:]) for (op, args) in splitargs]

    def cleanup(args):
        cleanitup = True
        for arglist in args:
            for a in arglist:
                if a != '_?_':
                    cleanitup = False
        return cleanitup
    argstoset = [(op,arglist) for (op,arglist) in argstoset if not cleanup(arglist)]
    return argstoset

def matches_sketch(p,s,strict=False):
    if len(p) != len(s):
        return False
    z = zip(p,s)
    for ((opp,argsp),(ops,argss)) in z:
        if opp != ops:
            return False
        if len(argsp) != len(argss):
            return False
        if strict:
            for (mandp,mands) in zip(argsp,argss):
                for mand in mands:
                    if mand not in mandp:
                        return False
    return True

#prereq: sketches match
def refine_sketch(p,s):
    return [(ops, [valss.intersection(valsp) for (valsp,valss) in zip(argsp,argss)]) for ((opp,argsp),(ops,argss)) in zip(p,s)]

def to_sketch(p):
    sk = to_list_format(p.stmt_string())
    return sk

def fit_progs_into_abstraction(cands):
    #each values in sketches is a list of the sketch and a list of tuples of a path to a hole and must-include values of it
    #each sketch is only present once
    sketches = []
    count = 0
    cands = [to_list_format(p.stmt_string()) for p in cands]
    for p in cands:
        for i, s in enumerate(sketches):
            if matches_sketch(p,s):
                count += 1
                sketches[i] = refine_sketch(p,s)
                break
        else:
            sketches.append(p)
    prlog("We could have avoided looking at " + str(count) + " programs out of " + str(len(cands)),pr=True)
    for p in sketches:
        print(p)
    print("Printed the candidates") 
    return sketches



def remove_duplicate_columns(df):
    """Given a pandas table deuplicate column duplicates"""
    to_drop = []
    col_num = len(df.columns)
    
    for i, c1 in enumerate(df.columns):
        c1 = df.columns[i]
        if c1 in to_drop: continue

        for j, c2 in enumerate(df.columns):    
            if i >= j: continue
            if t_or_l_inclusion(tuple(df[c1]), tuple(df[c2]),wild_card=None):
                to_drop.append(c2)

    ret_table = df[[c for c in df.columns if c not in to_drop]]
    return ret_table

def prlog(s,pr=False):
    if pr:
        print(s)
    with open("/Users/peter/Documents/UCSB/falx/falx/output/peterlogs/interfacelog.txt",'a') as f:
        f.write(s)

with open("/Users/peter/Documents/UCSB/falx/falx/output/peterlogs/timinglog.txt",'w') as f:
    f.write("timing...\n")
def prtime(tag, duration):
    with open("/Users/peter/Documents/UCSB/falx/falx/output/peterlogs/timinglog.txt",'a') as f:
        f.write(tag + ":" + str(duration) + "\n")

def check_table_inclusion(table1, table2, wild_card="??"):
    """check if table1 is included by table2 (projection + subset), 
        this is sound but not complete: 
            if it thinks two tables are not equal, they absolutely inequal, 
        tables are records"""
    res = align_table_schema(table1, table2,boolean_result=True)

    if res is None:
        return False
    if res == False:
        return False
    if res == []:
        return False
    if res == {}:
        return False
    return True

    # if len(table1) == 0:
    #     return True

    # mapping = {}
    # vals2_dicts = {}
    # for k2 in table2[0].keys():
    #     vals2_dicts[k2] = construct_value_dict([r[k2] for r in table2 if k2 in r])
    
    # for k1 in table1[0].keys():
    #     mapping[k1] = []
    #     vals1_dict = construct_value_dict([r[k1] for r in table1 if k1 in r])
    #     for k2 in table2[0].keys():
    #         vals2_dict = vals2_dicts[k2]
    #         contained = True
    #         for x in vals1_dict:

    #             if wild_card != None and x == wild_card:
    #                 # we consider this x value matches anything
    #                 continue

    #             if x not in vals2_dict:
    #                 contained = False
    #             if contained == False:
    #                 break
    #         if contained:
    #             mapping[k1].append(k2)

    # #print(mapping)

    # # distill plausible mappings from the table
    # # not all choices generated from the approach above generalize, we need to check consistency
    # t1_schema = list(mapping.keys())
    # mapping_id_lists = [list(range(len(mapping[key]))) for key in t1_schema]
    # check_ok = all([len(l) > 0 for l in mapping_id_lists])
    # return check_ok


def t_or_l_inclusion(t1,t2,wild_card="??"):
    for x1,x2 in zip(list(t1),list(t2)):
        if x1 != None and x1 == wild_card:
            continue
        if x1 != x2:
            return False
    return True

def align_table_schema(table1, table2, check_equivalence=False, boolean_result=False, find_all_alignments=False, wild_card="??"):
    """align table schema, assume that table1 is contained by table2
    Args:
        find_all_alignments: whether to find all alignments or not
    """
    start = time.time()

    with open("petertestinterface.txt", 'a') as f:
        f.write("table1: " + str(table1) + "\n")
        f.write("table2: " + str(table2) + "\n")

    if len(table1) > len(table2):
        # cannot find any mapping
        print("no mapping because t1 > t2")
        return None

    if boolean_result and len(table1) == 0:
        prtime("align", time.time()-start)
        return True

    mapping = {}
    vals2_dicts = {}
    #each key in the larger table is associated with a multi-set of its values
    for k2 in table2[0].keys():
        vals2_dicts[k2] = construct_value_dict([r[k2] for r in table2 if k2 in r])

    for k1 in table1[0].keys():
        mapping[k1] = []
        #same with the smaller table
        vals1_dict = construct_value_dict([r[k1] for r in table1 if k1 in r])
        for k2 in table2[0].keys():
            vals2_dict = vals2_dicts[k2]
            contained = True
            for x in vals1_dict:
                if wild_card != None and x == wild_card:
                    # the same wildcard code from above works here as well
                    continue

                if (x not in vals2_dict) or (vals2_dict[x] < vals1_dict[x]):
                    contained = False
                if check_equivalence and (x not in vals2_dict or vals2_dict[x] != vals1_dict[x]):
                    contained = False
                if contained == False:
                    break
            if contained and check_equivalence:
                for x in vals2_dict:
                    if x not in vals1_dict:
                        contained = False
                        break

            if contained:
                mapping[k1].append(k2)
    
    #print(mapping)

    # distill plausible mappings from the table
    # not all choices generated from the approach above generalize, we need to check consistency
    t1_schema = list(mapping.keys())
    mapping_id_lists = [list(range(len(mapping[key]))) for key in t1_schema]

    all_choices = list(itertools.product(*mapping_id_lists))


        # directly return if there is only one choice, !!!should still check it to ensure correctness
    #if len(all_choices) == 1:
    #    return {key:mapping[key][0] for key in mapping}

    all_alignments = []
    for mapping_id_choices in all_choices:
        # the following is an instantiation of the the mapping
        inst = { t1_schema[i]:mapping[t1_schema[i]][mapping_id_choices[i]] for i in range(len(t1_schema))}

        def value_handling_func(val):
            if isinstance(val, (int,)):
                return val
            try:
                val = float(val)
                val = np.round(val, 5)
            except:
                pass
            return val

        # distill the tables for checking
        frozen_table1 = [tuple([value_handling_func(r[key]) for key in t1_schema if key in r]) for r in table1]
        frozen_table2 = [tuple([value_handling_func(r[inst[key]]) for key in t1_schema if inst[key] in r]) for r in table2]

        with open("petertestinterface.txt", 'a') as f:
            f.write("frozen_table2: " + str(frozen_table2) + "\n")
        
        B = nx.Graph()
        B.add_nodes_from(frozen_table1, bipartite=0)
        B.add_nodes_from([str(x) for x in frozen_table2], bipartite=1)
        graph_edges = [(t1,str(t2)) for (t1,t2) in itertools.product(frozen_table1,frozen_table2) if t_or_l_inclusion(t1,t2)]
        B.add_edges_from(graph_edges)
        top_nodes = {n for n, d in B.nodes(data=True) if d["bipartite"] == 0}
        best_matching = nx.bipartite.maximum_matching(B,top_nodes=top_nodes)
        if len(best_matching) / 2 == len(frozen_table1):
            if find_all_alignments:
                all_alignments.append(inst)
            else:
                if boolean_result: 
                    prtime("align", time.time()-start)
                    return True
                prtime("align", time.time()-start)
                return inst

        # if all([frozen_table1.count(t) <= frozen_table2.count(t) for t in frozen_table1]):
        #     if find_all_alignments:
        #         all_alignments.append(inst)
        #     else:
        #         return inst

    if boolean_result:
        prtime("align", time.time()-start)
        return len(all_alignments) > 0

    if find_all_alignments:

        prtime("align", time.time()-start)
        return all_alignments

    prtime("align", time.time()-start)
    return None


def construct_value_dict(values):
    new_values = []
    values = np.array(values)
    for v in values:
        try:
            v = v.astype(np.float64)
            v = np.round(v, 5)
            new_values.append(v)
        except:
            new_values.append(v)

    values = new_values

    value_dict = {}
    for x in values:
        if not x in value_dict:
            value_dict[x] = 0
        value_dict[x] += 1
    return value_dict


def update_search_grammar(extra_consts, in_file, out_file):
    """let the user to provide constants to the synthesis target grammar."""

    current_grammar = None
    with open(in_file, "r") as f:
        current_grammar = f.read()

    if extra_consts:
        consts = "enum SmallStr {{\n  {0} \n}}".format(",".join(['"{}"'.format(x) for x in extra_consts]))

        extra = '''
        func mutateCustom: Table r -> Table a, BoolFunc b, ColInt c, SmallStr d {
          row(r) == row(a);
          col(r) == col(a) + 1;
        }

        func filter: Table r -> Table a, BoolFunc b, ColInt c, SmallStr d {
          row(r) < row(a);
          col(r) == col(a);
        }'''
        new_grammar = consts + "\n" + current_grammar + "\n" + extra
    else:
        new_grammar = current_grammar

    with open(out_file, "w") as g:
        g.write(new_grammar)


if __name__ == '__main__':
    pass
    #update_search_grammar(["Total Result", ""], "dsl/tidyverse.tyrell.base", "dsl/tidyverse.tyrell")
    