import pandas as pd
import numpy as np
import sys,os
from ctypes import *
from copy import copy,deepcopy

MAPTYPES = ["Archipelago", "Atoll", "Corners", "Arc", "Snowflake"]
SIZES = ["Small","Medium","Large"]



# Define bitmasks to extract a single bit from the island.
# E.g. island.diff==1: Compatible with normal only.
#      island.diff==2: Compatible with hard only.
#      island.diff==3: Compatible with both.
DIFFS = {"Normal": 1,
         "Hard":   2}
REGIONS = {"-":        1, 
           "Moderate": 2,
           "Colony01": 4,
           "Arctic":   8,
           "Africa":  16}
GAMEMODES = {"SandboxSingleplayer": 1,
             "SandboxMultilayer": 2,
             "CampaignMode": 4}
ISLAND_TYPE = {"Normal": 1,
               "Starter": 2,
               "Decoration": 4,
               "ThirdParty": 8,
               "PirateIsland": 16}



OTHER_PATHS = {"cape":      ["maps/moderate_c_01.csv"],
               "arctic":    ["maps/colony_03_sp.csv"],
               "enbesa":    ["maps/colony02_01.csv"],
               "enbesa_mp": ["maps/colony02_01_mp.csv"],
               "newworld":  [f"maps/colony01_l_0{i}.csv" for i in range(1,4)]}


def LoadNewWorld(mapsize, islandsize, difficulty, gamemode):
    templates = pd.read_csv("templates/templates.csv")
    templates.fillna("", inplace=True)  # Turn blank strings to "" instead of nan floats.
    region = "Colony01"
    iscampaign = gamemode == "CampaignMode"
    templates = templates[templates.IslandSize.apply(lambda x: islandsize in x.split(";")) &
                          templates.TemplateSize.apply(lambda x: mapsize in x.split(";")) &
                          templates.TemplateRegion.apply(lambda x: region in x.split(";")) &
                          templates.IsUsedByMapGenerator &
                          (templates.Campaign == iscampaign)
                          ]
    paths = ["maps/"+path.split("/")[-2]+".csv" for path in templates.TemplateFilename]
    worlds = [pd.read_csv(path) for path in paths]
        
    return worlds, LoadIslands(region, difficulty, gamemode)
    
    



def Load(maptype, mapsize, islandsize, difficulty, gamemode):
    """Load oldworld, cape and all relevant islands."""
    assert maptype in MAPTYPES, f"Maptype must be one of {MAPTYPES}"
    assert mapsize in SIZES, f"Mapsize must be one of: {SIZES}"
    assert islandsize in SIZES, f"Islandsize must be one of: {SIZES}"
    assert difficulty in DIFFS, f"Difficulty must be one of: {list(DIFFS.keys())}"
    assert gamemode in GAMEMODES, f"Gamemode must be one of: {list(GAMEMODES.keys())}"

    iscampaign = gamemode == "CampaignMode"

    templates = pd.read_csv("templates/templates.csv")
    templates.fillna("", inplace=True)  # Turn blank strings to "" instead of nan floats.
    
    templates = templates[templates.IslandSize.apply(lambda x: islandsize in x.split(";")) &
                          templates.TemplateSize.apply(lambda x: mapsize in x.split(";")) &
                          templates.TemplateMapType.apply(lambda x: maptype in x.split(";")) &
                          templates.IsUsedByMapGenerator &
                          (templates.Campaign == iscampaign)
                          ]
    
    oldpaths = ["maps/"+path.split("/")[-2]+".csv" for path in templates.TemplateFilename]

    assert not len(oldpaths)>1, "The code cannot handle multiple templates."
    assert not len(oldpaths)<1, "No matching template found."
    oldworld = pd.read_csv(oldpaths[0])
    cape = pd.read_csv("maps/moderate_continental_01.csv")

    return oldworld, cape, LoadIslands("Moderate", difficulty, gamemode)


