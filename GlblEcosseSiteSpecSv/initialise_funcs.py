"""
#-------------------------------------------------------------------------------
# Name:        initialise_funcs.py
# Purpose:     script to read and write the setup and configuration files
# Author:      Mike Martin
# Created:     31/07/2015
# Licence:     <your licence>
#-------------------------------------------------------------------------------
"""
__prog__ = 'initialise_funcs.py'
__version__ = '0.0.0'

# Version history
# ---------------
# 
from os.path import join, normpath, exists, isfile, isdir, split, splitext, splitdrive
from os import makedirs, getcwd, name as os_name
from json import load as json_load, dump as json_dump
from json.decoder import JSONDecodeError
from glob import glob
from time import sleep
from sys import exit
from pandas import read_excel
from xlrd import XLRDError

from set_up_logging import set_up_logging
from glbl_ecss_cmmn_cmpntsGUI import print_resource_locations
from glbl_ecsse_low_level_fns import check_cultiv_json_fname, check_rotation_json_fname
from shape_funcs import format_bbox, calculate_area
from weather_datasets_ltd_data import read_weather_dsets_detail, change_weather_resource, record_weather_settings
from hwsd_bil import check_hwsd_integrity
from mngmnt_fns_and_class import ManagementSet

APPLIC_STR = 'glbl_ecss_site_spec_sv'
ERROR_STR = '*** Error *** '
WARNING_STR = '*** Warning *** '

MAX_COUNTRIES = 350

RUN_SETTINGS_SETUP_LIST =[ 'completed_max', 'check_space_every', 'kml_flag', 'last_gcm_only_flag',
                                    'max_countries', 'space_remaining_limit', 'soil_test_flag', 'zeros_file']

SETTINGS_SETUP_LIST = ['config_dir', 'fname_png', 'log_dir', 'n_inputs_xls', 'proj_path', 'regions_fname',
                       'sims_dir', 'weather_dir', 'shp_dir', 'shp_dir_gadm', 'python_exe', 'runsites_py',
                       'weather_resource', 'wthr_prj_dir']
MIN_GUI_LIST = ['aveWthrFlag', 'autoRunEcFlag', 'bbox', 'cultivJsonFname', 'daily_mode', 'manureFlag', 'regionIndx',
                    'yearFrom', 'rotaJsonFname', 'rotationFlag', 'wthrRsrce', 'maxCells', 'allRegionsFlag',
                                                                                'perenCrops', 'autoRunEcFlag']
CMN_GUI_LIST = ['cruStrtYr', 'cruEndYr', 'climScnr', 'futStrtYr', 'futEndYr', 'cropIndx', 'gridResol', 'eqilMode']

sleepTime = 5

def initiation(form):
    """
    initialise the programme
    """

    # avoids errors when exiting
    # ==========================
    form.wthr_sets = None
    form.req_resol_deg = None
    form.req_resol_granul = None
    form.rota_pattern = None
    form.glbl_n_inpts = None

    settings = _read_setup_file(APPLIC_STR )
    form.setup = settings['setup']
    form.settings = settings['setup']   # TODO: duplication but necessary for logging

    form.setup['applic_str'] = APPLIC_STR
    form.setup['crops'] = dict({'Maize':15, 'Sugarcane':10, 'Wheat':5})
    form.regions = settings['regions']
    form.fobjs = None
    form.zeros_file = None

    # check weather data
    # ==================
    read_weather_dsets_detail(form)
    wthr_rsrce_generic = form.settings['weather_resource']
    form.wthr_rsrces_generic = wthr_rsrce_generic
    if wthr_rsrce_generic == 'WrldClim':
        form.wthr_scenarios = list(['126', '245', '370', '585'])
    elif wthr_rsrce_generic == 'CRU':
        form.wthr_scenarios = list(['A1B_MG1', 'A2_MG1', 'B1_MG1', 'B2_MG1'])
    else:
        print(ERROR_STR + wthr_rsrce_generic + ' is not an allowed weather resource - must be CRU or WrldClim')
        sleep(sleepTime)
        exit(0)

    form.parms_settings = _read_site_specific_parms()

    config_files = build_and_display_studies(form)
    if len(config_files) > 0:
        form.setup['config_file'] = config_files[0]
    else:
        '''
        form.setup['config_file'] = normpath(normpath(form.setup['config_dir']
                                                                         + '/' + APPLIC_STR + '_dummy.json'))
        '''
        print(ERROR_STR + 'there must be at least one config file in ' + form.setup['config_dir'])
        sleep(sleepTime)
        exit(0)

    set_up_logging(form, APPLIC_STR)

    # Nitpars, fnames.dat and model_switches must be present - crop_pars for limited data mode only
    # =============================================================================================
    form.dflt_ecosse_fnames = {}
    for ecosse_fname in list(['Model_Switches', 'fnames', 'CROP_SUN', 'Nitpars']):
        dflt_ecosse_fname = join(form.setup['ecosse_fpath'], ecosse_fname + '.dat')
        if isfile(dflt_ecosse_fname):
            form.dflt_ecosse_fnames[ecosse_fname.lower()] = dflt_ecosse_fname
        else:
            print(ERROR_STR + '{} file must exist'.format(dflt_ecosse_fname))
            sleep(sleepTime)
            exit(0)

    form.config_files = config_files
    form.crop_defns = _read_crop_defns(form.dflt_ecosse_fnames['crop_sun'])

    # Look for and create definition for countries file
    # =================================================
    glec_dir, dummy = split(form.setup['hwsd_dir'])
    soil_dir = join(glec_dir, 'Soil')
    states_fn = join(soil_dir, 'all_Countries.nc')
    if isfile(states_fn):
        form.cntries_defn = ManagementSet(states_fn, 'countries')
    else:
        form.cntries_defn = None

    return

