import json
import itertools
import numpy as np

import pandas as pd
import networkx as nx

def remove_duplicate_columns(df):
    """Given a pandas table deuplicate column duplicates"""
    to_drop = []
    col_num = len(df.columns)
    
    for i, c1 in enumerate(df.columns):
        c1 = df.columns[i]
        if c1 in to_drop: continue

        for j, c2 in enumerate(df.columns):    
            if i >= j: continue
            if t_or_l_inclusion(tuple(df[c1]), tuple(df[c2])):
                to_drop.append(c2)

    ret_table = df[[c for c in df.columns if c not in to_drop]]
    return ret_table


def check_table_inclusion(table1, table2, wild_card=None):
    """check if table1 is included by table2 (projection + subset), 
        this is sound but not complete: 
            if it thinks two tables are not equal, they absolutely inequal, 
        tables are records"""
    if len(table1) == 0:
        return True

    mapping = {}
    vals2_dicts = {}
    for k2 in table2[0].keys():
        vals2_dicts[k2] = construct_value_dict([r[k2] for r in table2 if k2 in r])
    
    for k1 in table1[0].keys():
        mapping[k1] = []
        vals1_dict = construct_value_dict([r[k1] for r in table1 if k1 in r])
        for k2 in table2[0].keys():
            vals2_dict = vals2_dicts[k2]
            contained = True
            for x in vals1_dict:

                if wild_card != None and x == wild_card:
                    # we consider this x value matches anything
                    continue

                if x not in vals2_dict:
                    contained = False
                if contained == False:
                    break
            if contained:
                mapping[k1].append(k2)

    #print(mapping)

    # distill plausible mappings from the table
    # not all choices generated from the approach above generalize, we need to check consistency
    t1_schema = list(mapping.keys())
    mapping_id_lists = [list(range(len(mapping[key]))) for key in t1_schema]
    check_ok = all([len(l) > 0 for l in mapping_id_lists])
    return check_ok


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

    with open("petertestinterface.txt", 'a') as f:
        f.write("table1: " + str(table1) + "\n")
        f.write("table2: " + str(table2) + "\n")

    if len(table1) > len(table2):
        # cannot find any mapping
        return None

    if boolean_result and len(table1) == 0:
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

    if boolean_result: return len(all_choices) > 0

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
                return inst

        # if all([frozen_table1.count(t) <= frozen_table2.count(t) for t in frozen_table1]):
        #     if find_all_alignments:
        #         all_alignments.append(inst)
        #     else:
        #         return inst

    if find_all_alignments:
        return all_alignments

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
    