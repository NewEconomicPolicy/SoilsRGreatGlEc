"""
#-------------------------------------------------------------------------------
# Name:
# Purpose:     consist of high level functions invoked by main GUI
# Author:      Mike Martin
# Created:     06/03/2026
# Licence:     <your licence>
#-------------------------------------------------------------------------------
#
"""
__prog__ = 'wthr_generation_rothc_fns'
__version__ = '0.0.1'
__author__ = 's03mm5'

from os import listdir, rmdir, makedirs
from os.path import join, isdir, exists, split

from numpy import array, arange
from numpy.ma.core import MaskedConstant, MaskError
from numpy.ma import concatenate
from netCDF4 import Dataset

from warnings import filterwarnings
from time import time, strftime, sleep
from _datetime import datetime

from getClimGenNC import ClimGenNC
from getClimGenFns import open_wthr_NC_sets

from getClimGenFns import update_fetch_progress, get_wthr_nc_coords

NULL_VALUE = -9999
GRANULARITY = 120

ERROR_STR = '*** Error *** '
WARNING_STR = '*** Warning *** '

MISSING_VALUE = -999.0
METRIC_LIST = ['precip', 'tas']
PERIOD_LIST = ['hist', 'fut']
ALL_METRICS = ['prec','tave']
METRIC_VARNAMES = {'precip': 'prec', 'tas': 'tave'}

def read_hwsd_wthr_dsets(climgen, hist_wthr_dsets, fut_wthr_dsets, bbox, strt_yr, end_yr):
    """
    get precipitation and temperature data for all times
    """
    lon_ll, lat_ll, lon_ur, lat_ur = bbox
    lat_ll_indx, lon_ll_indx = get_wthr_nc_coords(climgen.hist_wthr_set_defn, lat_ll, lon_ll)
    lat_ur_indx, lon_ur_indx = get_wthr_nc_coords(climgen.hist_wthr_set_defn, lat_ur, lon_ur)

    strt_yr_hist = climgen.hist_wthr_set_defn['year_start']
    end_yr_hist = climgen.hist_wthr_set_defn['year_end']
    try:
        strt_indx_hist = (strt_yr - strt_yr_hist) * 12
    except TypeError as err:
        print(ERROR_STR + str(err))

    strt_yr_fut = climgen.fut_wthr_set_defn['year_start']
    strt_indx_fut = (end_yr_hist - strt_yr_fut + 1) * 12
    end_indx_fut = (end_yr - strt_yr_fut + 1) * 12

    wthr_slices = {}
    for period in PERIOD_LIST:
        wthr_slices[period] = {}

    slices_concat = {}
    for metric in METRIC_LIST:

        # history datasets
        # ===============
        t1 = time()
        print('Reading historic data for metric ' + metric)
        varname = climgen.hist_wthr_set_defn[metric]
        wthr_slices['hist'][metric] = hist_wthr_dsets[metric].variables[varname][strt_indx_hist:,
                                                                lat_ll_indx:lat_ur_indx, lon_ll_indx:lon_ur_indx]
        t2 = time()
        print('Time taken: {}'.format(int(t2 -t1)) + ' for metric: ' + metric)

        print('Reading future data for metric ' + metric)
        varname = climgen.fut_wthr_set_defn[metric]
        wthr_slices['fut'][metric] = fut_wthr_dsets[metric].variables[varname][strt_indx_fut:end_indx_fut,
                                                                lat_ll_indx:lat_ur_indx, lon_ll_indx:lon_ur_indx]
        t3 = time()
        print('Time taken: {}'.format(int(t3 - t2)) + ' for metric: ' + metric)

        slices_concat[metric] = concatenate([wthr_slices['hist'][metric], wthr_slices['fut'][metric]], axis=0)

    ntime_steps = slices_concat[metric].shape[0]
    lats = hist_wthr_dsets[metric].variables['lat'][lat_ll_indx:lat_ur_indx]
    lons = hist_wthr_dsets[metric].variables['lon'][lon_ll_indx:lon_ur_indx]

    return slices_concat, ntime_steps, lats, lons