def change_config_file(form, new_study = None):
    """
    identify and read the new configuration file
    """
    if new_study is None:
        new_study = form.w_combo00s.currentText()
        if new_study == '':     # this can happen when saving to the config file
            return

    new_config = form.setup['applic_str'] + '_' + new_study
    config_file = normpath(form.setup['config_dir'] + '/' + new_config + '.json')

    if isfile(config_file):
        form.setup['config_file'] = config_file
        read_config_file(form)
        form.setup['study'] = new_study
        form.w_study.setText(new_study)
        return
    else:
        print(WARNING_STR + 'Could not locate ' + config_file)
        return

def build_and_display_studies(form):
    """
    is called at start up and when user creates a new project
    """

    # read all the configuration files
    # ================================
    applic_str = form.setup['applic_str']
    config_files = glob(form.setup['config_dir'] + '/' + applic_str + '*.json')
    studies = []
    for fname in config_files:
        dummy, remainder = fname.split(applic_str)
        study, dummy = splitext(remainder)
        if study != '':
            studies.append(study.lstrip('_'))
    form.studies = studies

    # display studies list
    # ====================
    if hasattr(form, 'w_combo00s'):
        form.w_combo00s.clear()
        for study in studies:
            form.w_combo00s.addItem(study)

    return config_files

def _read_crop_defns(crop_pars_fname):
        """
        read crop names and their corresponding codes
        """
        with open(crop_pars_fname) as fhand:
            lines = fhand.readlines()

        crop_defns = {}
        for iline in range(0, len(lines), 9):
            crop_name = lines[iline].strip()
            code = int(lines[iline + 1].strip())
            crop_defns[crop_name] = code

        return crop_defns

def _default_parms_settings():
    """

    """
    _default_parms = {
        'site': {
            'iom_c': 0.0,
            'toc': 2.7,
            'drain_class': 2,
            'depth_imperm_lyr': 3,
            'wtr_tbl_dpth': 300,
            'prev_lu': 1,
            'prev_crop_code': 1,
            'yield_prev_crop': 8.0,
            'prev_crop_harvest_doy': 0,
            'equil_mode': 2
        },
        'cultivation': {
            'cult_type': 3,
            'cult_vigor': 0.5
        }
    }
    return _default_parms

def _read_site_specific_parms():
    """
    read programme run settings from the parameters file, if it exists
    """
    func_name = __prog__ + '  _read_site_specific_parms'

    # look for setup file here...
    parms_setup_file = join(getcwd(), 'additional_setup', 'site_specific_parms.json')

    if exists(parms_setup_file):
        with open(parms_setup_file, 'r') as fsetup:
            try:
                parms_settings = json_load(fsetup)
            except (JSONDecodeError, OSError, IOError) as err:
                print(err)
    else:
        parms_settings = _default_parms_settings()

    return parms_settings

