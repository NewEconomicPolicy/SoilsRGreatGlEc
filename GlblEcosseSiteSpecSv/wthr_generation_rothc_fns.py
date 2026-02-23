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
from os.path import split, join, exists, lexists, normpath
from numpy.ma import is_masked
from netCDF4 import Dataset
from time import time
from PyQt5.QtWidgets import QApplication

from getClimGenNC import ClimGenNC
from getClimGenFns import (fetch_WrldClim_data, fetch_WrldClim_NC_data, associate_climate,
                           open_wthr_NC_sets, get_wthr_nc_coords, join_hist_fut_to_sim_wthr)
from glbl_ecsse_low_level_fns import update_wthr_rothc_progress, update_soc_rothc_progress

from thornthwaite import thornthwaite

ERROR_STR = '*** Error *** '
WARNING_STR = '*** Warning *** '

GRANULARITY = 120
NC_FROM_TIF_FN ='E:\\Saeed\\GSOCmap_0.25.nc'
METRIC_LIST = list(['precip', 'tas'])
METRIC_DESCRIPS = {'precip': 'precip = total precipitation (mm)',
                    'tas': 'tave = near-surface average temperature (degrees Celsius)'}

def _generate_file_names(out_dirs, grid_coord, fut_or_hist):
    """
     C
     """
    skip_flag = False
    wthr_fnames = {}
    nexist = 0
    for metric in METRIC_LIST:
        wthr_fname = metric + '_' + grid_coord + '.txt'
        wthr_fnames[metric] = join(out_dirs[fut_or_hist], wthr_fname)

        # potentially skip existing files
        # ===============================
        if exists(wthr_fnames[metric]):
            nexist += 1

    # if both files exist then skip
    # =============================
    if nexist == 2:
        skip_flag = True

    return wthr_fnames, skip_flag

def _generate_rothc_weather(form, climgen, org_soil_defn, num_band, bbox, out_dirs, max_cells):
    """
    C
    """
    fut_wthr_set = form.weather_set_linkages['WrldClim'][1]
    hist_wthr_dsets, fut_wthr_dsets = open_wthr_NC_sets(climgen)

    last_time = time()
    aoi_res = _fetch_grid_cells_from_socnc(org_soil_defn, bbox)
    lon_ll_aoi, lat_ll_aoi, lon_ur_aoi, lat_ur_aoi = bbox

    n_soc_cells = len(aoi_res)
    mess = 'Band {}\taoi LL lon/lat: {} {}\t'.format(num_band, lon_ll_aoi, lat_ll_aoi)
    print(mess + 'UR lon/lat: {} {}\t# cells with data: {}'.format(lon_ur_aoi, lat_ur_aoi, n_soc_cells))
    QApplication.processEvents()
    if n_soc_cells == 0:
        return

    # main loop
    # =========
    nskipped, nnodata, ncmpltd, noutbnds = 4*[0]
    for site_rec in aoi_res:
        update_wthr_rothc_progress(last_time, noutbnds, nnodata, ncmpltd, nskipped)
        gran_lat, gran_lon, lat, lat_indx, lon, lon_indx, grid_coord, soil_carb = site_rec
        grid_coord = '{0:0=5g}_{1:0=5g}'.format(gran_lat, gran_lon)

        wthr_fut_fns, fut_skip_flag = _generate_file_names(out_dirs, grid_coord, 'fut')
        wthr_hist_fns, hist_skip_flag = _generate_file_names(out_dirs, grid_coord, 'hist')
        if fut_skip_flag and hist_skip_flag:
            nskipped += 1
            continue

        # weather set lat/lons
        # ====================
        hist_lat_indx, hist_lon_indx = get_wthr_nc_coords(climgen.hist_wthr_set_defn, lat, lon)
        fut_lat_indx, fut_lon_indx = get_wthr_nc_coords(climgen.fut_wthr_set_defn, lat, lon)
        if hist_lat_indx < 0 or fut_lat_indx < 0:
            noutbnds += 1
            continue

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
        # no weather for this grid cell - so look at adjacent weather cells
        ' ================================================================='
        if pettmp_fut is None or pettmp_hist is None:

            # expand areaa of weather extraction
            # =================================
            wrld_clim_indices = (fut_lat_indx - 1, fut_lat_indx + 1, fut_lon_indx - 1, fut_lon_indx + 1)
            pettmp_hist = fetch_WrldClim_NC_data(form.lgr, wrld_clim_indices, climgen, hist_wthr_dsets)
            pettmp_fut = fetch_WrldClim_NC_data(form.lgr, wrld_clim_indices, climgen, fut_wthr_dsets)
            retcode = associate_climate(site_rec, climgen, pettmp_hist, pettmp_fut)
            if len(retcode) == 0:
                mess = WARNING_STR + 'no weather data'
                print(mess + ' for site with lat: {}\tlon: {}'.format(round(lat, 3), round(lon, 3)))
                nnodata += 1
                continue
            else:
                pettmp_hist, pettmp_fut = retcode
                pettmp_sim = join_hist_fut_to_sim_wthr(climgen, pettmp_hist, pettmp_fut)
        else:
            pettmp_sim = join_hist_fut_to_sim_wthr(climgen, pettmp_hist, pettmp_fut)

        # create weather
        # ==============
        if not fut_skip_flag:
            _make_rthc_fut_files(wthr_fut_fns, lat, lat_indx, lon, lon_indx, climgen, lat_wthr, lon_wthr, pettmp_sim)

        if not hist_skip_flag:
            _make_rthc_hist_files(wthr_hist_fns, lat, lat_indx, lon, lon_indx, climgen, lat_wthr, lon_wthr, pettmp_hist)

        ncmpltd += 1
        if ncmpltd >= max_cells:
            break

    mess = '\nCompleted RothC weather generation for Band {}'.format(num_band)
    mess += ' - total number of sets written: {}'.format(ncmpltd)
    mess += '\n\tCells skipped: {}\tnno data: {}\tcompleted: {}'.format(nskipped, nnodata, ncmpltd)
    print(mess + '\tout of bounds: {}\n'.format(noutbnds))

    return

