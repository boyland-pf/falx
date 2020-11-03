
import json
import pandas as pd
import os
import datetime
from pprint import pprint
import subprocess
import argparse

import sys

sys.path.append(os.path.abspath('..'))

from falx.visualization.chart import VisDesign
# from matplotlib_chart import MatplotlibChart
# import table_utils
# from timeit import default_timer as timer

from falx.interface import FalxInterface

# default directories
PROJ_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
DATA_DIR = os.path.join(PROJ_DIR, "benchmarks")

# arguments
parser = argparse.ArgumentParser()
parser.add_argument("--data_dir", dest="data_dir", default=DATA_DIR, help="the directory of all benchmarks")
parser.add_argument("--data_id", dest="data_id", default="001", 
                    help="the id of the benchmark, if None, it runs for all tests in the data_dir")
parser.add_argument("--num_samples", dest="num_samples", default=4, type=int, help="the number of samples")
parser.add_argument("--p", dest="p_abs", default="0.0", type=str, help="proportion per row of abstraction")
parser.add_argument("--backend", dest="backend", default="vegalite", type=str, help="visualization backend")
parser.add_argument("--prune", dest="prune", default="falx", type=str, help="prune strategy (falx, forward, morpheus)")
parser.add_argument("--heu", dest="heuristics", default="True", type=str, help="Enumeration heuristics (True or False)")

def test_benchmarks(data_dir, data_id, num_samples, p_abs, backend, prune,h):
    """load the dataset into panda dataframes """
    test_targets = None
    if data_id is not None:
        test_targets = [str(data_id)] # + '.json']
    else:   
        test_targets = [fname for fname in os.listdir(data_dir) if fname.endswith(".json")]

    benchmarks = []
    for fname in test_targets:

        with open(os.path.join(data_dir, fname), "r") as f:
            data = json.load(f)

        if not "vl_spec" in data: 
            # ignore cases that do not have vl specs
            continue

        print("====> run synthesize {}".format(fname))
        print("# num samples per layer: {}".format(num_samples))

        # read the dataset and create visualization
        input_data = data["input_data"]
        extra_consts = data["constants"] if "constants" in data else []
        vis = VisDesign.load_from_vegalite(data["vl_spec"], data["output_data"])
        trace = vis.eval()

        result = FalxInterface.synthesize([input_data], trace, extra_consts=extra_consts, num_samples = num_samples, p_abs = p_abs, config = {"solution_limit": 50, "time_limit_sec": 60*10, "heuristics": h})

        # print("## synthesize result for task {}".format(fname))
        # for p, vis in result:
        #     print("# table_prog:")
        #     print("  {}".format(p))
            #print("# vis_spec:")
            # if backend == "vegalite":
            #     vl_obj = vis.to_vl_obj()
            #     data = vl_obj.pop("data")["values"]
            #     print("    {}".format(vl_obj))
            # else:
            #     print(vis)

if __name__ == '__main__':
    flags = parser.parse_args()
    test_benchmarks(flags.data_dir, flags.data_id, flags.num_samples, flags.p_abs, flags.backend, flags.prune, flags.heuristics)
