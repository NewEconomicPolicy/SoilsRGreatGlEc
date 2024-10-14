#-------------------------------------------------------------------------------
# Name:        make_site_spec_files_classes.py
# Purpose:     Generate ECOSSE site mode inpt files
# Author:      Mark Richards, University of Aberdeen
# Created:     30/05/2012
# Licence:     <your licence>
#-------------------------------------------------------------------------------
#!/usr/bin/env python

__version__ = '1.0.00'

from os.path import join, normpath
from datetime import timedelta, date
from calendar import month_abbr
from shutil import copyfile

from pedotransfer import boelter, bss

def _crop_rotation(iyr, climgen, rota_pattern):
    """
    return crop name and code for this year
    """
    crop_code = climgen.crop_codes[0]
    crop_name = climgen.crop_names[0]

    if rota_pattern is not None:
        if iyr >= rota_pattern['start_year']:

            crop_names = list(rota_pattern['crops'].keys())
            n_rota_crops = len(crop_names)
            i_rota = iyr % n_rota_crops

            crop_name = crop_names[i_rota]
            crop_code = rota_pattern['crops'][crop_name]

    return crop_name, crop_code

def _residues_incorporate(cultiv_pattern, nyears):
    """
    return list of residues incorporated flags for each year
    """
    residues_incorp = []
    cultiv_iter = iter(cultiv_pattern.keys())
    change_year = 0  # initialise to zero to force a read of the cultivation pattern
    this_key = next(cultiv_iter)
    for iyr in range(nyears):
        if iyr >= change_year:
            dummy, dummy, residue_incorp = cultiv_pattern[this_key]  # read the cultivation pattern
            try:
                this_key = next(cultiv_iter)  # get the next year when there is a change
                change_year = int(this_key)
            except StopIteration:
                change_year = 99999

        residues_incorp.append(residue_incorp)

    return residues_incorp

