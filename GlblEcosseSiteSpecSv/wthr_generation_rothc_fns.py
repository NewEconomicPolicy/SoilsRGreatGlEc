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

from time import time
from locale import format_string
from os.path import join, normpath, isdir, split
from os import listdir, makedirs

from netCDF4 import Dataset

from getClimGenNC import ClimGenNC
from getClimGenFns import (fetch_WrldClim_data, open_wthr_NC_sets, get_wthr_nc_coords, join_hist_fut_to_sim_wthr)
from make_site_spec_files_classes import MakeSiteFiles
from glbl_ecsse_low_level_fns import check_run_mask, set_region_study, update_wthr_progress
from prepare_ecosse_low_level import fetch_long_term_ave_wthr_recs, make_met_files
from mngmnt_fns_and_class import create_proj_data_defns, open_proj_NC_sets, close_proj_NC_sets
from hwsd_soil_class import _gran_coords_from_lat_lon

from thornthwaite import thornthwaite

ERROR_STR = '*** Error *** '
WARNING_STR = '*** Warning *** '
QUICK_FLAG = False       # forces break from loops after max cells reached in first GCM and SSP

NGRANULARITY = 120
NEXPCTD_MET_FILES = 302
MAX_BANDS = 500000
LTA_RECS_FN = 'lta_ave.txt'

SPACER_LEN = 12

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
    ntotal_wrttn = 0
    for wthr_set in form.weather_set_linkages['WrldClim']:
        this_gcm, scnr = wthr_set.split('_')
        if scnr == 'hist':  # apply filter
            continue
        elif scnr != '585':
            if this_gcm != 'UKESM1-0-LL':
                continue

        # process complete dataset
        # ========================
        wthr_set = form.wthr_sets[this_gcm]
        strt_year = wthr_set['year_start']
        end_year  = wthr_set['year_end']
        ds_precip = wthr_set['ds_precip']
        ds_tas = wthr_set['ds_tas']

        hist_wthr_dsets, fut_wthr_dsets = dict(), dict()
        for metric, ds_fname in zip(list(['precip', 'tas']), list(['ds_precip', 'ds_tas'])):
            # hist_wthr_dsets[metric] = Dataset(hist_wthr_set_defn[ds_fname])
            fut_wthr_dsets[metric] = Dataset(wthr_set[ds_fname])

        for lat_indx, lat in enumerate(wthr_set['longitudes']):
            for lon_indx, lon in enumerate(wthr_set['latitudes']):
                pass
            pass

        mess = '\nProcessing weather set: ' + this_gcm + '\tScenario: ' + scnr
        print(mess)
        print('Completed weather set: ' + this_gcm + '\tScenario: ' + scnr + '\n')

    print('Finished RothC weather generation - total number of sets written: {}'.format(ntotal_wrttn))

    return
'''
       #  open required NC sets
        # ======================
        hist_wthr_dsets, fut_wthr_dsets = open_wthr_NC_sets(climgen)
        ncmpltd = 0
        warning_count = 0
        ngrowing = 0
        nno_grow = 0
        nalrdys = 0

        # main AOI traversal loops - outer: North to South, inner: East to West
        # ========================
        last_time = time()
        for nband, lat_indx in enumerate(range(lat_ur_indx, lat_ll_indx - 1, -1)):
            if nband > MAX_BANDS:
                break

            lat = mask_defn.lats[lat_indx]

            ngrow_this_band, nalrdys_this_band, nnodata, noutbnds = 4*[0]

            for lon_indx in range(lon_ll_indx, lon_ur_indx + 1):
                lon = mask_defn.lons[lon_indx]

                mask_val = mask_defn.nc_dset.variables['cropmask'][lat_indx, lon_indx]
                crop_grown = int(mask_val.item())
                if crop_grown == 0:
                    nno_grow += 1
                    continue

                ngrow_this_band += 1

                alrdy_flag, dummy, met_fnames = _check_wthr_cell_exstnc(proj_dir, climgen, lat, lon)
                if alrdy_flag:
                    nalrdys_this_band += 1
                    continue

                form.setup['bbox'] = list([lon - resol_d2, lat - resol_d2, lon + resol_d2, lat + resol_d2])

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

                last_time = update_wthr_progress(last_time, ncmpltd, nnodata, ntotal_grow, ngrowing, nno_grow,
                                                                                                            region)
                if ncmpltd >= max_cells:
                    break

            # finished this latitude band - report progress
            # =============================================
            ngrowing += ngrow_this_band
            nalrdys += nalrdys_this_band
            mess = '\tBand {} with lat: {}\t# growing locations: {}\t'.format(nband, lat, ngrow_this_band)
            mess += 'already existing: {}\tskipped: {}'.format(nalrdys_this_band, nnodata)
            form.lgr.info(mess)
            print(mess)

            if ncmpltd >= max_cells:
                print('\nFinished checking after {} cells completed\tband: {}'.format(ncmpltd, nband))
                break

        # close NC files
        # ==============
        for metric in list(['precip', 'tas']):
            hist_wthr_dsets[metric].close()
            fut_wthr_dsets[metric].close()

        ntotal_str = format_string('%d', ntotal_grow, grouping=True)
        ntotal_prcnt = round(100 * (ngrowing / ntotal_grow), 2)
        mess = 'Completed Region: ' + region + '\tLocations - growing: '
        mess += '{}\tno grow: {}\ttotal: {}\t {}%'.format(ngrowing, nno_grow, ntotal_str, ntotal_prcnt)
        print(mess)

        if QUICK_FLAG:
            break
'''

