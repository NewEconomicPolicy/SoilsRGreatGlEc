#-------------------------------------------------------------------------------
# Name:        prepare_ecosse_files.py
# Purpose:
# Author:      s03mm5
# Created:     08/12/2015
# Copyright:   (c) s03mm5 2015
# Licence:     <your licence>
#-------------------------------------------------------------------------------
#
__version__ = '1.0.00'
__prog__ = 'prepare_ecosse_files.py'

from os import makedirs
from os.path import lexists, join, normpath, basename
from shutil import copyfile

from prepare_ecosse_low_level import fetch_long_term_ave_wthr_recs, make_met_files
from glbl_ecss_cmmn_funcs import write_kml_file, write_signature_file, write_manifest_file
from hwsd_soil_class import _gran_coords_from_lat_lon

SPACER_LEN = 12

def _make_line(data, comment):
    """

    """
    spacer_len = max(SPACER_LEN - len(data), 2)
    spacer = ' ' * spacer_len
    
    return '{}{}# {}\n'.format(data, spacer, comment)

def _make_lta_file(site, clim_dir):
    """
    write long term average climate section of site.txt file
    """
    lines = []
    for precip, month in zip(site.lta_precip, site.months):
        lines.append(_make_line('{}'.format(precip),'{} long term average monthly precipitation [mm]'.format(month)))

    for tmean, month in zip(site.lta_tmean, site.months):
        lines.append(_make_line('{}'.format(tmean),'{} long term average monthly temperature [mm]'.format(month)))

    lta_ave_fn = join(clim_dir, 'lta_ave.txt')
    with open(lta_ave_fn, 'w') as fhand:
        fhand.writelines(lines)

    # will be copied
    # ==============
    make_avemet_file(clim_dir, site.lta_precip, site.lta_pet, site.lta_tmean)

    return lta_ave_fn

def make_avemet_file(clim_dir, lta_precip, lta_pet, lta_tmean):
    """
    will be copied
    """
    avemet_dat = join(clim_dir, 'AVEMET.DAT')
    with open(avemet_dat, 'w') as fobj:
        for imnth, (precip, pet, tmean) in enumerate(zip(lta_precip, lta_pet, lta_tmean)):
            fobj.write('{} {} {} {}\n'.format(imnth + 1, precip, pet, tmean))

    return

def make_wthr_files(site, lat, lon, climgen, pettmp_hist, pettmp_fut):
    """
    generate ECOSSE historic and future weather data
    """
    func_name = 'make_ecosse_files'

    if not isinstance(pettmp_hist, dict) or not isinstance(pettmp_fut, dict):
        print('Bad input to ' + func_name)
        return

    gran_lat, gran_lon = _gran_coords_from_lat_lon(lat, lon)

    # calculate historic average weather
    # ==================================
    hist_lta_precip, hist_lta_tmean, hist_weather_recs = fetch_long_term_ave_wthr_recs(climgen, pettmp_hist)

    # write a single set of met files for all simulations for this grid cell
    # ======================================================================
    gran_coord = '{0:0=5g}_{1:0=5g}'.format(gran_lat, gran_lon)
    clim_dir = normpath( join(site.sims_dir, climgen.region_wthr_dir, gran_coord) )
    met_fnames = make_met_files(clim_dir, lat, climgen, pettmp_fut)     # future weather

    # create additional weather related files from already existing met files
    # =======================================================================
    irc = climgen.create_FutureAverages(clim_dir, lat, site, hist_lta_precip, hist_lta_tmean)
    lta_ave_fn = _make_lta_file(site, clim_dir)

    return

def make_ecosse_files(site, climgen, soil_defn, fert_recs, plant_day, harvest_day, yield_val,
                                                                                hist_lta_recs, met_fnames):
    """
    generate sets of Ecosse files for each site
    where each site has one or more soils and each soil can have one or more dominant soils
    pettmp_grid_cell is climate data for this soil grid point
    """
    func_name = 'make_ecosse_files'
    pettmp_fut,  hist_lta_precip, hist_lta_tmean = 3*[None]

    gran_lat = soil_defn.gran_lat
    gran_lon = soil_defn.gran_lon
    lat = float(soil_defn.lat)
    lon = float(soil_defn.lon)
    mu_globals_pairs = soil_defn.mu_global_pairs

    # write a single set of met files for all simulations for this grid cell
    # ======================================================================
    gran_coord = '{0:0=5g}_{1:0=5g}'.format(gran_lat, gran_lon)
    met_rel_path = '..\\..\\' + climgen.region_wthr_dir + '\\' + gran_coord + '\\'

    #------------------------------------------------------------------
    # Create a set of simulation input files for each dominant
    # soil-land use type combination
    #------------------------------------------------------------------

    # construct directory name with all dominant soils
    # ===============================================
    ntotal_cells = sum(mu_globals_pairs.values())   # typically 3600, 900, 400, 100 for 0.5, 0.25, 0.166667, 0.1 degree respectively
    for pair in mu_globals_pairs.items():
        mu_global, ncells = pair
        area_for_soil = soil_defn.area*ncells/ntotal_cells
        try:
            soil_list = soil_defn.soil_recs[mu_global]
        except KeyError as err:
            print('Error {} processing cell at lat: {} Lon: {}'.format(err, lat, lon))
            continue

        for soil_num, soil in enumerate(soil_list):
            identifer = 'lat{0:0=7d}_lon{1:0=7d}_mu{2:0=5d}_s{3:0=2d}'.format(gran_lat, gran_lon,
                                                                              mu_global, soil_num + 1)
            sim_dir = join(site.sims_dir, climgen.region_study, identifer)
            if not lexists(sim_dir):
                makedirs(sim_dir)

            site.create_site_soil_layers(soil)
            if soil_num == 0:       # MJM 2021_05_14 - only required once
                site.data_modify_mnthly(lat, lon, climgen, met_fnames, fert_recs, plant_day, harvest_day, yield_val)
            site.write_sim_files(sim_dir, soil, hist_lta_recs, met_rel_path)

            # write kml and signature files
            # ==============================
            if soil_num == 0:
                write_kml_file(sim_dir, str(mu_global), mu_global, lat, lon)

            write_signature_file(sim_dir, mu_global, soil, lat, lon, climgen.region)

            # copy across Ecosse dat files
            # ============================
            for key_fname in site.dflt_ecosse_fnames.items():
                key, inp_fname = key_fname
                out_fname = join(sim_dir, basename(inp_fname))
                copyfile(inp_fname, out_fname)

        # manifest file is essential for subsequent processing
        # ====================================================
        write_manifest_file(climgen.region_study, climgen.fut_clim_scen, sim_dir,
                                            soil_list, mu_global, lat, lon, area_for_soil)
    # end of Soil loop
    # ================

    return