class MakeSiteFiles(object):
    """

    """
    _luts = ['ara', 'gra', 'for', 'nat', 'mis', 'src']
    months = list(month_abbr[1:])

    def __init__(self, form,  climgen, comments = True, spacer_len = 12, nan = -999):
        """

        """
        if hasattr(form, 'w_equimode'):
            equil_mode = form.w_equimode.text()
            manure_flag = form.w_manure.isChecked()
        else:
            equil_mode = form.equimode
            manure_flag = False

        self.comments = comments      # True = write comments, False = leave them out
        self.spacer_len = spacer_len  # Number of spaces between data and comment
        self.nan = nan
        self.sims_dir      = form.setup['sims_dir']
        self.equil_mode    = equil_mode         # Mode of equilibrium run
        self.manure_flag   = manure_flag
        self.dflt_ecosse_fnames = form.dflt_ecosse_fnames

        nyears              = climgen.sim_end_year - climgen.sim_start_year + 1     # Number of years in simulation
        self.nyears         = nyears
        self.start_year     = climgen.sim_start_year     # start year of simulation
        self.ncrops         = nyears  # Number of crops - one crop per year
        self.ncultivations  = nyears  # one cultivation per year
        self.cultiv_pattern = form.cultiv_pattern
        self.rota_pattern = form.rota_pattern
        self.residues_incorp = _residues_incorporate(form.cultiv_pattern, nyears)
        self.hwsd_ref_depths = [30, 100]  # see HWSD manual

        #-----------------------------------------------------------------------
        # Input data
        # Model settings - timestep (0=30 min, 1=daily, 2=weekly, 3=monthly)
        # -----------------------------------------------------------------------
        if climgen.sim_mnthly_flag:
            self.timestep = 3
        else:
            self.timestep = 1

        self.crop_model = 0            # 0=SUNDIAL, 1=MAGEC
        self.start_doy  = 0            # Day of the year that the simulation starts on
        self.ntime_steps = nan         # Number of timesteps in simulation
        self.fixed_sim_end = 0         # Fixed end of simulation? (0=no, 1=yes)
        self.met_fnames    = []        # Names of the met files

        # Site
        # ====
        self.lat = nan  # Latitude [decimal degrees]
        self.lon = nan  # Longitude [decimal degrees]

        # Soil
        # ====
        self.nlyrs = nan
        self.lyr_depths = []
        self.soil_lyrs = {}
        for lut in self._luts:
            self.soil_lyrs[lut] = []
        self.soil_name = 'xxxx'         # Name of soil
        self.soil_code = nan            # Soil code number
        self.drain_class = nan          # Drainage class (1=low, 2=moderate, 3=high) Not currently implemented.
        self.depth_imperm_lyr = nan     # Depth to impermeable layer (1=50cm, 2=100cm, 3=150cm
        self.date_reaches_fc = 1        # Date soil reaches field capacity (1=01/01; 2=01/06)
        self.wtr_tbl_dpth = nan         # Water Table depth [cm],  if > 150 cm than there is no effect
        self.clay = nan                 # clay content [proportion]
        self.bulk_density = nan         # Bulk desnity [g/cm3]
        self.swc_wp = nan               # Soil water content at wilting point [mm/25cm]
        self.awc_fc = nan               # Available water content at field capacity [mm/25cm]
        self.awc_sat = nan              # Available water content at saturation [mm/25cm]
        self.biohum_stable_n2c = 0.118    # Stable N:C ratio of biomass and humus
        self.biohum_frac = 0.29          # Fraction of BIO + HUM formed: (biomass + humus) / total decomposition
        self.biohum_from_bio = 0.85      # Fraction of BIO + HUM produced from biomass decomposition
        self.biohum_from_hum = 0.85      # Fraction of BIO + HUM produced from humus decomposition
        self.bio_frac = 0.028             # Fraction of biomass in total organic C
        self.min_n_lvl = 0.0            # Minimum level of nitrate in soil [kg N/ha/50cm layer]
        self.k_bio = 0.635                # Rate constant for biomass decomposition [/year]
        self.k_hum = 0.02                # Rate constant for humus decomposition [/year]
        self.toc = nan                   # Total organic matter in top 50cm of soil [kg C/ha]
        self.iom_c = nan                  # Inert organic matter in top 50cm of soil [kg C/ha]
        self.soil_depth = 25.0           # Depth of soil used in initialisation [cm]
        self.ph = nan                   # pH of soil
        self.ph_zero_decomp = 2.5       # pH at which decomposition has declined to zero
        self.ph_decline_decomp = 5.5    # pH at which decomposition starts to decline

        # Climate
        # =======
        self.lta_precip = None
        self.lta_tmean = None
        self.lta_pet = None

        # Land use
        # ========
        self.prev_lu = nan   # Land use before equilibrium run (1=arable, 2=grass, 3=forestry, 4=natural/scrub
        self.future_lu = []  # List of future land use codes (1 per year)

        # Crops & plant inputs
        # ====================
        self.prev_crop_code = nan       # Previous crop code
        self.yield_prev_crop = nan      # Yield of previous crop [t/ha]

        self.crops        = []   # List of Crop objects
        self.cultivations = []   # List of Cultivation objects
        self.future_pi    = []   # List of future annual plant inputs (1 element per year), 0 = estimate using MIAMI
        self.plant_inputs = {}
        for lut in self._luts:
            self.plant_inputs[lut] = 0
        self.prev_crop_harvest_doy = nan

        # Inputs
        # ======
        self.atmos_n_dep = 0.0

        # Not yet implemented
        # ===================
        self.c_accum_b4_change = 0.0
        self.ch4_b4_change = 0.0
        self.co2_b4_change = 0.0
        self.doc_loss_b4_change = 0.0

        self.del_soil_lyrs()

        # adjust planting and harvest day to simulate perennial crops
        # ===========================================================
        year_from = int(form.w_yr_from.text())
        if form.w_use_peren.isChecked():
            self.peren_yr = year_from
        else:
            self.peren_yr = None

        if form.w_manure.isChecked():
            self.manure_yr = year_from
        else:
            self.manure_yr = 0

    def create_site_soil_layers(self, soil_list):
        """
        rework soil list into an intelligible dictionary
        """
        # soc, Bulk density [g/cm3], pH ,  % clay by weight, % silt by weight, % sand by weight
        soil_metric_list = list(['soc', 'Bulk_Density', 'ph', 'clay', 'silt', 'sand'])

        if len(soil_list) == 7:
            num_lyrs = 1
            lyr_depths = self.hwsd_ref_depths[0:1]
        else:
            num_lyrs = 2
            lyr_depths = self.hwsd_ref_depths[:]

        soil = {}
        for metric in soil_metric_list:
            soil[metric] = []

        for lyr_num in range(num_lyrs):  # typically: 2
            for ic, metric in enumerate(soil_metric_list):
                strt_indx = 6 * lyr_num
                soil[metric].append(soil_list[strt_indx + ic])

        self.nlyrs = num_lyrs
        self.lyr_depths = lyr_depths

        self.soil_name = 'xxxx'  # TODO: ideas?
        lu_names = self._luts

        # use first layer
        # ===============
        ilayer = 0
        self.iom_c = 0.0  # TODO: estimate Inert organic matter?

        for ilayer in range(self.nlyrs):
            for lu in range(len(lu_names)):
                self.add_soil_lyr(
                    lu_names[lu],
                    soil['soc'][ilayer],  # TODO: check this value, soil carbon content [kgC/ha]
                    soil['Bulk_Density'][ilayer],
                    soil['ph'][ilayer],
                    soil['clay'][ilayer],
                    soil['silt'][ilayer],
                    soil['sand'][ilayer]
                )

        # Sozanka equation
        # ================
        self.min_n_lvl = round(5 + (soil['clay'][0] * 10.0 / 65.0), 1)

        # Calculate soil water capacities
        # ===============================
        # TODO: check whether top soil or sub-soil required
        bulk_dens = soil['Bulk_Density'][0]
        org_carb = soil['soc'][0] / (bulk_dens * self.lyr_depths[0] * 1000.0)

        if org_carb > 30.0:
            # Peat, so use Boelter equations
            wc_wp, awc_fc, awc_sat = boelter(bulk_dens, self.soil_depth * 10.0)
        else:
            # Non-peat so use British Soil Service equations
            wc_wp, awc_fc, awc_sat = bss(
                soil['sand'][0], soil['silt'][0], soil['clay'][0], org_carb, bulk_dens, self.soil_depth * 10.0, True)

        self.wc_wp = round(wc_wp, 1)
        self.awc_fc = round(awc_fc, 1)
        self.awc_sat = round(awc_sat, 1)

        # only required for output
        # ========================
        self.soc = soil['soc'][0]
        self.clay = soil['clay'][0]
        self.ph = soil['ph'][0]
        self.bulk_dens = bulk_dens

        return

    def data_modify_mnthly(self, lat, lon, climgen, met_fnames, fert_recs, plant_day, harvest_day, yield_val):
        """

        """
        if self.timestep != 3:
            print('*** Error *** method data_modify_mnthly is for monthly timestep only')

        # create lists
        # ============
        year_list = []
        for iyr in range(self.nyears):
            year_list.append(iyr)

        n_uptake = 0    # Crop N uptake at harvest (0=calculate internally)

        start_year = self.start_year
        self.ntime_steps = self.nyears * 12
        self.toc = 2.7  # total organic matter in top 50cm of soil [kg C/ha] varies between 0.39 to 5.27 (not used)
        self.iom_c = 0.0  # TODO: estimate this? Inert organic matter in top 50cm of soil [kg C/ha]
        self.met_fnames = met_fnames

        # transfer data from grid cell to self
        # ====================================
        self.lat = round(float(lat), 3)
        self.lon = round(float(lon), 3)

        self.drain_class      = 2    # mngmnt - Drainage class (1=low; 2=moderate; 3=high)
        self.depth_imperm_lyr = 3    # mngmnt - Depth to impermeable layer (1=50cm; 2=100cm; 3=150cm)
        self.wtr_tbl_dpth     = 300  # mngmnt - Water Table of soil (cms)
        self.prev_lu          = 1    # Arable
        self.prev_crop_code   = 1    # mngmnt - Previous crop (from CROP_SUN.DAT)
        self.yield_prev_crop  = yield_val  # mngmnt - Yield of previous crop (t/ha)
        self.prev_crop_harvest_doy = 0          # must not be more than 12 in case of monthly timestep
        self.soil_code = 1

        # assume single annual crop
        # =========================
        naccum_tsteps = 0
        year = start_year
        for iyr, fert_rec in enumerate(fert_recs):

            plant_date = date(year, 1, 1) + timedelta(plant_day)
            harvest_date = date(year, 1, 1) + timedelta(harvest_day)

            # simulate perennial crops
            # ========================
            if self.peren_yr is not None:
                if iyr >= self.peren_yr:
                    plant_date = date(year, 1, 15)
                    harvest_date = date(year, 11, 15)

            sowing_ts    = naccum_tsteps + plant_date.month
            harvest_ts   = naccum_tsteps + harvest_date.month

            crop = Crop()
            crop.crop_name, crop.code = _crop_rotation(iyr, climgen, self.rota_pattern)
            crop.sowing_doy  = sowing_ts
            crop.harvest_doy = harvest_ts
            crop.n_uptake    = n_uptake
            crop.exp_yield   = yield_val
            crop.residues_inc = self.residues_incorp[iyr]

            if crop.code == 12:     # Setaside
                crop.nfert_apps = 0
                crop.nmanure_apps = 0
            else:
                if self.manure_flag and iyr >= self.manure_yr:
                    crop.nfert_apps = 0
                    manure = ManureApplication(fert_rec.amount, fert_rec.app_moy)
                    crop.manure_apps.append(manure)
                    crop.nmanure_apps = len(crop.manure_apps)
                else:
                    # args: amount, app_moy, no3_pc, nh4_pc, urea_pc, non_amm_sulphate_salts=0, labelled=0
                    # ====================================================================================
                    crop.nmanure_apps = 0
                    fert = FertiliserApplication(fert_rec.amount, fert_rec.app_moy, fert_rec.no3_pc,
                                                                        fert_rec.nh4_pc, fert_rec.urea_pc)
                    crop.fert_apps.append(fert)
                    crop.nfert_apps = len(crop.fert_apps)

            self.crops.append(crop)

            naccum_tsteps += 12
            year += 1

        # end here unless cultivations requested
        # ======================================
        if self.cultiv_pattern is None:
            return

        # cultivations
        # ==================
        cultiv_day = max(0, plant_day - 31)  # always one month ahead

        cultiv_iter = iter(self.cultiv_pattern.keys())    # create an iterator
        change_year = 0     # initialise to zero to force a read of the cultivation pattern
        this_key = next(cultiv_iter)
        naccum_tsteps = 0
        sbtrct_mnth = 0
        for iyr in range(self.ncultivations):

            # simulate perennial crops
            # ========================
            if self.peren_yr is not None:
                if iyr >= self.peren_yr:
                    cultiv_day = 15 # january
                    sbtrct_mnth = 1
                else:
                    sbtrct_mnth = 0

            if iyr >= change_year:
                cult_type, cult_vigor, dummy = self.cultiv_pattern[this_key]   # read the cultivation pattern
                try:
                    this_key = next(cultiv_iter)  # get the next year when there is a change
                    change_year = int(this_key)
                except StopIteration:
                    change_year = 99999

            cult_date = date(year, 1, 1) + timedelta(cultiv_day)  # Tillage one month before sowing
            cult_ts = naccum_tsteps + cult_date.month - sbtrct_mnth
            cultivation = Cultivation(cult_ts, cult_type, cult_vigor)
            self.cultivations.append(cultivation)

            naccum_tsteps += 12

        return

    def add_soil_lyr(self, lut_name, c_content, bulk_density, ph, clay_pc, silt_pc, sand_pc):
        """

        """
        self.soil_lyrs[lut_name.lower()].append(
                                    SoilLyr(c_content, bulk_density, ph, clay_pc, silt_pc, sand_pc, self.nan))

    def del_soil_lyrs(self):
        """

        """
        for lut in self._luts:
            self.soil_lyrs[lut] = []

    def _line(self, data, comment):
        """

        """
        spacer_len = max(self.spacer_len - len(data), 2)
        spacer = ' ' * spacer_len
        return '{}{}# {}\n'.format(data, spacer, comment)

    def validate(self):
        pass

    def write_sim_files(self, directory, soil, hist_weather_recs, met_rel_path):
        """

        """
        # self._write_fnames_file(directory)
        self._write_management_file(directory, met_rel_path)
        self._write_soil_file(directory)
        self._write_site_file(directory, hist_weather_recs)
        self._write_avemet_file(directory, met_rel_path)
        '''
        write_crop_sun_file(directory)
        write_crop_pars(directory)  # crop_pars for limited data only
        write_model_switches(directory)
        write_nitpars(directory)
        '''

    def _write_avemet_file(self, directory, met_rel_path):
        """

        """
        avemet_from = join(self.sims_dir, met_rel_path[6:], 'AVEMET.DAT')
        avemet_to = join(directory, 'AVEMET.DAT')
        copyfile(avemet_from, avemet_to)
        '''
        with open(join(directory, 'AVEMET.DAT'), 'w') as f:
            for i, (p, pet, t) in enumerate(zip(self.lta_precip, self.lta_pet, self.lta_tmean)):
                f.write('{} {} {} {}\n'.format(i + 1, p, pet, t))
        '''
    def _write_fnames_file(self, directory):
        """

        """
        dmodel = 1    # Denitrification model chosen: Bradbury, 1 or NEMIS, 2
        icmodel = 2   # Initialisation of SOM pools: fixed initialisation = 1, ICFIXED; RothC equilibrium run = 2, ICROTHCEQ
        inmodel = 1   # Initialisation of N: Bradbury's assumption of stable C:N ratio = 1, INSTABLECN; passed C:N ratio of DPM and RP = 2, INPASSCN
        docmodel = 2  # DOC model: DOC model on =1, DOC_ON; DOC model off = 2, DOC_OFF
        cnmodel = 1   # CN model: C:N ratio obtained by method of MAGEC = 1, CNMAGEC; C:N ratio obtained by method of Foereid = 2, CNFOEREID
        sparmodel = 2 # Soil parameter model: Soil parameters read in from soil.txt file = 1, SPARFILE; Soil parameters calculated from TOC = 2, SPARCALC

        # Type of equilibrium run:	EQNPP, EQTOC, EQNPPTOC, EQHILLIER, EQJONES /1,2,3,4,5/
        # =======================
        equil_mode = float(self.equil_mode)
        if equil_mode >= 9:
            eqmodel = 5
        elif equil_mode == 6:
            eqmodel = 4
        else:
            eqmodel = int(equil_mode)

        imfunc = 0    # Calculation of moisture rate modifiers: IMFUNC_ROTHC = 0, IMFUNC_HADLEY = 1
        itfunc = 0    # Calculation of temp.rate modifiers: ITFUNC_ROTHC = 0, ITFUNC_HADLEY = 1
        ch4model = 0  # CH4 model: CH4 model off = 0, CH4_OFF; Richards CH4 model on = 1, CH4_RICHARDS; Aitkenhead CH4 model on = 2, CH4_AITKENHEAD
        ec_eqrun = 0  # ECOSSE equilibrium run, (0 = off, 1 = on)

        with open(join(directory, 'fnames.dat'), 'w') as f:
            f.write("'management.txt'  'soil.txt'  'site.txt'")
            f.write('\n{}		 DMODEL'.format(dmodel))
            f.write('\n{}		 ICMODEL'.format(icmodel))
            f.write('\n{}		 INMODEL'.format(inmodel))
            f.write('\n{}		 DOCMODEL'.format(docmodel))
            f.write('\n{}		 CNMODEL'.format(cnmodel))
            f.write('\n{}		 SPARMODEL'.format(sparmodel))
            f.write('\n{}		 EQMODEL'.format(eqmodel))
            f.write('\n{}		 IMFUNC'.format(imfunc))
            f.write('\n{}		 ITFUNC'.format(itfunc))
            f.write('\n{}		 CH4MODEL'.format(ch4model))
            f.write('\n{}		 EC_EQRUN'.format(ec_eqrun))
            f.flush()

    def _write_management_file(self, directory, met_rel_path):
        """

        """
        _line = self._line  # Optimisation
        lines = []
        lines.append(self._line('{}'.format(self.soil_code),  'Soil code number'))
        lines.append(self._line('{}'.format(self.drain_class),'Drainage class (1=low, 2=moderate, 3=high) '
                                                                                        'Not currently implemented.'))
        lines.append(self._line('{}'.format(self.depth_imperm_lyr),
                                                            'Depth to impermeable layer (1=50cm, 2=100cm, 3=150cm)'))
        lines.append(self._line('{}'.format(self.prev_crop_code),  'Previous crop code'))
        lines.append(self._line('{}'.format(self.yield_prev_crop), 'Yield of previous crop [t/ha]'))
        lines.append(self._line('{}'.format(self.atmos_n_dep),     'Atmospheric N deposition [kg N/ha]'))
        lines.append(self._line('{}'.format(self.date_reaches_fc),
                                                              'Date field reaches field capacity (1=01/01; 2=01/06)'))
        lines.append(self._line('{}'.format(self.timestep),   'Timestep (0=30 min, 1=daily, 2=weekly, 3=monthly)'))
        lines.append(self._line('{}'.format(self.crop_model), 'Crop model type (0=SUNDIAL, 1=MAGEC)'))
        lines.append(self._line('{}'.format(self.nyears),     'Number of years in simulation'))
        lines.append(self._line('{}'.format(int(self.prev_crop_harvest_doy - self.start_doy)),
                                                                'Timesteps from 01/01 to harvest of previous crop'))
        lines.append(self._line('{}'.format(self.start_year),   'First year of simulation'))
        lines.append(self._line('{}'.format(self.ntime_steps),  'End of simulation [number of timesteps]'))
        lines.append(self._line('{}'.format(self.fixed_sim_end),'Fixed end of simulation? (0=no, 1=yes)'))
        lines.append(self._line('{}'.format(self.lat),          'Latitude [decimal degrees]'))
        lines.append(self._line('{}'.format(self.wtr_tbl_dpth),
                                                 'Water table depth [cm], if > 150 cm there is no effect'))
        for iyr, fname in enumerate(self.met_fnames):
            lines.append(self._line("'{}{}'".format(met_rel_path, fname), 'Met file for year {}'.format(iyr+1)))
        lines.append(self._line('{}'.format(self.ncrops), 'Number of crops'))

        # stanza to permit timing of crops and numbers of fertiliser and manure application
        # =================================================================================
        for cropnum, crop in enumerate(self.crops):
            lines.append(self._line('{}'.format(crop.code),
                                                    'CROP {}\t\tsequence {}'.format(crop.crop_name, cropnum + 1)))
            lines.append(self._line('{}'.format(int(crop.sowing_doy)), 'Timesteps to sowing date from 01/01/01'))
            lines.append(self._line('{}'.format(round(crop.n_uptake,2)),
                                                    'Crop N uptake at harvest (0=calculate internally) [kg N/ha]'))
            lines.append(self._line('{}'.format(int(crop.harvest_doy)), 'Timesteps to harvest date from 01/01/01'))
            lines.append(self._line('{}'.format(crop.exp_yield),        'Expected yield [t/ha]'))
            lines.append(self._line('{}'.format(crop.residues_inc),     'Crop residues incorporated (0=No, 1=Yes'))
            lines.append(self._line('{}'.format(crop.nfert_apps),       'Number of fertiliser applications'))
            lines.append(self._line('{}'.format(crop.nmanure_apps),     'Number of organic manure applications'))

            # stanza for fertiliser applications
            # ==================================
            if crop.nfert_apps >= 1:
                for fert in crop.fert_apps:
                    lines.append(_line('{}'.format(round(fert.amount,2)), 'Amount of fertiliser applied [kg N/ha]'))
                    lines.append(_line('{}'.format(int(fert.app_moy)),    'Timesteps to fertiliser application'))
                    lines.append(_line('{}'.format(fert.no3_pc),          'Percentage NO3'))
                    lines.append(_line('{}'.format(fert.nh4_pc),          'Percentage NH4'))
                    lines.append(_line('{}'.format(fert.urea_pc),         'Percentage urea'))
                    lines.append(_line('{}'.format(fert.non_amm_sulphate_salts),
                                        'Does fert.contain ammonium salts other than ammonium sulphate (0=No, 1=Yes)'))
                    lines.append(_line('{}'.format(fert.labelled),        'Has fertiliser been labelled (0=No, 1=Yes)'))

            # stanza for manure applications
            # ==============================
            if crop.nmanure_apps >= 1:
                for manure in crop.manure_apps:
                    lines.append(_line('{}'.format(round(manure.amount,2)), 'Amount of manure applied [kg N/ha]'))
                    lines.append(_line('{}'.format(int(manure.app_moy)),    'Timesteps to manure application'))
                    lines.append(_line('{}'.format(manure.type),            'Type of manure'))
                    lines.append(_line('{}'.format(manure.labelled),        'Has manure been labelled (0=No, 1=Yes)'))

        # stanza for cultivations
        # =======================
        lines.append(self._line('{}'.format(self.ncultivations), 'Number of cultivations'))
        for icult, cult in enumerate(self.cultivations):
            lines.append(_line('{}'.format(int(cult.cult_doy)),  'Timesteps from 01/01 when cultivation occurred'))
            lines.append(_line('{}'.format(cult.cult_type),      'Type of cultivation'))
            lines.append(_line('{}'.format(cult.cult_vigor),     'Vigour of cultivation'))

        with open(join(directory, 'management.txt'), 'w') as fhand:
            fhand.writelines(lines)

    def _write_site_file(self, directory, hist_weather_recs, site_filename='site.txt'):
        """

        """
        _line = self._line
        output = []
        # Soil parameters
        output.append(_line('{0}'.format(self.equil_mode), 'Mode of equilibrium run'))
        output.append(_line('{0}'.format(self.nlyrs),      'Number of soil layers (max 10)'))
        for lyr_num, lyr_depth in enumerate(self.lyr_depths):
            output.append(_line('{0}'.format(lyr_depth),   'Depth of bottom of SOM layer {} [cm]'.format(lyr_num+1)))
        for key in self._luts:
            for lyr_num in range(self.nlyrs):
                output.append(_line('{}'.format(self.soil_lyrs[key][lyr_num].soc),
                              'C content [kgC/ha] for this soil under {} in SOM layer {}'.format(key, lyr_num + 1)))

                bulk_dens = round(float(self.soil_lyrs[key][lyr_num].bulk_dens), 3)
                output.append(_line('{}'.format(bulk_dens),
                              'Bulk density [g/cm3] for this soil under {} in SOM layer {}'.format(key, lyr_num+1)))

                ph = round(float(self.soil_lyrs[key][lyr_num].ph), 1)
                output.append(_line('{}'.format(ph),
                               'pH for this soil under {} in SOM layer {}'.format(key, lyr_num+1)))

                clay_pc = round(float(self.soil_lyrs[key][lyr_num].clay_pc), 1)
                output.append(_line('{}'.format(clay_pc),
                                '% clay by weight for this soil under {} in SOM layer {}'.format(key, lyr_num+1)))

                silt_pc = round(float(self.soil_lyrs[key][lyr_num].silt_pc), 1)
                output.append(_line('{}'.format(silt_pc),
                                '% silt by weight for this soil under {} in SOM layer {}'.format(key, lyr_num+1)))

                sand_pc = round(float(self.soil_lyrs[key][lyr_num].sand_pc), 1)
                output.append(_line('{}'.format(sand_pc),
                                '% sand by weight for this soil under {} in SOM layer {}'.format(key, lyr_num+1)))
        for key in self._luts:
            output.append(_line('{0}'.format(self.plant_inputs[key]),
                          '{} long term average plant C input [kgC/ha/yr] (used in modes 1 & 3 only)'.format(key)))

        # Long term average climate
        # =========================
        for rec in hist_weather_recs:
            output.append(rec + '\n')
        '''
        for precip, month in zip(self.lta_precip, self.months):
            output.append(_line('{}'.format(precip),
                          '{} long term average monthly precipitation [mm]'.format(month)))
        for tmean, month in zip(self.lta_tmean, self.months):
            output.append(_line('{}'.format(tmean),
                          '{} long term average monthly temperature [mm]'.format(month)))
        '''
        # Other bits and bobs
        # ===================
        output.append(_line('{}'.format(self.lat),              'Latitude [decimal deg]'))
        output.append(_line('{}'.format(self.wtr_tbl_dpth),     'Water table depth at start [cm]'))
        output.append(_line('{}'.format(self.drain_class),      'Drainage class'))
        output.append(_line('{}'.format(self.c_accum_b4_change),
                            'C accumulated before change [kgC/ha/yr] (only for mode 4 - if not use a dummy a value)'))
        output.append(_line('{}'.format(self.ch4_b4_change),
                            'CH4 emission before change [kgC/ha/yr] (not used yet)'))
        output.append(_line('{}'.format(self.co2_b4_change),
                            'CO2 emission before change [kgC/ha/yr] (not used yet)'))
        output.append(_line('{}'.format(self.doc_loss_b4_change),
                            'DOC loss before change [kgC/ha/yr] (not used yet)'))
        output.append(_line('{}'.format(self.nyears),           'Number of growing seasons to simulate'))

        # Future land use and plant inputs - used to read "If plant input set to zero it is obtained from RothC instead"
        # =============================================================================================================
        # for lu, pi in zip(self.future_lu, self.future_pi):
        land_use = 1
        plant_input = 1000.0*self.yield_prev_crop
        # pi = 0.0

        for yr_num in range(self.nyears):
            output.append(_line('{}, {}'.format(land_use, round(plant_input,1)),
                            'Year {} land use and plant C input [kgC/ha/yr] (Not used in mode 7)'.format(yr_num + 1)))
            yr_num += 1

        # Climate file names
        # ==================
        for year_num, fname in enumerate(self.met_fnames):
            output.append(_line('{}'.format(fname), 'Year {} climate file'.format(year_num + 1)))

        path = join(normpath(directory), site_filename)
        with open(path, 'w', newline='') as file:
            file.writelines(output)

    def _write_soil_file(self, directory):
        """

        """
        lines = []
        lines.append(self._line('{}'.format(self.soil_name),         'Soil name'))
        lines.append(self._line('{}'.format(self.soil_code),         'Soil code (used in management file)'))
        lines.append(self._line('{}'.format(self.awc_fc),
                                        'Available water content at field capacity [mm/0-25cm]'))
        lines.append(self._line('{}'.format(self.biohum_stable_n2c), 'Stable N:C of biomass and humus pools'))
        lines.append(self._line('{}'.format(self.biohum_frac),
                                        'Fraction of BIO + HUM formed: (BIO + HUM) / Total decomposition'))
        lines.append(self._line('{}'.format(self.biohum_from_bio), 'Biomass/Humus produced from biomass decomposition'))
        lines.append(self._line('{}'.format(self.biohum_from_hum), 'Biomass/Humus produced from humus decomposition'))
        lines.append(self._line('{}'.format(self.bio_frac),        'Fraction of biomass in total organic C'))
        lines.append(self._line('{}'.format(self.min_n_lvl),
                                        'Minimum level of nitrate in soil [kgN/ha/50cm layer]'))
        lines.append(self._line('{}'.format(self.k_bio),         'Rate constant for biomass decomposition [/year]'))
        lines.append(self._line('{}'.format(self.k_hum),         'Rate constant for humus decomposition [/year]'))
        lines.append(self._line('{}'.format(self.soc),           'Total organic C in top 50 cm of soil [kgC/ha]'))
        lines.append(self._line('{}'.format(self.iom_c),         'Inert organic matter in top 50 cm of soil [kgC/ha]'))
        lines.append(self._line('{}'.format(self.prev_lu),
                                        'Land use before equilibrium run (1=arable, 2=grass, 3=forestry, 4=natural'))
        lines.append(self._line('{}'.format(round(float(self.clay),1)), 'Clay content [proportion]'))
        lines.append(self._line('{}'.format(self.soil_depth),           'Depth of soil used in initialisation [cm]'))
        lines.append(self._line('{}'.format(round(float(self.ph),1)),   'pH of soil '))
        lines.append(self._line('{}'.format(self.ph_zero_decomp), 'pH at which decomposition has declined to zero'))
        lines.append(self._line('{}'.format(self.ph_decline_decomp), 'pH at which decomposition starts to decline'))
        lines.append(self._line('{}'.format(round(float(self.bulk_dens),1)), 'bulk denisty [g/cm3]'))
        lines.append(self._line('{}'.format(self.awc_sat),        'Available water content at saturation [mm/0-25cm]'))
        lines.append(self._line('{}'.format(self.wc_wp),          'Water content at wilting point [mm/0-25cm]'))

        with open(join(directory, 'soil.txt'), 'w') as file:
            file.writelines(lines)
