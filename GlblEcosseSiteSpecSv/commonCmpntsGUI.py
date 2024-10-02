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

__prog__ = 'commonCmpntsGUI.py'
__version__ = '0.0.1'
__author__ = 's03mm5'

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel, QComboBox, QRadioButton, QButtonGroup, QPushButton, QCheckBox

from shape_funcs import calculate_area, format_bbox
from initialise_funcs import write_config_file
from glbl_ecss_cmmn_funcs import write_study_definition_file

resolutions = {120:'30"', 30:'2\'', 20:'3\'', 10:'6\'', 6:'10\'', 4:'15\'', 3:'20\'', 2:'30\''}
reverse_resols = {}

for key in resolutions:
    reverse_resols[resolutions[key]] = key

def calculate_grid_cell(form, granularity = 120):

    latitude = 52.0
    # use current lower left latitude for reference
    latText = form.w_ll_lat.text()
    try:
        latitude = float(latText)
    except ValueError:
        print(latText)

    resol = form.combo16.currentText()
    try:
        granul = reverse_resols[resol]
    except KeyError as e:
        print(str(e))
        return

    resol_deg = 1.0/float(granul)  # units of decimal degrees
    bbox = list([0.0, latitude, resol_deg, latitude + resol_deg])
    area = calculate_area(bbox)
    form.lbl16a.setText(format_bbox(bbox,area,2))

    form.req_resol_upscale = int(granularity/granul)    # number of base granuals making up one side of a cell
    form.req_resol_granul = granul                            # number of cells per degree
    form.req_resol_deg = resol_deg                            # size of each trapizoid cell in decimal degrees

    return

def _fetch_wthr_detail(form):
    """

    """
    generic_rsrce = form.wthr_rsrces_generic
    rsrce_hist = generic_rsrce + '_hist'

    # so far only CRU and WrldClim are permitted
    # ==========================================
    if generic_rsrce == 'WrldClim':
        rsrce_fut = 'UKESM1-0-LL_126'
    else:
        rsrce_fut = 'ClimGen_A1B'

    start_year = form.wthr_sets[rsrce_hist]['year_start']
    end_year   = form.wthr_sets[rsrce_hist]['year_end']
    hist_syears = list(range(start_year, end_year))
    hist_eyears = list(range(start_year + 1, end_year + 1))

    start_year = form.wthr_sets[rsrce_fut]['year_start']
    end_year = form.wthr_sets[rsrce_fut]['year_end']
    fut_syears = range(start_year, end_year)
    fut_eyears = list(range(start_year + 1, end_year + 1))

    return hist_syears, hist_eyears, fut_syears, fut_eyears

def _fetch_land_use_types():
    """

    """
    luTypes = {};
    lu_type_abbrevs = {}
    for lu_type, abbrev, ilu in zip(
            ['Arable', 'Forestry', 'Miscanthus', 'Grassland', 'Semi-natural', 'SRC', 'Rapeseed', 'Sugar cane'],
            ['ara', 'for', 'mis', 'gra', 'nat', 'src', 'rps', 'sgc'],
            [1, 3, 5, 2, 4, 6, 7, 7]):
        luTypes[lu_type] = ilu
        lu_type_abbrevs[lu_type] = abbrev

    return luTypes, lu_type_abbrevs