def read_all_wthr_dsets(climgen, hist_wthr_dsets, fut_wthr_dsets, strt_yr, end_yr):
    """
    get precipitation and temperature data for all times
    """
    strt_yr_hist = climgen.hist_wthr_set_defn['year_start']
    end_yr_hist = climgen.hist_wthr_set_defn['year_end']
    try:
        strt_indx_hist = (strt_yr - strt_yr_hist) * 12
    except TypeError as err:
        print(ERROR_STR + str(err))

    strt_yr_fut = climgen.fut_wthr_set_defn['year_start']
    strt_indx_fut = (end_yr_hist - strt_yr_fut + 1) * 12
    end_indx_fut = (end_yr - strt_yr_fut + 1) * 12

    wthr_slices = {}
    for period in PERIOD_LIST:
        wthr_slices[period] = {}

    slices_concat = {}
    for metric in METRIC_LIST:

        # history datasets
        # ===============
        t1 = time()
        print('Reading historic data for metric ' + metric)
        varname = climgen.hist_wthr_set_defn[metric]
        wthr_slices['hist'][metric] = hist_wthr_dsets[metric].variables[varname][strt_indx_hist:, :, :]
        t2 = time()
        print('Time taken: {}'.format(int(t2 -t1)) + ' for metric: ' + metric)

        print('Reading future data for metric ' + metric)
        varname = climgen.fut_wthr_set_defn[metric]
        wthr_slices['fut'][metric] = fut_wthr_dsets[metric].variables[varname][strt_indx_fut:end_indx_fut, :, :]
        t3 = time()
        print('Time taken: {}'.format(int(t3 - t2)) + ' for metric: ' + metric)

        slices_concat[metric] = concatenate([wthr_slices['hist'][metric], wthr_slices['fut'][metric]], axis=0)

    ntime_steps = slices_concat[metric].shape[0]

    return slices_concat, ntime_steps

def read_all_wthr_smpl_dsets(climgen, hist_wthr_dsets, fut_wthr_dsets):
    """
    get precipitation and temperature data for all times
    """
    wthr_slices = {}
    for period in PERIOD_LIST:
        wthr_slices[period] = {}

    for metric in METRIC_LIST:

        # history datasets
        # ===============
        t1 = time()
        print('Reading historic data for metric ' + metric)
        varname = climgen.hist_wthr_set_defn[metric]
        wthr_slices['hist'][metric] = hist_wthr_dsets[metric].variables[varname][:, :, :]
        t2 = time()
        print('Time taken: {}'.format(int(t2 -t1)) + ' for metric: ' + metric)

        print('Reading future data for metric ' + metric)
        varname = climgen.fut_wthr_set_defn[metric]
        wthr_slices['fut'][metric] = fut_wthr_dsets[metric].variables[varname][:, :, :]
        t3 = time()
        print('Time taken: {}'.format(int(t3 - t2)) + ' for metric: ' + metric)

    return wthr_slices

def fetch_WrldClim_sngl_data(lgr, lat, lon, wthr_slices, lat_indx, lon_indx, hist_flag=False):
    """
    C
    """
    pettmp = {}
    for metric in METRIC_LIST:

        slice = wthr_slices[metric][:, lat_indx, lon_indx]

        # test to see if cell data is valid, if not then this location is probably sea
        # =============================================================================
        if type(slice[0]) is MaskedConstant:
            pettmp = None
            mess = 'No data at lat: {} {}\tlon: {} {}\thist_flag: {}\n'.format(lat, lat_indx, lon, lon_indx, hist_flag)
            lgr.info(mess)
            # print(mess)
        else:
            pettmp[metric] = [float(val) for val in slice]

    return pettmp