def make_rthc_wthr_files(site, lat, lon, climgen, pettmp_hist, pettmp_sim):
    """
    generate ECOSSE historic and future weather data
    """
    gran_lat, gran_lon = _gran_coords_from_lat_lon(lat, lon)
    gran_coord = '{0:0=5g}_{1:0=5g}'.format(gran_lat, gran_lon)
    clim_dir = normpath(join(site.wthr_prj_dir, climgen.region_wthr_dir, gran_coord))
    if not isdir(clim_dir):
        makedirs(clim_dir)  # always create even if no weather data

    if pettmp_hist is None:
        return

    # calculate historic average weather
    # ==================================
    hist_lta_precip, hist_lta_tmean, hist_weather_recs = fetch_long_term_ave_wthr_recs(climgen, pettmp_hist)

    # write a single set of met files for all simulations for this grid cell
    # ======================================================================
    met_fnames = make_met_files(clim_dir, lat, climgen, pettmp_sim)  # future weather

    # create additional weather related files from already existing met files
    # =======================================================================
    irc = climgen.create_FutureAverages(clim_dir, lat, site, hist_lta_precip, hist_lta_tmean)
    lta_ave_fn = _make_lta_file(site, clim_dir)

    return

def fetch_hist_lta_from_lat_lon(proj_dir, climgen, lat, lon):
    """
    check existence of weather cell
    """
    read_lta_flag = True
    integrity_flag, hist_lta_recs, met_fnames = _check_wthr_cell_exstnc(proj_dir, climgen, lat, lon, read_lta_flag)

    return integrity_flag, hist_lta_recs, met_fnames

def _check_wthr_cell_exstnc(proj_dir, climgen, lat, lon, read_lta_flag=False):
    """
    check existence and integrity of weather cell
    allowable criteria are 1) a full set of weather files, namely 300 met files e.g. met2014s.txt, lta_ave.txt and AVEMET.DAT
                           2) an empty directory
    """
    integrity_flag = False
    hist_lta_recs = None
    met_fnames = None
    gran_lat, gran_lon = _gran_coords_from_lat_lon(lat, lon)
    gran_coord = '{0:0=5g}_{1:0=5g}'.format(gran_lat, gran_lon)

    if split(proj_dir)[1] == 'Wthr':
        clim_dir = normpath(join(proj_dir, climgen.region_wthr_dir, gran_coord))
    else:
        clim_dir = normpath(join(proj_dir, 'Wthr', climgen.region_wthr_dir, gran_coord))

    if isdir(clim_dir):
        fns = listdir(clim_dir)
        nfiles = len(fns)
        if nfiles == 0 or nfiles >= 302:
            if nfiles == 0:
                integrity_flag = True
                hist_lta_recs, met_fnames = None, None
            else:
                if 'lta_ave.txt' in fns:
                    if read_lta_flag:
                        lta_ave_fn = join(clim_dir, 'lta_ave.txt')
                        hist_lta_recs = []
                        with open(lta_ave_fn, 'r') as fave:
                            for line in fave:
                                line = line.rstrip()  # strip out all tailing whitespace
                                hist_lta_recs.append(line)

                    integrity_flag = True
                    met_fnames = fns[2:]

    return integrity_flag, hist_lta_recs, met_fnames