def commonSection(form, grid, irow):
    """

    """
    hist_syears, hist_eyears, fut_syears, fut_eyears = _fetch_wthr_detail(form)
    form.land_use_types,  form.lu_type_abbrevs = _fetch_land_use_types()

    # =========
    icol = 0
    lbl10w = QLabel('Weather resource:')
    lbl10w.setAlignment(Qt.AlignRight)
    helpText = 'permissable weather dataset resources are limited to CRU only'
    lbl10w.setToolTip(helpText)
    grid.addWidget(lbl10w, irow, icol)

    icol += 1
    lbl10x = QLabel(form.weather_rsrce_generic)
    lbl10x.setToolTip(helpText)
    grid.addWidget(lbl10x, irow, icol)

    icol += 1
    lbl10y = QLabel('GCM:')
    lbl10y.setAlignment(Qt.AlignRight)
    lbl10y.setToolTip(helpText)
    grid.addWidget(lbl10y, irow, icol)

    icol += 1
    WDGT_SIZE_100 = 100
    combo10w = QComboBox()
    for wthr_resource in form.wthr_gcms:
        combo10w.addItem(wthr_resource)
    combo10w.setFixedWidth(WDGT_SIZE_100)
    combo10w.currentIndexChanged[str].connect(form.reloadClimScenarios)
    form.combo10w = combo10w
    grid.addWidget(combo10w, irow, icol)

    # scenarios
    # =========
    icol += 1
    lbl10 = QLabel('Climate Scenario:')
    lbl10.setAlignment(Qt.AlignRight)
    helpText = 'Ecosse requires future average monthly precipitation and temperature derived from climate models.\n' \
        + 'The data used here is ClimGen v1.02 created on 16.10.08 developed by the Climatic Research Unit\n' \
        + ' and the Tyndall Centre. See: http://www.cru.uea.ac.uk/~timo/climgen/'

    lbl10.setToolTip(helpText)
    grid.addWidget(lbl10, irow, icol)

    icol += 1
    combo10 = QComboBox()
    for scen in form.wthr_scenarios:
        combo10.addItem(str(scen))
    combo10.setFixedWidth(80)
    form.combo10 = combo10
    grid.addWidget(combo10, irow, icol)

    # next line
    # =========
    irow += 1
    lbl09s = QLabel('Historic start year:')
    lbl09s.setAlignment(Qt.AlignRight)
    helpText = 'Ecosse requires long term average monthly precipitation and temperature\n' \
            + 'which is derived from datasets managed by Climatic Research Unit (CRU).\n' \
            + ' See: http://www.cru.uea.ac.uk/about-cru'
    lbl09s.setToolTip(helpText)
    grid.addWidget(lbl09s, irow, 0)

    combo09s = QComboBox()
    for year in hist_syears:
        combo09s.addItem(str(year))
    combo09s.setFixedWidth(80)
    form.combo09s = combo09s
    grid.addWidget(combo09s, irow, 1)    # row, column, rowSpan, columnSpan

    lbl09e = QLabel('End year:')
    lbl09e.setAlignment(Qt.AlignRight)
    grid.addWidget(lbl09e, irow, 2)

    combo09e = QComboBox()
    for year in hist_eyears:
        combo09e.addItem(str(year))
    combo09e.setFixedWidth(80)
    form.combo09e = combo09e
    grid.addWidget(combo09e, irow, 3)

    # line 11
    # =======
    irow += 1
    lbl11s = QLabel('Simulation start year:')
    helpText = 'Simulation start and end years determine the number of growing seasons to simulate\n' \
            + 'CRU and CORDEX resources run to 2100 whereas EObs resource runs to 2017'
    lbl11s.setToolTip(helpText)
    lbl11s.setAlignment(Qt.AlignRight)
    grid.addWidget(lbl11s, irow, 0)

    combo11s = QComboBox()
    for year in fut_syears:
        combo11s.addItem(str(year))
    form.combo11s = combo11s
    combo11s.setFixedWidth(80)
    grid.addWidget(combo11s, irow, 1)

    lbl11e = QLabel('End year')
    lbl11e.setAlignment(Qt.AlignRight)
    grid.addWidget(lbl11e, irow, 2)

    combo11e = QComboBox()
    for year in fut_eyears:
        combo11e.addItem(str(year))
    combo11e.setFixedWidth(80)
    form.combo11e = combo11e
    grid.addWidget(combo11e, irow, 3)
    
    w_ave_wthr = QCheckBox('Start simulation from 1801')
    helpText = 'Select this option to start simulation from 1801 - only activated when weather already exists\n' + \
                                                                    ' and start of simulation is indicated as 1901'
    w_ave_wthr.setToolTip(helpText)
    grid.addWidget(w_ave_wthr, irow, 4, 1, 2)
    form.w_ave_wthr = w_ave_wthr

    # row 13
    # ======
    irow += 1
    w_cult_file = QPushButton("Cultivation file")
    helpText = 'Select a JSON file comprising year index, cultivation type, vigour and residues incorporated'
    w_cult_file.setToolTip(helpText)
    grid.addWidget(w_cult_file, irow, 0)
    w_cult_file.clicked.connect(form.fetchCultivJsonFile)

    w_lbl13 = QLabel('')
    grid.addWidget(w_lbl13, irow, 1, 1, 5)
    form.w_lbl13 = w_lbl13

    # for message from check_cultiv_json_fname
    # =======================================
    w_lbl14 = QLabel('')
    grid.addWidget(w_lbl14, irow, 6, 1, 2)
    form.w_lbl14 = w_lbl14

    # line 15
    # =======
    irow += 1
    w_fert = QRadioButton("Fertiliser")
    helpText = 'If this option is selected, then file is treated as fertiliser'
    w_fert.setToolTip(helpText)
    grid.addWidget(w_fert, irow, 1)
    form.w_fert  = w_fert

    w_manure = QRadioButton("Manure")
    helpText = 'If this option is selected, then file is treated as manure'
    w_manure.setToolTip(helpText)
    grid.addWidget(w_manure, irow, 2)
    form.w_manure = w_manure

    w_inputs_choice = QButtonGroup()
    w_inputs_choice.addButton(w_fert)
    w_inputs_choice.addButton(w_manure)
    w_manure.setChecked(True)

    # assign check values to radio buttons
    w_inputs_choice.setId(w_manure, 2)
    w_inputs_choice.setId(w_fert, 1)    
    form.w_inputs_choice = w_inputs_choice

    # row 16
    # ======
    irow += 1
    w_rota_file = QPushButton("Crop rotation file")
    helpText = 'Select a JSON file comprising crop rotation detail'
    w_rota_file.setToolTip(helpText)
    grid.addWidget(w_rota_file, irow, 0)
    w_rota_file.clicked.connect(form.fetchCropRotaJsonFile)

    w_lbl16 = QLabel('')
    grid.addWidget(w_lbl16, irow, 1, 1, 5)
    form.w_lbl16 = w_lbl16

    # line 17
    # =======
    w_crop_rota = QCheckBox("Use crop rotation file")
    helpText = 'If this option is selected, then the crop rotation specified in the NC file will be used'
    w_crop_rota.setChecked(False)
    w_crop_rota.setToolTip(helpText)
    grid.addWidget(w_crop_rota, irow, 4, 1, 2)
    form.w_crop_rota = w_crop_rota

    # for message from check_crop_rota_json_fname
    # ===========================================
    irow += 1
    w_lbl17 = QLabel('')
    grid.addWidget(w_lbl17, irow, 1, 1, 3)
    form.w_lbl17 = w_lbl17

    return irow

