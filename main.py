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
     Main focus is a scoring of the maps.
     We define a score for each island and get the best seeds that match our requirement.

Both steps offer these filter settings:
    1) Unwanted islands. These may not appear.
    2) Wanted islands, old world. All of these islands must appear.
    3) Wanted islands, cape. All of these must appear too.

However, refinement does not filter anything by default.
Instead, it works by sorting the resulting seeds by score:
    The score is the sum of island scores across old world and cape.
    The finder will then give back the highest scoring islands.
    You assign a score to each island based on personal preference
    and the output is the best scoring map.
    (Scoring is much slower than using filters, but should still take just a second.)

Baseline is basically preprocessing and only happens once.
Refinement is where you repeatedly change your requirements until you have just a handful of excellent seeds left.

By default, the finder uses the best seed from the refinement and directly draws the map.
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
gamemode    = "SandboxSingleplayer"


# These settings affect some small islands only.
oldworldnpcs   = 2    # Does not include Archibald and pirate.
oldworldpirate = 1    # 0 or 1.


# Define scores for refinement for each island.
# This is where you specify your personal island preference.
# The values below are the land tiles of each island.
# But that is only a rough guideline. Surely there are better values:
#   1) Harbor tiles can vary quite a bit (check the islandtiles folder).
#   2) Squareness of the island and cliffs can influence the choice.
# Unspecified islands have a score of 0.
# So if we only care about the largest islands, we can comment out the rest.
# This will find the best large islands, though medium islands may suffer.

scores = {'L1':  29977, 'L2':  27159, 'L3':  26100,
          'L4':  30583, 'L5':  28267, 'L6':  30004,
          'L7':  29693, 'L8':  28213, 'L9':  26862,
          'L10': 29964, 'L11': 29178, 'L12': 29572,
          'L13': 29658, 'L14': 28431, 'CI':  27959, 
          'M1':  11268, 'M2':  13784, 'M3':  15340,
          'M4':  15972, 'M5':  15992, 'M6':  15761,
          'M7':  14788, 'M8':  15270, 'M9':  12611,
          'S1':  2066,  'S2':  2663,  'S3':  3741,
          'S4':  2579,  'S5':  3539,  'S6':  3035,
          'S7':  2056,  'S8':  1573,  'S9':  2422,
          'S10': 3392,  'S11': 1747,  'S12': 3495,
          
          'L1R': 28494, 'L2R': 26000, 'L3R': 24804,
          'L4R': 29521, 'L5R': 27359, 'L6R': 28986,
          'L7R': 28055, 'L8R': 26468, 'L9R': 24664,
          'L10R':25970, 'L11R':27791, 'L12R':28232,
          'L13R':27666, 'L14R':25753, 'CIR': 26390, 
          'M1R': 10563, 'M2R': 12827, 'M3R': 14430,
          'M4R': 15184, 'M5R': 15570, 'M6R': 14952,
          'M7R': 13858, 'M8R': 14268, 'M9R': 11743,
          }



# Islands that appear only on normal difficulty: M7 M8 M9 L1 L6 L7 L9 L10 L12 L13
# Islands that appear only on hard difficulty: M2R M4R M6R L3R L8R L9R L10R L14R




# Filtering is probably not needed for refinement.
unwanted = ""
wantedold = ""
wantedcape = ""





# Various output settings:
writecount = 15  # Only print the first ... seeds.
plotcount = 1
# Usage:
#   plotcount = 0    =>  Do not visualize anything. 
#   plotcount = 3    =>  Visualize 3 seeds and show them directly.
#   plotcount = -10  =>  Visualize 10 seeds and save them only.




# These settings work best for the largest maps on Large Large Normal; Corners, Atoll, Arc, Archipelago.
# (Though Archipelago is not recommended because it has 1 small island less than the others.)
# Try to keep the seeds below 100k (100,000).
# It is possible to define a required score for baseline filtering and ignore the other settings,
# but relying exclusively on that is ~4 times slower than defining unwanted islands.
unwantedbaseline = "M1R M2R M3R M4R M5R M6R M7R M8R M9R CIR L1R L2R L3R L4R L5R L6R L7R L8R L9R L10R L11R L12R L13R L14R "
wantedbaselineold = ""
wantedbaselinecape = ""
minscorebaseline = -1e30  # Baseline must have this score at least. Leave this at -1e30 to not filter by score.



if (maptype, mapsize, islandsize, difficulty) == ("Atoll", "Large", "Small","Hard"):
    minscorebaseline = 347000  # Outdated value before coast tiles were removed.
    unwantedbaseline = ""

# Snowflake needs some finetuning already to keep the seeds down.
if (maptype, mapsize, islandsize, difficulty) == ("Snowflake", "Large", "Large","Normal"):
    wantedbaselineold += "L1 L6"
    unwantedbaseline  += "CI L8"

# Smaller maps will be even worse.


# Campaign:
if gamemode == "CampaignMode":
    unwantedbaseline += " L3 L5 M1"





minscore = -1e30  # No filtering needed for refinement because we sort anyway.
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


pd.options.display.max_colwidth = 100
pd.options.display.width  = 0
pd.options.display.max_rows  = 100


oldworld, cape, allislands = Load(maptype, mapsize, islandsize, difficulty, gamemode)