def _read_setup_file(applic_str):
    """
    # read settings used for programme from the setup file, if it exists,
    # or create setup file using default values if file does not exist
    """
    func_name = __prog__ + ' _read_setup_file'

    # validate setup file
    # ===================
    fname_setup = applic_str + '_setup.json'
    setup_file = join(getcwd(), fname_setup)

    if exists(setup_file):
        with open(setup_file, 'r') as fsetup:
            try:
                settings = json_load(fsetup)
            except (JSONDecodeError, OSError, IOError) as err:
                print(err)
                sleep(sleepTime)
                exit(0)
    else:
        print('Setup file ' + setup_file + ' not found')
        sleep(sleepTime)
        exit(0)

    print('Read setup file ' + setup_file)

    # validate setup file
    # ===================
    grp = 'run_settings'
    for key in RUN_SETTINGS_SETUP_LIST:
        if key not in settings[grp]:
            print(ERROR_STR + 'setting {} is required in setup file {} '.format(key, setup_file))
            sleep(sleepTime)
            exit(0)

    grp = 'setup'
    for key in SETTINGS_SETUP_LIST:
        if key not in settings[grp]:
            print(ERROR_STR + 'setting {} is required in setup file {} '.format(key, setup_file))
            sleep(sleepTime)
            exit(0)

    # TODO: fix this anomaly
    # ======================
    settings[grp]['last_gcm_only_flag'] = settings['run_settings']['last_gcm_only_flag']

    # initialise vars
    # ===============
    config_dir = settings[grp]['config_dir']
    hwsd_dir = settings[grp]['hwsd_dir']
    log_dir = settings[grp]['log_dir']
    proj_path = settings[grp]['proj_path']
    regions_fname = settings[grp]['regions_fname']
    sims_dir = settings[grp]['sims_dir']
    weather_dir = settings[grp]['weather_dir']

    # make sure directories exist for configuration and log files
    # ===========================================================
    check_hwsd_integrity(hwsd_dir)

    print('Checking drives, this may take a while...')
    for path_name in list([log_dir, config_dir, sims_dir, regions_fname, weather_dir]):
        drv_nm, tail_nm = splitdrive(path_name)
        if not isdir(drv_nm):
            print(ERROR_STR + 'Drive {} for {} does not exist'.format(drv_nm, path_name))
            sleep(sleepTime)
            exit(0)

    if not isdir(log_dir):
        makedirs(log_dir)

    if not isdir(config_dir):
        makedirs(config_dir)

    if not isdir(sims_dir):
        try:
            makedirs(sims_dir)
        except BaseException as err:
            print(ERROR_STR + str(err) + '\n\tmaking sims_dir ' + sims_dir)
            sleep(sleepTime)
            exit(0)

    # file comprising world regions
    # ============================
    if isfile(regions_fname):
        settings['regions'] = _read_regions_file(regions_fname)
    else:
        print(ERROR_STR + 'reading {}\tregions definition file {} must exist'.format(setup_file, regions_fname))
        sleep(sleepTime)
        exit(0)

    # weather is crucial
    # ==================
    if not isdir(weather_dir):
        print(ERROR_STR + 'reading {}\tClimate path {} must exist'.format(setup_file, weather_dir))
        sleep(sleepTime)
        exit(0)

    # location of Ecosse files e.g. fnames.dat
    # ========================================
    ecosse_fpath = join(proj_path, 'Ecosse_input_files')
    if not isdir(ecosse_fpath):
        print(ERROR_STR + 'reading {}\tEcosse path {} must exist'.format(setup_file, ecosse_fpath))
        sleep(sleepTime)
        exit(0)
    settings[grp]['ecosse_fpath'] = ecosse_fpath
    settings[grp]['max_countries'] = MAX_COUNTRIES

    lta_nc_fname = None
    print_resource_locations(setup_file, config_dir, hwsd_dir, weather_dir, lta_nc_fname, sims_dir, log_dir)

    return settings

