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
__prog__ = 'glbl_ecsse_high_level_fns.py'
__version__ = '0.0.1'
__author__ = 's03mm5'

from time import time
from locale import LC_ALL, setlocale, format_string
from PyQt5.QtWidgets import QApplication

from hwsd_bil import HWSD_bil
from hwsd_soil_class import HWSD_soil_defn

from getClimGenNC import ClimGenNC
from getClimGenFns import check_clim_nc_limits, open_wthr_NC_sets, get_wthr_nc_coords
from make_site_spec_files_classes import MakeSiteFiles
from prepare_ecosse_files import make_ecosse_files

from glbl_ecss_cmmn_funcs import write_study_definition_file
from glbl_ecsse_low_level_fns import Cell_hwsd_data_frame, check_run_mask, make_fert_recs, set_region_study, update_progress
from mngmnt_fns_and_class import create_proj_data_defns, open_proj_NC_sets, close_proj_NC_sets
from runsites_high_level import run_ecosse_wrapper

from shape_funcs import calculate_area, MakeBboxesNitroInpts
from initialise_funcs import change_config_file
from wthr_generation_fns import fetch_hist_lta_from_lat_lon

WARNING_STR = '*** Warning *** '

SKIP_GRAFT = False   # avoid IO intensive overhead to test Mean N Application spreadsheet methodology

def all_generate_banded_sims(form):
    """
    get all studies, then change config files
    """
    study_set = [form.w_combo00s.itemText(istdy) for istdy in range(form.w_combo00s.count())]

    for study in study_set:
        change_config_file(form, study)
        QApplication.processEvents()
        form.update() # Updates the widget but does not cause an immediate repaint

        region = form.w_combo00a.currentText()
        crop_name = form.w_combo00b.currentText()
        print('\nGenerating cells for crop: {}\tregion: {}'.format(crop_name, region))
        generate_banded_sims(form, region, crop_name)

    print('Finished processing {} studies'.format(len(study_set)))
    return

