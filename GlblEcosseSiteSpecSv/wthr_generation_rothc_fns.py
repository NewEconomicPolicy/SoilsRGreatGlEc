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

NC_FROM_TIF_FN ='E:\\Saeed\\GSOCmap_0.25.nc'
METRIC_LIST = list(['precip', 'tas'])
METRIC_DESCRIPS = {'precip': 'precip = total precipitation (mm)',
                    'tas': 'tave = near-surface average temperature (degrees Celsius)'}

def generate_rothc_weather(form):
    """
    C
    """
    out_dir = 'E:\\Saeed\\outputs'
    if not exists(out_dir):
        mkdir(out_dir)
    print('\nWill write Rothc dlimate data to: ' + out_dir)

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
    sim_strt_year = 2001

    fut_wthr_set = form.weather_set_linkages['WrldClim'][1]
    sim_end_year = form.wthr_sets[fut_wthr_set]['year_end']

    this_gcm = form.w_combo10w.currentText()
    scnr =  form.w_combo10.currentText()

    region, crop_name = 2*[None]
    climgen = ClimGenNC(form, region, crop_name, sim_strt_year, sim_end_year, this_gcm, scnr)
    hist_wthr_dsets, fut_wthr_dsets = open_wthr_NC_sets(climgen)

    # check each value, discarding Nans - total size of file is 618 x 1440 = 889,920 cells
    # ====================================================================================
    dset = Dataset(NC_FROM_TIF_FN)
    latvar = dset.variables['lat']
    lonvar = dset.variables['lon']
    last_time = time()

    nmasked, noutbnds, nnodata, ncmpltd, nskipped = 5*[0]
    for lat_indx, lat_ma in enumerate(latvar):
        for lon_indx, lon_ma in enumerate(lonvar):
            lat = lat_ma.item()
            lon = lon_ma.item()
            last_time = update_wthr_rothc_progress(last_time, nmasked, noutbnds, nnodata, ncmpltd, nskipped)
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

                # setup output files
                # ==================
                grid_coord = '{0:0=5g}_{1:0=5g}'.format(lat_indx, lon_indx)

                wthr_fnames = {}
                nexist = 0
                for metric in METRIC_LIST:
                    wthr_fname = metric + '_' + grid_coord + '.txt'
                    wthr_fnames[metric] = join(out_dir, wthr_fname)
                    if exists(wthr_fnames[metric]):
                        # print('File ' + wthr_fname + ' already exists - will skip')
                        nexist += 1

                # if both files exist then skip
                # =============================
                if nexist == 2:
                    nskipped += 1
                    continue

                # weather set lat/lons
                # ====================
                lat_wthr = climgen.fut_wthr_set_defn['latitudes'][fut_lat_indx]
                lon_wthr = climgen.fut_wthr_set_defn['longitudes'][fut_lon_indx]

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
                # site_obj = MakeSiteFiles(form, climgen)
                make_rthc_wthr_files(wthr_fnames, lat, lat_indx, lon, lon_indx, climgen,
                                                    lat_wthr, lon_wthr, pettmp_hist, pettmp_sim)
                ncmpltd += 1
                if ncmpltd >= max_cells:
                    break

    dset.close()

    print('Finished RothC weather generation - total number of sets written: {}'.format(ncmpltd))

    return

def make_rthc_wthr_files(wthr_fnames, lat, lat_indx, lon, lon_indx, climgen, lat_wthr, lon_wthr, pettmp_hist, pettmp_sim):
    """
    write a RothC weather dataset
    """
    hdr_recs = _fetch_header_recs(lat, lat_indx, lon, lon_indx, climgen, lat_wthr, lon_wthr)
    frst_rec, period, location_rec, box_rec, grid_ref_rec = hdr_recs

    for metric in METRIC_LIST:
        metric_descr = METRIC_DESCRIPS[metric]
        data_recs = _generate_data_recs(pettmp_sim[metric])

        with open(wthr_fnames[metric], 'w') as fobj:
            fobj.write(frst_rec)
            fobj.write('\n.' + metric_descr)
            fobj.write('\nPeriod=' + period + ' Variable=.' + metric)
            fobj.write('\n' + location_rec)
            fobj.write('\n' + box_rec)
            fobj.write('\n' + grid_ref_rec)
            for data_rec in data_recs:
                fobj.write('\n' + data_rec)
            fobj.flush()

    return

def _fetch_header_recs(lat, lat_indx, lon, lon_indx, climgen, lat_wthr, lon_wthr):
    """
    create strings for header records
    From the WorldClim database of high spatial resolution global weather and climate data.
    """
    gcm = climgen.wthr_rsrce
    scnr = climgen.fut_clim_scen
    frst_rec = 'From the WorldClim database of global weather and climate data using GCM: '
    frst_rec += gcm + '\tScenario: ' + scnr
    period = str(climgen.sim_start_year) + '-' + str(climgen.sim_end_year)
    location_rec = '[Long= ' + str(round(lon, 3)) + ', ' + str(round(lon_wthr, 3))
    location_rec += '] [Lati= ' + str(round(lat, 3)) + ', ' + str(round(lat_wthr))
    location_rec +=  '] [Grid X,Y= ' + str(lon_indx) + ', ' + str(lat_indx) + ']'
    box_rec = '[Boxes=   31143] [Years=' + period + '] [Multi=    0.1000] [Missing=-999]'
    grid_ref_rec = 'Grid-ref=  ' + str(lon_indx) + ', ' + str(lat_indx)

    return (frst_rec, period, location_rec, box_rec, grid_ref_rec)

def _generate_data_recs(pettmp):
    """
    create strings for header records
    """
    nvals = len(pettmp)
    rec_list = []
    for indx in range(0, nvals, 12):
        vals_yr = pettmp[indx: indx + 12]
        rec_str = str([round(val, 2) for val in vals_yr])
        rec_str = rec_str.replace(', ', '\t')
        rec_str = rec_str.replace(', ', '\t')
        rec_str = rec_str.replace('[','')
        rec_str = rec_str.replace(']','')
        rec_list.append(rec_str)

    return rec_list
