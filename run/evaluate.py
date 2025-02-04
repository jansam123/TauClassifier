"""
Evaluate.py
___________________________________________________________________
Compute predictions using a weights file
Writes out y_pred array for each NTuple into a .npz
"""

import ray
import numpy as np
import sys
from config.config import get_cuts, config_dict
from scripts.utils import logger
from config.variables import variable_handler
from config.files import gammatautau_files, jz_files, testing_files, ntuple_dir, all_files
from scripts.DataLoader import DataLoader
from scripts.preprocessing import Reweighter
import glob
from ray.util import inspect_serializability


def split_list(alist, wanted_parts=1):
    """
    Splits a list into list of smaller lists
    :param alist: A list to split up
    :param wanted_parts: Number of parts to split alist into
    :returns: A split up list
    """
    length = len(alist)
    return [alist[i * length // wanted_parts: (i + 1) * length // wanted_parts]
			for i in range(wanted_parts)]

def evaluate(args):
    """
    Evaluates the network output for each NTuple and writes them to an npz file
    :param args: An argparse.Namespace object. Args that must be parsed:
                 -weights: A path to the network weights to evaluate
                 -ncores: Number of files to process in parallel
    """
    # Initialize Ray
    # ray.init()

    # Load model
    model_config = config_dict
    model_weights = args.weights
    reweighter = Reweighter(ntuple_dir, prong=args.prong)
    assert model_weights != "", logger.log("\nYou must specify a path to the model weights", 'ERROR')

    # Get files
    files = glob.glob("../NTuples/*/*.root")
    nbatches = 250
    
    # Split files into groups to speed things up, will process args.ncores files in parallel
    if args.ncores > len(files):
        args.ncores = len(files)
    if args.ncores < 0:
        args.ncores = 1
    files = split_list(files, len(files)//args.ncores)   
    
    # Make DataLoaders
    for file_chunk in files:
        dataloaders = []
        for file in file_chunk:
                flabel = "JZ1" 
                if "26443658" in file:
                    flabel = "Gammatautau"
                dl = DataLoader(file, [file], 1, nbatches, variable_handler, cuts=get_cuts(args.prong)[flabel], 
                                    reweighter=reweighter, no_gpu=True)
                dataloaders.append(dl)
                # inspect_serializability(dl)
        # Save predictions for each file in parallel
        
        for dl in dataloaders:
            dl.update_ntuples(args.model, model_config, model_weights)
        # [dl.update_ntuples(args.model, model_config, model_weights) for dl in dataloaders]
        # # ray.get([dl.predict(args.model, model_config, model_weights) for dl in dataloaders])
        # for dl in dataloaders:
        #     ray.kill(dl)