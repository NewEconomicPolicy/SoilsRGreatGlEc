"""
#-------------------------------------------------------------------------------
# Name:        glbl_ecsse_low_level_test_fns.py
# Purpose:     consist of low level functions invoked by high level module
# Author:      Mike Martin
# Created:     11/12/2015
# Licence:     <your licence>
#-------------------------------------------------------------------------------
#
"""

__prog__ = 'glbl_ecsse_low_level_test_fns.py'
__version__ = '0.0.1'
__author__ = 's03mm5'

from numpy.ma.core import MaskedArray, MaskedConstant, MaskError
from numpy import ndarray, int32

from shape_funcs import MakeBboxesNitroInpts

GRANULARITY = 120
WARNING_STR = '*** Warning *** '

def check_cntry_prvnc_mappings(form):
    '''
    called from GUI
    NB  vars ending in _dset indicate netCDF4 dataset objects
        vars ending in _defn are objects which comprising NC file attributes e.g. resolution, extents, file location
    '''
    glbl_n_inpts = MakeBboxesNitroInpts(form.settings, form.cntries_defn)

    print()

def make_fert_recs_test(lggr, fert_defns, lat, lon, record_ndays):
    '''
    test fertiliser NCs
    '''
    func_name =  __prog__ + ' make_fert_recs'
    mess = '*** Error *** in ' + func_name

    # fertilizer datasets all have same lat/lon resolution
    # ====================================================
    for key in fert_defns:
        lat_indx, lon_indx, ret_code = fert_defns[key].get_nc_coords(lat, lon)
        break

    # Amount of fertiliser applied [kg N/ha] 1961 to 2010
    # ===================================================
    metric = 'TN_input_1961_2010'
    var_name = fert_defns[metric].var_names[0]
    amounts = fert_defns[metric].nc_dset.variables[var_name][:, lat_indx, lon_indx]
    if type(amounts[0]) is MaskedConstant:
        mess += ' fertiliser amount has type of MaskedConstant, should be float32'
        lggr.info(mess + ' Lat: {} {}\tLon: {} {}'.format(lat, lat_indx, lon, lon_indx))
        return None

    # day of year - in Ecosse translates to timesteps to fertiliser application
    # =========================================================================
    metric = 'Ninput_date_ver1'
    var_name = fert_defns[metric].var_names[0]
    day_of_year = fert_defns[metric].nc_dset.variables[var_name][:, lat_indx, lon_indx]

    ndoys = 0
    for day in day_of_year:
        if type(day) is int32:
            ndoys += 1

    record_ndays[str(ndoys)] += 1

    # use data.mask command to obtain non-masked data by getting all the indices which are False
    # ==========================================================================================
    '''
    try:        
       
        doy = day_of_year[day_of_year.mask == False].item()
        if not isinstance(doy, int):
            mess += ' doy has type: ' + type(doy)
            lggr.info(mess + ' Lat: {}\tLon: {}'.format(lat, lon))
            return None

    except ValueError as err:
        mess += ' could not convert fertilizer day of year array: ' + str(err)
        lggr.info(mess  + ' Lat: {}\tLon: {}'.format(lat, lon) )
        return None
    '''

    return ndoys

