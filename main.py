"""Seed finder for Anno 1800.
Steps:
1) Baseline filtering:
     This brute forces all seeds (0 to 2147483647).
     By default it removes all seeds with river islands (on old world + cape + new world).
     The result is stored on disk in the seeds folder.
     If more than 100000 seeds are found, only the ones with the best scores are saved.
     
     When many unwanted islands are defined, runtime is roughly 2000 seconds on a single core
     (but it uses all cores available).
     When no unwanted islands are defined, runtime is roughly 4 times slower (8000 seconds).

2) Refinement:
     This does the same as baseline filtering, but only checks seeds that passed the baseline.
     So this may seem redundant.
     It is however useful for NPC/pirate configurations.
     They only have a small impact on scores (and no impact on river islands).
     So for riverless setups, a single baseline file should work very well for any NPC/pirate.


Baseline will NOT RUN if a suitable seed file already exists.
Things that are not checked:
    1) Unwanted islands
    2) NPCs
    3) Pirates
If you changed any of these and want to create a new baseline, you must go into the seeds folder
and delete/rename the current baseline file.


Both baseline filtering and refinement use the same scoring:
    The score is the sum of island scores across old world and cape and new world.
    The finder will then give back the highest scoring islands.
    You assign a score to each island based on personal preference
    and the output is the best scoring map.
    The default scoring is the number of buildable (nonharbor, noncoast) tiles.

By default, the finder uses the best seed from the refinement and directly draws the map.
You can adjust the plotcount variable to plot multiple seeds or none at all.

If you need to abort baseline filtering for some reason, press Ctrl+C.
If you just kill the window instead, you will need to kill all (invisible) child processes from the task manager.

For the visualizer:
    Because each half of the map is drawn independently, the same island may appear larger or smaller.
    Essentially each world (old world vs cape) is zoomed in depending on how large the world is,
    so that takes up exactly half of the screen.


Other tools:
    visualize.py can be run directly to show a seed of your choice.
    util.py can be run directly to give some stats on how many small/medium/large islands there are on various templates.
"""
import os
import numpy as np
import pandas as pd
import multiprocessing as mp
from queue import Empty
from ctypes import *
from visualize import Plot
import matplotlib.pyplot as plt
from util import Load, BinarizeWorld, BinarizeIslands, CountDraws, Slot, World
from time import time


# General map settings:
maptype     = "Corners"
mapsize     = "Large"
islandsize  = "Large"
difficulty  = "Normal"
gamemode    = "SandboxSingleplayer"
dlc12       = True  # Is DLC 12 active (True/False). If True, the new world is larger.

# These settings affect some small islands only.
oldworldnpcs   = 2    # Does not include Archibald and pirate.
oldworldpirate = 1    # 0 or 1.
newworldnpcs   = 1    # 0 or 1.
newworldpirate = 1    # 0 or 1.


# Define scores for each island.
# This is where you specify your personal island preference.
# The values below are the land tiles of each island.
# But that is only a rough guideline. Surely there are better values:
#   1) Harbor tiles (not included in the score) can vary quite a bit.
#   2) Squareness of the island and cliffs can influence the choice.
# Unspecified islands have a score of 0.
# So if we only care about the largest islands, we can comment out medium+small islands.
# This will find the best large islands, though medium islands may suffer.

# Old world / capes scores:
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

# New world scores:
scoresnew = {'L1':  26170, 'L2':  28281, 'L3':  28001,
             'L4':  28420, 'L5':  27257, 'L6':  20870,
             'L7':  20389, 'L8':  31806,
             'M1':  13560, 'M2':  12694, 'M3':  16118,
             'M4':  14733, 'M5':  15003, 'M6':  15158,
             'M7':  14959, 'M8':  15277, 'M9':  12880, 'M10': 14036,
             'S1':  1926,  'S2':  2194,  'S3':  2180,
             'S4':  3092,  'S5':  5052,  'S6':  7480,
             'S7':  3376,
             'L1R': 23144, 'L2R': 24662, 'L3R': 24602,
             'L4R': 24528, 'L5R': 23435, 'L6R': 18444,
             'L7R': 18728, 'L8R': 30591,
             'M1R': 11918, 'M2R': 11346, 'M3R': 13416,
             'M4R': 12323, 'M5R': 12815, 'M6R': 13418,
             'M7R': 11742, 'M8R': 14141, 'M9R': 12351, 'M10R': 12857}