def _make_rthc_hist_files(wthr_fnames, lat, lat_indx, lon, lon_indx, climgen, lat_wthr, lon_wthr, pettmp_hist):
    """
    write a RothC weather dataset
    """
    hdr_recs = _fetch_hist_hdr_recs(lat, lat_indx, lon, lon_indx, climgen, lat_wthr, lon_wthr)
    frst_rec, period, location_rec, box_rec, grid_ref_rec = hdr_recs

    for metric in METRIC_LIST:
        metric_descr = METRIC_DESCRIPS[metric]

        pettmp = _reform_hist_rec(climgen, pettmp_hist[metric])
        data_recs = _generate_data_recs(pettmp)

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

def _fetch_segment(pettmp, strt_yr_data, yr_strt, yr_end):
    """
    create strings for header records
    From the WorldClim database of high spatial resolution global weather and climate data.
    """
    indx_strt =  12 * (yr_strt - strt_yr_data)
    indx_end = 12 * (yr_end - strt_yr_data + 1)
    segmnt = pettmp[indx_strt:indx_end]
    nyears = int(len(segmnt)/12)

    return segmnt, nyears

def _reform_hist_rec(climgen, pettmp):
    """
    create strings for header records
    From the WorldClim database of high spatial resolution global weather and climate data.
    """
    seg1, nyears = _fetch_segment(pettmp, climgen.hist_start_year, 1961, 2000)
    seg2, nyears = _fetch_segment(pettmp, climgen.hist_start_year, 1971, 2000)
    pettmp = seg1 + seg2 + seg2
    pettmp.reverse()

    return pettmp

def _fetch_hist_hdr_recs(lat, lat_indx, lon, lon_indx, climgen, lat_wthr, lon_wthr):
    """
    create strings for header records
    From the WorldClim database of high spatial resolution global weather and climate data.
    """
    frst_rec = 'From the WorldClim database of global weather and climate data using historic data'

    # period = str(climgen.hist_start_year) + '-' + str(climgen.hist_end_year)
    period = str(1901) + '-' + str(2000)    # TODO - requires improvemnt

    location_rec = '[Long= ' + str(round(lon, 3)) + ', ' + str(round(lon_wthr, 3))
    location_rec += '] [Lati= ' + str(round(lat, 3)) + ', ' + str(round(lat_wthr))
    location_rec +=  '] [Grid X,Y= ' + str(lon_indx) + ', ' + str(lat_indx) + ']'
    box_rec = '[Boxes=   31143] [Years=' + period + '] [Multi=    0.1000] [Missing=-999]'
    grid_ref_rec = 'Grid-ref=  ' + str(lon_indx) + ', ' + str(lat_indx)

    return (frst_rec, period, location_rec, box_rec, grid_ref_rec)

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

