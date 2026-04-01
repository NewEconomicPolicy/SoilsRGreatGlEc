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
from numpy.ma.core import MaskedConstant, MaskError
from warnings import filterwarnings
from time import time
from netCDF4 import Dataset
from numpy import array
from time import strftime, sleep
from _datetime import datetime
from numpy import arange

from getClimGenNC import ClimGenNC
from getClimGenFns import open_wthr_NC_sets

from getClimGenFns import update_fetch_progress

NULL_VALUE = -9999
GRANULARITY = 120

ERROR_STR = '*** Error *** '
WARNING_STR = '*** Warning *** '

MISSING_VALUE = -999.0
METRIC_LIST = ['precip', 'tas']
PERIOD_LIST = ['hist', 'fut']
ALL_METRICS = ['prec','tave']
METRIC_VARNAMES = {'precip': 'prec', 'tas': 'tave'}

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
    strt_yr = 1981
    end_yr = 2080

    strt_yr_hist = climgen.hist_wthr_set_defn['year_start']
    end_yr_hist = climgen.hist_wthr_set_defn['year_end']
    strt_indx_hist = (strt_yr - strt_yr_hist) * 12

    strt_yr_fut = climgen.fut_wthr_set_defn['year_start']
    strt_indx_fut = (end_yr_hist - strt_yr_fut + 1) * 12
    end_indx_fut = (end_yr - strt_yr_fut + 1) * 12

    wthr_slices = {}
    for period in PERIOD_LIST:
        wthr_slices[period] = {}

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

def wldclim_dset_resize(form):
    """
    called from GUI;
    """

    # weather choice
    # ==============
    scnr = form.w_combo10.currentText()
    this_gcm = form.w_combo10w.currentText()

    fut_strt_year = form.wthr_sets[this_gcm + '_' + scnr]['year_start']
    fut_end_year = form.wthr_sets[this_gcm + '_' + scnr]['year_end']
    nmnths_fut = 12 * (fut_end_year - fut_strt_year + 1)

    hist_wthr_set = 'WrldClim_hist'
    hist_strt_year = form.wthr_sets[hist_wthr_set]['year_start']
    hist_end_year = form.wthr_sets[hist_wthr_set]['year_end']
    nmnths_hist = 12 * (hist_end_year - hist_strt_year + 1)

    region, crop_name = 2 * [None]
    climgen = ClimGenNC(form, region, crop_name, fut_strt_year, fut_end_year, this_gcm, scnr)

    _make_resize_dirs(climgen, this_gcm, scnr)

    for metric in METRIC_LIST:
        clone_fn = climgen.fut_wthr_set_defn['ds_' + metric]
        out_fn = climgen.fut_wthr_set_defn['ds_05_' + metric]
        _create_resize_nc(clone_fn, out_fn, METRIC_VARNAMES[metric], fut_strt_year, nmnths_fut)

        clone_fn = climgen.hist_wthr_set_defn['ds_' + metric]
        out_fn = climgen.hist_wthr_set_defn['ds_05_' + metric]
        _create_resize_nc(clone_fn, out_fn, METRIC_VARNAMES[metric], hist_strt_year, nmnths_hist)

    nlats = len(climgen.fut_wthr_set_defn['latitudes'])
    nlons = len(climgen.fut_wthr_set_defn['longitudes'])

    hist_wthr_dsets, fut_wthr_dsets = open_wthr_NC_sets(climgen)
    wthr_slices = read_all_wthr_dsets(climgen, hist_wthr_dsets, fut_wthr_dsets)
    print('\nfinished reading slices' )

    return