def _write_default_setup_file(setup_file):
    """
    #  stanza if setup_file needs to be created
    """
    # Windows only for now
    # =====================
    os_system = os_name
    if os_system != 'nt':
        print('Operating system is ' + os_system + 'should be nt - cannot proceed with writing default setup file')
        sleep(sleepTime)
        exit(0)

    # return list of drives
    # =====================
    import win32api

    drives = win32api.GetLogicalDriveStrings()
    drives = drives.split('\000')[:-1]
    if 'S:\\' in drives:
        root_dir_app = 'S:\\tools\\'  # Global Ecosse installed here
        root_dir_user = 'H:\\'  # user files reside here
    elif 'E:\\' in drives:
        root_dir_app = 'E:\\'
        root_dir_user = 'E:\\AbUniv\\'
    else:
        root_dir_app = 'C:\\'
        root_dir_user = 'C:\\AbUniv\\'

    suite_path = root_dir_user + 'GlobalEcosseSuite\\'
    data_path = root_dir_app + 'GlobalEcosseData\\'
    outputs_path = root_dir_app + 'GlobalEcosseOutputs\\'
    root_dir_user += 'GlobalEcosseSuite\\'
    runsites_py = ''

    _default_setup = {
        'setup': {
            'root_dir_user': root_dir_user,
            'fname_png': join(suite_path + 'Images', 'Tree_of_life.PNG'),
            'shp_dir': data_path + 'CountryShapefiles',
            'python_exe': 'E:\\Python36\\python.exe',
            'runsites_py': runsites_py,
            'proj_loc': root_dir_user,
            'sims_dir': outputs_path + 'EcosseSims',
            'log_dir': root_dir_user + 'logs',
            'config_dir': root_dir_user + 'config',
            'regions_fname': '',
            'hwsd_dir': data_path + 'HWSD_NEW',
            'weather_dir': 'E:\\GlobalEcosseData'
        },
        'run_settings': {
            'completed_max': 5000000000,
            'check_space_every': 10,
            'kml_flag': True,
            'last_gcm_only_flag': True,
            "max_countries": 350,
            'space_remaining_limit': 1270,
            'soil_test_flag': False,
            'zeros_file': False
        }
    }
    # create setup file
    # =================
    with open(setup_file, 'w') as fsetup:
        json_dump(_default_setup, fsetup, indent=2, sort_keys=True)
        return _default_setup

def _write_default_config_file(config_file):
    """
    ll_lon,    ll_lat  ur_lon,ur_lat
    stanza if config_file needs to be created
    """
    bbox_default = [0,0,0,0]
    _default_config = {
        'minGUI': {
            'aveWthrFlag': False,
            'bbox': bbox_default,
            'cultivJsonFname': '',
            'daily_mode': True,
            "manureFlag": False,
            "regionIndx": 0,
            "wthrRsrce": 0
        },
        'cmnGUI': {
            'climScnr': 0,
            'cropIndx': 0,
            'cruStrtYr': 0,
            'cruEndYr': 0,
            'eqilMode': 9.5,
            'futStrtYr': 0,
            'futEndYr': 0,
            'gridResol': 0
        }
    }
    # if config file does not exist then create it...
    with open(config_file, 'w') as fconfig:
        json_dump(_default_config, fconfig, indent=2, sort_keys=True)
        return _default_config

