import arcpy, os, sys, shutil,string, qaqcUtils, glob

# This script is really a "Driver" that implements a variety of routines found in the module qaqcUtils.py
#

def printMessage(messageString):
    print messageString
    arcpy.AddMessage(messageString)

# the tool can be run from a toolbox in ArcMAP...if not, then edit the line in the If not loop.
src = arcpy.GetParameterAsText(0)
if not src:
    src = "Z:/lidar_admin/data/county/jackson"

# the templateSRC is a folder that contains templates for things like Geodatabases etc.
templateSRC = "x:/projects/state_lidar/templates"

# geodatabase and las are two folderst that are to be in the src folder. 
gdbPath = os.path.join(src,"geodatabase")
lasPath = os.path.join(src,"las")

# create the tile index for the files found in the folders...
printMessage("\tExtracting Tile Index")
qaqcUtils.makeTileIndex(src)


# do the initial QA/QC....
printMessage("Performing initial QA/QC for project area "+ src)
qaqcUtils.validateData(src)


# mosaic all of the individual DEMs
printMessage("\tMosaicing and processing DEM")
qaqcUtils.mosaicRaster(src)

# mosaic all of the individual edge-of-water breaklines...
printMessage("\tMosaicing breaklines...")
qaqcUtils.mergeBreaklines(src)

# now process the contours for each of the tiles in the delivery...
# 
arcpy.env.workspace = gdbPath
gdbList = arcpy.ListWorkspaces("*")
for gdb in gdbList:
    if not arcpy.Exists(gdb+"/Contour_data/contours"):
        printMessage("\tGenerating Contours for " + gdb)
        qaqcUtils.generateContours(gdb)

# now merge all of the individual tiled contours
printMessage("\tMerging Contours into Single feature class...")
qaqcUtils.mergeContours(src)

# now process all of the LAS files and extract the building polygons from them
#
lasList = os.listdir(lasPath)
for las in lasList:
    ext = os.path.splitext(las)[1]
    tile_name = os.path.splitext(las)[0]
    if string.lower(ext) == ".las":
        input = os.path.join(src,"las",las)
        output = os.path.join(src,"geodatabase",tile_name+".gdb","buildings")
        if not arcpy.Exists(output):
            try:
                printMessage("\tGenerating building footprints for " + tile_name)
                qaqcUtils.extractBuildings(input,output)
            except:
                pass

# now merge the individual building tiles into a single feature class
printMessage("\tMerging Building Polygons for entire area...")
qaqcUtils.mergeBuildings(src)

# now build the LAS pyramids....
qaqcUtils.buildLASPyramids(src)

printMessage("Process Complete!")