# Depending on taste, the new world tiles may be worth less than the old world tiles.
# As an example, we multiply the new world scores by 0.2 to make them less important for the scoring.
scoresnew = {k:v*0.2 for k,v in scoresnew.items()}









# Old world islands exclusive to normal difficulty: M7 M8 M9 L1 L6 L7 L9 L10 L12 L13
# Old world islands exclusive to hard difficulty:   M2R M4R M6R L3R L8R L9R L10R L14R
# New world islands exclusive to normal difficulty: M2 M4 M7 M8 M10 L1 L3 L4 L6 L7
# New world islands exclusive to hard difficulty:   M2R M4R M7R M8R M10R L1R L3R L4R L6R L7R

# All islands found here may not appear in the respective world.
# If you do not care about rivers but only scores, you would use "" here.
unwanted    = "M1R M2R M3R M4R M5R M6R M7R M8R M9R CIR L1R L2R L3R L4R L5R L6R L7R L8R L9R L10R L11R L12R L13R L14R " # Old+cape
unwantednew = "M1R M2R M3R M4R M5R M6R M7R M8R M9R M10R L1R L2R L3R L4R L5R L6R L7R L8R"     # New world



# Various output settings:
writecount = 15  # Only print the ... best seeds.
plotcount = 1
# Usage:
#   plotcount = 0    =>  Do not visualize anything. 
#   plotcount = 3    =>  Visualize 3 seeds and show them directly.




##########
# The setttings below should probably be kept unchanged:

# Number of cores/threads to use for baseline filtering.
# If your CPU has NO hyperthreading, you can remove the //2 to speed things up.
N_CPU = mp.cpu_count()//2

NHITS = 100000  # The maximum number of baseline seeds saved in the seeds folder for this configuration.
# The baseline shall not have more than ~100k entries.
# If we exceed that value we increase the minscore until we go below.



# Range of seeds to test.
START = 0
END = 0x80000000



###########################
###########################
assert 0 <= oldworldnpcs   <= 2, "The number of NPCs in the old world must be one of: 0,1,2"
assert 0 <= newworldnpcs   <= 1, "The number of NPCs in the new world must be one of: 0,1"
assert 0 <= oldworldpirate <= 1, "The number of pirates in the old world must be one of: 0,1"
assert 0 <= newworldpirate <= 1, "The number of pirates in the new world must be one of: 0,1"
def f(s):
    return sorted(s.replace(",","").strip().upper().split())

unwanted = f(unwanted)
unwantednew = f(unwantednew)

pd.options.display.max_colwidth = 100
pd.options.display.width  = 0
pd.options.display.max_rows  = 100

oldworld, cape, newworlds, oldislands, newislands = Load(maptype, mapsize, islandsize, difficulty, gamemode, dlc12)

# Do NOT substitute these variables into where they are used.
# Or the garbage collector will delete their data before C even runs.
roldworld, rcape, rnewworlds = BinarizeWorld(oldworld), BinarizeWorld(cape), [BinarizeWorld(w) for w in newworlds]
rislands    = [BinarizeIslands(islands, unwanted, scores) for islands in oldislands]
rislandsnew = [BinarizeIslands(islands, unwantednew, scoresnew) for islands in newislands]




def IslandArgs(allislands):
    rv = []
    for islands in allislands:
        rv += [islands.ctypes.data, len(islands)]
    return rv

olddraws = CountDraws(oldworld, oldworldnpcs+1, oldworldpirate)
capedraws = CountDraws(cape, oldworldnpcs, oldworldpirate) 
newdraws = max(CountDraws(w, newworldnpcs, newworldpirate) for w in newworlds) + 1
maxdraws = max(olddraws, capedraws, newdraws)  # The same initial random numbers are shared across worlds.


