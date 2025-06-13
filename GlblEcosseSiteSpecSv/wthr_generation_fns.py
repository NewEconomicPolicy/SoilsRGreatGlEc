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
from locale import format_string
from os.path import join, normpath, isdir, split
from os import listdir, walk, makedirs

from getClimGenNC import ClimGenNC
from getClimGenFns import (fetch_WrldClim_data, open_wthr_NC_sets, get_wthr_nc_coords, join_hist_fut_to_sim_wthr)
from make_site_spec_files_classes import MakeSiteFiles
from glbl_ecsse_low_level_fns import check_run_mask, set_region_study, update_wthr_progress, update_avemet_progress
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

def generate_all_weather(form):
    """
    C
    """
    all_regions = form.w_all_regions.isChecked()
    if all_regions:
        region_slctd = None
    else:
        region_slctd = form.w_combo00a.currentText()


    max_cells = int(form.w_max_cells.text())
    crop_name = form.w_combo00b.currentText()

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
        print(ERROR_STR + 'verifing NC files for study ' + form.setup['region_study'])
        return

    mask_defn, yield_defn, dates_defn, fert_defns = proj_data_defns
    del proj_data_defns

    # define study
    # ============
    set_region_study(form)

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
        if scnr == 'hist' or scnr != '585':             # mod
            continue

        # for each region
        # ===============
        for irow, region in enumerate(form.regions_df['Region']):

            if region_slctd is None:
                pass
            else:
                if region_slctd != region:
                    continue

            mess = '\nProcessing weather set: ' + this_gcm + '\tScenario: ' + scnr + '\tRegion: ' + region
            mess += '\tCrop: ' + crop_name
            print(mess)

            lon_ll, lon_ur, lat_ll, lat_ur, wthr_dir_abbrv = form.regions_df.iloc[irow][1:]
            bbox = list([lon_ll, lat_ll, lon_ur, lat_ur])

            form.setup['region_wthr_dir'] = wthr_dir_abbrv
            climgen = ClimGenNC(form, region, crop_name, sim_strt_year, sim_end_year, this_gcm, scnr)

            # identify geo-extent for this run
            # ================================
            lat_ur_indx, lon_ur_indx, ret_code = mask_defn.get_nc_coords(lat_ur, lon_ur)
            lat_ll_indx, lon_ll_indx, ret_code = mask_defn.get_nc_coords(lat_ll, lon_ll)
            lat_ur_indx, ntotal_grow = check_run_mask(mask_defn, lon_ll_indx, lat_ll_indx, lon_ur_indx, lat_ur_indx)
            if ntotal_grow == 0:
                print('Nothing to grow for this AOI')
                return

            nbands = lat_ur_indx - lat_ll_indx + 1
            print('Will process {} bands'.format(nbands))

            #  open required NC sets
            # ======================

            open_proj_NC_sets(mask_defn, yield_defn, dates_defn, fert_defns)
            hist_wthr_dsets, fut_wthr_dsets = open_wthr_NC_sets(climgen)

            # main AOI traversal loops - outer: North to South, inner: East to West
            # ========================
            ncmpltd, warning_count, ngrowing, nno_grow, nalrdys = 5*[0]      # for each band
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
                    make_wthr_files(site_obj, lat, lon, climgen, pettmp_hist, pettmp_sim)
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
            close_proj_NC_sets(mask_defn, yield_defn, dates_defn, fert_defns)
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

        print('Completed weather set: ' + this_gcm + '\tScenario: ' + scnr + '\n')

    print('Finished weather generation - total number of sets written: {}'.format(ntotal_wrttn))

    return


def make_avemet_file(clim_dir, lta_precip, lta_pet, lta_tmean):
    """
    will be copied
    """
    avemet_dat = join(clim_dir, 'AVEMET.DAT')
    with open(avemet_dat, 'w') as fobj:
        for imnth, (precip, pet, tmean) in enumerate(zip(lta_precip, lta_pet, lta_tmean)):
            fobj.write('{} {} {} {}\n'.format(imnth + 1, precip, pet, tmean))

    return

def make_wthr_files(site, lat, lon, climgen, pettmp_hist, pettmp_sim):
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
    clim_dir = normpath(join(proj_dir, climgen.region_wthr_dir, gran_coord))
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