def LoadIslands(region, difficulty, gamemode):
    small = pd.read_csv("islands/small.csv")
    medium = pd.read_csv("islands/medium.csv")
    large = pd.read_csv("islands/large.csv")
    allislands = [small, medium, large]
    # Select the relevant islands only.
    # Turn the short name into the index and make sure it is unique.
    for islands in allislands:
        islands.drop(islands.index[~(islands.region & REGIONS[region]).astype(bool)],inplace=True)
        islands.drop(islands.index[~(islands["diff"] & DIFFS[difficulty]).astype(bool)],inplace=True)
        islands.drop(islands.index[~(islands.gamemode & GAMEMODES[gamemode]).astype(bool)],inplace=True)
        islands.set_index("shortname",inplace=True)
        assert islands.index.nunique() == len(islands), "Short name is not unique."
    return allislands

        



###
# Pure Python map creation.

def Shuffle(df, mt):
    """Return a dataframe copy with its rows shuffled."""
    ids = list(df.index)
    mt.Shuffle(ids)
    return df.loc[ids]

def ChooseIslandsForSlots(slots, mt, world, allislands):
    """For each slot, pick a compatible island."""
    chosen = []
    for i,slot in slots.iterrows():
        # NPC slots (id 3) and pirate slots (id 4) are treated like normal (id 0) island slots here.
        # Has no effect on the normal/starter island call of this function because those have id 0 and 1.
        slotid = slot.id
        if 3<=slotid<=4: slotid = 0
        slotid = 1<<slotid

        
        islands = allislands[slot.sz]
        candidates = []
        for j,island in islands.iterrows():
            if island.id & slotid:
                candidates.append(island)
        assert candidates, "Pool of islands is empty. Does this ever happen?"

        num = mt.Randint(len(candidates))
        island = candidates[num]

        slot.name = island.name
        slot["rotation"] = mt.Randint(4)  # 90 degrees each.
        slot["path"] = island.path

        chosen.append(slot)

        islands.drop(island.name, inplace=True)
        # If there is a river variant, we need to remove it as well.
        if slot.sz>0:
            try:
                if island.name.endswith("R"):
                    islands.drop(island.name[:-1], inplace=True)
                else:
                    islands.drop(island.name+"R", inplace=True)
            except KeyError:
                pass
    return pd.DataFrame(chosen)


def Map(seed, world, allislands, npccount, piratecount, hasblake = True, verbose=False):
    """Return a dataframe with all islands placed.

    Placement order:
        1) Normal/Starter islands: slotid == 1, as well as (slotid==0 and slottype==1)
        2) Pirate/NPCs: slotid == 4, as well as slotid==3.
    Not implemented:
        3) Unknown function.
        4) Decoration (tiny) islands. ~17000 RNG draws. (1+2 take <100 draws.)
        5) Fertility
        6) Mineslots
    """
    allislands = deepcopy(allislands)
    
    mt = MT(seed)
    # If we have multiple worlds to choose from, pick one.
    if type(world) is list:
        world = world[mt.Randint(len(world))]
    
    slots = world
    if verbose: print(f"{mt.mti():04x} Selected template.")

    # Starter island slots (id 1) are shuffled.
    # Then concatenate them with normal island slots (id 0 and type 1).
    # The result is shuffled once more and then sorted so that high ids come first.
    starters = Shuffle(slots[slots.id==1], mt)
    normals = slots[(slots.id==0) & slots.type==1]
    both = pd.concat([normals, starters])
    
    both = Shuffle(both, mt)
    both = both.sort_values("id", kind="stable", ascending=0)
    if verbose: print(f"{mt.mti():04x} Shuffled normal/starter. 0x{len(both):02x} slots.")

    # Pick most islands (small, medium, large) from that.
    chosen = ChooseIslandsForSlots(both, mt, world, allislands)
    if verbose: print(f"{mt.mti():04x} Selected normal/starter islands.")


    # Distribute NPCs/pirates onto the corresponding slots and fill the rest with small islands.
    def PlaceNPCs(slots, npcs, partyid):
        partyname = {4:"Pirate", 3:"NPC"}[partyid]
        mt.Shuffle(npcs)
        if partyid==3 and hasblake:
            # Archibald Blake always comes first.
            npcs.remove("02")
            npcs = ["02"] + npcs
        if verbose: print(f"""{mt.mti():04x} Shuffled {partyname}.""")
        if len(npcs) > len(slots):
            # Not enough slots available.
            # This only happens on Cape which has no such slots at all.
            return pd.DataFrame({"x":[],"y":[],"type":[],"id":[],"sz":[],"rotation":[]}), slots
        # Distribute and rotate.
        slots = Shuffle(slots, mt)
        taken = slots[:len(npcs)].copy()
        rest = slots[len(npcs):]
        taken["rotation"]  = [mt.Randint(4) for npc in npcs]
        taken.index        = [f"{partyname}_{npc}" for npc in npcs]
        if verbose: print(f"""{mt.mti():04x} Placed {partyname}.""")
        return taken, rest
    
    pirateIds = list(range(piratecount))
    pirate, rest = PlaceNPCs(slots[slots.id==4], pirateIds, 4)

    npcIds = ["08","07"][:npccount]
    if hasblake:
        npcIds = ["02"] + npcIds
    npcslots = pd.concat([slots[slots.id==3], rest])
    npc, rest = PlaceNPCs(npcslots, npcIds, 3)
    
    # Shuffle the remaining islands again and choose small islands.
    rest = Shuffle(rest, mt)
    rest = rest.sort_values("id", kind="stable", ascending=0)
    if verbose: print(f"{mt.mti():04x} Shuffled rest islands.")

    rest = ChooseIslandsForSlots(rest, mt, world, allislands)
    if verbose: print(f"{mt.mti():04x} Selected rest islands. 0x{len(rest):02x} slots.\n")
    
    # Now we have placed all islands on the map.
    islands = pd.concat([chosen,rest]).sort_index()
    
    df = pd.concat([islands, pirate, npc])
    return df




