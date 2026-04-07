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
__prog__ = 'wthr_generation_mscnfr_fns'
__version__ = '0.0.1'
__author__ = 's03mm5'

from os import mkdir, remove
from os.path import isdir, join, exists, isfile
from pathlib import Path
from numpy.ma import is_masked
from netCDF4 import Dataset
from csv import writer, reader
from time import time
from PyQt5.QtWidgets import QApplication

from wthr_generation_misc_fns import read_all_wthr_dsets, read_hwsd_wthr_dsets
from getClimGenNC import ClimGenNC
from getClimGenFns import (fetch_WrldClim_data, fetch_WrldClim_NC_data, associate_climate,
                           open_wthr_NC_sets, get_wthr_nc_coords, join_hist_fut_to_sim_wthr)
from thornthwaite import thornthwaite
from glbl_ecsse_low_level_fns import update_wthr_progress, check_cell_within_csv

ERROR_STR = '*** Error *** '
WARNING_STR = '*** Warning *** '

GRANULARITY = 120

PERIOD_LIST = ['hist', 'fut']
METRIC_LIST = list(['precip', 'tas'])
METRIC_DESCRIPS = {'precip': 'precip = total precipitation (mm)',
                    'pet': 'pet = potential evapotranspiration [mm/month]',
                    'tas': 'tave = near-surface average temperature (degrees Celsius)'}
NMETRICS = len(METRIC_LIST)

def generate_mscnfr_hwsd_wthr(form):
    """
    create 10 arc minute data
    """
    if hasattr(form, 'hwsd_mu_globals'):
        bbox = form.hwsd_mu_globals.bbox
    else:
        print(WARNING_STR + 'No HWSD data available')
        return

    form.w_abandon.setCheckState(0)
    max_cells = int(form.w_max_cells.text())
    output_dir = join(form.w_out_dir.text(), 'hwsd')  # typically  G:\MscnfrOutpts\WorldClim'
    strt_yr = int(form.w_sim_strt_yr.text())  # start and end year, typically 1981, 2080
    end_yr = int(form.w_sim_end_yr.text())

    # weather choice
    # ==============
    sim_strt_year = 2001
    this_gcm = form.w_combo10w.currentText()
    scnr = form.w_combo10.currentText()

    fut_wthr_set = this_gcm + '_' + scnr
    sim_end_year = form.wthr_sets[fut_wthr_set]['year_end']

    region = 'HWSD'
    crop_name = None
    climgen = ClimGenNC(form, region, crop_name, sim_strt_year, sim_end_year, this_gcm, scnr)

    hist_wthr_dsets, fut_wthr_dsets = open_wthr_NC_sets(climgen)
    wthr_slices, ntime_steps, lats, lons = read_hwsd_wthr_dsets(climgen, hist_wthr_dsets, fut_wthr_dsets,
                                                                                        bbox, strt_yr, end_yr)

    mess = 'Will generate {} csv files consisting of metrics'.format(len(METRIC_LIST))
    print(mess + ' and a meteogrid file consisting of grid coordinates')

    grid_size = climgen.hist_wthr_set_defn['resol_lon']
    miscan_fobjs, writers = _open_csv_file_sets(METRIC_LIST + ['meteogrid'], output_dir, lats[0], lats[-1],
                                                                    lons[0], lons[-1], grid_size, strt_yr, end_yr)

    # for each location, where there is data, build set of data
    # =========================================================
    n_nodata, n_not_inside, n_with_data, ntotal = 4*[0]
    last_time = time()

    # create 10 arc minute world data
    # ===============================
    for lat_indx, lat in enumerate(lats):

        for lon_indx, lon in enumerate(lons):
            if not check_cell_within_csv(form.hwsd_mu_globals.data_frame, lat, lon):
                n_not_inside += 1
                continue

            pettmp, data_flag = _fetch_wthr_data(wthr_slices, lat_indx, lon_indx)

            # write data
            # ==========
            if data_flag:
                n_with_data += 1
                pettmp['meteogrid'] = list([lon, lat])
                _write_mscnfr_out(pettmp, writers, ntime_steps)
                if n_with_data >= max_cells:
                    break
            else:
                n_nodata += 1

            if n_with_data >= max_cells:
                last_time = update_wthr_progress(last_time, n_with_data, n_nodata, ntotal, ntotal, ntotal, region)
                break

    # close netCDF and csv files
    # ==========================
    for var_name in METRIC_LIST + ['meteogrid']:
        miscan_fobjs[var_name].close()

    print('\nAll done - not inside: {}'.format(n_not_inside))

    return

