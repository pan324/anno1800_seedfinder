"""Code flow to retrieve island infos.
Needed for each island:
  1) Size
  2) Region,
  3) difficulty
  4) id/type
  5) gamemode


assets.xml:
  Retrieve all RandomIsland entries. Each entry has:
    FilePath: To a7m file.
    IslandRegion: Moderate, ...
    IslandDifficulty: Normal;Hard
    IslandType: Normal;Starter;Decoration;ThirdParty;PirateIsland
    IslandBaseName: Is the same for river and nonriver variant (optional)
    AllowedGameType: SandboxSingleplayer;SandboxMultilayer;CampaignMode  (optional, default value: all three)

Now we have 2,3,4,5.


assets.xml:
  Retrieve .//MapGenerator/IslandSizes
  This tells us the xsize and ysize that corresponds that allow us to sort islands into the three lists:
    0) Small, 1) Medium, 2) Large
  Islands do NOT tell just tell us their size directly. We must use this.

Open up the a7minfo for each island (next to the a7m) and retrieve the ActiveMapRect (x0,y0,x1,x2):
  xsize=x1-x0
  ysize=y1-y0
  for xlim,ylim in IslandSizes:
    if xsize<=xlim and ysize<=ylim:
      Remember this size for this island.

Now we have everything.
Sort by name/path and save as raw.csv for further processing.


Further processing:
Split into 3 lists depending on size.
Filter so that we only keep id<=3.
Binarize the enums into bitmasks.
Save as csv.
"""



import sys,os,zlib, shutil
from binascii import hexlify, unhexlify
from struct import pack,unpack
import pandas as pd
import xml.etree.ElementTree as ET
import matplotlib.pyplot as plt
from io import StringIO


root = ".."  # Path to all extracted files.
ASSET_PATH = root+"/data/config/export/main/asset/assets.xml"
pd.options.display.max_colwidth = 100
pd.options.display.width  = 0
pd.options.display.max_rows = 200

try: os.mkdir("islands")
except: pass


def SaveRaw():
    """Create the raw.csv file with all islands in one place."""
    # Retrieve RandomIsland data.
    assets = ET.parse(ASSET_PATH)
    node = assets.getroot()
    islands = node.findall(".//RandomIsland")
    df = pd.DataFrame()
    for island in islands:
        df2 = pd.read_xml(StringIO(ET.tostring(island).decode()),xpath=".")
        df = pd.concat([df, df2])
    df = df.set_index("FilePath")




    # Get the IslandSizes from the mapgenerator.
    mapgenerator = node.findall(".//MapGenerator")
    assert len(mapgenerator) == 1, "Multiple map generators found."
    mapgenerator = mapgenerator[0]

    def Df(node, xpath="."):
        """Same as a normal pd.read_xml except that we include rownames."""
        data = ET.tostring(node).decode()
        df = pd.read_xml(StringIO(data),xpath=xpath+"/*")
        df.index = pd.read_xml(StringIO(data), xpath=xpath).columns
        return df
    islandsizes = Df(mapgenerator, "IslandSizes")



    # Now go through the a7minfo files.
    sizes = []
    for path in df.index:
        a7minfo = root +"/"+path+"info"
        assert os.path.exists(a7minfo), f"Cannot find {a7minfo}"
        cmd = os.path.normpath(r"../FileDBReader/FileDBReader.exe decompress -y -f "+a7minfo)
        rv = os.system(cmd)
        if rv:
            raise Exception("Could not run cmd. FileDBReader not found?")

        node = ET.parse(a7minfo[:-8]+".xml").getroot()
        rectangle = node.find("ActiveMapRect")
        if rectangle is None:
            print("No rectangle data:",a7minfo)
            continue

        x0,y0,x1,y1 = unpack("IIII",unhexlify(rectangle.text))
        xsize = x1-x0
        ysize = y1-y0

        # Find the right size.
        for sz,(xlim,ylim) in islandsizes.iterrows():
            if xsize<=xlim and ysize<=ylim:
                sizes.append(sz)
                break
        else:
            sizes.append("Very large")  # Unused.

    df["sz"] = sizes
    df = df.sort_index()
    df.to_csv("islands/raw.csv")



SaveRaw()







# Now work a bit with that island data.
# We need to split it into three lists.

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



df = pd.read_csv("islands/raw.csv", index_col = 0)

from util import SIZES, REGIONS, DIFFS, GAMEMODES, ISLAND_TYPE

def BitMask(s, table, defaultval=0):
    """Return the bitmask of s, using table (dictionary).
    E.g. BitMask("Normal;Hard", DIFFS) => 3
    """
    if pd.isna(s):
        return defaultval
    mask = 0
    for word in s.split(";"):
        mask += table[word]
    return mask


df["id"] = df.IslandType.apply(BitMask, args=[ISLAND_TYPE])
df["diff"] = df.IslandDifficulty.apply(BitMask, args=[DIFFS])
df["region"] = df.IslandRegion.apply(BitMask, args=[REGIONS])
df["gamemode"] = df.AllowedGameType.apply(BitMask, args=[GAMEMODES, 7])


for sz in ["Small","Medium","Large"]:
    data = df[(df.sz == sz) & (df.id<=3)].copy()
    intsize = SIZES.index(sz)
    data["shortname"] = data.index.map(lambda x:ShortName(x,intsize))
    
    # Needed columns:
    #   path, region, three, diff, id, gamemode, shortname.

    data = data.loc[:,["region","diff","id","gamemode","shortname"]]
    data.index.name = "path"

    data.to_csv(f"islands/{sz}.csv")

























    