def generate_banded_rothc_wthr(form):
    """
    called from GUI; based on generate_banded_sims from HoliSoilsSpGlEc project
    GSOCmap_0.25.nc organic carbon has latitiude extant of 83 degs N, 56 deg S
    """
    LAT_STEP = 5.0
    START_AT_BAND = 0
    END_AT_BAND = 20

    out_dirs = _make_output_dirs()

    max_cells = int(form.w_max_cells.text())
    org_soil_defn = read_soil_organic_detail(form)

    # bounding box
    # ============
    lon_ll_aoi, lon_ur_aoi = 0.0, 20.0
    lat_ll_aoi, lat_ur_aoi = -53.0, 83.0
    nbands = int((lat_ur_aoi - lat_ll_aoi) / LAT_STEP) + 1
    nbands_to_prcss = END_AT_BAND - START_AT_BAND + 1

    mess = 'Total # of bands: {}\twill process {} bands\t'.format(nbands, nbands_to_prcss)
    mess += 'starting and ending at bands {} and {}'.format(START_AT_BAND, END_AT_BAND)
    print(mess)
    QApplication.processEvents()

    bbox_aoi = list([lon_ll_aoi,lat_ll_aoi,lon_ur_aoi,lat_ur_aoi])

    # weather choice
    # ==============
    weather_resource = form.w_combo10w.currentText()

    # main banding loop
    # =================
    sim_strt_year = 2001

    fut_wthr_set = form.weather_set_linkages['WrldClim'][1]
    sim_end_year = form.wthr_sets[fut_wthr_set]['year_end']

    this_gcm = form.w_combo10w.currentText()
    scnr =  form.w_combo10.currentText()

    region, crop_name = 2 * [None]
    climgen = ClimGenNC(form, region, crop_name, sim_strt_year, sim_end_year, this_gcm, scnr)

    band_reports = []
    lat_ur = lat_ur_aoi
    for iband in range(nbands):
        lat_ll_new = lat_ur - LAT_STEP
        num_band = iband + 1
        if lat_ll_new > lat_ur_aoi:
            mess = 'Skipping simulations at band {} since new band latitude floor '.format(num_band)
            print(mess + '{} exceeds AOI upper latitude {}'.format(round(lat_ll_new,6), round(lat_ur_aoi, 3)))

        elif num_band < START_AT_BAND:
            mess = 'Skipping out of area band {} of {}'.format(num_band, nbands)
            mess += ' with latitude extent of min: {}\tmax: {}'.format(round(lat_ll_new, 3), round(lat_ur, 3))
            print(mess)

        elif num_band > END_AT_BAND:
            print('Exiting from processing after {} bands'.format(num_band - 1))
            break
        else:
            bbox = list([lon_ll_aoi, lat_ll_new, lon_ur_aoi, lat_ur])
            form.bbox = bbox
            mess = '\nProcessing band {} of {}'.format(num_band, nbands_to_prcss)
            mess += ' with latitude extent of min: {}\tmax: {}'.format(round(lat_ll_new, 3), round(lat_ur, 3))
            QApplication.processEvents()

            report = _generate_rothc_weather(form, climgen, org_soil_defn, num_band, bbox, out_dirs, max_cells)   # does actual work
            band_reports.append(report)

        # check to see if the last band is completed
        # ==========================================
        if lat_ll_aoi > lat_ll_new:
            break

        lat_ur = lat_ll_new

    print('Finished processing after {} bands of latitude extents'.format(num_band))
    #      ======================================================
    QApplication.processEvents()
    form.band_reports = band_reports
    for report in band_reports:
        form.lgr.info(report)

    return

