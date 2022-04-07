import pandas as pd
import os


# Data obtained in x64dbg through conditional breakpoint logging:
#   [{s:[rdi]}, {u:4:[rdi+60]}, {u:4:[rdi+64]}, {u:4:[rdi+68]}, {u:4:[rdi+6c]}, {u:4:[rdi+70]}],
# at 00007FF681FD7DA8. (shortly after rdgs::CMapGenerator::GetMatchingIsland)
# This corresponds to
#   ["name",      "region",        "three",         "diff",         "id",         "gamemode"]       
#
# This covers the first part of the island placement (normal and starter islands).
# The second part places NPC outposts. Retrieve their islands with the same logging command.
#
# Do not start the game from the debugger or the DRM will stop you.
# Attach the debugger instead.
# Attach only after the splash screens or it will crash. Wait for the main menu.
#
#
# Code flow:
#   maps = loadmaps(maptype)  # E.g. maptype = "corners".
#   slots = random.choice(maps)  # <=> Shuffle and then pick.
#   random.shuffle(slots)  # Actually shuffle twice and sort.
#   for slot in slots:
#     candidates = []
#     islands = allislands[slot.size]  # islands is a list of small/medium/large islands. 
#     for island in islands:
#       BREAKPOINT
#       if island is compatible with slot:
#         candidates.append(island)
#     choice = random.randint(len(candidates))
#     island = islands[choice]
#     islands.pop(island)
#
# Because islands are being popped, we get the full list only on the first slot of that size.

 


