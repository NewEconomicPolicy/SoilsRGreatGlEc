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
from prepare_ecosse_low_level import update_progress
from mngmnt_fns_and_class import create_proj_data_defns, open_proj_NC_sets, close_proj_NC_sets
from glbl_ecsse_low_level_test_fns import make_fert_recs_test
from glbl_ecsse_low_level_fns import check_run_mask, set_region_study
from runsites_high_level import run_ecosse_wrapper
from initialise_funcs import change_config_file

WARNING_STR = '*** Warning *** '
REGION_ABBREVS = ['Australasia', 'Africa','Asia', 'Europe','NAmerica','SAmerica']   # map to regions
SKIP_GRAFT = True   # avoid IO intensive overhead to test Mean N Application spreadsheet methodology

def all_generate_banded_sims_test(form, all_regions_flag = True):
    """

    """
    nstudies = len(form.studies)
    ncombo = form.combo00s.count()
    if nstudies != ncombo:
        mess = WARNING_STR + 'Option to generate simulations for all regions not available'
        print(mess + ' - number of studies {} should match number of entries in studies combobox {}'
                                                                                            .format(nstudies, ncombo))
        return None

    '''
    get current study, create list of all studies based on current study, then change config files if these studies exist
    '''
    study = form.w_study.text()
    if study.find('_') == -1:
        print(WARNING_STR + 'study name must have an underscore to run all regions')
        return None

    study_set = []
    cmmn_nm = study.split('_')[1]   # common name
    for region in REGION_ABBREVS:
        study_set.append(region + '_' + cmmn_nm)

    if all_regions_flag:

        for study in study_set:
            if(change_config_file(form, study)):
                form.update()
                region = form.combo00a.currentText()
                crop_name = form.combo00b.currentText()
                print('\nGenerating cells for crop: {}\tregion: {}'.format(crop_name, region))
                generate_banded_sims_test(form, region, crop_name)
    else:
        region = form.combo00a.currentText()
        for crop_indx, crop_name in enumerate(form.setup['crops']):
            form.combo00b.setCurrentIndex(crop_indx)
            form.update()
            print('\nGenerating cells for crop: {}\tregion: {}'.format(crop_name, region))
            generate_banded_sims_test(form, region, crop_name)

def generate_banded_sims_test(form, region, crop_name):
    """
    called from GUI
    NB  vars ending in _dset indicate netCDF4 dataset objects
        vars ending in _defn are objects which comprising NC file attributes e.g. resolution, extents, file location
    """
    year_from = int(form.w_yr_from.text())

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

    # fetch bounding box
    # ==================
    lon_ll = float(form.w_ll_lon.text())
    lat_ll = float(form.w_ll_lat.text())
    lon_ur = float(form.w_ur_lon.text())
    lat_ur = float(form.w_ur_lat.text())
    form.setup['bbox'] =  list([lon_ll, lat_ll, lon_ur, lat_ur])

    # verify mask, sowing, yields, fertiliser NC files
    # ================================================
    proj_data_defns = create_proj_data_defns(form.setup['proj_path'],  crop_name, req_resol_deg)
    if proj_data_defns is None:
        print('*** Error *** verifing NC files for study ' + form.setup['region_study'])
        return

    mask_defn, yield_defn, dates_defn, fert_defns = proj_data_defns
    del(proj_data_defns)
    yld_varname = yield_defn.var_name

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
    record_ndays = {str(n): 0 for n in range(12)}
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

            ngrowing += 1
            ngrow_this_band += 1

            doys = make_fert_recs_test(form.lgr, fert_defns, lat, lon, record_ndays)
            if doys == 0:
                warning_count += 1
                continue

            ncompleted += 1

            last_time = update_progress(last_time, ncompleted, nskipped, ntotal_grow, ngrowing, nno_grow, hwsd = None)
            if ncompleted >= max_cells:
                break

        # finished this band - report progress
        # ====================================
        if ncompleted >= max_cells:
            print('\nFinishing run after {} cells completed'.format(ncompleted))
            break

    # close NC files
    # ==============
    close_proj_NC_sets(mask_defn, yield_defn, dates_defn, fert_defns)

    print('Completed Region: {}\tCrop: {}\tLocations - growing: {}\tno grow: {}\ttotal: {}\t {}%'
                    .format(region,  crop_name, ngrowing, nno_grow, ntotal_grow, round(100*(ngrowing/ntotal_grow),2)))
    print('record_ndays = ' + str(record_ndays))

    # run further steps if requested
    # =============================
    if form.w_auto_run_ec.isChecked():
        run_ecosse_wrapper(form)

    return
