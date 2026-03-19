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

from os import mkdir
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
from glbl_ecsse_low_level_fns import update_wthr_rothc_progress, update_soc_rothc_progress

ERROR_STR = '*** Error *** '
WARNING_STR = '*** Warning *** '

GRANULARITY = 120
NC_FROM_TIF_FN ='GSOCmap_0.25.nc'
METRIC_LIST = list(['precip', 'tas', 'pet'])
METRIC_DESCRIPS = {'precip': 'precip = total precipitation (mm)',
                    'pet': 'pet = potential evapotranspiration [mm/month]',
                    'tas': 'tave = near-surface average temperature (degrees Celsius)'}
NMETRICS = len(METRIC_LIST)


def generate_rothc_wthr(form):
    """
    called from GUI; based on generate_banded_sims from HoliSoilsSpGlEc project
    GSOCmap_0.25.nc organic carbon has latitiude extant of 83 degs N, 56 deg S
    """
    form.w_abandon.setCheckState(0)
    out_dirs, no_wrthr_list_fn, exstng_no_wrthr_coords = _make_output_dirs(form)
    new_no_wrthr_coords = []
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

    org_soil_defn = _read_soil_organic_detail(form)
    if org_soil_defn is None:
        return

    aoi_res = _fetch_grid_cells_from_socnc(org_soil_defn, out_dirs, exstng_no_wrthr_coords, max_cells)

    # main loop
    # =========
    nskipped, nnodata, ncmpltd, noutbnds = 4*[0]
    last_time = time()

    for site_rec in aoi_res:
        last_time, cancel_flag = update_wthr_rothc_progress(last_time,
                                    noutbnds, nnodata, ncmpltd, nskipped, form.w_abandon)
        if cancel_flag:
            print(WARNING_STR + '\nCancelling run')
            break

        lat, lat_indx, lon, lon_indx, grid_coord, wthr_fut_fns, wthr_hist_fns, soil_carb = site_rec

        # weather set lat/lons
        # ====================
        hist_lat_indx, hist_lon_indx = get_wthr_nc_coords(climgen.hist_wthr_set_defn, lat, lon)
        fut_lat_indx, fut_lon_indx = get_wthr_nc_coords(climgen.fut_wthr_set_defn, lat, lon)
        if hist_lat_indx < 0 or fut_lat_indx < 0:
            noutbnds += 1
            continue

        # Get future and historic weather data
        # ====================================
        if read_all_flag:
            pettmp_hist = fetch_WrldClim_sngl_data(form.lgr, lat, lon, wthr_slices['hist'],
                                                   hist_lat_indx, hist_lon_indx, hist_flag=True)
        else:
            pettmp_hist = fetch_WrldClim_data(form.lgr, lat, lon, climgen, hist_wthr_dsets,
                                                hist_lat_indx, hist_lon_indx, hist_flag=True)
        if pettmp_hist is None:
            pettmp_fut = None
        else:
            if read_all_flag:
                pettmp_fut = fetch_WrldClim_sngl_data(form.lgr, lat, lon, wthr_slices['fut'],
                                                                                fut_lat_indx, fut_lon_indx)
            else:
                pettmp_fut = fetch_WrldClim_data(form.lgr, lat, lon, climgen, fut_wthr_dsets,
                                                                                fut_lat_indx, fut_lon_indx)

        # no weather for this grid cell - so look at adjacent weather cells
        ' ================================================================='
        if pettmp_fut is None or pettmp_hist is None:

            # expand area of weather extraction
            # =================================
            nextnsn = 5
            wrld_clim_indices = _fetch_wthr_search_indices(fut_lat_indx, nlats, fut_lon_indx, nlons, nextnsn)
            if read_all_flag:
                pettmp_hist = fetch_WrldClim_area_data(form.lgr, wrld_clim_indices, climgen, wthr_slices['hist'])
                pettmp_fut = fetch_WrldClim_area_data(form.lgr, wrld_clim_indices, climgen, wthr_slices['fut'])
            else:
                pettmp_hist = fetch_WrldClim_NC_data(form.lgr, wrld_clim_indices, climgen, hist_wthr_dsets)
                pettmp_fut = fetch_WrldClim_NC_data(form.lgr, wrld_clim_indices, climgen, fut_wthr_dsets)

            site_rec_frig = (lat_indx, lon_indx, lat, lon)
            retcode = associate_climate(site_rec_frig, climgen, pettmp_hist, pettmp_fut, report_flag=False)
            if len(retcode) == 0:
                mess = '\n' + WARNING_STR + 'no weather data'
                print(mess + ' for site with lat: {}\tlon: {}'.format(round(lat, 3), round(lon, 3)))
                new_no_wrthr_coords.append([round(lat, 5), lat_indx, lon, lon_indx, grid_coord])
                nnodata += 1
                continue
            else:
                pettmp_hist, pettmp_fut = retcode

        pettmp_hist = _generate_pet(climgen, pettmp_hist, lat)
        pettmp_fut = _generate_pet(climgen, pettmp_fut, lat)

        pettmp_sim = join_hist_fut_to_sim_wthr(climgen, pettmp_hist, pettmp_fut)

        # create weather and PET
        # ======================
        _make_rthc_files(wthr_fut_fns, lat, lat_indx, lon, lon_indx,
                                                climgen, fut_lat_indx, fut_lon_indx, pettmp_sim, fut_flag=True)
        _make_rthc_files(wthr_hist_fns, lat, lat_indx, lon, lon_indx,
                                                climgen, fut_lat_indx, fut_lon_indx, pettmp_hist)
        ncmpltd += 1

    _append_no_weather_file(no_wrthr_list_fn, new_no_wrthr_coords)

    mess = '\nCompleted weather generation  - number of sets completed: {}'.format(ncmpltd)
    mess += '\tskipped: {}\tno data: {}'.format(nskipped, nnodata)
    print(mess + '\tout of bounds: {}\n'.format(noutbnds))

    return