# Do NOT substitute these variables into where they are used.
# Or the garbage collector will delete their data before C even runs.
roldworld, rcape = BinarizeWorld(oldworld), BinarizeWorld(cape)
rislandsbaseline = [BinarizeIslands(islands, unwantedbaseline, scores) for islands in allislands]
rislands = [BinarizeIslands(islands, unwanted, scores) for islands in allislands]
rwanted,rwantedcape = BinarizeWanted(allislands, wantedold), BinarizeWanted(allislands, wantedcape)
rwantedbaseline, rwantedcapebaseline = BinarizeWanted(allislands, wantedbaselineold), BinarizeWanted(allislands, wantedbaselinecape)


def IslandArgs(allislands):
    rv = []
    for islands in allislands:
        rv += [islands.ctypes.data, len(islands)]
    return rv
def WorldArgs(world, offsets):
    assert len(offsets)==4, "There should be one offset for starter,npc,pirate,end section."
    return world.ctypes.data, *offsets
def WantedArgs(wanted):
    return wanted.ctypes.data, len(wanted)


olddraws = CountDraws(oldworld, oldworldnpcs+1, oldworldpirate)
capedraws = CountDraws(cape, oldworldnpcs, oldworldpirate) 


# Push all the constant data into an easy to use argument.
fixedargsbaseline = [olddraws, capedraws, minscorebaseline,
                     oldworldnpcs, oldworldpirate, 
                     *IslandArgs(rislandsbaseline),
                     *WorldArgs(*roldworld),
                     *WorldArgs(*rcape),
                     *WantedArgs(rwantedbaseline), *WantedArgs(rwantedcapebaseline),
                     ]

fixedargs = [olddraws, capedraws, minscore,
             oldworldnpcs, oldworldpirate, 
             *IslandArgs(rislands),
             *WorldArgs(*roldworld),
             *WorldArgs(*rcape),
             *WantedArgs(rwanted), *WantedArgs(rwantedcape),
             ]


absdir = os.path.split(__file__)[0]
dll = CDLL(absdir+"/src/findseed.dll")

dll.find.restype = c_int32
dll.find.argtypes = [c_uint32, c_uint32, c_uint32, c_void_p,  # Seed to test, scores.
                     c_uint32, c_uint32, c_float, # Draw counts. Minimum score.
                     c_uint32, c_uint32,  # NPC, pirate count.
                     c_void_p, c_uint32, c_void_p, c_uint32, c_void_p, c_uint32,  # Islands.
                     c_void_p, c_uint32, c_uint32, c_uint32, c_uint32,  # Old world.
                     c_void_p, c_uint32, c_uint32, c_uint32, c_uint32,  # Cape world.
                     c_void_p, c_uint32, c_void_p, c_uint32,  # Wanted.
                     ]


def Job(start, end, stepsize, queue, fixedargs = fixedargsbaseline, find=dll.find):
    """Worker task for the baseline. Feed the queue with good seeds."""
    # Decide whether we want scoring or not. If threshold is -1e30 or smaller, we ignore the scoring.
    if minscorebaseline > -1e30:
        score = np.zeros(1,dtype=np.float32)
        p = score.ctypes.data
    else:
        p = c_void_p(0)
    
    while start < end:
        res = find(start, end, stepsize, p, *fixedargs)
        queue.put(res)
        if res == -1:
            break
        start = res+stepsize

def Score(seed):
    """Get the score for an accepted seed."""
    score = np.zeros(1,dtype=np.float32)
    seed = dll.find(seed, seed+1, 1, score.ctypes.data, *fixedargs)
    return score[0]


if __name__ == "__main__":
    setting = f"{maptype}_{mapsize}_{islandsize}_{difficulty}_{gamemode}"
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
                    counter += 1
                    if not counter % 100:
                        # Show the general progress but also get an estimate of the total number of seeds.
                        prog = seed/size
                        estimate = counter/prog
                        print(f"{prog:6.1%}  Estimated number of seeds: {estimate:,.0f}")
        except:
            raise
        finally:
            # Either successful finish or interrupted.
            for p in ps:
                p.terminate()
        # Success. Sort the numbers and save to file.
        with open(baselinepath,"w") as f:
            f.write(" ".join(unwantedbaseline)+" ; "+" ".join(wantedbaselineold)+" ; "+" ".join(wantedbaselinecape)+"\n")
            for seed in sorted(seeds):
                f.write(str(seed)+"\n")
        print("Baseline created.\n\n\n")

    print(f"Refinements, unwanted {unwanted}, wantedold {wantedold}, wantedcape {wantedcape}")
    
    # Refine on one core in Python.
    seeds = []
    score = np.zeros(1,dtype=np.float32)

    for i,seed in enumerate(open(baselinepath)):
        if not i: continue
        seed = int(seed)
        seed = dll.find(seed, seed+1, 1, score.ctypes.data, *fixedargs)
        if seed!=-1:
            seeds.append((seed,score[0]))

    print("Number of seeds:",len(seeds))
    seeds.sort(key=lambda x:-x[1])
    print(f"{'Seed:':>11} score")
    for seed,score in seeds[:writecount]:
        print(f"{seed:10}: {score:g}")
    seeds = [seed[0] for seed in seeds]
    
    if plotcount>0:
        for i,seed in enumerate(seeds):
            if i==plotcount: break
            Plot(seed, oldworld, cape, allislands, oldworldnpcs, oldworldpirate)
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
            
        
            




















