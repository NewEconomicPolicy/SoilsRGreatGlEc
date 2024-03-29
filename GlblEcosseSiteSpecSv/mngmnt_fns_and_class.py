#-------------------------------------------------------------------------------
# Name:        mngmnt_fns_and_class.py
# Purpose:     script to create objects describing NC data sets
# Author:      Mike Martin
# Created:     31/05/2020
# Licence:     <your licence>
#-------------------------------------------------------------------------------
#!/usr/bin/env python

__prog__ = 'mngmnt_fns_and_class.py'
__version__ = '0.0.0'

# Version history
# ---------------
# 
from os.path import join, normpath, split, splitext
from netCDF4 import Dataset
from glob import glob

WARNING_STR = '*** Warning *** '

def create_proj_data_defns(project_path, crop_name, req_resol_deg):
    """

    """
    crop = crop_name.lower()
    resol = str(req_resol_deg)

    resource = 'cropmasks'
    crop_mask_path = join(project_path, resource, crop)
    mask_fnames = glob(crop_mask_path + '\\*' + resol + '*.nc')
    if len(mask_fnames) == 0:
        print('*** Error *** ' + crop_mask_path + ' no mask files found')
        return None

    mask_defn = ManagementSet(mask_fnames[0], resource)

    # for now we just use the mean of the yields from 2000 to 2014;  NB yield is a Python reserved word
    # =================================================================================================
    resource = 'yields'
    obs_path = join(project_path, 'obs_' + crop, resol + 'deg', 'nc' )
    yield_fnames = glob(obs_path + '\\*mean*.nc')
    if len(yield_fnames) == 0:
        print('*** Error *** ' + obs_path + ' no yield files found')
        return None

    yield_defn = ManagementSet(yield_fnames[0], resource)

    # fertiliser
    # ==========
    resource = 'fertilizer'
    fert_path = join(project_path, 'fertilizer')
    fert_fnames = glob(fert_path + '\\*.nc4')
    if len(fert_fnames) == 0:
        print('*** Error *** ' + fert_path + ' no ' + resource + ' files found')
        return None

    fert_defns = {}
    for fert_fname in fert_fnames:
        dummy, short_fn = split(fert_fname)
        root_name, dummy = splitext(short_fn)
        # skip not needed dataset
        if root_name == 'Ninput_date_random_ver1':
            continue
        fert_defns[root_name] = ManagementSet(fert_fname, resource)

    fert_defns = fert_defns

    # sowing_harvest
    # ==============
    resource = 'sowing_harvest'
    dates_path = join(project_path, 'sowing_harvest')
    dates_fname = glob(dates_path + '\\' + crop_name + '*.nc')
    if len(dates_fname) == 0:
        print('*** Error *** ' + dates_path + ' no sowing harvest dates file found')
        return None

    dates_defn = ManagementSet(dates_fname[0], resource)

    return mask_defn, yield_defn, dates_defn, fert_defns

def open_proj_NC_sets(mask_defn, yield_defn, dates_defn, fert_defns):
    """
    """
    mask_defn.nc_dset  = Dataset(mask_defn.nc_fname, mode='r')
    yield_defn.nc_dset = Dataset(yield_defn.nc_fname, mode='r')
    dates_defn.nc_dset = Dataset(dates_defn.nc_fname, mode='r')
    for metric in fert_defns:
        fert_defns[metric].nc_dset = Dataset(fert_defns[metric].nc_fname, mode='r')

    return

def close_proj_NC_sets(mask_defn, yield_defn, dates_defn, fert_defns):

    mask_defn.nc_dset.close()
    yield_defn.nc_dset.close()
    dates_defn.nc_dset.close()
    for metric in fert_defns:
        fert_defns[metric].nc_dset.close()

class ManagementSet(object, ):
    """

    """
    def __init__(self, nc_fname, resource):
        """

        """
        nc_fname = normpath(nc_fname)

        nc_dset = Dataset(nc_fname, mode='r')
        if 'lat' in nc_dset.variables:
            lat_var = 'lat'
            lon_var = 'lon'
        else:
            lat_var = 'latitude'
            lon_var = 'longitude'
        lats = nc_dset.variables[lat_var][:]
        lons = nc_dset.variables[lon_var][:]

        # record var names
        # ================
        exclude_vars = list([lat_var, lon_var, 'time'])
        start_year = None
        end_year   = None
        var_names  = []
        for var in nc_dset.variables:
            if var not in exclude_vars:
                var_names.append(var)

            if var == 'time':
                time_var = nc_dset.variables[var]
                time_units = time_var.units
                since_time = time_units.split('since')[1]
                start_year = int(since_time.split('-')[0]) + time_var[0]    # messy way to get to 1961
                end_year =   start_year + len(time_var) - 1

        nc_dset.close()

        lat_frst = float(lats[0])
        lon_frst = float(lons[0])
        lat_last = float(lats[-1])
        lon_last = float(lons[-1])

        # required for bounding box
        # =========================
        if lat_last > lat_frst:
            lat_ll = lat_frst
            lat_ur = lat_last
        else:
            lat_ll = lat_last
            lat_ur = lat_frst

        if lon_last > lon_frst:
            lon_ll = lon_frst
            lon_ur = lon_last
        else:
            lon_ll = lon_last
            lon_ur = lon_frst

        self.lat_frst = float(lats[0])
        self.lon_frst = float(lons[0])
        self.lat_last = float(lats[-1])
        self.lon_last = float(lons[-1])

        self.lat_var = lat_var
        self.lon_var = lon_var
        self.bbox = lon_ll, lat_ll, lon_ur, lat_ur

        self.nc_fname = nc_fname
        self.var_names = var_names
        if resource == 'yields':
            self.var_name = None
            for var_name in list(['yield', 'yield_national_all']):
                if var_name in var_names:
                    self.var_name = var_name
        self.nc_dset   = None

        # resolutions
        # ===========
        self.resol_lon = (lons[-1] - lons[0])/(len(lons) - 1)
        self.resol_lat = (lats[-1] - lats[0])/(len(lats) - 1)
        self.max_lat_indx = len(lats) - 1
        self.max_lon_indx = len(lons) - 1

        #
        self.lats = list(lats)
        self.lons = list(lons)
        self.start_year = start_year
        self.end_year   = end_year

    def get_nc_coords(self, latitude, longitude):

        ret_code = 'OK'

        lat_indx = int(round((latitude -  self.lat_frst)/self.resol_lat))
        lon_indx = int(round((longitude - self.lon_frst)/self.resol_lon))

        if lat_indx < 0 or lat_indx > self.max_lat_indx:
            ret_code = WARNING_STR + 'latitude index {} out of bounds for latitude {}\tmax indx: {}'.format(lat_indx,
                                                                                round(latitude, 4), self.max_lat_indx)
        if lon_indx < 0 or lon_indx > self.max_lon_indx:
            ret_code = WARNING_STR + 'longitude index {} out of bounds for longitude {}\tmax indx: {}'.format(lon_indx,
                                                                                round(longitude, 4), self.max_lon_indx)
        return lat_indx, lon_indx, ret_code