# Push all the constant data into an easy to use argument.
fixedargs = [maxdraws, 
             oldworldnpcs, oldworldpirate, newworldnpcs, newworldpirate,
             *IslandArgs(rislands),
             *IslandArgs(rislandsnew),
             roldworld, rcape, *rnewworlds, 1 if gamemode=="CampaignMode" else 3]

absdir = os.path.split(__file__)[0]
dll = CDLL(absdir+"/src/findseed.dll")

dll.find.restype = c_int32
dll.find.argtypes = [c_uint32, c_uint32, c_uint32, c_void_p,  # Seed range to test, scores.
                     c_float, c_uint32, #  Minimum score. Draw counts.
                     c_uint32, c_uint32, c_uint32, c_uint32, # NPC, pirate count.
                     c_void_p, c_uint32, c_void_p, c_uint32, c_void_p, c_uint32,  # Old Islands.
                     c_void_p, c_uint32, c_void_p, c_uint32, c_void_p, c_uint32,  # New islands.
                     *[POINTER(World) for i in range(5)], c_uint32  # Worlds. Number of new worlds (3 or 1).
                     ]


def Job(start, end, stepsize, queue, minscore, fixedargs = fixedargs, find=dll.find):
    """Worker task for the baseline. Feed the queue with good seeds."""
    score = np.zeros(1, dtype=np.float32)
    p = score.ctypes.data
    
    while start < end:
        res = find(start, end, stepsize, p, minscore, *fixedargs)
        if res == -1:
            break
        queue.put((res,score[0]))
        start = res+stepsize
    queue.put((-1,0))  # This job is done. Inform the parent thread.


def Score(seed):
    """Get the score for an accepted seed."""
    score = np.zeros(1,dtype=np.float32)   
    seed = dll.find(seed, seed+1, 1, score.ctypes.data, -1e30, *fixedargs)
    return score[0]


def GetMinScore(scores, fraction):
    """Given scores of a fractional simulation, return the minscore needed
    to get roughly NHITS scores in a full simulation.
    Basically a percentile calculation."""

    # Do we even need to do anything or do we need all seeds we can get?
    expected = int(fraction*NHITS)
    if len(scores) <= expected:
        # At this rate we get less than NHITS in the full simulation.
        return -1e30  # We need all seeds. The unwanteds are hard to satisfy.
    else:
        # There are too many seeds.
        # Cut off the worst scores so that len(scores) == expected.
        # Sort scores and partition into scores[:-expected] (NOT WANTED) and scores[-expected:] (WANTED).
        return sorted(scores)[-expected]