# Prepare the C calls.
# The Mersenne Twister uses the seed to create a state out of 624 ints.
# Then when we first want a random number, it creates a forward buffer of another 624 ints.
# The random numbers that we actually need is far lower.
# The typical large map uses just 70 RNG draws, including NPCs and pirates.
# Without them, just 56 RNG draws.
# So a large part of the buffer is wasted.
# => Modify the RNG so that it only creates the needed buffer.
#
# We can reuse the RNG state across old world and cape, because they both start from the seed again.
# But realistically, there is no need.
# In the old world, we get one good hit for every 2**14 = 16384 trials.
# Saving the RNG cannot improve the performance by even 0.01%.
#
# Selecting "random" for the maptype expands the pool of available maps.
# Without "random", the game randomly draws from a pool of exactly on possible map.
# With "random", the pool contains all maps.
# The RNG does nothing when there is only one choice, so "random" introduces an additional RNG draw.
# This shifts everything. The overall number of trials we could pull off is 20% larger for each maptype.
# Around 2.5B instead of 2.1B.
# But the normal seed range already has nice results, so no need to implement that.
#
# Another consideration is to buffer the cape results.
# The cape is the same regardless of all settings except island difficulty.
# The odds are only 2**6 = 64 however, which still leaves many seeds for the main world.
# The buffer would take about 2**25 * 4 bytes = 134 MB which is not an issue.
#
# Some islands are better than others and we actually need to quantify this.
# If given the choice between one large island without river and another large island with river,
# the river island might be preferable. No good data on that however.
#
# For now, instead of a scoring, define filtering, where each island either is allowed or not.
# When an island is selected but not allowed, we stop and try the next seed.
#
#
# NPCs only affect small islands (and not even all of them) and are ignored.
# Many of the checks for the islands can be preprocessed:
#   Island region
#   Diff
#   Gamemode
# which leaves only the id.
#
#
# Overall code flow (when maptype is not "random"):
#   Preprocess everything in Python for the desired template:
#     Slot data is used only as follows.
#       1) Get everything with slot.id==1
#       2) Get everything with slot.id==0 & slot.type==1
#       3) Grab islands that match slot.sz.
#       4) Choose islands that match slot.id.
#     We can calculate 1) and 2) beforehand.
#     3 works because sizes are mutually exclusive.
#     Step 4 seems hard to optimize.
#     It would nice to go from islands[slot.sz] to islands[slot.sz][slot.id],
#     but then one of these lists would be a subset of the other.
#     And the bookkeeping would also be trouble.
#
#     Island data needs:
#       1) Id, which is either 1 (normal island) or 3 (normal+starter island).
#       2) Is it unwanted.
#          This might become a quality score later on instead of just banning stuff.
#       3) Something to communicate river/non-river pairs.
#          Keep a byte that is either 1 (partner is one to the right)
#          or -1 (partner is one to the left) or 0 (no partner).
#       4) Has it been picked yet.
#          Instead of moving all data in the array after an island has been picked,
#          we just flag it and then skip on all iterations afterwards.
#
#   Now call multiple jobs in C, covering different parts of the seed range.
#   Each job takes all the needed data as well as a seed start and seed end.
#   It then runs along that range and returns a seed as soon as it finds one.
#   Python can then print/save the seed and restart the job from the current position as needed.

