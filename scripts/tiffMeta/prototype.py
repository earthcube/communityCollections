# import gdal
import os
import rioxarray as rxr
# import earthpy as et

testfile = "/home/fils/src/Projects/ECO/DeCODER/data/merit/dir_n60w180/n65w155_dir.tif"

f = rxr.open_rasterio(testfile, masked=True)

# filename=gdal.Open("/home/fils/src/Projects/ECO/DeCODER/data/merit/dir_n60w180/n65w155_dir.tif")
# metadata=filename.GetMetadata()
# print(metadata)

print("The crs of your data is:", f.rio.crs)
print("The nodatavalue of your data is:", f.rio.nodata)
print("The shape of your data is:", f.shape)
print("The spatial resolution for your data is:", f.rio.resolution())
print("The metadata for your data is:", f.attrs)
print(f.rio.resolution())
print("The spatial extent of this data is: ",f.rio.bounds())