def _append_no_weather_file(no_wrthr_list_fn, new_no_wrthr_coords):
    """
    append no weather file
    """
    n_new_wthr = len(new_no_wrthr_coords)
    if n_new_wthr > 0:
        fobj = open(no_wrthr_list_fn, 'a', newline='')
        wrtr = writer(fobj, delimiter=',')
        for rec in new_no_wrthr_coords:
            wrtr.writerow(rec)
        fobj.close()
        print('Wrote {} new no weather grid cells to: '.format(n_new_wthr) + no_wrthr_list_fn)

    return

def _fetch_wthr_search_indices(lat_indx, nlats, lon_indx, nlons, nextnsn):
    """
    search box must lie within weather dataset extent
    """
    lat_ll_indx = max(lat_indx - nextnsn, 0)
    lon_ll_indx = max(lon_indx - nextnsn, 0)

    lat_ur_indx = min(lat_indx + nextnsn, nlats)
    lon_ur_indx = min(lon_indx + nextnsn, nlons)

    wrld_clim_indices = (lat_ll_indx, lat_ur_indx, lon_ll_indx, lon_ur_indx)

    return wrld_clim_indices

def _make_rthc_files(wthr_fnames, lat, lat_indx, lon, lon_indx,
                     climgen, lat_wthr_indx, lon_wthr_indx, pettmp, fut_flag=False):
    """
    write a RothC weather dataset
    """
    out_dir = split(wthr_fnames['pet'])[0]
    if not isdir(out_dir):
        mkdir(out_dir)

    hdr_recs = _fetch_hdr_recs(lat, lat_indx, lon, lon_indx, climgen, lat_wthr_indx, lon_wthr_indx, fut_flag)
    frst_rec, period, soc_lctn_rec, wthr_lctn_rec, grid_ref_rec = hdr_recs

    for metric in METRIC_LIST:
        metric_descr = METRIC_DESCRIPS[metric]

        if fut_flag:
            data_recs = _generate_data_recs(pettmp[metric])
        else:
            pettmp_hist = _reform_hist_rec(climgen, pettmp[metric])
            data_recs = _generate_data_recs(pettmp_hist)

        with open(wthr_fnames[metric], 'w') as fobj:
            fobj.write(frst_rec)
            fobj.write('\n.' + metric_descr)
            fobj.write('\nPeriod=' + period + ' Variable=.' + metric)
            fobj.write('\n' + soc_lctn_rec)
            fobj.write('\n' + wthr_lctn_rec)
            fobj.write('\n' + grid_ref_rec)
            for data_rec in data_recs:
                fobj.write('\n' + data_rec)
            fobj.flush()
    return