def CountDraws(world, npcs, pirates):
    """Return the number of RNG draws for the world.
    This is needed to speed up the C code."""
    slots = world
    starters = slots[slots.id==1]
    normals = slots[(slots.id==0) & slots.type==1]
    npcslots = slots[slots.id==3]
    pirateslots = slots[slots.id==4]
    
    def shuffle(n):
        return max(0,n-1)
    
    # The first shuffle takes the starters only.
    # The second takes both.
    # Each shuffle draws one number fewer than there are items.
    draws = shuffle(len(starters))
    draws+= shuffle(len(starters)+len(normals))

    # Now place the islands around the map.
    # Each slot draws two randints, one for island and one for rotation.
    draws += 2 * (len(starters)+len(normals))

    # Pirates.
    draws += shuffle(pirates)
    draws += shuffle(len(pirateslots))
    draws += pirates  # Rotate.

    # NPCs.
    draws += shuffle(npcs)
    draws += shuffle(len(npcslots)+len(pirateslots)-pirates)  # Shuffle NPC + unused pirate slots.
    draws += npcs  # Rotate.

    # Now shuffle the rest and then place small islands.
    rest = max(0,len(npcslots)+len(pirateslots) - npcs - pirates)
    draws += shuffle(rest)
    draws += 2*rest
    return draws


def BinarizeIslands(islands, unwanted = [], scores={}):
    """Return an array of island structs for the C code.

    struct Island {
        char id;
        char picked;
        char unwanted;
        char rivershift;
        float score;
    }; 
    """
    rawislands = np.zeros(len(islands),dtype={"names":["id","picked","unwanted","rivershift", "score"],
                                              "formats":["i1","i1","i1","i1","f4"]})
    for i,(name,d) in enumerate(islands.iterrows()):
        rawislands[i]["id"] = d.id
        if name in unwanted:
            rawislands[i]["unwanted"] = 1
        
        if "R" in name:
            # Find non-river counterpart, if any.
            try:
                j = islands.index.get_loc(name.replace("R",""))

                # Now figure out where that counterpart is in relation to us.
                # Assign that shift to our value. Assign the opposite value to the counterpart.
                shift = j-i
                rawislands[i]["rivershift"] = shift
                rawislands[j]["rivershift"] = -shift
            except KeyError:
                pass
            
        # Has it been picked yet? Nope.
        rawislands[i]["picked"] = 0
        rawislands[i]["score"] = scores.get(name,0)

##    return rawislands.ctypes.data, len(rawislands)  # Is garbage collected on return. Ouch.
    return rawislands

def BinarizeWorld(world):
    """Return an array with slots for the C code.
    It is a single array with multiple sections, in this order:
        normal, starter, npc, pirate
    (So essentially the order of ids, except no decoration islands.)
    The game first draws from normal/starter and then from npc/pirate,
    so it is good to have everything in one spot.

    Return the array and the offset of each section.
    struct Slot {
        char size;
        char id;  // This is the id used for matching islands. Shifted and replaced for id==3 and id==4.
        int16_t actualid;  // This is the original id.
    };
    """
    slots = world
    normal = slots[(slots.id==0) & slots.type==1]
    starter = slots[slots.id==1]
    npc = slots[slots.id==3]
    pirate = slots[slots.id==4]

    offsets = [0]
    rawarrays = []
    for array in (normal, starter, npc, pirate):
        rawarray = np.zeros(len(array), dtype="u1, u1, u2")
        for i,(_,d) in enumerate(array.iterrows()):
            did = 0 if d.id in (3,4) else d.id
            rawarray[i] = (d.sz, 1<<did, d.id)
        rawarrays.append(rawarray)
        offsets.append(offsets[-1] + len(array))

    # Put everything into a single array.
    # Afterwards we just tell the shuffler which part of that data to shuffle.
    rawworld = np.concatenate(rawarrays)
    return rawworld, offsets[1:]



