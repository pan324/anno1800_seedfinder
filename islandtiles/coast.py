"""This fails because the game is very picky about rounding down and rounding up and so on."""


from xml.etree import ElementTree as ET
from binascii import unhexlify
import numpy as np
from struct import pack,unpack
import matplotlib.pyplot as plt
from matplotlib.path import Path
import sys,os
from copy import copy
import bezier
import math



def FillMask(mask, polygon):
    """Write ones into all locations of the mask that are within the polygon."""
    path = Path(polygon)
    xmin = polygon[0].min()
    xmax = polygon[0].max()
    ymin = polygon[1].min()
    ymax = polygon[1].max()
    # Turn min/max into integers.
    # Assume that we can never go out of bounds, so xmin=242.3 means that tile 242 can never be reached.
    xmin,ymin = math.ceil(xmin),math.ceil(ymin)
    xmax,ymax = math.floor(xmax),math.floor(ymax)
    height = ymax-xmin+1
    width = xmax-xmin+1
    x,y = np.mgrid[xmin:xmin+width, ymin:ymin+height]
    xy = np.stack([x.flat, y.flat],1)
    submask = path.contains_points(xy).reshape(width,height)
    mask[xmin:xmin+width,ymin:ymin+height] = submask


def ReadBits(byte): return [(byte>>i)&1 for i in range(8)]


### Cubic Beziers:
### We define 4 points,
###   p0 is start. p3 is end.
###   p1 is that point attached to p0, as known from vector graphics.
###   p2 is that point attached to p3.
##def B(t, p0,p1,p2,p3):
##    return (1-t)**3 * p0 + 3*(1-t)**2*t * p1 + 3*(1-t)*t**2 * p2 + t**3 * p3
##p0 = np.array([0.,0])
##p1 = np.array([1.0,0.5])
##p2 = np.array([0.5,1.0])
##p3 = np.array([1.5,1.5])
##t = np.linspace(0,1,100)[...,None]
##res =  B(t,p0,p1,p2,p3).T
# The bezier package makes this easy.
##nodes = np.asfortranarray([[0.0, 1.0, 0.5, 1.5],
##                           [0.0, 0.5, 1.0, 1.5]])  + 100
##curve = bezier.Curve(nodes, degree=3)
##curve.plot(100)
####plt.plot(res[0],res[1], linestyle="--")
##
##xcurve = bezier.Curve(np.asfortranarray([[0.0, 5.0],[0.2,0.2]]) + 100, degree=1)
####xcurve+=100
##res = curve.intersect(xcurve)
### The result is a vector of t values, so we plug it into the xcurve again to get coords.
##print(res)
### The intersect function deviates by 0.001 from the true result.
### This precision is independent of the absolute values involved.
### If necessary, abandon the bezier package completely and use a root finder instead.
##res = xcurve.evaluate(res[1,0])
##plt.scatter(*res)
##plt.show()







# The package does not support three dimensions, which the data has.
# BUT: We can see from the B definition that the dimensions do not interact at all.
# So we can safely ignore the height dimension and focus on x,y.

# For each Bezier curve, the game gives a direction, e.g. left.
# This means that all tiles left of the curve are coast.






for dirname in os.listdir("."):
    if not os.path.isdir(dirname): continue

