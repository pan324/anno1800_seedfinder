"""Seed finder for Anno 1800.
Steps:
1) Baseline filtering:
     This brute forces all seeds (0 to 2147483647).
     Main focus is on the removal of unwanted islands.
     By default it removes all seeds with river islands (on old world + cape).
     The result is stored on disk in the seeds folder.
     Runtime is roughly 2000 seconds on a single core (but it uses all cores available).
2) Refinement:
     This only checks seeds that passed the baseline.
     Main focus is the selection of wanted islands.

Both steps essentially do the same under the hood and offer these filter settings:
    1) Unwanted islands. These may not appear.
    2) Wanted islands, old world. All of these islands must appear.
    3) Wanted islands, cape. All of these must appear too.


Baseline is basically preprocessing and only happens once.
Refinement is where you repeatedly change your requirements until you have just a handful of excellent seeds left.

By default, the finder uses the first seed from the refinement and directly draws the map.
You can adjust the plotcount variable to show multiple seeds, and to either show them directly or to save to disk.


If you need to abort baseline filtering for some reason, press Ctrl+C.
If you just kill the window instead, you will need to kill all (invisible) child processes from the task manager.

The baseline filtering can cause very large files when map and islands are small.
That is because it is far easier to get no rivers when a map has only few islands and many of them are small.
It is necessary to adjust the baseline to exclude more islands in such cases.

For the visualizer:
    Because each half of the map is drawn independently, the same island may appear larger or smaller.
    Essentially each world (old world vs cape) is zoomed in depending on how large the world is,
    so that takes up exactly half of the screen.
"""
import os
import numpy as np
import pandas as pd
import multiprocessing as mp
from queue import Empty
from ctypes import *
from visualize import Plot
import matplotlib.pyplot as plt
from util import Load, BinarizeWorld, BinarizeIslands, BinarizeWanted, CountDraws



# General map settings:
maptype     = "Corners"
mapsize     = "Large"
islandsize  = "Large"
difficulty  = "Normal"


# Refinement settings:
# Islands that appear only on normal difficulty: M7 M8 M9 L1 L6 L7 L9 L10 L12 L13
# Islands that appear only on hard difficulty: M2R M4R M6R L3R L8R L9R L10R L14R
# The islands that appear only on normal are really nice. We want them.
# L14 is also pretty nice, though if we include everything we end up with no seeds at all.

unwanted = "L2 L3 CI L8 L4 L5"
wantedold = "M7 M8 M9 L1 L6 L7 L9 L10 L12 L13"
wantedcape = "L1 L13"









# Various output settings:
writecount = 15  # Only print the first ... seeds.
plotcount = 1
# Usage:
#   plotcount = 0    =>  Do not visualize anything. 
#   plotcount = 3    =>  Visualize 3 seeds and show them directly.
#   plotcount = -10  =>  Visualize 10 seeds and save them only.



# Not used for baseline or refinement. Only for the visualizer:
oldworldnpcs   = 2    # Does not include Archibald and pirate.
oldworldpirate = 1    # 0 or 1.





# Finder limitations:
#    Small island settings might not always work.
#    (Because some small islands are placed after NPCs,
#    and the NPC part is only implemented by the visualizer, not the finder.)
#
# Visualizer limitations:
#    The game slightly moves islands around from their original position.
#    And it occasionally rotates them.





# These settings work best for the largest maps on Large Large Normal; Corners, Atoll, Arc, Archipelago.
# (Though Archipelago is not recommended because it has 1 small island less than the others.)
# Try to keep the seeds below 100k (100,000). 
unwantedbaseline = "M1R M2R M3R M4R M5R M6R M7R M8R M9R CIR L1R L2R L3R L4R L5R L6R L7R L8R L9R L10R L11R L12R L13R L14R "
wantedbaselineold = ""
wantedbaselinecape = ""

### Snowflake Large Large Normal needs some finetuning already to keep the seeds down.
##wantedbaselineold += "L1 L6"
##unwantedbaseline  += "CI L8"

# Smaller maps will be even worse.





##########
# The setttings below should probably be kept unchanged:

# Number of cores/threads to use for baseline filtering.
# If your CPU has NO hyperthreading, you can remove the //2 to speed things up.
N_CPU = mp.cpu_count()//2

# Range of seeds to test.
START = 0
END = 0x80000000




###########################
###########################
assert 0 <= oldworldnpcs <= 2, "The number of NPCs in the old world must be one of: 0,1,2"
assert 0 <= oldworldpirate <= 1, "The number of pirates in the old world must be one of: 0,1"
def f(s):
    return s.replace(",","").strip().upper().split()
unwanted = f(unwanted)
wantedold = f(wantedold)
wantedcape = f(wantedcape)
unwantedbaseline = f(unwantedbaseline)
wantedbaselineold = f(wantedbaselineold)
wantedbaselinecape = f(wantedbaselinecape)




for data in [unwanted, wantedold, wantedcape, unwantedbaseline, wantedbaselineold, wantedbaselinecape]:
    data[:] = [s.upper() for s in data]



pd.options.display.max_colwidth = 100
pd.options.display.width  = 0
pd.options.display.max_rows  = 100


oldworld, cape, allislands = Load(maptype, mapsize, islandsize, difficulty)


