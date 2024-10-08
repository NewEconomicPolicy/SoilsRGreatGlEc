#-------------------------------------------------------------------------------
# Name:        getClimGenNC.py
# Purpose:     read netCDF files comprising ClimGen data
# Author:      s03mm5
# Created:     08/12/2015
# Copyright:   (c) s03mm5 2015
# Licence:     <your licence>
#-------------------------------------------------------------------------------
#!/usr/bin/env python

__prog__ = 'getClimGenNC.py'
__author__ = 's03mm5'

from os import remove, mkdir
from os.path import join, normpath, isdir, isfile
from os.path import split as split_dir

from thornthwaite import thornthwaite

numSecsDay = 3600*24
ngranularity = 120
wthr_rsrce_permitted = list(['CRU', 'EObs', 'EWEMBI'])

ERROR_STR = '*** Error *** '

def _consistency_check(pettmp, varnams_mapped):
    '''
    make sure for a each key if one metric is zero length then all other metrics for that key are also blank
    TODO: this function only works for two metrics and is unpythonic!
    '''
    metric_list = list(varnams_mapped.values())
    metric0 = metric_list[0]
    metric1 = metric_list[1]
    for key in pettmp[metric0]:
        len_key0 = len(pettmp[metric0][key])

        if len_key0 == 0:
            pettmp[metric1][key] = []

        len_key1 = len(pettmp[metric1][key])
        if len_key1 == 0:
            pettmp[metric0][key] = []

    return pettmp

def _check_list_for_none(metric_list):
    '''
    if a None is found then return an empty list
    '''
    for indx, val in enumerate(metric_list):
        if val is None:
            return []

    return metric_list

class ClimGenNC(object,):

    def __init__(self, form, region, crop_name, sim_start_year, sim_end_year= -999, this_gcm=None , scnr=None):
        """

        """
        func_name =  __prog__ +  ' ClimGenNC __init__'

        if form.w_mnthly.isChecked():   # monthly timestep
            sim_mnthly_flag = True
        else:
            sim_mnthly_flag = False     # daily timestep

        ave_wthr_flag = form.w_ave_wthr.isChecked()
        if this_gcm is None:
            wthr_rsrce = form.combo10w.currentText()
            fut_clim_scen = form.combo10.currentText()
        else:
            wthr_rsrce = this_gcm
            fut_clim_scen = scnr

        hist_start_year = int(form.combo09s.currentText())
        hist_end_year = int(form.combo09e.currentText())

        # ===============================================================
        hist_wthr_set = form.wthr_sets['WrldClim_hist']
        fut_wthr_set  = form.wthr_sets[wthr_rsrce + '_' + fut_clim_scen]

        # create weather resource directory if necessary
        # ==============================================
        region_wthr_dir = form.setup['region_wthr_dir'] + wthr_rsrce + '_' + fut_clim_scen
        clim_dir = normpath(join(form.setup['sims_dir'], region_wthr_dir))
        if not isdir(clim_dir):
            mkdir(clim_dir)
            print('\tcreated: ' + clim_dir)

        self.region_wthr_dir = region_wthr_dir

        self.region_study = form.setup['region_study']
        self.region = region
        crop_code = form.setup['crops'][crop_name]
        self.crop_names = list([crop_name])
        self.crop_codes = list([crop_code])

        # make sure start and end years are within dataset limits
        # =======================================================
        self.wthr_rsrce         = wthr_rsrce
        self.fut_clim_scen      = fut_clim_scen
        self.fut_wthr_set_defn  = fut_wthr_set
        self.hist_wthr_set_defn = hist_wthr_set
        self.lgr = form.lgr

        hist_start_year = max(hist_wthr_set['year_start'], hist_start_year)
        hist_end_year   = min(hist_wthr_set['year_end'], hist_end_year)
        self.num_hist_years = hist_end_year - hist_start_year + 1
        self.hist_start_year = hist_start_year
        self.hist_end_year   = hist_end_year

        self.months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

        # New stanza to facilitate option when user selects "use average weather"
        # =======================================================================
        num_years_str = '{:0=3d}'.format(self.num_hist_years)
        self.met_ave_file = 'met' + num_years_str + 'a.txt'
        self.num_ave_wthr_years = hist_end_year - hist_start_year + 1   # taken into account only historic data years

        self.ave_wthr_flag   = ave_wthr_flag
        self.sim_mnthly_flag = sim_mnthly_flag
        self.sim_start_year  = sim_start_year

        if sim_end_year == -999:
            sim_end_year = self.fut_wthr_set_defn['year_end']
        self.sim_end_year = sim_end_year

        self.num_sim_years   =  sim_end_year - sim_start_year + 1
        self.sim_ave_file    = 'met{}_to_{}_ave.txt'.format(sim_start_year, sim_end_year)

    def create_FutureAverages(self, clim_dir, lat_inp, site, lta_precip, lta_tmean):
        '''
        use prexisting metyyyys.txt files to generate a text file of average weather which will subsequently
        be included in the input.txt file
        also create a climate file for each of the simulation years based on average weather from the CRU year range
        '''
        func_name =  ' create_FutureAverages'
        full_func_name =  __prog__ +  func_name

        sim_start_year = self.sim_start_year
        sim_end_year   = self.sim_end_year
        months = self.months

        # delete if already exists
        # =======================
        sim_ave_met_file = join(normpath(clim_dir), self.sim_ave_file)
        if isfile(sim_ave_met_file):
            remove(sim_ave_met_file)

        met_ave_file = join(normpath(clim_dir), self.met_ave_file)
        if isfile(met_ave_file):
            remove(met_ave_file)

        # read  precipitation and temperature
        # ===================================
        sim_precip = {}
        sim_tmean = {}
        for month in months:
            sim_precip[month] = 0.0
            sim_tmean[month] = 0.0

        for year in range(sim_start_year, sim_end_year):
            fname = 'met{0}s.txt'.format(year)
            met_fpath = join(clim_dir, fname)

            if not isfile(met_fpath):
                print('File ' + met_fpath + ' does not exist - will abandon average weather creation')
                return -1

            with open(met_fpath, 'r', newline='') as fpmet:
                lines = fpmet.readlines()

            for line, month in zip(lines, months):
                tlst = line.split('\t')
                try:
                    sim_precip[month] += float(tlst[1])
                    sim_tmean[month]  += float(tlst[3].rstrip('\r\n'))
                except IndexError as err:
                    print(ERROR_STR + str(err))

        # note float conversion from float32 otherwise rounding does not work as expected
        lta = {'pet': [], 'precip': lta_precip, 'tas': lta_tmean}
        lta['pet'] = thornthwaite(lta['tas'], lat_inp, year)

        site.lta_pet = [round(float(pet), 1) for pet in lta['pet']]
        site.lta_precip = [round(float(precip), 1) for precip in lta['precip']]
        site.lta_tmean = [round(float(tmean), 1) for tmean in lta['tas']]

        dummy, location = split_dir(clim_dir)
        self.lgr.info('Generated average weather at location {} in function {}'.format(location, func_name))

        return 0