def read_config_file(form):
    """
    read widget settings used in the previous programme session from the config file, if it exists,
    or create config file using default settings if config file does not exist
    """
    func_name = __prog__ + ' read_config_file'

    config_file = form.setup['config_file']
    if exists(config_file):
        try:
            with open(config_file, 'r') as fconfig:
                config = json_load(fconfig)
                print('Read config file ' + config_file)
        except (OSError, IOError, JSONDecodeError) as err:
            print(ERROR_STR + str(err) + ' in config file:\n\t' + config_file)
            sleep(sleepTime)
            exit(0)
    else:
        config = _write_default_config_file(config_file)
        print('Wrote configuration file ' + config_file)

    grp = 'minGUI'
    for key in MIN_GUI_LIST:
        if key not in config[grp]:
            if key == 'perenCrops':
                config[grp]['perenCrops'] = False
            else:
                print(ERROR_STR + 'attribute {} required for group {} in config file {}'.format(key, grp, config_file))
                sleep(sleepTime)
                exit(0)

    ave_weather        = config[grp]['aveWthrFlag']
    auto_run_ec        = config[grp]['autoRunEcFlag']
    form.setup['bbox'] = config[grp]['bbox']
    daily_mode         = config[grp]['daily_mode']
    cultiv_json_fname  = config[grp]['cultivJsonFname']

    manure_flag = config[grp]['manureFlag']
    rota_json_fname    = config[grp]['rotaJsonFname']
    rotation_flag      = config[grp]['rotationFlag']
    peren_crops        = config[grp]['perenCrops']

    max_cells          = config[grp]['maxCells']
    all_regions        = config[grp]['allRegionsFlag']
    yr_from = config[grp]['yearFrom']

    # build bounding boxes for countries and peovinces of large countries
    # ===================================================================
    if 'glblNflag' not in config[grp]:
        glbl_n_flag = False
    else:
        glbl_n_flag = config[grp]['glblNflag']

    # cultivation and crop rotation
    # =============================
    form.w_lbl13.setText(cultiv_json_fname)
    form.w_lbl14.setText(check_cultiv_json_fname(form))  # displays file info
    form.w_lbl16.setText(rota_json_fname)
    form.w_lbl17.setText(check_rotation_json_fname(form))  # displays file info
    form.w_combo00a.setCurrentIndex(config[grp]['regionIndx'])

    # make sure index is within the permissable range of entries
    wthr_rsrce_indx = config[grp]['wthrRsrce']
    if not isinstance(wthr_rsrce_indx, int):
        wthr_rsrce_indx = 0  # sets to CRU, the default

    nitems = form.w_combo10w.count()
    if wthr_rsrce_indx >= 0 and wthr_rsrce_indx < nitems:
        form.w_combo10w.setCurrentIndex(wthr_rsrce_indx)

    wthr_rsrce = form.w_combo10w.currentText()
    change_weather_resource(form, wthr_rsrce)

    # common area
    # ===========
    grp = 'cmnGUI'
    for key in config[grp]:
        if key not in CMN_GUI_LIST:
            print(ERROR_STR + 'attribute {} required for group {} in config file {}'.format(key, grp, config_file))
            sleep(sleepTime)
            exit(0)

    scenario = config[grp]['climScnr']
    hist_strt_year = config[grp]['cruStrtYr']
    hist_end_year = config[grp]['cruEndYr']
    sim_strt_year = config[grp]['futStrtYr']
    sim_end_year = config[grp]['futEndYr']

    # TODO: use code from build_and_display_studies function to derive study from configuration file
    # ==============================================================================================
    dummy, remainder = config_file.split(form.setup['applic_str'])
    study, dummy = splitext(remainder)
    form.w_study.setText(study.lstrip('_'))

    form.w_combo09s.setCurrentIndex(hist_strt_year)
    form.w_combo09e.setCurrentIndex(hist_end_year)
    form.w_combo10.setCurrentIndex(scenario)
    form.w_combo11s.setCurrentIndex(sim_strt_year)
    form.w_combo11e.setCurrentIndex(sim_end_year)

    # TODO: an undesirable patch
    # ==========================
    nitems = form.w_combo11e.count()
    form.w_combo11e.setCurrentIndex(nitems - 1)

    form.w_combo00b.setCurrentIndex(config[grp]['cropIndx'])
    form.w_combo16.setCurrentIndex(config[grp]['gridResol'])
    form.w_equimode.setText(str(config[grp]['eqilMode']))

    # record weather settings
    # =======================
    form.wthr_settings_prev[wthr_rsrce] = record_weather_settings(scenario, hist_strt_year, hist_end_year,
                                                                            sim_strt_year, sim_end_year)
    # bounding box set up
    # ===================
    area = calculate_area(form.setup['bbox'])
    ll_lon, ll_lat, ur_lon, ur_lat = form.setup['bbox']
    form.w_ll_lon.setText(str(ll_lon))
    form.w_ll_lat.setText(str(ll_lat))
    form.w_ur_lon.setText(str(ur_lon))
    form.w_ur_lat.setText(str(ur_lat))
    form.lbl03.setText(format_bbox(form.setup['bbox'], area))
    form.bbox = form.setup['bbox'] # legacy

    form.w_max_cells.setText(str(max_cells))
    form.w_yr_from.setText(str(yr_from))

    # set check boxes
    # ===============
    if all_regions:
        form.w_all_regions.setCheckState(2)
    else:
        form.w_all_regions.setCheckState(0)

    if auto_run_ec:
        form.w_auto_run_ec.setCheckState(2)
    else:
        form.w_auto_run_ec.setCheckState(0)

    if ave_weather:
        form.w_ave_wthr.setCheckState(2)
    else:
        form.w_ave_wthr.setCheckState(0)

    if glbl_n_flag:
        form.w_glbl_n_inpts.setCheckState(2)
    else:
        form.w_glbl_n_inpts.setCheckState(0)

    if daily_mode:
        form.w_daily.setChecked(True)
    else:
        form.w_mnthly.setChecked(True)

    if manure_flag:
        form.w_manure.setChecked(True)
    else:
        form.w_fert.setChecked(True)

    if form.rota_pattern is None or not rotation_flag:
        form.w_crop_rota.setCheckState(0)
    else:
        form.w_crop_rota.setCheckState(2)

    if peren_crops:
        form.w_use_peren.setChecked(True)
    else:
        form.w_use_peren.setChecked(False)

    # files to run Ecosse
    # ==================
    runsites_py = form.setup['runsites_py']
    if isfile(runsites_py):
        print('Will use ECOSSE run script: ' + runsites_py)
    else:
        print(WARNING_STR + 'ECOSSE run script {} does not exist, ECOSSE cannot be run'.format(runsites_py))
        form.w_run_ecosse.setEnabled(False)

    python_exe = form.setup['python_exe']
    if isfile(python_exe):
        print('Will use Python interpreter: ' + python_exe + ' for ECOSSE run script')
    else:
        print(WARNING_STR + 'Python interpreter {} does not exist, ECOSSE cannot be run'.format(python_exe))
        form.w_run_ecosse.setEnabled(False)

    # runsites configuration file
    # ===========================
    runsites_config_file = join(form.setup['config_dir'], 'global_ecosse_site_spec_runsites_config.json')

    mess = 'Run sites configuration file ' + runsites_config_file
    if exists(runsites_config_file):
        mess += ' exists'
    else:
        mess += ' does not exist - cannot run ECOSSE'
        form.w_run_ecosse.setEnabled(False)
        runsites_config_file = None

    form.setup['runsites_config_file'] = runsites_config_file
    print(mess)

    form.w_use_dom_soil.setChecked(True)
    form.w_use_high_cover.setChecked(True)

    return True