# Do NOT substitute these variables into where they are used.
# Or the garbage collector will delete their data before C even runs.
roldworld, rcape = BinarizeWorld(oldworld), BinarizeWorld(cape)
rislandsbaseline = [BinarizeIslands(islands, unwantedbaseline) for islands in allislands]
rislands = [BinarizeIslands(islands, unwanted) for islands in allislands]
rwanted,rwantedcape = BinarizeWanted(allislands, wantedold), BinarizeWanted(allislands, wantedcape)
rwantedbaseline, rwantedcapebaseline = BinarizeWanted(allislands, wantedbaselineold), BinarizeWanted(allislands, wantedbaselinecape)


def IslandArgs(allislands):
    rv = []
    for islands in allislands:
        rv += [islands.ctypes.data, len(islands)]
    return rv
def WorldArgs(world, normlen):
    return world.ctypes.data, normlen, len(world)
def WantedArgs(wanted):
    return wanted.ctypes.data, len(wanted)

# Push all the constant data into an easy to use argument.
fixedargsbaseline = [CountDraws(oldworld), CountDraws(cape),
                     *IslandArgs(rislandsbaseline),
                     *WorldArgs(*roldworld), *WorldArgs(*rcape),
                     *WantedArgs(rwantedbaseline), *WantedArgs(rwantedcapebaseline)
                     ]

fixedargs = [CountDraws(oldworld), CountDraws(cape),
             *IslandArgs(rislands),
             *WorldArgs(*roldworld), *WorldArgs(*rcape),
             *WantedArgs(rwanted), *WantedArgs(rwantedcape)]





absdir = os.path.split(__file__)[0]
dll = CDLL(absdir+"/src/findseed.dll")

dll.find.restype = c_int32
dll.find.argtypes = [c_uint32, c_uint32, c_uint32, c_uint32, c_uint32,
                     c_void_p, c_uint32, c_void_p, c_uint32, c_void_p, c_uint32,
                     c_void_p, c_uint32, c_uint32, c_void_p, c_uint32, c_uint32,
                     c_void_p, c_uint32, c_void_p, c_uint32
                     ]


def Job(start, end, stepsize, queue, fixedargs = fixedargsbaseline, find=dll.find):
    """Worker task for the baseline. Feed the queue with good seeds."""
    while start < end:
        res = find(start, end, stepsize, *fixedargs)
        queue.put(res)
        if res == -1:
            break
        start = res+stepsize






if __name__ == "__main__":
    setting = f"{maptype}_{mapsize}_{islandsize}_{difficulty}"
    baselinepath = f"seeds/{setting}.txt"

    try: os.mkdir("seeds")
    except FileExistsError: pass


    # If a baseline does not exist yet, create it.
    # Otherwise just use it, even if the current unwantedbaseline does not match the settings of the file.
    # This makes it easy to create a preset for each map type once and then ignore the unwantedbaseline completely.
    if not os.path.exists(baselinepath):
        print("No baseline found. Creating baseline in",baselinepath)
        # Baseline first, then refine.
        queue = mp.Queue()
        ps = []

        for tid in range(N_CPU):
            p = mp.Process(target=Job, args=(START+tid, END, N_CPU, queue))
            p.start()
            ps.append(p)

        workers = N_CPU
        seeds = []
        size = END-START
        try:
            counter = 0
            while workers:
                try:
                    seed = queue.get(timeout=1)  # This ensures that keyboard interrupts take just a second.
                except Empty:
                    continue
                
                if seed==-1:
                    workers-=1
                else:
                    seeds.append(seed)
                    if not counter % 100:
                        # Show the general progress but also get an estimate of the total number of seeds.
                        prog = seed/size
                        estimate = counter/prog
                        print(f"{prog:6.1%}  Estimated number of seeds: {estimate:,.0f}")
                    counter += 1
        except:
            raise
        finally:
            # Either successful finish or interrupted.
            for p in ps:
                p.terminate()
        # Success. Sort the numbers and save to file.
        with open(baselinepath,"w") as f:
            f.write(" ".join(unwantedbaseline)+" ; "+" ".join(unwantedbaseline)+" ; "+" ".join(unwantedbaseline)+"\n")
            for seed in sorted(seeds):
                f.write(str(seed)+"\n")
        print("Baseline created.\n\n\n")



    print(f"Refinements, unwanted {unwanted}, wantedold {wantedold}, wantedcape {wantedcape}")
    # Refine on one core in Python.
    seeds = []
    for i,seed in enumerate(open(baselinepath)):
        if not i: continue
        seed = int(seed)
        seed = dll.find(seed, seed+1, 1, *fixedargs)
        if seed!=-1:
            seeds.append(seed)

    print("Number of seeds:",len(seeds))
    print("First seeds:")
    for seed in seeds[:writecount]:
        print(seed)


    
    if plotcount>0:
        for i,seed in enumerate(seeds):
            if i==plotcount: break
            Plot(seeds[0], oldworld, cape, allislands, oldworldnpcs, oldworldpirate)
            plt.show()

    elif plotcount<0:
        plotcount *= -1
        print(f"Storing {min(plotcount,len(seeds))} results in folder (removing all previous):",setting)
        try: os.mkdir(setting)
        except FileExistsError:
            for name in os.listdir(setting):
                os.remove(setting+"/"+name)
        for i,seed in enumerate(seeds):
            if i==plotcount: break
            Plot(seed, oldworld, cape, allislands, oldworldnpcs, oldworldpirate)
            plt.savefig(f"{setting}/{seed}.png")
            plt.close()
            
        
            




