##    for fname in os.listdir(dirname):
##        if not fname.endswith("tmp.xml"): continue
##        et = ET.parse(dirname+"/"+fname)
##        root = et.getroot()
##        for i,data in enumerate(root.findall(".//AreaManagerData/None/Data")):
##            outname = dirname+"/"+"manager"+str(i)
##            open(outname,"wb").write(unhexlify(data.text))
##            os.system(r"E:\hex\anno\FileDBReader\FileDBReader.exe decompress -f "+outname)


    for fname in os.listdir(dirname):
        if not fname.startswith("manager") or not fname.endswith(".xml"): continue
        et = ET.parse(dirname+"/"+fname)
        root = et.getroot()
        curves = root.findall(".//CoastLine")
        if not curves: continue
        if not "m_01" in dirname: continue
        print(dirname+"/"+fname)

        curves = root.findall(".//CoastLine/..")



        mask = np.zeros([320,320],dtype=int)
        for curve in curves:
            position = UnpackElem("3f", curve, "Position")[::2]
            path = curve.find("BezierPath/Path")
            xmin,ymin = UnpackElem("3f", path, "Minimum")[::2]
            xmax,ymax = UnpackElem("3f", path, "Maximum")[::2]

            # Integer versions that are slightly inside the actual BBox.
            xmin2,ymin2 = math.ceil(xmin),math.ceil(ymin)
            xmax2,ymax2 = math.floor(xmax),math.floor(ymax)
            

            # All values (except d) in three dimensions (x,z,y).
            # The z coordinate is not interesting, so we will ignore it entirely.
            #
            # Position: Position of the first point of the spline (actually redundant).
            # Minimum, Maximum: Usually just the bounding box for all curves.
            #
            # Curve items:
            #   p: Position.
            #   i: Ingoing (previous). This is a position offset.
            #   o: Outgoing (next). This is a position offset.
            #   d: Direction.
            #      d == [0,1]: Everything above the curve is coast.
            #      d == [0,-1]: Everything below the curve is coast.
            #      d == [1,0]: Everything right of the curve is coast.
            #      d == [-1,0]: Everything left of the curve is coast.
            # 
            # Bezier needs data in a different shape.
            # Curve k needs: p[k], p[k]+o[k], p[k+1]+i[k+1], p[k+1]  and also d[k].
            # Unneeded values: i[0], d[-1], o[-1]

            # First, grab all data so that k,k+1 lookups are easier.
            p = []
            i = []
            o = []
            d = []
            for elem in path.find("BezierCurve"):
                p.append(UnpackElem("3f",elem, "p")[::2])
                i.append(UnpackElem("3f",elem, "i")[::2])
                o.append(UnpackElem("3f",elem, "o")[::2])
                d.append(list(UnpackElem("2f",elem, "d")))

            # Now run through the items.
            # The idea is to set up either horizonal lines (if d == left,right)
            # or vertical lines (if d == up,down) and then intersect the grid with the curve.
            for p0,p1,p2,p3,direction in zip(p,o,i[1:],p[1:], d):  
                nodes = np.asfortranarray(np.stack([p0,p1+p0, p2+p3, p3], axis=1))
                curve = bezier.Curve(nodes, degree=3)
                if direction == [1,0]:
                    # Fill right. Draw horizontal lines across the BBox.
                    # The y start and end points are still required.
                    start = math.ceil(min(p0[1],p3[1]))
                    end = math.floor(max(p0[1],p3[1])) 
                    for y in range(start,end+1):
                        grid = bezier.Curve(np.asfortranarray([[xmin-20,xmax+20], [y,y]]), degree=1)
##                        print(curve.intersect(grid))
                        x,y2 = grid.evaluate(curve.intersect(grid)[1,0])
                        mask[y,math.ceil(x):xmax2] = 1
                # Same idea for the other three cases.
                elif direction == [-1,0]:
                    # Fill left.
                    start = math.ceil(min(p0[1],p3[1]))
                    end = math.floor(max(p0[1],p3[1])) 
                    for y in range(start,end+1):
                        grid = bezier.Curve(np.asfortranarray([[xmin-20,xmax+20], [y,y]]), degree=1)
                        x,y2 = grid.evaluate(curve.intersect(grid)[1,0])
                        mask[y,xmin2:math.floor(x)] = 1
                elif direction == [0,1]:
                    # Fill above.
                    start = math.ceil(min(p0[0],p3[0]))
                    end = math.floor(max(p0[0],p3[0])) 
                    for x in range(start,end+1):
                        grid = bezier.Curve(np.asfortranarray([[x,x], [ymin-20,ymax+20]]), degree=1)
                        
                        print(curve.intersect(grid))
                        x2,y = grid.evaluate(curve.intersect(grid)[1,0])
                        mask[math.ceil(y):ymax2,x] = 1
                elif direction == [0,-1]:
                    # Fill below.
                    start = math.ceil(min(p0[0],p3[0]))
                    end = math.floor(max(p0[0],p3[0])) 
                    for x in range(start,end+1):
                        grid = bezier.Curve(np.asfortranarray([[x,x], [ymin-20,ymax+20]]), degree=1)
                        x2,y = grid.evaluate(curve.intersect(grid)[1,0])
                        mask[ymin2:math.floor(y),x] = 1
                        
                        


 
          
















