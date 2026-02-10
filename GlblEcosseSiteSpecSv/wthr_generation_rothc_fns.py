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

from os.path import split

from netCDF4 import Dataset

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

    dset = Dataset(NC_FROM_TIF_FN)
    dset.close()

    print('Finished RothC weather generation - total number of sets written: {}'.format(ntotal_wrttn))

    return

def make_rthc_wthr_files(site, lat, lon, climgen, pettmp_hist, pettmp_sim):
    """
    write a RothC weather data
    """

    return