def write_avemet_files(form):
    """
    traverse each GCM and SSP dataset group e.g. UKESM1-0-LL 585
    """
    print('')
    max_cells = int(form.w_max_cells.text())
    sims_dir = form.setup['sims_dir']

    nwrote = 0
    for wthr_set in form.weather_set_linkages['WrldClim']:
        wthr_rsrce, scnr = wthr_set.split('_')
        if scnr == 'hist':  # mod
            continue

        # for each region
        # ===============
        for irow, region in enumerate(form.regions_df['Region']):
            lon_ll, lon_ur, lat_ll, lat_ur, wthr_dir_abbrv = form.regions_df.iloc[irow][1:]

            # main traversal loop
            # ===================
            region_wthr_dir = wthr_dir_abbrv + wthr_rsrce + '_' + scnr
            clim_dir = normpath(join(sims_dir, region_wthr_dir))

            mess = '\nProcessing weather set: ' + wthr_rsrce + '\tScenario: ' + scnr + '\tRegion: ' + region
            mess += '\t\tabbrev: ' + wthr_dir_abbrv + '\n\tclim_dir: ' + clim_dir
            print(mess)

            if not isdir(clim_dir):
                print(clim_dir + ' *** does not exist ***')
                break

            # step through each directory comprising ECOSSE met files
            # =======================================================
            last_time = time()
            nwrote = 0
            for drctry, subdirs, files in walk(clim_dir):
                nfiles = len(files)
                nsubdirs = len(subdirs)
                if nsubdirs > 0:  # first directory has four scenarios e.g.  Y:\GlblEcssOutputsSv\EcosseSims\AfUKESM1-0-LL_126
                    continue

                # there should be 300 met files plus lta_ave.txt and AVEMET.DAT
                # =============================================================
                last_time = update_avemet_progress(last_time, wthr_rsrce, scnr, region, nwrote)
                if nfiles >= NEXPCTD_MET_FILES:
                    continue

                # if lta_ave.txt is not present then something is wrong
                # =====================================================
                if LTA_RECS_FN in files:
                    lta_ave_fn = join(drctry, LTA_RECS_FN)
                    with open(lta_ave_fn, 'r') as flta_ave:

                        lta_recs = flta_ave.readlines()
                        vals = [float(rec.split('#')[0]) for rec in lta_recs]
                        lta_precip, lta_tmean = vals[:12], vals[12:]

                        gran_coord = split(drctry)[1]
                        gran_lat = int(gran_coord.split('_')[0])
                        cell_lat = 90.0 - gran_lat / NGRANULARITY
                        lta_pet = thornthwaite(lta_tmean, cell_lat)

                        make_avemet_file(drctry, lta_precip, lta_pet, lta_tmean)
                        nwrote += 1
                else:
                    print(WARNING_STR + LTA_RECS_FN + ' file should be present in ' + drctry)

            if nwrote >= max_cells:
                print('\nFinished checking having written {} AVEMET.DAT files'.format(nwrote))
                break

            print('Completed Region: ' + region)

        print('Completed weather set: ' + wthr_rsrce + '\tScenario: ' + scnr + '\n')

    print('Finished AVEMET creation - checked: {} cells'.format(nwrote))
    return

def _make_lta_file(site, clim_dir):
    """
    write long term average climate section of site.txt file
    """

    lines = []
    lta_precip, lta_tmean = site.lta_precip, site.lta_tmean
    if lta_precip is None or lta_tmean is None:
        return

    for precip, month in zip(lta_precip, site.months):
        lines.append(_make_line('{}'.format(precip), '{} long term average monthly precipitation [mm]'.format(month)))

    for tmean, month in zip(lta_tmean, site.months):
        lines.append(_make_line('{}'.format(tmean), '{} long term average monthly temperature [mm]'.format(month)))

    lta_ave_fn = join(clim_dir, 'lta_ave.txt')
    with open(lta_ave_fn, 'w') as fhand:
        fhand.writelines(lines)

    # will be copied
    # ==============
    make_avemet_file(clim_dir, site.lta_precip, site.lta_pet, site.lta_tmean)

    return lta_ave_fn

def _make_line(data, comment):
    """

    """
    spacer_len = max(SPACER_LEN - len(data), 2)
    spacer = ' ' * spacer_len

    return '{}{}# {}\n'.format(data, spacer, comment)