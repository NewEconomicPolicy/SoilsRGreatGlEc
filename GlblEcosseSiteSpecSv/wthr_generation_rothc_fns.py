"""
#-------------------------------------------------------------------------------
# Name:
# Purpose:     consist of high level functions invoked by main GUI
# Author:      Mike Martin
# Created:     11/12/2015
# Licence:     <your licence>
#-------------------------------------------------------------------------------
#
"""
__prog__ = 'wthr_generation_rothc_fns'
__version__ = '0.0.1'
__author__ = 's03mm5'

from os import mkdir
from os.path import split, join, exists
from numpy.ma import is_masked
from netCDF4 import Dataset
from time import time

from getClimGenNC import ClimGenNC
from getClimGenFns import (fetch_WrldClim_data, open_wthr_NC_sets, get_wthr_nc_coords, join_hist_fut_to_sim_wthr)
from make_site_spec_files_classes import MakeSiteFiles
from glbl_ecsse_low_level_fns import update_wthr_rothc_progress

from thornthwaite import thornthwaite

ERROR_STR = '*** Error *** '
WARNING_STR = '*** Warning *** '
QUICK_FLAG = False       # forces break from loops after max cells reached in first GCM and SSP
NC_FROM_TIF_FN ='E:\\Saeed\\GSOCmap_0.25.nc'

def generate_rothc_weather(form):
    """
    C
    """
    max_cells = int(form.w_max_cells.text())

    # check resolution
    # ================
    permitted_resols = list([0.25, 0.5])
    req_resol_deg = form.req_resol_deg
    if req_resol_deg not in permitted_resols:
        print('Only resolutions of ' + str(permitted_resols) + ' degrees are permitted')
        return

    resol_d2 = req_resol_deg/2

    # define study
    # ============
    sims_dir = form.setup['sims_dir']
    proj_dir = split(sims_dir)[0]
    sim_strt_year = 1801

    fut_wthr_set = form.weather_set_linkages['WrldClim'][1]
    sim_end_year = form.wthr_sets[fut_wthr_set]['year_end']

    # for each GCM and SSP dataset group e.g. UKESM1-0-LL 585
    # =======================================================
    print('')
    for wthr_set in form.weather_set_linkages['WrldClim']:
        this_gcm, scnr = wthr_set.split('_')
        if scnr == 'hist':  # apply filter
            continue
        elif scnr != '585':
            if this_gcm != 'UKESM1-0-LL':
                continue

        # process complete dataset
        # ========================
        wthr_set = form.wthr_sets[wthr_set]
        strt_year = wthr_set['year_start']
        end_year  = wthr_set['year_end']
        ds_precip = wthr_set['ds_precip']
        ds_tas = wthr_set['ds_tas']

        hist_wthr_dsets, fut_wthr_dsets = dict(), dict()
        for metric, ds_fname in zip(list(['precip', 'tas']), list(['ds_precip', 'ds_tas'])):
            # hist_wthr_dsets[metric] = Dataset(hist_wthr_set_defn[ds_fname])
            fut_wthr_dsets[metric] = Dataset(wthr_set[ds_fname])

        ntotal_wrttn = 0
        '''
        for lat_indx, lat in enumerate(wthr_set['longitudes']):
            for lon_indx, lon in enumerate(wthr_set['latitudes']):
                ntotal_wrttn += 1
        '''
        mess = '\nProcessing weather set: ' + this_gcm + '\tScenario: ' + scnr
        print(mess)
        mess = 'Completed weather set: ' + this_gcm + '\tScenario: ' + scnr
        print(mess + '\tfiles written: ' + format(ntotal_wrttn, ',') + ' \n')

    region, crop_name = 2*[None]
    climgen = ClimGenNC(form, region, crop_name, sim_strt_year, sim_end_year, this_gcm, scnr)
    hist_wthr_dsets, fut_wthr_dsets = open_wthr_NC_sets(climgen)

    # check each value, discarding Nans
    # =================================
    dset = Dataset(NC_FROM_TIF_FN)
    latvar = dset.variables['lat']
    lonvar = dset.variables['lon']
    last_time = time()

    nmasked, noutbnds, nnodata, ncmpltd = 4*[0]
    for lat_indx, lat_ma in enumerate(latvar):
        for lon_indx, lon_ma in enumerate(lonvar):
            lat = lat_ma.item()
            lon = lon_ma.item()
            last_time = update_wthr_rothc_progress(last_time, nmasked, noutbnds, nnodata, ncmpltd)
            soil_carb = dset.variables['Band1'][lat_indx][lon_indx]
            if is_masked(soil_carb):
                val = soil_carb.item()
                nmasked += 1
            else:
                # generate weather dataset indices which enclose the AOI for this band
                # ====================================================================
                hist_lat_indx, hist_lon_indx = get_wthr_nc_coords(climgen.hist_wthr_set_defn, lat, lon)
                fut_lat_indx, fut_lon_indx = get_wthr_nc_coords(climgen.fut_wthr_set_defn, lat, lon)
                if hist_lat_indx < 0 or fut_lat_indx < 0:
                    noutbnds += 1
                    continue

                # Get future and historic weather data
                # ====================================
                pettmp_hist = fetch_WrldClim_data(form.lgr, lat, lon, climgen, hist_wthr_dsets,
                                                  hist_lat_indx, hist_lon_indx, hist_flag=True)
                if pettmp_hist is None:
                    pettmp_fut = None
                else:
                    pettmp_fut = fetch_WrldClim_data(form.lgr, lat, lon, climgen, fut_wthr_dsets,
                                                     fut_lat_indx, fut_lon_indx)
                if pettmp_fut is None or pettmp_hist is None:
                    nnodata += 1
                    continue
                else:
                    pettmp_sim = join_hist_fut_to_sim_wthr(climgen, pettmp_hist, pettmp_fut)

                # create weather
                # ==============
                site_obj = MakeSiteFiles(form, climgen)
                make_rthc_wthr_files(site_obj, lat, lon, climgen, pettmp_hist, pettmp_sim)
                ncmpltd += 1
                ntotal_wrttn += 1
                if ncmpltd >= max_cells:
                    break

    dset.close()

    print('Finished RothC weather generation - total number of sets written: {}'.format(ntotal_wrttn))

    return

def make_rthc_wthr_files(site, lat, lon, climgen, pettmp_hist, pettmp_sim):
    """
    write a RothC weather dataset
    """
    out_dir = 'E:\\Saeed\\outputs'
    if not exists(out_dir):
        mkdir(out_dir)

    with open(join(out_dir, 'fnames.txt'), 'w') as fobj:
        fobj.write('From Wthe orldClim database of high spatial resolution global weather and climate data.')
        fobj.write('\n.tave = near-surface average temperature (degrees Celsius)')
        fobj.write('\nPeriod=2021-2120 Variable=.tave')
        fobj.write('\n[Long= -11.00,  32.00] [Lati=  34.00,  72.00] [Grid X,Y= 258, 228]')
        fobj.write('\n[Boxes=   31143] [Years=2021-2120] [Multi=    0.1000] [Missing=-999]')
        fobj.write('\nGrid-ref=   4, 109')
        fobj.flush()

    return
