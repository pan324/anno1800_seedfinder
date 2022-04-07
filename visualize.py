"""Draw a plot of the old world and cape at the same time.
The plot is divided in two parts:
    Old world on the left.
    Cape on the right.

Each of them has a different zoom level so that they fit into their half of the screen.
This means that on large old worlds, cape islands seem larger (because the map is zoomed in more).

This script has full support for NPCs, which is not implemented in the C code for seed finding.
"""


import sys,os,copy
import pandas as pd
import matplotlib.pyplot as plt
from util import Load, MT, Map

    

from PIL import Image, ImageDraw, ImageFont
import tkinter  # To get the screen resolution.


def ScreenSize():
    """Return the x,y size of the current screen."""
    # Get screen resolution of some tk window.
    # The default task bar is 40 pixel, which we subtract.
    # Another 30 pixels for the bar at the top.
    # Another 40 pixels for the (unusable) toolbar at the plot window bottom.
    root = tkinter.Tk()
    root.withdraw()
    x, y = root.winfo_screenwidth(), root.winfo_screenheight()
    return x, y-40-30-40

def MoveWindow(x=0,y=0):
    """Move the window to the x,y position."""
    # https://stackoverflow.com/a/37999370
    # The -8 offset is required but strange though.
    backend = plt.matplotlib.get_backend()
    f = plt.gcf()
    if backend == 'TkAgg':
        f.canvas.manager.window.wm_geometry("+%d+%d" % (x-8, 0))
    elif backend == 'WXAgg':
        f.canvas.manager.window.SetPosition((x-8, 0))
    else:
        f.canvas.manager.window.move(x-8, 0)
    

def PlotWorld(df, pos=0):
    """Plot a worldmap. pos can have these values:
    pos == 0: Plot this map in the left half of the screen.
    pos == 1: Plot this map in the left half of the screen, but create a large canvas.
    pos == 2: Add to an existing figure. Fill the right half of the screen."""
    # Python figimage is seriously odd.
    # But still better than the alternative (inset_axes) which just does not work.
    # Forget xlim and ylim, they have no effect and only introduce ugly ticks and borders.
    # We directly live in pixel space only, so figsize*dpi defines our canvas.
    # We cannot pan the map either. The pixels are absolute.
    global f
    root = tkinter.Tk()
    root.withdraw()

    xscreen,yscreen = ScreenSize()
    xscreen /= 2

    # Open a figure with these dimensions already.
    # We have 100 dpi by default.
    # So we just divide our x,y by 100 to get the inches.
    plt.style.use('dark_background')
    if pos==0:
        f = plt.figure(figsize=(xscreen/100, yscreen/100))
    elif pos==1:
        f = plt.figure(figsize=(2*xscreen/100, yscreen/100))
    MoveWindow()


    # Now consider the data.
    # The images know their size in number of pixels.
    # We can get ingame coordinates from by
    #   ingamesize = pixelsize*SCALE
    # where SCALE is a constant independent of map.
    #
    # Once we have everything in ingame coordinates, we can transform them so that:
    #   x==0 has the left edge of the leftmost island.
    #   x==xscreen has the right edge of the rightmost island.
    #   Same for y.
    images = []
    for i,d in df.iterrows():
        if d.name.startswith("Pirate"):
            path = "pics/NPC_03.png"
            name = ""
        elif d.name.startswith("NPC"):
            path = "pics/"+d.name+".png"
            name = ""
        else:
            path = "pics/" + d.path.split("/")[-1].replace(".a7m",".png")
            name = d.name
        im = Image.open(path)
        if "NPC" not in path: im = im.rotate(90*d.rotation)
        images.append([name, d.x, d.y, im.width, im.height, d.sz, im])

    df = pd.DataFrame(images, columns = ["name","x","y","xsize","ysize","sz","data"]).set_index("name")
    # Convert the image pixel size into data coordinates through some (unknown) scale.
    # The bounding boxes should have almost no overlap now, or the images will overlap.
##    SCALE = 0.45  # Correct scale if the original images were not downsized in copypics.    
    SCALE = 0.9 
    df.loc[:,"xsize":"ysize"] *= SCALE

    # Find the borders and size of the map in ingame coordinates.
    x0 = min(df.x - df.xsize/2)
    x1 = max(df.x + df.xsize/2)
    xs = x1-x0
    y0 = min(df.y - df.ysize/2)
    y1 = max(df.y + df.ysize/2)
    ys = y1-y0

    # Shift and rescale so that we cover all bounding boxes exactly.
    # (We need to use one scale for both axes.)
    scale = min(xscreen/xs, yscreen/ys)  # Converter: datacoords -> pixelcoords
    
    df.x = (df.x - x0)*scale
    df.y = (df.y - y0)*scale
    df.xsize*=scale
    df.ysize*=scale
    # Now we have correct bounding boxes placed across the map.
    # The images themselves still need to be resized to obey the boxes.

    for i,d in df.iterrows():
        # If pos is active, we shift everything to the right by xscreen pixels.
        x = d.x + (xscreen if pos==2 else 0)
        y = d.y 
        # Resize the images themselves in two steps:
        #   pixelcoords -> datacoords -> (correct) pixelcoords
        im = d.data
        im = im.resize((int(im.width*SCALE*scale), int(im.height*SCALE*scale)))
        # Plotting text with plt.text puts the text always below the image.
##        plt.text(x,y, d.name, transform=None, zorder=-300, color="yellow", fontsize=30)
        # So instead we draw the text into the image itself.
        # But ImageDraw cannot scale the fontsize by default, so we need to combine it with ImageFont.
        draw = ImageDraw.Draw(im)
        font = ImageFont.truetype("C:/Windows/Fonts/Arial.ttf", 25)
        draw.text((int(im.width/2), int(im.height/2)), d.name, font=font)
        
        # figimage always draws images from the bottom left, so we need to center the data.
        plt.figimage(im, x - d.xsize/2, y - d.ysize/2)        


def Plot(seed, oldworld, cape, allislands, npccount, piratecount):
    PlotWorld(Map(seed, oldworld, allislands, npccount, piratecount), pos=1)
    PlotWorld(Map(seed, cape, allislands, npccount, piratecount, hasblake=False), pos=2)


if __name__ == "__main__":
    maptype     = "Snowflake"
    mapsize     = "Large"
    islandsize  = "Large"
    difficulty  = "Normal"
    seeds       = [1234321]
    
    pd.options.display.max_colwidth = 100
    pd.options.display.width  = 0


    # NPCs and pirates do not affect the selection/position/rotation of medium and large islands.
    # Lowering these numbers will increase the numbers of small islands by the same amount.
    npccount    = 2  # Does not include Archibald and pirate.
    piratecount = 1  # 0 or 1.



    # Order: Harlow 49, Blake 2d, Kahina 4e, Eli 2e
    oldworld, cape, allislands = Load(maptype, mapsize, islandsize, difficulty)

    for seed in seeds:
##        for region in [oldworld]:
##            df = Map(seed, region, allislands, npccount, piratecount)
##            plt.figure(figsize=(12,9))
##            color = ["C"+str(i) for i in df.id]
##            plt.scatter(df.x, df.y, s=(df.sz+0.8)**2*40,c=color)
##            for i,d in df.iterrows():
##                plt.annotate(d.name, [d.x, d.y])
##            plt.show()

        Plot(seed, oldworld, cape, allislands, npccount, piratecount)
        plt.show()




    
    