def generate_banded_sims(form, region, crop_name):
    """
    called from GUI
    NB  vars ending in _dset indicate netCDF4 dataset objects
        vars ending in _defn are objects which comprising NC file attributes e.g. resolution, extents, file location
    """
    setlocale(LC_ALL, '')
    year_from = int(form.w_yr_from.text())
    glbl_n_flag = False
    if form.w_glbl_n_inpts.isChecked() and form.glbl_n_inpts is None:
        if form.cntries_defn is None:
            form.glbl_n_inpts = None
        else:
            form.glbl_n_inpts = MakeBboxesNitroInpts(form.settings, form.cntries_defn)
            glbl_n_flag = True
    else:
        form.glbl_n_inpts = None

    if form.w_use_peren.isChecked():
        peren_flag = True
    else:
        peren_flag = False

    if form.w_use_dom_soil.isChecked():
        use_dom_soil_flag = True        # use dominant soil only
    else:
        use_dom_soil_flag = False

    if form.w_use_high_cover.isChecked():
        use_high_cover_flag = True      # use soil with highest coverage
    else:
        use_high_cover_flag = False

    if form.w_ave_wthr.isChecked():
        start_from_1801 = True
    else:
        start_from_1801 = False

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
    set_region_study(form)

    # create required HWSD object - confirms HWSD existence
    # =====================================================
    hwsd = HWSD_bil(form.lgr, form.setup['hwsd_dir'])
    soil_defn = HWSD_soil_defn(form.lgr)
    sims_dir = form.setup['sims_dir']

    # fetch bounding box
    # ==================
    lon_ll = float(form.w_ll_lon.text())
    lat_ll = float(form.w_ll_lat.text())
    lon_ur = float(form.w_ur_lon.text())
    lat_ur = float(form.w_ur_lat.text())
    form.setup['bbox'] = list([lon_ll, lat_ll, lon_ur, lat_ur])

    # =========================================================
    write_study_definition_file(form)
    if start_from_1801:
        sim_strt_year = 1801
    else:
        sim_strt_year = int(form.w_combo11s.currentText())
    sim_end_year = int(form.w_combo11e.currentText())

    # verify mask, sowing, yields, fertiliser NC files
    # ================================================
    proj_data_defns = create_proj_data_defns(form.setup['proj_path'], crop_name, req_resol_deg)
    if proj_data_defns is None:
        print('*** Error *** verifing NC files for study ' + form.setup['region_study'])
        return

    mask_defn, yield_defn, dates_defn, fert_defns = proj_data_defns
    del proj_data_defns
    yld_varname = yield_defn.var_name

    # weather choice - CRU is default, check requested AOI coordinates against weather dataset extent
    # ===============================================================================================
    if not check_clim_nc_limits(form, form.setup['bbox'], form.wthr_rsrces_generic):
        return

    climgen = ClimGenNC(form, region, crop_name, sim_strt_year, sim_end_year)

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

    # main AOI traversal loops - outer: North to South, inner: East to West
    # ========================
    start_at_band = 0
    print('Starting at band {}'.format(start_at_band))

    nbands = lat_ur_indx - lat_ll_indx + 1
    last_time = time()
    ncompleted = 0
    nskipped = 0
    warning_count = 0
    ngrowing = 0; nno_grow = 0
    for nband, lat_indx in enumerate(range(lat_ur_indx, lat_ll_indx - 1, -1)):

        lat = mask_defn.lats[lat_indx]
        ngrow_this_band = 0
        area = None

        for lon_indx in range(lon_ll_indx, lon_ur_indx + 1):
            lon = mask_defn.lons[lon_indx]

            mask_val = mask_defn.nc_dset.variables['cropmask'][lat_indx, lon_indx]
            crop_grown = int(mask_val.item())
            if crop_grown == 0:
                nno_grow += 1
                continue

            if lat == 45.75 and lon == 136.75:
                print('')
            ngrowing += 1
            ngrow_this_band += 1

            form.setup['bbox'] = list([lon - resol_d2, lat - resol_d2, lon + resol_d2, lat + resol_d2])
            if area is None:
                area = calculate_area(form.setup['bbox'])

            # retrieve soil detail for this cell
            # ==================================
            nrows_read = hwsd.read_bbox_mu_globals(form.setup['bbox'])   # create grid of MU_GLOBAL values
            mu_global_pairs = hwsd.get_mu_globals_dict()    # retrieve dictionary of mu_globals and number of occurrences
            if mu_global_pairs is None:
                nskipped += 1
                continue
            cell_hwsd_df = Cell_hwsd_data_frame(form.lgr, hwsd)  # create data frame for cell
            soil_recs = hwsd.get_soil_recs(mu_global_pairs)            # create soil records - updates bad_muglobals
            if soil_recs is None:
                nskipped += 1
                continue

            soil_defn.populate(lat, lon, area, cell_hwsd_df, mu_global_pairs, soil_recs)

            # yield has same resolution as mask
            # =================================
            val = yield_defn.nc_dset.variables[yld_varname][lat_indx, lon_indx]
            yield_val = round(float(val.item()), 2)

            lat_date_indx, lon_date_indx, ret_code = dates_defn.get_nc_coords(lat, lon)
            if ret_code == 'OK':
                day = dates_defn.nc_dset.variables['harvest'][lat_date_indx, lon_date_indx]
                harvest_day = int(day.item())
                day = dates_defn.nc_dset.variables['plant'][lat_date_indx, lon_date_indx]
                plant_day = int(day.item())
                fert_recs = make_fert_recs(form.lgr, fert_defns, lat, lon, sim_strt_year, sim_end_year,
                                                            year_from, peren_flag, form.glbl_n_inpts, glbl_n_flag)
                if fert_recs is None:
                    warning_count += 1
                    continue
            else:
                form.lgr.info(ret_code)
                warning_count += 1
                continue

            # simplify if requested
            # =====================
            ret_code = soil_defn.simplify_soil_defn(use_dom_soil_flag, use_high_cover_flag, hwsd.bad_muglobals)
            if ret_code is None:
                warning_count += 1
                continue

            site_obj = MakeSiteFiles(form, climgen)

            integrity_flag, hist_lta_recs, met_fnames = fetch_hist_lta_from_lat_lon(sims_dir, climgen, lat, lon)

            if integrity_flag:
                make_ecosse_files(site_obj, climgen, soil_defn, fert_recs, plant_day, harvest_day,
                                                                     yield_val, hist_lta_recs, met_fnames)
                ncompleted += 1
            else:
                nskipped += 1

            last_time = update_progress(last_time, ncompleted, nskipped, ntotal_grow, ngrowing, nno_grow, hwsd)
            if ncompleted >= max_cells:
                break

        # finished this band - report progress
        # ====================================
        mess = 'Processed band {} of {} bands for lat: {}\tN growing locations: {}'.format(nband,
                                                                                        nbands, lat, ngrow_this_band)
        form.lgr.info(mess)
        if ncompleted >= max_cells:
            print('\nFinishing run after {} cells completed'.format(ncompleted))
            break

    # close NC files
    # ==============
    close_proj_NC_sets(mask_defn, yield_defn, dates_defn, fert_defns)

    if glbl_n_flag:
        form.glbl_n_inpts.cntries_defn.nc_dset.close()

    if len(hwsd.bad_muglobals) > 0:
        print('Bad mu globals: {}'.format(hwsd.bad_muglobals))

    ntotal_str = format_string('%d', ntotal_grow, grouping=True)
    print('Completed Region: {}\tCrop: {}\tLocations - growing: {}\tno grow: {}\ttotal: {}\t {}%\n'
                    .format(region,  crop_name, ngrowing, nno_grow, ntotal_str, round(100*(ngrowing/ntotal_grow),2)))

    # run further steps if requested
    # =============================
    if form.w_auto_run_ec.isChecked():
        run_ecosse_wrapper(form)
        print('\n')

    return