def _create_resize_nc(clone_fn, out_fn, metric, strt_yr=None, nmnths=None):
    """
    create new NC file and copy contents of clone to same
    """
    if metric not in ALL_METRICS:
        print(WARNING_STR + 'Metric must be in ' + str(ALL_METRICS))
        return None

    if strt_yr is None:
        time_dmnsn_flag = False     # time dimension flag
    else:
        time_dmnsn_flag = True

    print('\ncreating new dataset: ' + out_fn)
    try:
        nc_dset = Dataset(out_fn, 'w', format='NETCDF4_CLASSIC')
    except PermissionError as err:
        print(err)
        return None

    clone_dset = Dataset(clone_fn, 'r')
    nlats = clone_dset.variables['lat'].size
    lats = array(clone_dset.variables['lat'])
    resol_lat = (lats[-1] - lats[0]) / (lats.size - 1)

    new_lats = []
    for ic in range(1, nlats, 3):
        new_lats.append(lats[ic])

    nlons = clone_dset.variables['lon'].size
    lons = array(clone_dset.variables['lon'])
    resol_lon = (lons[-1] - lons[0]) / (lons.size - 1)

    new_lons = []
    for ic in range(1, nlons, 3):
        new_lons.append(lons[ic])

    # create global attributes
    # ========================
    date_stamp = strftime('%H:%M %d-%m-%Y')
    nc_dset.attributation = 'Created at ' + date_stamp + ' from WorldClim global climate data'
    nc_dset.history = 'XXXX'

    # setup time dimension - assume daily
    # ===================================
    mess = 'Number of longitudes: {}\tlatitudes: {}'.format(nlons, nlats)
    if time_dmnsn_flag:
        atimes, atimes_strt, atimes_end = _generate_mnthly_atimes(strt_yr, nmnths)  # create ndarrays
        mess += '\tmonths: {}'.format(nmnths)

    print(mess)

    # create dimensions
    # =================
    nc_dset.createDimension('lat', len(new_lats))
    nc_dset.createDimension('lon', len(new_lons))
    if time_dmnsn_flag:
        nc_dset.createDimension('time', len(atimes))
        nc_dset.createDimension('bnds', 2)

    # create the variable (4 byte float in this case)
    # createVariable method has arguments:
    #   first: name of the , second: datatype, third: tuple with the name (s) of the dimension(s).
    # ===================================
    lats_var = nc_dset.createVariable('lat', 'f4', ('lat',))
    lats_var.description = 'degrees of latitude North to South in ' + str(resol_lat) + ' degree steps'
    lats_var.units = 'degrees_north'
    lats_var.long_name = 'latitude'
    lats_var.axis = 'Y'
    lats_var[:] = new_lats

    lons_var = nc_dset.createVariable('lon', 'f4', ('lon',))
    lons_var.description = 'degrees of longitude West to East in ' + str(resol_lon) + ' degree steps'
    lons_var.units = 'degrees_east'
    lons_var.long_name = 'longitude'
    lons_var.axis = 'X'
    lons_var[:] = new_lons

    times = nc_dset.createVariable('time', 'f4', ('time',))
    times.units = 'days since 1900-01-01'
    times.calendar = 'standard'
    times.axis = 'T'
    times.bounds = 'time_bnds'
    times[:] = atimes

    # create time_bnds variable
    # =========================
    time_bnds = nc_dset.createVariable('time_bnds', 'f4', ('time', 'bnds'), fill_value=MISSING_VALUE)
    time_bnds._ChunkSizes = 1, 2
    time_bnds[:, 0] = atimes_strt
    time_bnds[:, 1] = atimes_end

    # create the time dependent metrics and assign default data
    # =========================================================
    var_metric = nc_dset.createVariable(metric, 'f4', ('time', 'lat', 'lon'), fill_value=MISSING_VALUE)
    if metric == 'prec':
        var_metric.units = 'mm'
        var_metric.long_name = 'Total precipitation'
    elif metric == 'tmax':
        var_metric.units = 'Degrees C'
        var_metric.long_name = 'Average maximum temperature'
    elif metric == 'tmin':
        var_metric.units = 'Degrees C'
        var_metric.long_name = 'Average minimum temperature'
    elif metric == 'tave':
        var_metric.units = 'Degrees C'
        var_metric.long_name = 'Average temperature'
    elif metric == 'srad':
        var_metric.units = 'kJ m-2 day-1'
        var_metric.long_name = 'Solar radiation'
    elif metric == 'wind':
        var_metric.units = 'm s-1'
        var_metric.long_name = 'Wind speed'

    # var_metric.alignment = clone_dset.variables['Band1'].alignment
    var_metric.missing_value = MISSING_VALUE

    # close netCDF files
    # ================
    nc_dset.sync()
    nc_dset.close()
    clone_dset.close()

    return out_fn

def _make_resize_dirs(climgen, this_gcm, scnr):
    """
    make new directories for o.5 derees datasets
    """
    base_dir_fut = climgen.fut_wthr_set_defn['base_dir']
    base_05_fut = base_dir_fut.replace('WrldClim_', 'WrldClim_05_')
    if not exists(base_05_fut):
        makedirs(base_05_fut)
    climgen.fut_wthr_set_defn['base_05_fut'] = base_05_fut

    ds_precip_shrt = split(climgen.fut_wthr_set_defn['ds_precip'])[1]
    climgen.fut_wthr_set_defn['ds_05_precip'] = join(base_05_fut, ds_precip_shrt.replace('10m', '30m'))
    ds_tas_shrt = split(climgen.fut_wthr_set_defn['ds_tas'])[1]
    climgen.fut_wthr_set_defn['ds_05_tas'] = join(base_05_fut, ds_tas_shrt.replace('10m', '30m'))

    base_dir_hist = climgen.hist_wthr_set_defn['base_dir']
    base_05_hist = base_dir_hist.replace('WrldClim_', 'WrldClim_05_')
    if not exists(base_05_hist):
        makedirs(base_05_hist)
    climgen.hist_wthr_set_defn['base_05_hist'] = base_05_hist

    ds_precip_shrt = split(climgen.hist_wthr_set_defn['ds_precip'])[1]
    climgen.hist_wthr_set_defn['ds_05_precip'] = join(base_05_hist, ds_precip_shrt.replace('10m', '30m'))
    ds_tas_shrt = split(climgen.hist_wthr_set_defn['ds_tas'])[1]
    climgen.hist_wthr_set_defn['ds_05_tas'] = join(base_05_hist, ds_tas_shrt.replace('10m', '30m'))

    return

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