def BinarizeWanted(allislands, wanteds):
    """Return an array with wanted islands for the C code.
    struct Wanted {
        // We want to check that islands[size][index].picked is true.
        int16_t size;
        int16_t index;
    };
    """
    rawarray = np.zeros(len(wanteds), dtype="u2, u2")
    for i,wanted in enumerate(wanteds):
        if "CI" in wanted:
            size = 2
        else:
            size = "SML".index(wanted[0])
        
        islands = allislands[size]
        try:
            index = islands.index.get_loc(wanted)
        except KeyError as e:
            e.args = (f"You want to include an island that does not exist on this difficulty: {wanted}",)
            raise
        rawarray[i] = (size, index) 
    return rawarray



# Mersenne Twister wrapper.
path = os.path.dirname(os.path.realpath(__file__))
dll = CDLL(path+"/src/findseed.dll")

dll.seed.argtypes = [c_uint32]
dll.draw.restype = c_uint32
dll.randint.argtypes = [c_uint32]
dll.randint.restype = c_uint32
dll.shuffle.argtypes = [c_void_p, c_uint32]
dll.mti.restype = c_uint32

class MT:
    """Mersenne twister RNG."""
    def __init__(self,seed):
        dll.seed(seed)
    def mti(self):
        return dll.mti()
    def Draw(self):
        return dll.draw()
    def Randint(self, n):
        """Return integer in the interval [0,n-1]."""
        assert n
        return dll.randint(n)
    def Shuffle(self, d):
        """Shuffle data in place."""
        permutations = np.arange(len(d), dtype=np.uint32)
        dll.shuffle(permutations.ctypes.data, len(d))
        d2 = copy(d)  # Shallow copy.
        for i,j in enumerate(permutations):
            d[i] = d2[j]


if __name__ == "__main__":
    mt = MT(1234321)
    nums = [mt.Draw() for i in range(10)]
    assert nums == [1469221705, 572008981, 774309, 202951789, 1181100079, 1343392663, 807019732, 288197851, 158012026, 523124643], "RNG yields unexpected numbers."

    gamemode = "SandboxSingleplayer"


    print("Islands that appear only in normal difficulty:")
    for size,islands in zip(SIZES, LoadIslands("Normal", gamemode)):
        print(f"{size}:", " ".join(islands[islands["diff"]==1].index)) 
    print("\nIslands that appear only in hard difficulty:")
    for size,islands in zip(SIZES, LoadIslands("Hard", gamemode)):
        print(f"{size}:", " ".join(islands[islands["diff"]==2].index))
    print()



    # Get stats on all island slots.
    print("Number of islands:                     S  M  L")
    for diff in DIFFS:
        for mapsize in SIZES[::-1]:
            for islandsize in SIZES[::-1]:
                for maptype in MAPTYPES:
                    slots,_,islands = Load(maptype, mapsize, islandsize, diff, gamemode)
                    normal = slots[(slots.id==0) & slots.type==1]
                    starter = slots[slots.id==1]
                    npc = slots[slots.id==3]
                    pirate = slots[slots.id==4]
                    assert (pirate.sz == 0).all()
                    assert (npc.sz == 0).all()
                    assert (starter.type == 1).all()
                    assert (pirate.type == 1).all()
                    assert (npc.type == 1).all()
                    # All relevant islands have type 1.
                    # And npcs+pirate have size 0.
                    #
                    # So a full map state can be given by: s0/s1/s2 n0/n1/n2 pirate npc
                    # where s0/s1/s2 is the number of starter islands per size. n0/n1/n2 is the normal islands per size.
                    #
                    # But first, get a rough overview of the total number of islands.
                    alls = pd.concat([normal,starter,npc,pirate])
                    rough = " ".join(f"{sum(alls.sz==sz):2}" for sz in range(3))

                    s = ""
                    s += "/".join(str(sum(starter.sz==sz)) for sz in range(3))+ " "
                    s += "/".join(str(sum(normal.sz==sz)) for sz in range(3)) + " "
                    s += str(len(pirate)) + " "+ str(len(npc))
                    s = ""  # It's just too much information.
                    
                    print(f"{maptype:12} {mapsize:7} {islandsize:7} {diff:7}  {rough:12} {s}")

                    

                    








