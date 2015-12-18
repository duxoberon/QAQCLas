import arcpy, os, string, glob

templateSRC = "x:/projects/state_lidar/templates"
utmZ15P = "PROJCS['NAD_1983_UTM_Zone_15N',GEOGCS['GCS_North_American_1983',DATUM['D_North_American_1983',SPHEROID['GRS_1980',6378137.0,298.257222101]],PRIMEM['Greenwich',0.0],UNIT['Degree',0.0174532925199433]],PROJECTION['Transverse_Mercator'],PARAMETER['False_Easting',500000.0],PARAMETER['False_Northing',0.0],PARAMETER['Central_Meridian',-93.0],PARAMETER['Scale_Factor',0.9996],PARAMETER['Latitude_Of_Origin',0.0],UNIT['Meter',1.0]]"
statewideRaster = "Database Connections/elev_viewer_dc.sde/dnrsdepg.dnrelev.dem_lidar_3m"

def printMessage(messageString):
    print messageString
    arcpy.AddMessage(messageString)

def validateData(src):
    projGDB = os.path.join(src,"elevation_data.gdb")
    if not arcpy.Exists(projGDB):
        arcpy.CreateFileGDB_management(src,"elevation_data.gdb","9.3")
        
    geoWorkspace = os.path.join(src,"geodatabase")

    arcpy.env.workspace = geoWorkspace
    workspaces = arcpy.ListWorkspaces("*")
    logName = os.path.join(src,"qaqcreport.txt")
    tableName = os.path.join(projGDB,"qaqc")
    if not arcpy.Exists(tableName):
        arcpy.CreateTable_management(projGDB,"qaqc",os.path.join(templateSRC,"elevation_data.gdb","qaqc"))
    f1 = open(logName,"w")
    qaqcRows = arcpy.InsertCursor(tableName)
    newRow = qaqcRows.newRow()
    counter = 0
    total = len(workspaces)
    for workspace in workspaces:
        counter += 1
        tile_name = os.path.basename(workspace)[:string.index(os.path.basename(workspace),".")]
        f1.write("==============================================\n")
        f1.write("  Tile = " + tile_name)
        printMessage("\t\tProcessing Tile = " + tile_name + " - " + str(counter) + " of " + str(total))

        lasName = os.path.join(src,"las",tile_name + ".las")
        if os.path.exists(lasName):
            newRow.las_file = "Present"
            f1.write("LAS File present and accounted for")
            printMessage("\t\tLAS File found...")
        else:
            newRow.las_file = "Missing"
            f1.write("\tERROR - LAS FILE MISSING!")
            printMessage("\t\tLAS File Not found!")
        newRow.tile_name = tile_name
        # start by validating the rasters    
        arcpy.env.workspace = workspace
        demLst = arcpy.ListRasters("*")
        if len(demLst) <> 1:
            if len(demLst) == 0:
                msg = "No DEM Found"
            if len(demLst) > 1:
                msg = "Too many rasters in workspace"
            f1.write("\t!!!!!!!!!!!!!!!!!!!______________Error Encountered - " + msg)
        else:
            rasterDesc = arcpy.Describe(demLst[0])
            propList = ["MINIMUM","MAXIMUM","MEAN","TOP","LEFT","RIGHT","BOTTOM","CELLSIZEX","CELLSIZEY"]
            for prop in propList:
                theProp = arcpy.GetRasterProperties_management(demLst[0],prop)[0]

                theValue = float(theProp)
                if prop == "MINIMUM":
                    newRow.min_elev = float(theValue)
                    min_elev = float(theValue)
                elif prop == "MAXIMUM":
                    newRow.max_elev = float(theValue)
                    max_elev = float(theValue)
                elif prop == "MEAN":
                    newRow.mean_elev = float(theValue)
                elif prop == "TOP":
                    newRow.max_y = float(theValue)
                elif prop == "BOTTOM":
                    newRow.min_y = float(theValue)
                elif prop == "LEFT":
                    newRow.min_x = float(theValue)
                elif prop == "RIGHT":
                    newRow.max_x = float(theValue)
                elif prop == "CELLSIZEX":
                    newRow.cellsize_x = float(theValue)
                elif prop == "CELLSIZEY":
                    newRow.cellsize_y = float(theValue)
            newRow.range_elev = (max_elev - min_elev)
            newRow.rows = rasterDesc.height
            newRow.columns = rasterDesc.width

            f1.write("\n")
            f1.write("\n")
        # now check the Points
        f1.write("-----------------------------------------------\n")
        f1.write(" POINT feature class specifics\n")
        pointFC = os.path.join(workspace,"terrain_data","bare_earth_points")
        if not arcpy.Exists(pointFC):
            f1.write("\t !!!!!!!! -------ERROR - Bare Earth Point Feature Class not found\n")
            newRow.bare_earth = "Missing"
        else:
            newRow.bare_earth = "Present"
            pointDesc = arcpy.Describe(pointFC)
            fields = pointDesc.fields
            if not pointDesc.HasZ:
                f1.write("\t !!!!!!!!--------ERROR - no Z-Values for points file\n")
            f1.write("-----------------------------------------------\n")
            f1.write("\n")
            f1.write("\n")

        # now check the Breaklines
        f1.write("-----------------------------------------------\n")
        f1.write(" Breakline feature class specifics\n")
        breaklineFC = os.path.join(workspace,"terrain_data","hydro_breaklines")
        if not arcpy.Exists(breaklineFC):
            f1.write("\t !!!!!!!! -------POTENTIAL ERROR - Hydro Breakline Feature Class not found\n")
            newRow.breaklines = "Missing"
        else:
            breaklineDesc = arcpy.Describe(breaklineFC)
            fields = breaklineDesc.fields
            newRow.breaklines = "Present"
            if not breaklineDesc.HasZ:
                f1.write("\t !!!!!!!!--------ERROR - no Z-Values for breaklines\n")
            if not breaklineDesc.FeatureType <> "Polygons":
                f1.write("\t !!!!!!!!--------ERROR - Invalid Feature Class for breaklines. Got a "+breaklineDesc.FeatureType+" expected a PolygonZ\n")
            typeFound = False

            # the following section was added on 2/25/2011 by Tim to check for valid fields in
            # the hydro breaklines. This was in response to a growing number of hydro breakline
            # files being not compliant.
            for field in fields:
                fieldName = string.upper(field.name)
                if fieldName == "TYPE":
                    typeFound = True
                if fieldName <> "SHAPE" and fieldName <> "OBJECTID" and fieldName <> "TYPE" and fieldName <> "FID" and fieldName <> "SHAPE_LENGTH" and fieldName <> "SHAPE_AREA":
                    f1.write("\t\tDeleting extra field "+ field.name + " from hydro breakline feature class")
                    try:
                        arcpy.DeleteField_management(breaklineFC,fieldName)
                    except:
                        pass

            if not typeFound:
                f1.write("\t\tAdding TYPE field to hydro breakline feature class")
                arcpy.AddField_management(breaklineFC,"type","text","#","#","10")

            # now calculate the TYPE field to be Water. This has been inconsistently done in the past...
            # I had originally used CalculateField tool but it didn't work very well...
            rows = arcpy.UpdateCursor(breaklineFC)
            row = rows.next()
            while row:
                row.setValue("TYPE","Water")
                row = rows.next()
            del rows
            del row
            f1.write("-----------------------------------------------\n")
            f1.write("\n")
            f1.write("\n")
        f1.write("==============================================\n")
        printMessage("")
        printMessage("")
        qaqcRows.insertRow(newRow)
    f1.close()
    del qaqcRows