'''
other classes
=============
'''
class Crop(object):
    """

    """
    def __init__(self, nan=-999):
        """

        """
        self.code = nan
        self.sowing_doy = nan               # Day of the year when crop is sown
        self.harvest_doy = nan              # Day of the year when crop is harvested
        self.n_uptake = 0                   # Crop N uptake at harvest (0=calculate internally) [kg N/ha]
        self.exp_yield = nan                # Expected yield [t/ha]
        self.residues_inc = nan             # Crop residues incorporated (0=No, 1=Yes)
        self.nfert_apps = nan               # Number of fertiliser applications
        self.fert_apps = []
        self.nmanure_apps = nan             # Number of organic manure applications
        self.manure_apps = []

    def validate(self):
        """

        """
        assert(self.code >= 0)
        assert(0 < self.sowing_doy <= 366)   # Day of the year when crop is sown
        assert(0 < self.harvest_doy <= 366)  # Day of the year when crop is harvested
        assert(0 <= self.n_uptake <= 1000)   # Crop N uptake at harvest (0=calculate internally) [kg N/ha]
        assert(0.0 < self.exp_yield <= 25.0) # Expected yield [t/ha]
        assert(self.residues_inc in [0,1])   # Crop residues incorporated (0=No, 1=Yes)
        assert(0 <= self.nfert_apps < 10)    # Number of fertiliser applications
        assert(0 <= self.nmanure_apps < 10)  # Number of organic manure applications

