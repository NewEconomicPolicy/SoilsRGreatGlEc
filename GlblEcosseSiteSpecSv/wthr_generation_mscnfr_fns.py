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
from os.path import isdir, join, exists, lexists, normpath, split
from pathlib import Path
from numpy.ma import is_masked
from netCDF4 import Dataset
from csv import writer, reader
from time import time
from PyQt5.QtWidgets import QApplication

from wthr_generation_misc_fns import read_all_wthr_dsets, fetch_WrldClim_sngl_data, fetch_WrldClim_area_data
from getClimGenNC import ClimGenNC
from getClimGenFns import (fetch_WrldClim_data, fetch_WrldClim_NC_data, associate_climate,
                           open_wthr_NC_sets, get_wthr_nc_coords, join_hist_fut_to_sim_wthr)
from thornthwaite import thornthwaite
from glbl_ecsse_low_level_fns import update_wthr_progress

ERROR_STR = '*** Error *** '
WARNING_STR = '*** Warning *** '

GRANULARITY = 120

PERIOD_LIST = ['hist', 'fut']
METRIC_LIST = list(['precip', 'tas', 'pet'])
METRIC_DESCRIPS = {'precip': 'precip = total precipitation (mm)',
                    'pet': 'pet = potential evapotranspiration [mm/month]',
                    'tas': 'tave = near-surface average temperature (degrees Celsius)'}
NMETRICS = len(METRIC_LIST)

def generate_mscnfr_wthr(form):
    """
    called from GUI; based on generate_banded_sims from HoliSoilsSpGlEc project
    GSOCmap_0.25.nc organic carbon has latitiude extant of 83 degs N, 56 deg S
    """
    form.w_abandon.setCheckState(0)
    max_cells = int(form.w_max_cells.text())
    read_all_flag = form.w_read_all.isChecked()

    # weather choice
    # ==============
    sim_strt_year = 2001

    fut_wthr_set = form.weather_set_linkages['WrldClim'][1]
    sim_end_year = form.wthr_sets[fut_wthr_set]['year_end']

    this_gcm = form.w_combo10w.currentText()
    scnr =  form.w_combo10.currentText()

    region, crop_name = 2 * [None]
    climgen = ClimGenNC(form, region, crop_name, sim_strt_year, sim_end_year, this_gcm, scnr)
    nlats = len(climgen.fut_wthr_set_defn['latitudes'])
    nlons = len(climgen.fut_wthr_set_defn['longitudes'])

    hist_wthr_dsets, fut_wthr_dsets = open_wthr_NC_sets(climgen)
    if read_all_flag:
        wthr_slices = read_all_wthr_dsets(climgen, hist_wthr_dsets, fut_wthr_dsets)

    mess = 'Will generate {} csv files consisting of metrics'.format(len(METRIC_LIST))
    print(mess + ' and a meteogrid file consisting of grid coordinates')

    lat_min, lat_max = 2*[None]
    var_names = ['precip', 'tas']
    output_dir = 'G:\\MscnfrOutpts\\WorldClim'
    miscan_fobjs, writers = _open_csv_file_sets(var_names, output_dir, lat_min, lat_max)

    # for each location, where there is data, build set of data
    # =========================================================
    num_nodata, num_with_data = 2*[0]
    last_time = time()
    for lat_indx in range(1, nlats, 3):
        lat = climgen.fut_wthr_set_defn['latitudes'][lat_indx]

        for lon_indx in range(1, nlons, 3):
            pettmp = {}
            lon = climgen.fut_wthr_set_defn['longitudes'][lon_indx]

            for period in PERIOD_LIST:
                pettmp[period] = {}
                for metric in METRIC_LIST:
                    if metric == 'pet':
                        continue
                    pettmp[period][metric] = wthr_slices[period][metric][:, lat_indx, lon_indx]

            # write data
            # ==========
            if pettmp == None:
                num_nodata += 1
            else:
                num_with_data += 1
                pettmp['meteogrid'] = list([lon, lat])
                write_mscnfr_out(pettmp, writers, num_time_steps)
                if num_with_data >= max_cells:
                    break

            if num_with_data >= max_cells:
                last_time = update_wthr_progress(last_time, num_nodata, num_with_data, num_total, lat, lon)
                break

        # close netCDF and csv files
        # ==========================
    for var_name in var_names:
        miscan_fobjs[var_name].close()

    print('\nAll done...')

    return

def _open_csv_file_sets(var_names, out_folder, lat_min, lat_max, lon_min = -180.0, lon_max = 180, grid_size = 0.5,
            start_year = 1901, stop_year = 2019, out_suff = '.txt', remove_flag = True):

    if not isdir(out_folder):
        print(out_folder + ' does not exist - please reselect output folder')
        return None, None

    header_recs = []
    header_recs.append('GridSize    ' + str(round(grid_size,3)))
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
    miscan_fobjs = {}; writers = {}

    # for each file write header records
    # ==================================
    for var_name in var_names:
        file_name = join(out_folder, var_name + out_suff)
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

def write_mscnfr_out(pettmp, writers, num_time_steps, meteogrid_flag = True):
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
            newlist = ['{:8d}'.format(int(10.0*val)) for val in pettmp[var_name]]
            for indx in range(0, num_time_steps, 12):
                rec = ''.join(newlist[indx:indx + 12])
                writers[var_name].writerow(list([rec]))

    return