def _reform_hist_rec(climgen, pettmp):
    """
    create strings for header records
    From the WorldClim database of high spatial resolution global weather and climate data.
    """
    seg1, nyears = _fetch_pettmp_segment(pettmp, climgen.hist_start_year, 1961, 2000)
    seg2, nyears = _fetch_pettmp_segment(pettmp, climgen.hist_start_year, 1971, 2000)
    pettmp = seg1 + seg2 + seg2
    pettmp.reverse()

    return pettmp

def _fetch_pettmp_segment(pettmp, strt_yr_data, yr_strt, yr_end):
    """
    create strings for header records
    From the WorldClim database of high spatial resolution global weather and climate data.
    """
    indx_strt =  12 * (yr_strt - strt_yr_data)
    indx_end = 12 * (yr_end - strt_yr_data + 1)
    segmnt = pettmp[indx_strt:indx_end]
    nyears = int(len(segmnt)/12)

    return segmnt, nyears

def _fetch_hdr_recs(lat, lat_indx, lon, lon_indx, climgen, lat_wthr_indx, lon_wthr_indx, fut_flag=True):
    """
    create strings for header records
    TODO: location_rec amd box_rec need clarifying
    """
    if fut_flag:
        gcm = climgen.wthr_rsrce
        scnr = climgen.fut_clim_scen
        frst_rec = 'From the WorldClim database of global weather and climate data using GCM: '
        frst_rec += gcm + '\tScenario: ' + scnr
        period = str(climgen.sim_start_year) + '-' + str(climgen.sim_end_year)
    else:
        frst_rec = 'From the WorldClim database of global weather and climate data using historic data'

        # period = str(climgen.hist_start_year) + '-' + str(climgen.hist_end_year)
        period = str(1901) + '-' + str(2000)    # TODO - requires improvemnt

    soc_lctn_rec = 'SOC Long= ' + str(round(lon, 3)) + '\tLat= ' + str(round(lat, 3))
    soc_lctn_rec += '\tGrid X,Y= ' + str(lon_indx) + ', ' + str(lat_indx)

    lat_wthr = climgen.fut_wthr_set_defn['latitudes'][lat_wthr_indx]
    lon_wthr = climgen.fut_wthr_set_defn['longitudes'][lon_wthr_indx]

    wthr_lctn_rec = 'Weather Long= ' + str(round(lon_wthr, 3)) + '\tLat= ' + str(round(lat_wthr, 3))
    wthr_lctn_rec += '\tGrid X,Y= ' + str(lon_wthr_indx) + ', ' + str(lat_wthr_indx)

    grid_ref_rec = 'Grid-ref=' + '{0:' '=4g},{1:' '=4g}'.format(lon_indx, lat_indx)

    return (frst_rec, period, soc_lctn_rec, wthr_lctn_rec, grid_ref_rec)