def save_clicked(form):

        # write last GUI selections
        write_config_file(form)
        write_study_definition_file(form)

def grid_coarseness(form, grid, irow):
    '''
   function to lay out grid resolution dropdown and reporting
    '''

    # row 16 - grid coarseness
    # ========================
    irow += 1
    lbl16 = QLabel('Grid resolution')
    lbl16.setAlignment(Qt.AlignRight)
    helpText = 'The size of each grid cell is described in arc minutes and arc seconds. The smallest cell resolution \n' \
        + 'corresponds to that of the HWSD database (30 arc seconds) and the largest to that used by the climate data ' \
        + '(30 arc minutes)'
    lbl16.setToolTip(helpText)
    # lbl16.setEnabled(False)
    grid.addWidget(lbl16, irow, 0)

    combo16 = QComboBox()
    for resol in sorted(resolutions,reverse = True):
        combo16.addItem(str(resolutions[resol]))
    # combo16.setEnabled(False)
    combo16.setToolTip(helpText)
    combo16.currentIndexChanged[str].connect(form.resolutionChanged)
    combo16.setFixedWidth(80)
    form.combo16 = combo16
    grid.addWidget(combo16, irow, 1)

    form.lbl16a = QLabel('')
    form.lbl16a.setToolTip(helpText)
    grid.addWidget(form.lbl16a, irow, 2, 1, 2)

    return irow

def exit_clicked(form, write_config_flag = True):

    # write last GUI selections
    if write_config_flag:
        write_config_file(form)

    # close various files
    if hasattr(form, 'fobjs'):
        if not form.fobjs is None:
            for key in form.fobjs:
                form.fobjs[key].close()

    # close logging
    try:
        form.lgr.handlers[0].close()
    except AttributeError:
        pass

    form.close()