def mergeBreaklines(src):
    # src variable represents the base folder of that data. For example, d:/dem_work/faribault
    # the script expects to find a folder called "Geodatabase" with a number of geodatabases underneath that
    # represent GDBs for each individual tile in the folder.
        
    printMessage("\t\tMerging Hydro Breaklines for project area")
    dest = os.path.join(src,"elevation_data.gdb","breaklines")
    dirLst = os.listdir(os.path.join(src,"geodatabase"))
    fcLst = []
    for f in dirLst:
        theFC = os.path.join(src,"geodatabase",f,"terrain_data","hydro_breaklines")
        if arcpy.Exists(theFC):
            fcLst.append(theFC)

    fcLstTxt = string.join(fcLst,";")
    arcpy.Merge_management(fcLstTxt,dest)
    
    # the following three lines were commented out on 2/25/2011 as the field checking is now done
    # during the validateData function..
    #arcpy.AddField_management(dest,"type","text","#","#","10")
    #desc = arcpy.Describe(dest)
    #arcpy.CalculateField_management(dest,"Type","Water","VB","#")
    
    dest1 = os.path.join(src,"elevation_data.gdb","hydro_breaklines")
    arcpy.Dissolve_management(dest,dest1,"type","#","SINGLE_PART","DISSOLVE_LINES")
    arcpy.Delete_management(dest)
    arcpy.AddMessage("finished mosaicing breaklines...")