large = [
["data/dlc06/sessions/islands/pool/colony02_3rdparty10_01/colony02_3rdparty10_01.a7m", 16, 3, 3, 2, 7],
["data/dlc06/sessions/islands/pool/colony02_l_01/colony02_l_01.a7m", 16, 3, 3, 2, 7],
["data/dlc06/sessions/islands/pool/colony02_l_03/colony02_l_03.a7m", 16, 3, 3, 2, 7],
["data/dlc06/sessions/islands/pool/colony02_l_05/colony02_l_05.a7m", 16, 3, 3, 2, 7],
["data/dlc06/sessions/islands/pool/colony02_l_06/colony02_l_06.a7m", 16, 3, 3, 2, 7],
["data/sessions/islands/pool/colony01/colony01_l_01/colony01_l_01.a7m", 0, 3, 0, 0, 7],
["data/sessions/islands/pool/colony01/colony01_l_01/colony01_l_01_river_01.a7m", 4, 3, 3, 3, 7],
["data/sessions/islands/pool/colony01/colony01_l_02/colony01_l_02.a7m", 0, 3, 0, 0, 7],
["data/sessions/islands/pool/colony01/colony01_l_02/colony01_l_02_river_01.a7m", 4, 3, 3, 3, 7],
["data/sessions/islands/pool/colony01/colony01_l_03/colony01_l_03.a7m", 0, 3, 0, 0, 7],
["data/sessions/islands/pool/colony01/colony01_l_03/colony01_l_03_river_01.a7m", 4, 3, 3, 1, 7],
["data/sessions/islands/pool/colony01/colony01_l_04/colony01_l_04.a7m", 0, 3, 0, 0, 7],
["data/sessions/islands/pool/colony01/colony01_l_04/colony01_l_04_river_01.a7m", 4, 3, 3, 1, 7],
["data/sessions/islands/pool/colony01/colony01_l_05/colony01_l_05.a7m", 0, 3, 0, 0, 7],
["data/sessions/islands/pool/colony01/colony01_l_05/colony01_l_05_river_01.a7m", 4, 3, 3, 3, 7],
["data/sessions/islands/pool/moderate/community_island/community_island.a7m", 2, 3, 3, 3, 7],
["data/sessions/islands/pool/moderate/community_island/community_island_river_01.a7m", 2, 3, 3, 3, 7],
["data/sessions/islands/pool/moderate/moderate_l_01/moderate_l_01.a7m", 2, 3, 1, 3, 7],
["data/sessions/islands/pool/moderate/moderate_l_01/moderate_l_01_river_01.a7m", 2, 3, 3, 3, 7],
["data/sessions/islands/pool/moderate/moderate_l_02/moderate_l_02.a7m", 2, 3, 3, 3, 3],
["data/sessions/islands/pool/moderate/moderate_l_02/moderate_l_02_river_01.a7m", 2, 3, 3, 3, 3],
["data/sessions/islands/pool/moderate/moderate_l_03/moderate_l_03.a7m", 2, 3, 3, 3, 7],
["data/sessions/islands/pool/moderate/moderate_l_03/moderate_l_03_river_01.a7m", 2, 3, 2, 1, 7],
["data/sessions/islands/pool/moderate/moderate_l_04/moderate_l_04.a7m", 2, 3, 3, 3, 7],
["data/sessions/islands/pool/moderate/moderate_l_04/moderate_l_04_river_01.a7m", 2, 3, 3, 3, 7],
["data/sessions/islands/pool/moderate/moderate_l_05/moderate_l_05.a7m", 2, 3, 3, 1, 7],
["data/sessions/islands/pool/moderate/moderate_l_05/moderate_l_05_river_01.a7m", 2, 3, 3, 1, 7],
["data/sessions/islands/pool/moderate/moderate_l_06/moderate_l_06.a7m", 2, 3, 1, 3, 7],
["data/sessions/islands/pool/moderate/moderate_l_06/moderate_l_06_river_01.a7m", 2, 3, 3, 3, 7],
["data/sessions/islands/pool/moderate/moderate_l_07/moderate_l_07.a7m", 2, 3, 1, 3, 3],
["data/sessions/islands/pool/moderate/moderate_l_07/moderate_l_07_river_01.a7m", 2, 3, 3, 3, 3],
["data/sessions/islands/pool/moderate/moderate_l_08/moderate_l_08.a7m", 2, 3, 3, 1, 7],
["data/sessions/islands/pool/moderate/moderate_l_08/moderate_l_08_river_01.a7m", 2, 3, 2, 1, 7],
["data/sessions/islands/pool/moderate/moderate_l_09/moderate_l_09.a7m", 2, 3, 1, 1, 7],
["data/sessions/islands/pool/moderate/moderate_l_09/moderate_l_09_river_01.a7m", 2, 3, 2, 1, 7],
["data/sessions/islands/pool/moderate/moderate_l_10/moderate_l_10.a7m", 2, 3, 1, 3, 7],
["data/sessions/islands/pool/moderate/moderate_l_10/moderate_l_10_river_01.a7m", 2, 3, 2, 1, 7],
["data/sessions/islands/pool/moderate/moderate_l_11/moderate_l_11.a7m", 2, 3, 3, 1, 7],
["data/sessions/islands/pool/moderate/moderate_l_11/moderate_l_11_river_01.a7m", 2, 3, 3, 1, 7],
["data/sessions/islands/pool/moderate/moderate_l_12/moderate_l_12.a7m", 2, 3, 1, 3, 7],
["data/sessions/islands/pool/moderate/moderate_l_12/moderate_l_12_river_01.a7m", 2, 3, 3, 3, 7],
["data/sessions/islands/pool/moderate/moderate_l_13/moderate_l_13.a7m", 2, 3, 1, 3, 7],
["data/sessions/islands/pool/moderate/moderate_l_13/moderate_l_13_river_01.a7m", 2, 3, 3, 3, 7],
["data/sessions/islands/pool/moderate/moderate_l_14/moderate_l_14.a7m", 2, 3, 3, 3, 7],
["data/sessions/islands/pool/moderate/moderate_l_14/moderate_l_14_river_01.a7m", 2, 3, 2, 1, 7],
]


