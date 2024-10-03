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

__prog__ = 'wthr_generation_fns'
__version__ = '0.0.1'
__author__ = 's03mm5'

from time import time
from locale import LC_ALL, setlocale, format_string

from getClimGenNC import ClimGenNC
from getClimGenFns import (fetch_WrldClim_data, open_wthr_NC_sets, get_wthr_nc_coords, join_hist_fut_to_sim_wthr)
from make_site_spec_files_classes import MakeSiteFiles
from prepare_ecosse_files import make_wthr_files
from glbl_ecsse_low_level_fns import check_run_mask, set_region_study, update_wthr_progress
from mngmnt_fns_and_class import create_proj_data_defns, open_proj_NC_sets, close_proj_NC_sets

WARNING_STR = '*** Warning *** '

def generate_all_weather(form, all_regions_flag = True):
    """

    """
    max_cells = int(form.w_max_cells.text())
    crop_name = form.combo00b.currentText()

    # check resolution
    # ================
    permitted_resols = list([0.25, 0.5])
    req_resol_deg = form.req_resol_deg
    if req_resol_deg not in permitted_resols:
        print('Only resolutions of ' + str(permitted_resols) + ' degrees are permitted')
        return

    resol_d2 = req_resol_deg/2

    # verify mask, sowing, yields, fertiliser NC files
    # ================================================
    proj_data_defns = create_proj_data_defns(form.setup['proj_path'], crop_name, req_resol_deg)
    if proj_data_defns is None:
        print('*** Error *** verifing NC files for study ' + form.setup['region_study'])
        return

    mask_defn, yield_defn, dates_defn, fert_defns = proj_data_defns
    del(proj_data_defns)

    # define study
    # ============
    set_region_study(form)

    start_from_1801 = True
    sim_strt_year = 1801

    fut_wthr_set = form.weather_set_linkages['WrldClim'][1]
    sim_end_year = form.wthr_sets[fut_wthr_set]['year_end']

    for wthr_set in form.weather_set_linkages['WrldClim']:
        this_gcm, scnr = wthr_set.split('_')

        for irow, region in enumerate(form.regions['Region']):
            lon_ll, lon_ur, lat_ll, lat_ur, wthr_dir = form.regions.iloc[irow][1:]
            bbox =  list([lon_ll, lat_ll, lon_ur, lat_ur])

            climgen  = ClimGenNC(form, region, crop_name, sim_strt_year, sim_end_year)

            # identify geo-extent for this run
            # ================================
            lat_ur_indx, lon_ur_indx, ret_code = mask_defn.get_nc_coords(lat_ur, lon_ur)
            lat_ll_indx, lon_ll_indx, ret_code = mask_defn.get_nc_coords(lat_ll, lon_ll)
            lat_ur_indx, ntotal_grow = check_run_mask(mask_defn, lon_ll_indx, lat_ll_indx, lon_ur_indx, lat_ur_indx)
            if ntotal_grow == 0:
                print('Nothing to grow for this AOI')
                return

            #  open required NC sets
            # ======================
            open_proj_NC_sets(mask_defn, yield_defn, dates_defn, fert_defns)
            hist_wthr_dsets, fut_wthr_dsets = open_wthr_NC_sets(climgen)

            # main AOI traversal loops - outer: North to South, inner: East to West
            # ========================
            start_at_band = 0
            print('Starting at band {}'.format(start_at_band))

            nbands = lat_ur_indx - lat_ll_indx + 1
            last_time = time()
            ncmpltd = 0
            nskipped = 0
            warning_count = 0
            ngrowing = 0; nno_grow = 0
            for nband, lat_indx in enumerate(range(lat_ur_indx, lat_ll_indx - 1, -1)):

                lat = mask_defn.lats[lat_indx]
                ngrow_this_band = 0

                for lon_indx in range(lon_ll_indx, lon_ur_indx + 1):
                    lon = mask_defn.lons[lon_indx]

                    mask_val = mask_defn.nc_dset.variables['cropmask'][lat_indx, lon_indx]
                    crop_grown = int(mask_val.item())
                    if crop_grown == 0:
                        nno_grow += 1
                        continue

                    ngrowing += 1
                    ngrow_this_band += 1

                    form.setup['bbox'] = list([lon - resol_d2, lat - resol_d2, lon + resol_d2, lat + resol_d2])

                    # generate weather dataset indices which enclose the AOI for this band
                    # ====================================================================
                    hist_lat_indx, hist_lon_indx = get_wthr_nc_coords(climgen.hist_wthr_set_defn, lat, lon)
                    fut_lat_indx, fut_lon_indx   = get_wthr_nc_coords(climgen.fut_wthr_set_defn, lat, lon)
                    if hist_lat_indx < 0 or fut_lat_indx < 0:
                        nskipped += 1
                        continue

                    # Get future and historic weather data
                    # ====================================
                    pettmp_hist = fetch_WrldClim_data(form.lgr, lat, lon, climgen, hist_wthr_dsets,
                                                      hist_lat_indx, hist_lon_indx, hist_flag = True)
                    pettmp_fut =  fetch_WrldClim_data(form.lgr, lat, lon, climgen, fut_wthr_dsets,
                                                      fut_lat_indx, fut_lon_indx)
                    if pettmp_fut is None or pettmp_hist is None:
                        nskipped += 1
                        continue

                    # generate sets of Ecosse files
                    # =============================
                    if len(pettmp_fut) == 0 or len(pettmp_hist) == 0:
                        ret_code = 'check weather at lat: {}\tlon:{}'.format(lat, lon)
                        form.lgr.info(ret_code)
                        warning_count += 1
                    else:
                        # create weather for simulated years
                        # ==================================
                        pettmp_sim = join_hist_fut_to_sim_wthr(climgen, pettmp_hist, pettmp_fut, start_from_1801)
                        site_obj = MakeSiteFiles(form, climgen, comments=True)
                        make_wthr_files(site_obj, lat, lon, climgen, pettmp_hist, pettmp_sim)
                        ncmpltd += 1

                    last_time = update_wthr_progress(last_time, ncmpltd, nskipped, ntotal_grow, ngrowing, nno_grow,
                                                                                                                region)
                    if ncmpltd >= max_cells:
                        break

                # finished this band - report progress
                # ====================================
                mess = 'Processed band {} of {} bands for lat: {}\tN growing locations: {}'.format(nband,
                                                                                nbands, lat, ngrow_this_band)
                form.lgr.info(mess)
                if ncmpltd >= max_cells:
                    print('\nFinishing run after {} cells completed'.format(ncmpltd))
                    break

            # close NC files
            # ==============
            close_proj_NC_sets(mask_defn, yield_defn, dates_defn, fert_defns)
            for metric in list(['precip', 'tas']):
                hist_wthr_dsets[metric].close()
                fut_wthr_dsets[metric].close()

            ntotal_str = format_string('%d', ntotal_grow, grouping=True)
            print('Completed Region: {}\tCrop: {}\tLocations - growing: {}\tno grow: {}\ttotal: {}\t {}%\n'
                            .format(region,  crop_name, ngrowing, nno_grow, ntotal_str, round(100*(ngrowing/ntotal_grow),2)))
    return