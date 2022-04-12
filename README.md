# Anno 1800 Seed Finder and Visualizer

The finder supports these filters:

1) Unwanted islands. These islands may not appear in old world or cape.
2) Wanted islands (old world). These islands must appear in the old world.
3) Wanted islands (cape). These islands must appear in cape.

Additionally, it will sort the results according to the sum of all island scores, where all island scores can be specified. The default score is the number of land tiles of all large islands.

The map type, map size, island size and island difficulty can be adjusted. The finder works in two iterations, a rough baseline filtering for rivers and then a fast seed refinement step. 

1) The baseline filtering brute forces through all 2147483648 possible seeds to discard universally bad islands (e.g. with rivers). Results are saved to disk. Performance is roughly 1 million seeds per second per CPU core, which means comfortable 2.5 minutes runtime on a 5950X. Baselines for the largest maps are already shipped with the repository. (Although only Atoll, Corners, Arc are recommended because they have the most islands. Run util.py for more information.)
2) The seed refinement loads the seeds created in step 1 from disk. Because relatively few seeds are left, refinement takes just a second to run. This makes it easy to tweak the requirements until just a handful of excellent seeds is found.

The results can be visualized. A map with islands and NPCs can be either shown directly or saved to disk. That map contains both the old world and the cape area, because these are the two worlds where the seed has an impact.

## Example

A search on Corners large/large/normal yields the following seeds. I have used three different scorings, all based on land tiles. Score "L" is the default and considers large islands only. Score "LM" considers all land tiles of large and medium islands. Score "LMS" includes small islands as well (and assumes all NPCs and pirates). The first seed has the optimal L score, the second seed has the optimal LM score, and the third seed has the optimal LMS score. 1384368905 offers around 2000 more tiles on large islands only but ends with 5000 fewer tiles overall. Still a very solid choice if one just wants to have a good time with large islands.

| Seed | L | LM | LMS |
| --- | --- | --- | --- |
| 1384368905 | 335992 | 471848 | 509801 |
| 1636799193 | 333327 | 475675 | 512269 |
| 1423628354 | 333762 | 474048 | 514571 |


## Installation

1) You must have Python: https://www.python.org/downloads/ Do the opposite of the install recommendations: Activate the PATH checkbox and do not install for all users.
2) The Python packages can be installed from a cmd window with: pip install numpy pandas matplotlib Pillow 
    1. If pip is not found, you did not select the PATH checkbox and you need to set your environment variable (or just reinstall). 
    2. If it fails due to permissions, then Python was installed for all users and not in the user directory, so cmd must be run from admin mode (or just reinstall).
3) Right click on the main.py file and choose Edit with IDLE. Adjust the settings as needed and press F5 to run.


## Notes 

The finder can only filter through island selection. Things that cannot be filtered are: Island rotation; island position; fertilities; mining slots. 

Fertilities and mining slots in particular are a fairly hard problem because they come at the end of island creation. To put things into perspective, the entire island+NPC placement and rotation is done with the first 70 random numbers from the Mersenne Twister. Then the game draws around 18000 more numbers before fertilities and mining slots are decided. There is a lot of additional game code to decipher and the filtering would be fairly slow even when using only the baseline seeds.

If you want to run the retrieval scripts yourself (copypics.py, maptemplatestocsv.py, maptocsv.py), they expect that the repository has two neighboring folders, one for the FileDBReader and one for all game assets as extracted with the RDAExplorer. I.e. the folders ../FileDBReader and ../data should exist.

The C code is basically a very streamlined (and stripped-down) version of the map creation in util.py. The latter does not reject early and is written mostly in Python, yielding just 25 seeds per second per core, so even working with only baseline data without further rejection would be pretty slow.

The overall code flow for each world (e.g. old world, new world, cape) is as follows:

1) Initialize a Mersenne Twister random number generator from the standard library (std::mt19937) with the seed that was given by the user.
2) From data/config/export/main/asset/assets.xml, load all MapTemplate items. Compare the actual user input (map type, map size, ...) with these items and keep only the items that match. Randomly select one of these items (std::uniform_int_distribution). (It just so happens that there is only exactly one item for each of these settings, except when the "random" map type was selected. Only the new world has multiple.) This is what the maptemplatestocsv.py retrieves.
3) The selected map template contains a path to an a7t file, which we are not interested in. But it is next to an a7tinfo file, which has information about the size of the world and also has the island slots. An island slot has coordinates and size and also type and id. The map generation later on is all about matching slots with compatible islands (in terms of size and type and id). maptocsv.py retrieves this a7tinfo data.
4) Independently of the map, all islands are loaded. The assets.xml has RandomIsland entries which specify FilePath (to a7m), region, difficulty, islandtype (which is actually the id to match with the slot.id). However, no size. The assets.xml also has an IslandSizes entry, which tells us that small islands are no more than 192 tiles per x and y, medium islands are 272, large islands are 384. The actual island sizes are in the a7minfo files next to the a7m file, where ActiveMapRect contains the values x0,y0,x1,y1. We retrieve xsize = x1-x0 and ysize=y1-y0 and from that can identify the island size. Create a separate list for each island size and also keep only islands with the id <= 3 (Normal;Starter islands only). Sort each list by FilePath.
5) Shuffle (std::shuffle) all starter slots (slots with id==1). 
6) Append the shuffled starter slots at the end of the normal slots (slots with id==0 and type==1). 
7) Shuffle the result.
8) Sort the result by id in descending order, so that starter slots are at the top.
9) For each slot: 
    1) Replace its id by 1<<id. 
    2) Get islands with the same size as the slot.
    3) Create a list of compatible islands. To be compatible, the island id must be compatible with the slot id (island.id & slot.id) and the island region must be compatible with the region of the world and the island difficulty must be compatible with the user setting and the island gamemode must be compatible with the user setting. (All checks except id can be pushed far out of the loop but that is not how the game does it.)
    4) Randomly select one island for this slot (std::uniform_int_distribution). Randomly select a rotation (values from 0 to 3, 90 degrees each, std::uniform_int_distribution). Remove the island and its nonriver/river variant from available islands for this world.
10) Shuffle all pirates (do nothing) and all pirate slots (id==4) and place the pirate on the first slot. Draw rotation.
11) Append the unused pirate slots at the end of the NPC slots (id==3). 
12) Shuffle all NPCs, but then sort so that Archibald Blake comes first. Cape has the same NPCs as the old world except Archibald Blake. 
13) Shuffle all slots and place the NPCs on the first few slots. Draw rotations.
14) Shuffle the all unused slots so far, sort them so that id==3 comes first, and treat them like normal slots (id=0). Then do step 9) with them. 

The cape world also shuffles the old world NPCs (but without Archibald Blake) but there are no NPC slots at all, so island placement is not affected. I think fertilities and mine slots in cape will be different depending on whether you have selected both old world NPCs or not. (The shuffle does not draw random numbers if there are fewer than 2 items to shuffle, so 0 NPCs and 1 NPC both do not advance the RNG.)



## Tools used

- x64dbg: Primary tool to follow the code. The game has some useful strings for logging, e.g. "Starting Map Creation, MapGenerator Seed : {}" which give a good idea of what is going on.
- ghidra: Defining structs was very useful. Sadly it did not want to communicate with x64dbg and its builtin debugger gets stuck.
- RDAExplorer
- FileDBReader