def _generate_data_recs(pettmp):
    """
    create strings for data records
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

def _generate_file_names(out_dirs, grid_coord, fut_or_hist):
    """
     C
     """
    skip_flag = False
    wthr_fnames = {}
    nexist = 0

    out_dir = join(out_dirs[fut_or_hist], grid_coord)
    for metric in METRIC_LIST:
        wthr_fname = metric + '_' + grid_coord + '.txt'
        wthr_fnames[metric] = join(out_dir, wthr_fname)

        # potentially skip existing files
        # ===============================
        if exists(wthr_fnames[metric]):
            nexist += 1

    # if both files exist then skip
    # =============================
    if nexist == NMETRICS:
        skip_flag = True

    return wthr_fnames, skip_flag

def _fetch_grid_cells_from_socnc(org_soil_defn, out_dirs, exstng_no_wrthr_coords, max_cells):
    """
    SOC file is lat=618, lon=1440 = 889,920 grid cells  Masked: 652,432     with value: 227,210
    """
    START_FROM = 138000

    ds_soil_org = org_soil_defn['ds_soil_org']
    soc_dset = Dataset(ds_soil_org)
    slice = soc_dset.variables['Band1'][:][:]

    last_time = time()
    nmasked, ncmpltd, nskipped, icount = 4 * [0]
    site_recs = []
    for lat_indx, lat in enumerate(soc_dset.variables['lat']):
        lat = lat.item()

        for lon_indx, lon in enumerate(soc_dset.variables['lon']):
            last_time = update_soc_rothc_progress(last_time, nmasked, ncmpltd, nskipped, icount)
            icount += 1
            if icount < START_FROM:
                continue

            lon = lon.item()
            soil_carb = slice[lat_indx][lon_indx]
            if is_masked(soil_carb):
                val = soil_carb.item()  # val should be zero
                nmasked += 1
            else:
                grid_coord = '{0:0=4g}_{1:0=4g}'.format(lon_indx, lat_indx)
                if grid_coord in exstng_no_wrthr_coords:
                    nskipped += 1
                    continue

                wthr_fut_fns, fut_skip_flag = _generate_file_names(out_dirs, grid_coord, 'fut')
                wthr_hist_fns, hist_skip_flag = _generate_file_names(out_dirs, grid_coord, 'hist')
                if fut_skip_flag and hist_skip_flag:
                    nskipped += 1
                    continue

                site_rec = ([lat, lat_indx, lon, lon_indx, grid_coord, wthr_fut_fns, wthr_hist_fns, soil_carb])
                site_recs.append(site_rec)
                ncmpltd += 1

            if ncmpltd >= max_cells:
                break

        if ncmpltd >= max_cells:
            break

    soc_dset.close()

    mess = '\nRetrieved {} cells from SOC file: {}'.format(format(ncmpltd, ',' ), ds_soil_org)
    print(mess)

    return site_recs

def _read_soil_organic_detail(form):
    """
    GSOCmap_0.25.nc organic carbon has latitiude extant of 83 degs N, 56 deg S
    """
    prj_dir = form.w_prj_dir.text()
    soc_fn = join(prj_dir, NC_FROM_TIF_FN)
    if not lexists(soc_fn):
        print(ERROR_STR + 'Soil organic carbon file ' + soc_fn + ' must exist, cannot continue')
        return

    soil_org_set = _fetch_soil_org_nc_parms(soc_fn)
    soil_org_set['base_dir'] = prj_dir
    soil_org_set['ds_soil_org'] = soc_fn

    return soil_org_set

def _fetch_soil_org_nc_parms(nc_fname):
    """
    create object describing soil organic dataset characteristics
    """
    # standard names
    # ==============
    lat = 'lat'
    lon = 'lon'

    # retrieve chcaracteristics
    # =========================
    nc_fname = normpath(nc_fname)
    nc_dset = Dataset(nc_fname, 'r')

    lat_var = nc_dset.variables[lat]
    lon_var = nc_dset.variables[lon]

    # use list comprehension to convert to floats
    # ===========================================
    lats = [round(float(lat), 5) for lat in list(lat_var)]  # rounding introduced for EObs
    lons = [round(float(lon), 5) for lon in list(lon_var)]

    lat_frst = lats[0]
    lon_frst = lons[0]
    lat_last = lats[-1]
    lon_last = lons[-1]

    if lat_last > lat_frst:
        lat_ll = lat_frst; lat_ur = lat_last
    else:
        lat_ll = lat_last; lat_ur = lat_frst

    if lon_last > lon_frst:
        lon_ll = lon_frst; lon_ur = lon_last
    else:
        lon_ll = lon_last; lon_ur = lon_frst

    # resolutions
    # ===========
    resol_lon = round((lons[-1] - lons[0])/(len(lons) - 1), 6)
    resol_lat = round((lats[-1] - lats[0])/(len(lats) - 1), 6)
    if abs(resol_lat) != abs(resol_lon):
        mess = WARNING_STR + ' soil organic resource has different lat/lon resolutions: '.format(nc_fname)
        print(mess + '{} {}'.format(resol_lat, resol_lon))

    nc_dset.close()

    # construct weather_resource
    # ==========================
    soil_org_rsrc = {'resol_lat': resol_lat, 'lat_frst': lat_frst, 'lat_last': lat_last,
                                                                                'lat_ll': lat_ll, 'lat_ur': lat_ur,
            'resol_lon': resol_lon, 'lon_frst': lon_frst, 'lon_last': lon_last, 'lon_ll': lon_ll, 'lon_ur': lon_ur,
            'longitudes': lons, 'latitudes': lats}

    print('Soc NC: {}\tresolution: {} degrees\n'.format(nc_fname, resol_lat))

    return soil_org_rsrc

def _make_output_dirs(form):
    """
    if necessary create output directories and no weather data file
    out_dir = 'E:\\Saeed\\outputs'
    """
    out_dir = form.setup['out_dir']
    if not exists(out_dir):
        mkdir(out_dir)
    print('\nWill write Rothc climate data to: ' + out_dir)
    form.setup['out_dir'] = out_dir

    out_dirs = {}
    for ctgry in ['fut', 'hist']:
        out_dirs[ctgry] = join(out_dir, ctgry)
        if not exists(out_dirs[ctgry]):
            mkdir(out_dirs[ctgry])

    # create or read no weather data file
    # ===================================
    no_wrthr_list_fn = join(out_dir, 'no_wthr_list.csv')
    if exists(no_wrthr_list_fn):
        fobj = open(no_wrthr_list_fn, 'r', newline='')
        rdr = reader(fobj, delimiter=',')
        grid_coords = [row[-1] for row in rdr]
        fobj.close()

    else:
        Path(no_wrthr_list_fn).touch()
        grid_coords = []

    print('Read {} no weather grid cells from: '.format(len(grid_coords)) + no_wrthr_list_fn)

    return  out_dirs, no_wrthr_list_fn, grid_coords

def _fetch_wrld_clim_indices(climgen, bbox):
    """
    not yet used
    """
    lon_ll, lat_ll, lon_ur, lat_ur = bbox

    resol = climgen.fut_wthr_set_defn['resol_lat']
    lat_frst = climgen.fut_wthr_set_defn['lat_frst']
    lon_frst = climgen.fut_wthr_set_defn['lon_frst']

    lat_indx_min = round((lat_ll - lat_frst)/resol)
    lat_indx_max = round((lat_ur - lat_frst)/resol)

    lon_indx_min = round((lon_ll - lon_frst) / resol)
    lon_indx_max = round((lon_ur - lon_frst) / resol)

    return (lat_indx_min, lat_indx_max, lon_indx_min, lon_indx_max)

def _generate_pet(climgen, pettmp, lat):
    """
    generate PET
    """
    year = climgen.sim_start_year
    pet = []
    for indx1 in range(0, len(pettmp['tas']), 12):
        indx2 = indx1 + 12
        one_yr_tas = pettmp['tas'][indx1:indx2]
        pet += thornthwaite(one_yr_tas, lat, year)
        year += 1

    pettmp['pet'] = pet

    return pettmp