medium = [
["data/dlc03/sessions/islands/pool/colony03_a01_01/colony03_a01_01.a7m", 8, 3, 3, 2, 7],
["data/dlc03/sessions/islands/pool/colony03_a01_02/colony03_a01_02.a7m", 8, 3, 3, 2, 5],
["data/dlc03/sessions/islands/pool/colony03_a01_02_mp/colony03_a01_02_mp.a7m", 8, 3, 3, 2, 2],
["data/dlc03/sessions/islands/pool/colony03_a01_03/colony03_a01_03.a7m", 8, 3, 3, 2, 7],
["data/dlc03/sessions/islands/pool/colony03_a01_04/colony03_a01_04.a7m", 8, 3, 3, 2, 7],
["data/dlc06/sessions/islands/pool/colony02_m_02/colony02_m_02.a7m", 16, 3, 3, 1, 7],
["data/dlc06/sessions/islands/pool/colony02_m_04/colony02_m_04.a7m", 16, 3, 3, 1, 7],
["data/dlc06/sessions/islands/pool/colony02_m_05/colony02_m_05.a7m", 16, 3, 3, 1, 7],
["data/dlc06/sessions/islands/pool/colony02_m_09/colony02_m_09.a7m", 16, 3, 3, 1, 7],
["data/sessions/islands/pool/colony01/colony01_m_01/colony01_m_01.a7m", 0, 3, 0, 0, 7],
["data/sessions/islands/pool/colony01/colony01_m_01/colony01_m_01_river_01.a7m", 4, 3, 3, 3, 7],
["data/sessions/islands/pool/colony01/colony01_m_02/colony01_m_02.a7m", 0, 3, 0, 0, 3],
["data/sessions/islands/pool/colony01/colony01_m_02/colony01_m_02_river_01.a7m", 4, 3, 3, 3, 3],
["data/sessions/islands/pool/colony01/colony01_m_03/colony01_m_03.a7m", 0, 3, 0, 0, 7],
["data/sessions/islands/pool/colony01/colony01_m_03/colony01_m_03_river_01.a7m", 4, 3, 3, 3, 7],
["data/sessions/islands/pool/colony01/colony01_m_04/colony01_m_04.a7m", 0, 3, 0, 0, 7],
["data/sessions/islands/pool/colony01/colony01_m_04/colony01_m_04_river_01.a7m", 4, 3, 3, 3, 7],
["data/sessions/islands/pool/colony01/colony01_m_05/colony01_m_05.a7m", 0, 3, 0, 0, 3],
["data/sessions/islands/pool/colony01/colony01_m_05/colony01_m_05_river_01.a7m", 4, 3, 3, 3, 3],
["data/sessions/islands/pool/colony01/colony01_m_06/colony01_m_06.a7m", 0, 3, 0, 0, 7],
["data/sessions/islands/pool/colony01/colony01_m_06/colony01_m_06_river_01.a7m", 4, 3, 3, 3, 7],
["data/sessions/islands/pool/moderate/moderate_m_01/moderate_m_01.a7m", 2, 3, 3, 3, 7],
["data/sessions/islands/pool/moderate/moderate_m_01/moderate_m_01_river_01.a7m", 2, 3, 3, 3, 7],
["data/sessions/islands/pool/moderate/moderate_m_02/moderate_m_02.a7m", 2, 3, 3, 1, 7],
["data/sessions/islands/pool/moderate/moderate_m_02/moderate_m_02_river_01.a7m", 2, 3, 2, 1, 7],
["data/sessions/islands/pool/moderate/moderate_m_03/moderate_m_03.a7m", 2, 3, 3, 3, 7],
["data/sessions/islands/pool/moderate/moderate_m_03/moderate_m_03_river_01.a7m", 2, 3, 3, 3, 7],
["data/sessions/islands/pool/moderate/moderate_m_04/moderate_m_04.a7m", 2, 3, 3, 1, 7],
["data/sessions/islands/pool/moderate/moderate_m_04/moderate_m_04_river_01.a7m", 2, 3, 2, 1, 7],
["data/sessions/islands/pool/moderate/moderate_m_05/moderate_m_05.a7m", 2, 3, 3, 3, 7],
["data/sessions/islands/pool/moderate/moderate_m_05/moderate_m_05_river_01.a7m", 2, 3, 3, 3, 7],
["data/sessions/islands/pool/moderate/moderate_m_06/moderate_m_06.a7m", 2, 3, 3, 1, 7],
["data/sessions/islands/pool/moderate/moderate_m_06/moderate_m_06_river_01.a7m", 2, 3, 2, 1, 7],
["data/sessions/islands/pool/moderate/moderate_m_07/moderate_m_07.a7m", 2, 3, 1, 3, 7],
["data/sessions/islands/pool/moderate/moderate_m_07/moderate_m_07_river_01.a7m", 2, 3, 3, 3, 7],
["data/sessions/islands/pool/moderate/moderate_m_08/moderate_m_08.a7m", 2, 3, 1, 3, 7],
["data/sessions/islands/pool/moderate/moderate_m_08/moderate_m_08_river_01.a7m", 2, 3, 3, 3, 7],
["data/sessions/islands/pool/moderate/moderate_m_09/moderate_m_09.a7m", 2, 3, 1, 3, 7],
["data/sessions/islands/pool/moderate/moderate_m_09/moderate_m_09_river_01.a7m", 2, 3, 3, 3, 7],
]