def generateContours(inGDB):
    arcpy.CheckOutExtension("spatial")
    tileName = os.path.splitext(os.path.basename(inGDB))[0]
    masterTileFC = os.path.join(templateSRC,"indx_q006kpy4.gdb/indx_q006kpy4")
    if arcpy.Exists("clipTile"): arcpy.Delete_management("clipTile")
    arcpy.MakeFeatureLayer_management(masterTileFC,"clipTile","DNR_QQQ_ID = '" + tileName + "'")
    # set the analysis environment
    arcpy.env.workspace = inGDB

    inRaster = "/DEM01"
    rasDesc = arcpy.Describe(inRaster)
    rasProj = rasDesc.SpatialReference
    arcpy.env.snapRaster = statewideRaster
    arcpy.env.overwriteOutput = 1
    # now use a smoothing operation on the output grid to create a grid suitable for contouring...
    arcpy.AddMessage("\tSmoothing Raster")
    aggRaster = arcpy.sa.Aggregate(inRaster,"3","MEAN")
    nbrRect = arcpy.sa.NbrRectangle(3,3,"CELL")
    smoothedRaster = arcpy.sa.FocalStatistics(aggRaster,nbrRect,"MEAN","DATA")
    # now create the contours from the temporary raster clipped on the buffered feature...
    arcpy.AddMessage("\tContouring Raster")
    arcpy.sa.Contour(smoothedRaster,"tmpContour","2","0","3.280839895")
    arcpy.CreateFeatureDataset_management(inGDB,"Contour_Data",rasProj)
    arcpy.AddMessage("\tClipping final contour_data/contours")
    arcpy.Clip_analysis("tmpContour","clipTile","Contour_Data/Contours")

    arcpy.AddField_management("Contour_Data/Contours","Elevation","Double")
    arcpy.AddField_management("Contour_Data/Contours","Contour_Type","Text","30")
    arcpy.CalculateField_management("Contour_Data/Contours","Elevation","[Contour]")
    arcpy.CalculateField_management("Contour_Data/Contours","contour_type", "getContour(!ELEVATION!)", "PYTHON_9.3", "def getContour(elev):\\n  import operator\\n  if operator.mod(elev,2) == 0:\\n    con_type = \"Intermediate\"\\n  if operator.mod(elev,10) == 0:\\n    con_type = \"Index\"\\n  return con_type\\n\\n\\n")
    arcpy.DeleteField_management("Contour_Data/Contours","ID;Contour")
    arcpy.Delete_management(aggRaster)
    arcpy.Delete_management(smoothedRaster)
    arcpy.Delete_management("tmpContour")
    arcpy.AddMessage("Done creating contours!")

def mergeContours(src):
    # src variable represents the base folder of that data. For example, d:/dem_work/faribault
    # the script expects to find a folder called "Geodatabase" with a number of geodatabases underneath that
    # represent GDBs for each individual tile in the folder.
        
    dest = os.path.join(src,"elevation_data.gdb","contours")
    dirLst = os.listdir(os.path.join(src,"geodatabase"))
    fcLst = []
    for f in dirLst:
        theFC = os.path.join(src,"geodatabase",f,"contour_data","contours")
        if arcpy.Exists(theFC):
            fcLst.append(theFC)

    fcLstTxt = string.join(fcLst,";")
    arcpy.Merge_management(fcLstTxt,dest)
    arcpy.AddMessage("finished mosaicing contours...")

def mosaicRaster(src):
    # this script mosaics the individual tiled DEMs together and then produces a 3 meter DEM and a hillshade.
    #
    arcpy.CheckOutExtension("Spatial")
    arcpy.env.pyramid = "PYRAMIDS NONE BILINEAR DEFAULT 75"

    outGDBName = "elevation_data.gdb"
    outGDB = os.path.join(src,outGDBName)
    printMessage("\t\tCreating Raster Dataset " + outGDB + "/" + "dem01")

    inputWorkspace = os.path.join(src,"geodatabase")
    targetRaster = os.path.join(outGDB,"dem01")
    printMessage("\t\tCreating 1 meter mosaic for " + src)
    arcpy.env.workspace = inputWorkspace
    wsList = arcpy.ListWorkspaces("*.*","FileGDB")
    arcpy.env.snapRaster = wsList[0]+"/dem01"

    if arcpy.Exists(outGDB + "/dem01"):
        arcpy.Delete_management(outGDB + "/dem01")
    arcpy.CreateRasterDataset_management(outGDB,"dem01","1","32_BIT_FLOAT","#","1","#","NONE","128 128","LZ77","10000 5600000")

    arcpy.WorkspaceToRasterDataset_management(inputWorkspace,targetRaster,"INCLUDE_SUBDIRECTORIES","LAST","FIRST","#","#","NONE","0.0","NONE","NONE")
    arcpy.BuildPyramids_management(targetRaster)
    arcpy.CalculateStatistics_management(targetRaster,"1","1")

    printMessage("\t\tAggregating to 3-meter raster for " + src)
    arcpy.env.snapRaster = statewideRaster
    aggRaster = arcpy.sa.Aggregate(targetRaster,"3","MEAN","EXPAND","DATA")
    aggRaster.save(os.path.join(outGDB,"dem03"))
    arcpy.BuildPyramids_management(aggRaster)
    arcpy.CalculateStatistics_management(aggRaster,"1","1")

    printMessage("\t\tCreating Hillshade of 3 meter raster")
    hsRaster = os.path.join(outGDB,"dem03hs")
    arcpy.HillShade_3d(aggRaster,hsRaster,"315","45","NO_SHADOWS","1")
    arcpy.BuildPyramids_management(hsRaster)
    arcpy.CalculateStatistics_management(hsRaster,"1","1")

