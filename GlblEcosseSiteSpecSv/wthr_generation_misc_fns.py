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

from os import listdir, rmdir
from os.path import join, isdir
from numpy.ma.core import MaskedConstant, MaskError
from warnings import filterwarnings
from time import time
from sys import stdout
from PyQt5.QtWidgets import QApplication

from getClimGenFns import update_fetch_progress

ERROR_STR = '*** Error *** '
WARNING = '*** Warning *** '

NULL_VALUE = -9999
GRANULARITY = 120


ERROR_STR = '*** Error *** '
WARNING_STR = '*** Warning *** '

METRIC_LIST = list(['precip', 'tas'])
PERIOD_LIST = list(['hist', 'fut'])

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

def read_all_wthr_dsets(climgen, hist_wthr_dsets, fut_wthr_dsets):
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