class ManureApplication(object):
    """

    """
    def __init__(self, amount, app_moy, type = 1, labelled = 0):

        self.amount = amount
        self.app_moy = app_moy
        self.type = type
        self.labelled = labelled

class FertiliserApplication(object):
    """

    """
    def __init__(self, amount, app_moy, no3_pc, nh4_pc, urea_pc, non_amm_sulphate_salts=0, labelled=0):

        self.amount = amount
        self.app_moy = app_moy
        self.no3_pc = no3_pc
        self.nh4_pc = nh4_pc
        self.urea_pc = urea_pc
        self.non_amm_sulphate_salts = non_amm_sulphate_salts
        self.labelled = labelled

    def validate(self):
        """

        """
        assert(self.amount >= 0.0 and self.amount < 1000.0)
        assert(self.app_moy > 0 and self.app_moy < 3601)
        assert(self.no3_pc >= 0.0 and self.no3_pc <= 100.0)
        assert(self.nh4_pc >= 0.0 and self.nh4_pc <= 100.0)
        assert(self.urea_pc >= 0.0 and self.urea_pc <= 100.0)
        assert(self.no3_pc + self.nh4_pc + self.urea_pc <= 100.0)
        assert(self.non_amm_sulphate_salts in [0, 1])
        assert(self.labelled in [0, 1])

class Cultivation(object):
    """

    """
    def __init__(self, cult_doy, cult_type, cult_vigor):
        self.cult_doy   = cult_doy             # Day of the year when cultivation occurred
        self.cult_type  = cult_type            # Type of cultivation – see table B1.1.3 in user manual
        self.cult_vigor = cult_vigor           # Vigour of cultivation (0.0 – 1.0)

    def validate(self):
        """

        """
        assert(0 < self.cult_doy <= 366)      # Day of the year when cultivation occurred
        assert(0 < self.cult_type <= 3)       # Type of cultivation – see table B1.1.3 in user manual
        assert(0.0 <= self.cult_vigor <= 1.0) # Vigour of cultivation (0.0 – 1.0)

class SoilLyr(object):
    """

    """
    def __init__(self, soc, bulk_dens, ph, clay_pc, silt_pc, sand_pc, no_data=-999):
        self.bulk_dens = bulk_dens
        self.ph = ph
        self.soc = soc     # C content
        self.clay_pc = clay_pc
        self.silt_pc = silt_pc
        self.sand_pc = sand_pc
        self.no_data = no_data

    def validate(self):
        """

        """
        pass