def extractBuildings(inputLAS, outputFC):
    # this script extracts the building points from a LAS file and then converts them to polygon features.
    #
    arcpy.CheckOutExtension("3d")
    tempDir = os.environ["temp"]
    bldgtmp1 = tempDir + "/bldgtmp1.shp"
    if arcpy.Exists(bldgtmp1): arcpy.Delete_management(bldgtmp1)
    arcpy.LASToMultipoint_3d(inputLAS, bldgtmp1,"1.5","6","ANY_RETURNS","#","#",'LAS')
    bldgtmp2 = tempDir + "/bldgtmp2.shp"
    if arcpy.Exists(bldgtmp2): arcpy.Delete_management(bldgtmp2)
    arcpy.MultipartToSinglepart_management(bldgtmp1,bldgtmp2)
    bldgtmp3 = tempDir + "/bldgtmp3.shp"
    if arcpy.Exists(bldgtmp3): arcpy.Delete_management(bldgtmp3)
    arcpy.AggregatePoints_cartography(bldgtmp2,bldgtmp3,"3")
    #arcpy.SimplifyPolygon_cartography(bldgtmp3, outputFC, "BEND_SIMPLIFY", "3", "0")
    arcpy.SimplifyBuilding_cartography(bldgtmp3, outputFC, 3, 2, "check_conflicts")

def mergeBuildings(src):
    # src variable represents the base folder of that data. For example, d:/dem_work/faribault
    # the script expects to find a folder called "Geodatabase" with a number of geodatabases underneath that
    # represent GDBs for each individual tile in the folder.
        
    dest = os.path.join(src,"elevation_data.gdb","buildings")
    dirLst = os.listdir(os.path.join(src,"geodatabase"))
    fcLst = []
    for f in dirLst:
        theFC = os.path.join(src,"geodatabase",f,"buildings")
        if arcpy.Exists(theFC):
            fcLst.append(theFC)

    fcLstTxt = string.join(fcLst,";")
    arcpy.Merge_management(fcLstTxt,dest)
    #arcpy.DefineProjection_management(dest,utmZ15P)
    arcpy.AddMessage("finished mosaicing buildings...")

def makeTileIndex(src):
    # this script creates the tile index for this delivery by extracting tiles from a master tile feature class
    #
    # what this script does is goe through all of the geodatabases in the geodatabase folder and then queries the template
    # feature class to produce a product. 
    projGDB = os.path.join(src,"elevation_data.gdb")
    if not arcpy.Exists(projGDB):
        arcpy.CreateFileGDB_management(src,"elevation_data.gdb","9.3")

    gdbPath = os.path.join(src,"geodatabase")
    gdbList = os.listdir(gdbPath)
    theQuery = ""
    i = 0
    for gdb in gdbList:
        tileName = os.path.splitext(gdb)[0]
        ext = os.path.splitext(gdb)[1]
        if string.lower(ext) == ".gdb":
            if i == 0:
                theQuery = theQuery + "\"DNR_QQQ_ID\" = '"+ tileName + "'"
            else:
                theQuery = theQuery + " or \"DNR_QQQ_ID\" = '"+ tileName + "'"
            i += 1
    printMessage("\t\tCreating Tile Index for " + src)
    if gp.exists("tile"): gp.delete("tile")
    arcpy.MakeFeatureLayer_management(os.path.join(templateSRC,"indx_q006kpy4.gdb","indx_q006kpy4"),"tile",theQuery)
    arcpy.CopyFeatures_management("tile",os.path.join(src,"elevation_data.gdb","tile_index"))

def buildLASPyramids(src):
    # this script builds LAS pyramid files for LP360...
    lasSrc = src+"/las"
    lasBat = os.path.join(lasSrc,"makePyrmids.bat")
    lasList = glob.glob(lasSrc+"/*.las")
    lpPyr = "c:/program files/lp360/bin/ldpyramid.exe"
    batFile = open(lasBat,"w")
    for las in lasList:
        qvr = string.replace(las,".las",".qvr")
        if not os.path.exists(qvr):
            batFile.write("\"" +lpPyr + "\" " + las + "\n")
    batFile.close()
    os.system("cmd.exe /c " + lasBat)

if __name__ == "__main__":
    # you can use this portion of the script to run individual pieces of code.
    source = "z:/lidar_admin/data/county/chisago"
    buildLASPyramids(source)