"""Not directly involved in the other tools.
Count the number of tiles per island.
This is a good starting point for scoring.


But the values are inaccurate for multiple reasons:
    1) AreaIDs contains all tiles that can ever be built on.
    2) Water mostly matches where water is, but occasionally a tile is not marked as water,
       despite being underwater. It behaves like a water tile, so apparently the game uses
       the heightmap for water/nonwater calculations anyway.
       The heightmap has 4 numbers for each tile though and it would require testing to understand the calculations.
    3) Coast tiles are nonwater tiles that only support very few building types.
       The game does not explicitly store these tiles.
       Coasts are given as Bezier curves and these are converted to tiles during the loading screen.
       If the calculations were just implemented in a straightforward manner, that would not even be an issue.
       But the game rounds these numbers up and down and to .5 values which makes it hard to simulate this.
    4) Not even all water tiles are guaranteed to be reachable.
       The coast tiles actually define our reach into the water areas.
       No coast = no water tiles.

So I just modded the assets.xml and templates.xml to build quays across entire islands (needs 150 workers to unlock).
In contrast to ornaments these quays are not limited to ~1000 tiles per placement.

Instead, this script here just retrieves the number of river tiles,
so we can subtract them from islands without rivers (which were retrieved ingame).
"""

import sys,os, zlib
from struct import unpack
import xml.etree.ElementTree as ET
from binascii import unhexlify
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
# The tiles are stored in the large a7m file for each island.
# Need to help out the FileDBReader a bit; the a7m has 2 zlib parts and it can read neither.
# We only need the first part.
# At 0x310 we get the offset when to stop reading. So we read from 0x318 until that offset.
# Put it in a temporary file for the DBReader to work with.
# Then retrieve the data from the converted xml file.
# The relevant parts are AreaIDs and Water. AreaIDs has these values:
#   0: Unbuildable water
#   1: Mountain/cliff (unbuildable)
#   8193: Buildable area, including water areas.
# Water has bits for each position and allows us to split the buildable area into water areas and land areas.

root = "../../data"

def ExpandBits(byte): return [byte>>i & 1 for i in range(8)]

def GetAreas(xmlpath):
    data = ET.parse(xmlpath)
    node = data.getroot()

    # Estimate the islands with river by calculating how many river tiles block land tiles.
    # The result will slightly underestimate land area because we subtract coast river tiles.

    res = node.find(".//Water")
    width = unpack("I", unhexlify(res.find("x").text))[0]
    height = unpack("I", unhexlify(res.find("y").text))[0]
    water = unhexlify(res.find("bits").text)
    water = np.array([bit for byte in water for bit in ExpandBits(byte)], dtype=float)
    water = water.reshape(width, height)
    water[water==0]=np.nan

    res = node.find(".//AreaIDs")
    width = unpack("I", unhexlify(res.find("x").text))[0]
    height = unpack("I", unhexlify(res.find("y").text))[0]
    area = unhexlify(res.find("val").text)
    area = np.array(unpack(f"{len(area)//2}h",area), dtype=float)
    area = area.reshape(width, height)
    area[area!=8193] = np.nan  # Keep only the buildable area.
    area[area==8193] = 1


    res = node.find(".//RiverGrid")
    width = unpack("I", unhexlify(res.find("x").text))[0]
    height = unpack("I", unhexlify(res.find("y").text))[0]
    river = unhexlify(res.find("bits").text)
    river = np.array([bit for byte in river for bit in ExpandBits(byte)], dtype=float)
    river = river.reshape(width, height)
    river[river!=0] = np.nan
    river[river==0] = 1

    return area, water, river



def Walks():
    yield os.walk(root+"/sessions/islands/pool")
    for dirname in os.listdir(root):
        if dirname.startswith("dlc"):
            yield os.walk(root+"/"+dirname+"/sessions")
    
found = {}
data = []
for walk in Walks():
    for dir0, dirs, fnames in walk:
        for fname in fnames:
            if not fname.endswith(".a7m"): continue
            path = (dir0+"/"+fname).replace("\\","/")
            newname = path.split("/")[-2]
            if "river" in fname: newname += "R"
            assert newname not in found
            found[newname] = path
            if not "river" in fname: continue

            tmppath = path[:-4]+"tmp"
            if not os.path.exists(tmppath):
                f = open(path,"rb")
                f.seek(0x310)
                offset = unpack("Q", f.read(8))[0]
                size = offset-0x318
                payload = f.read(size)
                payload = zlib.decompress(payload)
                open(tmppath,"wb").write(payload)
                cmd = os.path.normpath(r"../../FileDBReader/FileDBReader.exe decompress -f ")+os.path.normpath(tmppath)
                rv = os.system(cmd)
                if rv:
                    raise Exception("Could not run cmd. FileDBReader not found?")

            area,water,river = GetAreas(tmppath+".xml")

                    
            before = (water*area == 1).sum()
            after = (water*area*river == 1).sum()



            data.append((newname, before-after))


df = pd.DataFrame(data, columns = ["name","rivertiles"])

df = df[df.name.str.startswith("moderate_l_")
       |df.name.str.startswith("moderate_m_")
       |df.name.str.startswith("moderate_s_")
       |df.name.str.startswith("community_island")]


df.name = df.name.str.replace("moderate_","").str.replace("l_0","L").str.replace("l_","L").str.replace("m_0","M")\
          .str.replace("m_","M").str.replace("s_0","S").str.replace("s_","S")\
          .str.replace("community_island","CI")

df = df.set_index("name")
df.to_csv("rivertiles.csv")