if __name__ == "__main__":
    setting = f"{maptype}_{mapsize}_{islandsize}_{difficulty}_{gamemode}"
    baselinepath = f"seeds/{setting}.txt"

    try: os.mkdir("seeds")
    except FileExistsError: pass

    pirates = f"{oldworldnpcs} {oldworldpirate} {newworldnpcs} {newworldpirate}"
    signature = pirates + " / "+" ".join(unwanted)+" / "+" ".join(unwantednew)

    # If a baseline does not exist yet, create it.
    # Otherwise just use it, even if unwanteds/NPCs/pirates differ.
    if not os.path.exists(baselinepath):
        print("No baseline found. Creating baseline in",baselinepath)
        # Failure modes:
        #   1) Nothing is found. The worker jobs are never giving any feedback so even a progress bar is tricky.
        #      We can only inform the user and abort if that happens though.
        #   2) Too much is found. We want to restrict the baseline file to about 100k hits (depending on user setting).
        # => Make quick test runs with 0.01% workload and 1% workload and save all the scores.
        #    If the first run already has many seeds, use that for the minscore.
        #    Otherwise do the 1% run.
        #    If no scores are found, inform the user that the run is pointless and abort.
        #    If more than NHITS//100 are found, find the right percentile so that NHITS//100 are found.
        queue = mp.Queue()

        def QuickRun(end=END//10000):
            """0.01% workload (214748 seeds) or 1% workload run to make sure that are not getting swamped with seeds.
            These runs will find a suitable minscore needed for the full run."""
            ps = []
            for tid in range(N_CPU):
                p = mp.Process(target=Job, args=(START+tid, end, N_CPU, queue, -1e30))  ####
                p.start()
                ps.append(p)
            workers = N_CPU
            scores = []
            try:
                while workers:
                    try: seed,score = queue.get(timeout=1)  # This ensures that keyboard interrupts take just a second.
                    except Empty: continue
                    if seed==-1: workers-=1
                    else: scores.append(score)
            except: raise
            finally:  # Either successful finish or interrupted.
                for p in ps:
                    p.terminate()
            return scores

        print("Trying a 0.01% workload run to check the number of seeds.")
        scores = QuickRun(end=END//10000)
        if len(scores) > END//10000//10:
            # More than 10% seeds have been accepted. From these over 20k seeds, calculate the minscore.
            minscore = GetMinScore(scores, 1/10000)
            print("Setting minscore to:",minscore)
        else:
            # Less than 10% of seeds have been found. We can afford a 1% run to get an excellent estimate of minscore.
            print("Trying a 1% workload run to get a good minscore.")
            scores = QuickRun(end=END//100)
            if not scores:
                print("Not a single seed has been accepted in 1% of all seeds.")
                print("It is likely that no seed satisfies your unwanted lists.")
                print("You should abort by pressing ctrl+c and putting fewer items in unwanted.")
                print("If you do want to check the full range anyway, you do not need to do anything.")
                print("Please beware that the progress bar will appear stuck at 0% until the code is done.")
            minscore = GetMinScore(scores, 1/100)
            print("Setting minscore to:",minscore)


        # Full run:
        print("Full run:")
        ps = []
        for tid in range(N_CPU):
            p = mp.Process(target=Job, args=(START+tid, END, N_CPU, queue, minscore))
            p.start()
            ps.append(p)

        workers = N_CPU
        seeds = []
        size = END-START

        t00 = t0 = time()
        try:
            counter = seed = 0
            while workers:
                try:
                    seed,score = queue.get(timeout=1)  # This ensures that keyboard interrupts take just a second.
                except Empty:
                    continue
                finally:
                    tt = time()
                    if tt > t0 + 2:
                        # Show the general progress few seconds or so; also get an estimate of the total number of seeds.
                        prog = (seed if seed!=-1 else size)/size
                        estimate = counter/prog if prog else 0
                        print(f"{prog:6.1%}  Estimated number of seeds: {estimate:,.0f}")
                        t0 = tt
                
                if seed==-1:  # This worker has finished its entire range.
                    workers-=1
                else:
                    seeds.append((seed,score))
                    counter += 1
        except:
            raise
        finally:
            # Either successful finish or interrupted.
            for p in ps:
                p.terminate()
        # Success. Sort the numbers and save to file.
        with open(baselinepath,"w") as f:
            f.write(signature+"\n")
            for seed,score in sorted(seeds,key=lambda x:-x[1]):
                f.write(str(seed)+"\n")
        print(f"Baseline created in {time()-t00:g} seconds.\n\n\n")




##    print(f"Refinements, unwanted {unwanted}, unwantednew {unwantednew}, pirates {pirates}")
    
    # Refine on one core.
    seeds = []
    score = np.zeros(1,dtype=np.float32)

    for i,seed in enumerate(open(baselinepath)):
        if not i: continue
        seed = int(seed)
        seed = dll.find(seed, seed+1, 1, score.ctypes.data, -1e30, *fixedargs)
        if seed!=-1:
            seeds.append((seed,score[0]))

    print("Number of seeds:",len(seeds))
    seeds.sort(key=lambda x:-x[1])
    print(f"{'Seed:':>11} score")
    for seed,score in seeds[:writecount]:
        print(f"{seed:10}: {score:g}")
    seeds = [seed[0] for seed in seeds]

    if plotcount > 0:
        for seed in seeds[:plotcount]:
            Plot(seed, oldworld, cape, newworlds, oldislands, newislands, oldworldnpcs, oldworldpirate, newworldnpcs, newworldpirate)            
            plt.show()

    
            




