def fetch_WrldClim_area_data(lgr, aoi_indices, climgen, wthr_slices, hist_flag=False, report_flag=False):
    """
    get precipitation or temperature data for a given variable and lat/long indices for all times
    """
    func_name = __prog__ + ' fetch_WrldClim_area_data'
    filterwarnings("error")

    nkey_masked = 0
    lat_indx_min, lat_indx_max, lon_indx_min, lon_indx_max = aoi_indices
    ncells = (lat_indx_max + 1 - lat_indx_min) * (lon_indx_max + 1 - lon_indx_min)
    pettmp = {}
    pettmp['lat_lons'] = {}
    last_time = time()

    for metric in list(['precip', 'tas']):
        pettmp[metric] = {}
        slice = wthr_slices[metric][:, lat_indx_min:lat_indx_max + 1, lon_indx_min:lon_indx_max + 1]

        # reform slice
        # ============
        icells = 0
        for ilat, lat_indx in enumerate(range(lat_indx_min, lat_indx_max + 1)):
            lat = climgen.fut_wthr_set_defn['latitudes'][lat_indx]
            gran_lat = round((90.0 - lat) * GRANULARITY)

            for ilon, lon_indx in enumerate(range(lon_indx_min, lon_indx_max + 1)):
                try:
                    lon = climgen.fut_wthr_set_defn['longitudes'][lon_indx]
                except IndexError as err:
                    continue

                gran_lon = round((180.0 + lon) * GRANULARITY)
                key = '{:0=5d}_{:0=5d}'.format(int(gran_lat), int(gran_lon))
                icells += 1
                if report_flag:
                    last_time = update_fetch_progress(last_time, nkey_masked, icells, ncells)

                # validate values
                # ===============
                pettmp[metric][key] = NULL_VALUE
                val = slice[0, ilat, ilon]
                if type(val) is MaskedConstant:
                    lgr.info('val is ma.masked for key ' + key)
                    pettmp[metric][key] = None
                    nkey_masked += 1

                # add data for this coordinate
                # ============================
                if pettmp[metric][key] == NULL_VALUE:
                    record = [float(val) for val in slice[:, ilat, ilon]]
                    pettmp[metric][key] = record[:]

                pettmp['lat_lons'][key] = [lat, lon]

    return pettmp

def _generate_mnthly_atimes(fut_start_year, num_months):
    """
    expect 1092 for 91 years plus 2 extras for 40 and 90 year differences
    """

    atimes = arange(num_months)     # create ndarray
    atimes_strt = arange(num_months)
    atimes_end  = arange(num_months)

    date_1900 = datetime(1900, 1, 1, 12, 0)
    imnth = 1
    year = fut_start_year
    prev_delta_days = -999
    for indx in arange(num_months + 1):
        date_this = datetime(year, imnth, 1, 12, 0)
        delta = date_this - date_1900   # days since 1900-01-01

        # add half number of days in this month to the day of the start of the month
        # ==========================================================================
        if indx > 0:
            atimes[indx-1] = prev_delta_days + int((delta.days - prev_delta_days)/2)
            atimes_strt[indx-1] = prev_delta_days
            atimes_end[indx-1] =  delta.days - 1

        prev_delta_days = delta.days
        imnth += 1
        if imnth > 12:
            imnth = 1
            year += 1

    return atimes, atimes_strt, atimes_end
def clean_empty_dirs(form):
    """
    Remove empty directories
    """
    print('\n')
    out_dir = form.setup['out_dir']
    for period in PERIOD_LIST:
        period_dir = join(out_dir, period)

        nremoved, ndirs = 2 * [0]
        fns = listdir(period_dir)
        for fn in fns:
            this_dir = join(period_dir, fn)
            if isdir(this_dir):
                ndirs += 1
                nfiles = len(listdir(this_dir))
                if nfiles == 0:
                    rmdir(this_dir)
                    nremoved += 1

        print('Checked {} directories and removed {} empty ones from '.format(ndirs, nremoved) + period_dir)

    return