small = [
["data/dlc03/sessions/islands/pool/colony03_a01_05/colony03_a01_05.a7m", 8, 3, 3, 1, 7],
["data/dlc03/sessions/islands/pool/colony03_a01_06/colony03_a01_06.a7m", 8, 3, 3, 1, 7],
["data/dlc03/sessions/islands/pool/colony03_a01_07/colony03_a01_07.a7m", 8, 3, 3, 1, 7],
["data/dlc03/sessions/islands/pool/colony03_a01_08/colony03_a01_08.a7m", 8, 3, 3, 1, 7],
["data/dlc06/sessions/islands/pool/colony02_s_01/colony02_s_01.a7m", 16, 3, 3, 1, 2],
["data/dlc06/sessions/islands/pool/colony02_s_02/colony02_s_02.a7m", 16, 3, 3, 1, 7],
["data/dlc06/sessions/islands/pool/colony02_s_03/colony02_s_03.a7m", 16, 3, 3, 1, 7],
["data/dlc06/sessions/islands/pool/colony02_s_05/colony02_s_05.a7m", 16, 3, 3, 1, 7],
["data/sessions/islands/pool/colony01/colony01_s_01/colony01_s_01.a7m", 4, 3, 3, 1, 7],
["data/sessions/islands/pool/colony01/colony01_s_02/colony01_s_02.a7m", 4, 3, 3, 1, 7],
["data/sessions/islands/pool/colony01/colony01_s_03/colony01_s_03.a7m", 4, 3, 3, 1, 7],
["data/sessions/islands/pool/colony01/colony01_s_04/colony01_s_04.a7m", 4, 3, 3, 1, 7],
["data/sessions/islands/pool/moderate/moderate_s_01/moderate_s_01.a7m", 2, 3, 3, 1, 7],
["data/sessions/islands/pool/moderate/moderate_s_02/moderate_s_02.a7m", 2, 3, 3, 1, 7],
["data/sessions/islands/pool/moderate/moderate_s_03/moderate_s_03.a7m", 2, 3, 3, 1, 7],
["data/sessions/islands/pool/moderate/moderate_s_04/moderate_s_04.a7m", 2, 3, 3, 1, 7],
["data/sessions/islands/pool/moderate/moderate_s_05/moderate_s_05.a7m", 2, 3, 3, 1, 7],
["data/sessions/islands/pool/moderate/moderate_s_06/moderate_s_06.a7m", 2, 3, 3, 1, 7],
["data/sessions/islands/pool/moderate/moderate_s_07/moderate_s_07.a7m", 2, 3, 3, 1, 7],
["data/sessions/islands/pool/moderate/moderate_s_08/moderate_s_08.a7m", 2, 3, 3, 1, 7],
["data/sessions/islands/pool/moderate/moderate_s_09/moderate_s_09.a7m", 2, 3, 3, 1, 7],
["data/sessions/islands/pool/moderate/moderate_s_10/moderate_s_10.a7m", 2, 3, 3, 1, 7],
["data/sessions/islands/pool/moderate/moderate_s_11/moderate_s_11.a7m", 2, 3, 3, 1, 7],
["data/sessions/islands/pool/moderate/moderate_s_12/moderate_s_12.a7m", 2, 3, 3, 1, 7],
]

def ShortName(name, size):
    """E.g.
    data/sessions/islands/pool/moderate/moderate_l_01/moderate_l_01.a7m          => L1
    data/sessions/islands/pool/colony01/colony01_l_01/colony01_l_01_river_01.a7m => L1R
    data/sessions/islands/pool/moderate/community_island/community_island.a7m    => CI
    """
    if name=="Pirate" or name.startswith("NPC"): return name
    sz = "SML"[size]
    
    name = name.split(".")[0].split("/")[-1]
    if "_river" in name:
        assert "_river_01" in name    
        river = "R"
        name = name.replace("_river_01","")
    else:
        river = ""
    if name.startswith("community_island"): return "CI"+river
    suffix = ""
    try:
        num = str(int(name.split("_")[-1]))
    except ValueError:
        num = str(int(name.split("_")[-2]))
        suffix = name.split("_")[-1]
        
    return sz+num+river+suffix
    


labels = ["path","region","three","diff","id","gamemode"]

small = pd.DataFrame(small, columns=labels)#.set_index("name")
medium = pd.DataFrame(medium, columns=labels)#.set_index("name")
large = pd.DataFrame(large, columns=labels)#.set_index("name")

for i,islands in enumerate([small,medium,large]):
    islands["shortname"] = islands.path.map(lambda x:ShortName(x,i))



try: os.mkdir("islands")
except:1



small.to_csv("islands/small.csv", index = False)
medium.to_csv("islands/medium.csv", index = False)
large.to_csv("islands/large.csv", index = False)