def write_config_file(form):
    """
    write current selections to config file
    """

    # facilitate multiple config file choices
    # =======================================
    study = form.w_study.text()
    applic_str = form.setup['applic_str']
    config_file = join(form.setup['config_dir'], applic_str + '_' + study + '.json')

    # prepare the bounding box
    # ========================
    try:
        ll_lon = float(form.w_ll_lon.text())
        ll_lat = float(form.w_ll_lat.text())
        ur_lon = float(form.w_ur_lon.text())
        ur_lat = float(form.w_ur_lat.text())
    except ValueError:
        ll_lon = 0.0
        ll_lat = 0.0
        ur_lon = 0.0
        ur_lat = 0.0
    form.setup['bbox'] = list([ll_lon, ll_lat, ur_lon, ur_lat])

    # TODO:
    # print('Weather choice Id: {}'.format(form.w_weather_choice.checkedId()))
    config = {
        'cmnGUI': {
            'cropIndx': form.w_combo00b.currentIndex(),
            'cruStrtYr': form.w_combo09s.currentIndex(),
            'cruEndYr': form.w_combo09e.currentIndex(),
            'climScnr': form.w_combo10.currentIndex(),
            'futStrtYr': form.w_combo11s.currentIndex(),
            'futEndYr': form.w_combo11e.currentIndex(),
            'eqilMode': form.w_equimode.text(),
            'gridResol': form.w_combo16.currentIndex()
        },
        'minGUI': {
            'allRegionsFlag': form.w_all_regions.isChecked(),
            'aveWthrFlag': form.w_ave_wthr.isChecked(),
            'autoRunEcFlag': form.w_auto_run_ec.isChecked(),
            'bbox': form.setup['bbox'],
            'cultivJsonFname': form.w_lbl13.text(),
            'maxCells': form.w_max_cells.text(),
            'rotaJsonFname': form.w_lbl16.text(),
            'glblNflag': form.w_glbl_n_inpts.isChecked(),
            'daily_mode': form.w_daily.isChecked(),
            'manureFlag': form.w_manure.isChecked(),
            'perenCrops': form.w_use_peren.isChecked(),
            'yearFrom' : form.w_yr_from.text(),
            'rotationFlag': form.w_crop_rota.isChecked(),
            'regionIndx': form.w_combo00a.currentIndex(),
            'wthrRsrce': form.w_combo10w.currentIndex()
        }
    }
    if isfile(config_file):
        descriptor = 'Overwrote existing'
    else:
        descriptor = 'Wrote new'

    with open(config_file, 'w') as fconfig:
        try:
            json_dump(config, fconfig, indent=2, sort_keys=True)
            print('\n' + descriptor + ' configuration file ' + config_file)
        except BaseException as err:
            print(str(err))

    return

def _read_regions_file(regions_fname):
    """

    """
    print('Will use regions definition file: ' + regions_fname)
    try:
        data = read_excel(regions_fname, sheet_name='Regions', usecols=range(0, 6))
        regions = data.dropna(how='all')
    except (PermissionError, XLRDError) as err:
        print(ERROR_STR + '{} reading regions definition file {}'.format(err, regions_fname))
        sleep(sleepTime)
        exit(0)

    return regions
