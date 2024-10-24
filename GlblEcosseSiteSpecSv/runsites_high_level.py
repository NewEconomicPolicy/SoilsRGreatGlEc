"""
#-------------------------------------------------------------------------------
# Name:        runsites_high_level.py
# Purpose:     script to control ECOSSE runsites scripts and setup
# Author:      Mike Martin
# Created:     31/06/2020
# Licence:     <your licence>
#-------------------------------------------------------------------------------
"""

__prog__ = 'runsites_high_level.py'
__version__ = '0.0.0'

# Version history
# ---------------
# 
from os.path import join, normpath
from os import system
from json import load as json_load, dump as json_dump

def run_ecosse_wrapper(form):
    """
    C
    """
    func_name = __prog__ + ' runEcosse'

    # components of the command string exist have been checked at initiation
    # ======================================================================
    write_runsites_config_file(form)

    # run the script which runs ECOSSE with the simulation files
    cmd_str = form.setup['python_exe'] + ' ' + form.setup['runsites_py'] + ' ' + form.setup['runsites_config_file']
    system(cmd_str)

def write_runsites_config_file(form):
    """
    C
    """
    func_name = __prog__ + ' write_runsites_config_file'

    # read the runsites config file and edit one line
    # ======================================
    runsites_config_file = form.setup['runsites_config_file']
    try:
        with open(runsites_config_file, 'r') as fconfig:
            config = json_load(fconfig)
            print('Read config file ' + runsites_config_file)
    except (OSError, IOError) as err:
        print(err)
        return False

    # overwrite config file  TODO:  # config['Simulations']['resume_frm_prev'] = form.w_skip_sites.isChecked()
    # =====================
    sims_dir = normpath(join(form.setup['sims_dir'], form.setup['region_study']))
    crop_name = form.w_combo00b.currentText()
    config['General']['cropName'] = crop_name
    config['Simulations']['sims_dir'] = sims_dir

    with open(runsites_config_file, 'w') as fconfig:
        json_dump(config, fconfig, indent=2, sort_keys=True)
        print('Edited ' + runsites_config_file + '\n\twith simulation location: ' + sims_dir)

    return True