def _make_rthc_fut_files(wthr_fnames, lat, lat_indx, lon, lon_indx, climgen, lat_wthr, lon_wthr, pettmp_sim):
    """
    write a RothC weather dataset
    """
    hdr_recs = _fetch_fut_hdr_recs(lat, lat_indx, lon, lon_indx, climgen, lat_wthr, lon_wthr)
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

def _fetch_fut_hdr_recs(lat, lat_indx, lon, lon_indx, climgen, lat_wthr, lon_wthr):
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

def _fetch_grid_cells_from_socnc(org_soil_defn, bbox):
    """
    fetch grid cells from socNC file for given bounding box
    """
    lon_ll, lat_ll, lon_ur, lat_ur = bbox

    # check each value, discarding Nans - total size of file is 618 x 1440 = 889,920 cells
    # ====================================================================================
    soc_dset = Dataset(org_soil_defn['ds_soil_org'] )
    lat_ll_indx, lon_ll_indx = get_wthr_nc_coords(org_soil_defn, lat_ll, lon_ll)
    lat_ur_indx, lon_ur_indx = get_wthr_nc_coords(org_soil_defn, lat_ur, lon_ur)

    last_time = time()

    nmasked, ncmpltd = 2 * [0]
    site_recs = []
    for lat_indx in range(lat_ll_indx, lat_ur_indx):
        lat = org_soil_defn['latitudes'][lat_indx]

        for lon_indx in range(lon_ll_indx, lon_ur_indx):
            lon = org_soil_defn['longitudes'][lon_indx]
            last_time = update_soc_rothc_progress(last_time, nmasked, ncmpltd)

            soil_carb = soc_dset.variables['Band1'][lat_indx][lon_indx]

            # discard masked grid cells
            if is_masked(soil_carb):
                val = soil_carb.item()  # val should be zero
                nmasked += 1
            else:
                gran_lat = round((90.0 - lat) * GRANULARITY)
                gran_lon = round((180.0 + lon) * GRANULARITY)
                grid_coord = '{0:0=5g}_{1:0=5g}'.format(gran_lat, gran_lon)
                site_rec = ([gran_lat, gran_lon, lat, lat_indx, lon, lon_indx, grid_coord, soil_carb])
                site_recs.append(site_rec)

    return site_recs

def read_soil_organic_detail(form):
    """
    GSOCmap_0.25.nc organic carbon has latitiude extant of 83 degs N, 56 deg S
    """
    if not lexists(NC_FROM_TIF_FN):
        print(ERROR_STR + 'Soil organic carbon file ' + NC_FROM_TIF_FN + ' must exist, cannot continue')
        return

    soil_org_set = _fetch_soil_org_nc_parms(NC_FROM_TIF_FN)
    soil_org_set['base_dir'] = split(NC_FROM_TIF_FN)[0]
    soil_org_set['ds_soil_org'] = NC_FROM_TIF_FN

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

def _make_output_dirs():
    """
    if necessary create output directories
    """
    out_dir = 'E:\\Saeed\\outputs'
    if not exists(out_dir):
        mkdir(out_dir)
    print('\nWill write Rothc climate data to: ' + out_dir)

    out_dirs = {}
    for ctgry in ['fut', 'hist']:
        out_dirs[ctgry] = join(out_dir, ctgry)
        if not exists(out_dirs[ctgry]):
            mkdir(out_dirs[ctgry])

    return  out_dirs

def _fetch_wrld_clim_indices(climgen, bbox):

    lon_ll, lat_ll, lon_ur, lat_ur = bbox

    resol = climgen.fut_wthr_set_defn['resol_lat']
    lat_frst = climgen.fut_wthr_set_defn['lat_frst']
    lon_frst = climgen.fut_wthr_set_defn['lon_frst']

    lat_indx_min = round((lat_ll - lat_frst)/resol)
    lat_indx_max = round((lat_ur - lat_frst)/resol)

    lon_indx_min = round((lon_ll - lon_frst) / resol)
    lon_indx_max = round((lon_ur - lon_frst) / resol)

    return (lat_indx_min, lat_indx_max, lon_indx_min, lon_indx_max)

