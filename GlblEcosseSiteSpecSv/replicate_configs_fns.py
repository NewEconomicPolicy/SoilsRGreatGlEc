"""
#-------------------------------------------------------------------------------
# Name:
# Purpose:     consist of low level functions invoked by main GUI
# Author:      Mike Martin
# Created:     11/12/2015
# Licence:     <your licence>
#-------------------------------------------------------------------------------
#

"""
__prog__ = 'replicate_configs_fns'
__version__ = '0.0.1'
__author__ = 's03mm5'

from os.path import join, split, splitext, normpath, isfile
from copy import copy
from json import load as json_load, dump as json_dump

sleepTime = 5
ERROR_STR = '*** Error *** '

def copy_config_files(form):
    """
    method to look for fertiliser lines in original template files and create new template
    with these three lines as replacements:
    """
    content_dict = dict({'NO3':'7.7          # Percentage NO3', 'NH4':'84.6         # Percentage NH4',
                                                                        'urea':'7.7          # Percentage urea'})

    config_dir = form.settings['config_dir']
    region_indx = 0
    region_abbrv = form.regions_df['Wthr dir'][region_indx]
    tmplt_config_fns = []

    for study in form.studies:
        this_reg_abbrv = study.split('_')[0]
        if this_reg_abbrv == region_abbrv:
            short_fn_af = form.setup['applic_str'] + '_' + study + '.json'
            config_fn_path = normpath( join(config_dir, short_fn_af) )

            # check file in case it has been deleted
            # ======================================
            if isfile(config_fn_path):
                with open(config_fn_path, 'r') as fobj:
                    config_content = json_load(fobj)
            else:
                continue

            # write config files for the other 5 regions
            # ==========================================
            irow = 1
            for region in form.regions_abbrv[1:]:
                new_mngmnt_content = copy(config_content)
                ll_lon, ur_lon, ll_lat, ur_lat, wthr_dir = form.regions_df.iloc[irow][1:]
                bbox = list([ll_lon, ll_lat, ur_lon, ur_lat])
                new_mngmnt_content['minGUI']['bbox'] = bbox
                new_mngmnt_content['minGUI']['regionIndx'] = irow
                short_fname = short_fn_af.replace('_Af', '_' + region)
                with open(join(config_dir, short_fname), 'w') as fobj:
                    json_dump(new_mngmnt_content, fobj, indent=2, sort_keys=True)

                irow += 1

    print('Edited {} config files'.format(len(tmplt_config_fns)))

    return