def generate_mscnfr_wrld_wthr(form):
    """
    C
    """
    form.w_abandon.setCheckState(0)
    max_cells = int(form.w_max_cells.text())
    output_dir = join(form.w_out_dir.text(), 'wrld')   # typically  G:\MscnfrOutpts\WorldClim'
    strt_yr = int(form.w_sim_strt_yr.text())  # start and end year, typically 1981, 2080
    end_yr = int(form.w_sim_end_yr.text())

    # weather choice
    # ==============
    sim_strt_year = 2001

    fut_wthr_set = form.weather_set_linkages['WrldClim'][1]
    sim_end_year = form.wthr_sets[fut_wthr_set]['year_end']

    this_gcm = form.w_combo10w.currentText()
    scnr =  form.w_combo10.currentText()

    region = 'World'
    crop_name = None
    climgen = ClimGenNC(form, region, crop_name, sim_strt_year, sim_end_year, this_gcm, scnr)
    nlats = len(climgen.fut_wthr_set_defn['latitudes'])
    nlons = len(climgen.fut_wthr_set_defn['longitudes'])

    hist_wthr_dsets, fut_wthr_dsets = open_wthr_NC_sets(climgen)
    wthr_slices, ntime_steps = read_all_wthr_dsets(climgen, hist_wthr_dsets, fut_wthr_dsets, strt_yr, end_yr)

    mess = 'Will generate {} csv files consisting of metrics'.format(len(METRIC_LIST))
    print(mess + ' and a meteogrid file consisting of grid coordinates')

    lat_min = climgen.fut_wthr_set_defn['latitudes'][1]
    lat_max = climgen.fut_wthr_set_defn['latitudes'][-2]
    lon_min = climgen.fut_wthr_set_defn['longitudes'][1]
    lon_max = climgen.fut_wthr_set_defn['longitudes'][-2]
    grid_size = 0.5
    miscan_fobjs, writers = _open_csv_file_sets(METRIC_LIST + ['meteogrid'], output_dir, lat_min, lat_max,
                                                                        lon_min, lon_max, grid_size, strt_yr, end_yr)
    # for each location, where there is data, build set of data
    # =========================================================
    n_nodata, n_with_data, ntotal = 3*[0]
    last_time = time()

    # create 0.5 degree world data
    # ============================
    for lat_indx in range(1, nlats, 3):
        lat = climgen.fut_wthr_set_defn['latitudes'][lat_indx]

        for lon_indx in range(1, nlons, 3):
            lon = climgen.fut_wthr_set_defn['longitudes'][lon_indx]

            pettmp, data_flag = _fetch_wthr_data(wthr_slices, lat_indx, lon_indx)

            # write data
            # ==========
            if data_flag:
                n_with_data += 1
                pettmp['meteogrid'] = list([lon, lat])
                _write_mscnfr_out(pettmp, writers, ntime_steps)
                if n_with_data >= max_cells:
                    break
            else:
                n_nodata += 1

            if n_with_data >= max_cells:
                last_time = update_wthr_progress(last_time, n_with_data, n_nodata, ntotal, ntotal, ntotal, region)
                break

    # close netCDF and csv files
    # ==========================
    for var_name in METRIC_LIST + ['meteogrid']:
        miscan_fobjs[var_name].close()

    print('\nAll done...')

    return

def _fetch_wthr_data(wthr_slices, lat_indx, lon_indx):

    """
    check each metric and if data is not present then return
    """
    pettmp_ret = {}
    for metric in METRIC_LIST :
        pettmp = wthr_slices[metric][:, lat_indx, lon_indx]

        # check first 10 values
        # =====================
        data_flag = True
        for timindx in range(10):
            if is_masked(pettmp[timindx]):
                data_flag = False
                break

        pettmp_ret[metric] = pettmp

    return pettmp_ret, data_flag

def _open_csv_file_sets(var_names, out_folder, lat_min, lat_max, lon_min, lon_max, grid_size,
                                                 start_year, stop_year, out_suffx = '.txt', remove_flag = True):
    """
    write each variable to a separate file
    """
    if not isdir(out_folder):
        print(out_folder + ' does not exist - please reselect output folder')
        return None, None

    header_recs = []
    header_recs.append('GridSize    ' + str(round(grid_size,5)))
    header_recs.append('LongMin     ' + str(lon_min))
    header_recs.append('LongMax     ' + str(lon_max))
    header_recs.append('LatMin      ' + str(lat_min))
    header_recs.append('LatMax      ' + str(lat_max))
    header_recs.append('StartYear   ' + str(start_year))
    header_recs.append('StopYear    ' + str(stop_year))

    '''
    short_fnames = dict ( {'humidity': 'UKCP18_RHumidity','radiat_short': 'UKCP18_RadShortWaveNet', 'precip': 'precip',
                           'tempmin': 'Tmin', 'tempmax': 'Tmax', 'wind': 'Wind',
                            'cld': 'cloud','dtr': 'temprange', 'tmp': 'temperature', 'pre': 'precip', 'pet': 'pet'})
    '''
    # for each file write header records
    # ==================================
    miscan_fobjs = {}; writers = {}
    for var_name in var_names:
        file_name = join(out_folder, var_name + out_suffx)
        if remove_flag:
            if exists(file_name):
                remove(file_name)

        miscan_fobjs[var_name] = open(file_name, 'w', newline='')
        writers[var_name] = writer(miscan_fobjs[var_name])

        if var_name == 'meteogrid':
            hdr_recs = header_recs[0:5]
        else:
            hdr_recs = header_recs

        for header_rec in hdr_recs:
            writers[var_name].writerow(list([header_rec]))

    return miscan_fobjs, writers

def _write_mscnfr_out(pettmp, writers, num_time_steps, meteogrid_flag = True):
    """
    write each variable to a separate file
    """
    for var_name in pettmp.keys():

        # meteogrid is passed as a list comprising lat/long
        # =================================================
        if var_name == 'meteogrid':
            if meteogrid_flag:
                newlist = ['{:10.4f}'.format(val) for val in pettmp[var_name]]
                rec = ''.join(newlist)
                writers[var_name].writerow(list([rec]))
        else:
            # other metrics are passed as an ndarray which we convert to an integers after times by 10
            # ========================================================================================
            newlist = ['{:8d}'.format(int(10.0*val.item())) for val in pettmp[var_name]]
            for indx in range(0, num_time_steps, 12):
                rec = ''.join(newlist[indx:indx + 12])
                writers[var_name].writerow(list([rec]))

    return
