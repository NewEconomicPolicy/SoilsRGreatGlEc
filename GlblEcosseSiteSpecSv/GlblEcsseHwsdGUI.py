#-------------------------------------------------------------------------------
# Name:
# Purpose:     Creates a GUI with five adminstrative levels plus country
# Author:      Mike Martin
# Created:     11/12/2015
# Licence:     <your licence>
#-------------------------------------------------------------------------------
#!/usr/bin/env python

__prog__ = 'GlblEcsseHwsdGUI.py'
__version__ = '0.0.1'
__author__ = 's03mm5'

import sys
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QLabel, QWidget, QApplication, QHBoxLayout, QVBoxLayout, QGridLayout, QLineEdit, \
                                            QComboBox, QRadioButton, QButtonGroup, QPushButton, QCheckBox, QFileDialog

from initialise_funcs import read_config_file, initiation, change_config_file, build_and_display_studies
from commonCmpntsGUI import exit_clicked, commonSection, grid_coarseness, calculate_grid_cell, save_clicked
from glbl_ecsse_high_level_fns import generate_banded_sims, all_generate_banded_sims
from glbl_ecsse_low_level_fns import check_cultiv_json_fname, check_rotation_json_fname, set_region_study
from glbl_ecss_cmmn_funcs import write_study_definition_file
from runsites_high_level import run_ecosse_wrapper
from shape_funcs import format_bbox, calculate_area

from glbl_ecsse_high_level_test_fns import generate_banded_sims_test, all_generate_banded_sims_test
from glbl_ecsse_low_level_test_fns import check_cntry_prvnc_mappings
from wthr_generation_fns import generate_all_weather

WDGT_SIZE_80 = 80
WDGT_SIZE_100 = 100
WDGT_SIZE_120 = 120
WDGT_SIZE_180 = 180

class Form(QWidget):

    def __init__(self, parent=None):

        super(Form, self).__init__(parent)

        self.version = 'HWSD_grid'
        initiation(self)
        # define two vertical boxes, in LH vertical box put the painter and in RH put the grid
        # define horizon box to put LH and RH vertical boxes in
        hbox = QHBoxLayout()
        hbox.setSpacing(10)

        # left hand vertical box consists of png image
        # ============================================
        lh_vbox = QVBoxLayout()

        # LH vertical box contains image only
        lbl20 = QLabel()
        pixmap = QPixmap(self.setup['fname_png'])
        lbl20.setPixmap(pixmap)

        lh_vbox.addWidget(lbl20)

        # add LH vertical box to horizontal box
        hbox.addLayout(lh_vbox)

        # right hand box consists of combo boxes, labels and buttons
        # ==========================================================
        rh_vbox = QVBoxLayout()

        # The layout is done with the QGridLayout
        grid = QGridLayout()
        grid.setSpacing(10)	# set spacing between widgets

        # line 0
        # ======
        irow = 0
        lbl00 = QLabel('Study:')
        lbl00.setAlignment(Qt.AlignRight)
        grid.addWidget(lbl00, irow, 0)

        w_study = QLineEdit()
        w_study.setFixedWidth(WDGT_SIZE_180)
        grid.addWidget(w_study, irow, 1)
        self.w_study = w_study

        lbl00s = QLabel('Studies:')
        lbl00s.setAlignment(Qt.AlignRight)
        helpText = 'list of studies'
        lbl00s.setToolTip(helpText)
        grid.addWidget(lbl00s, irow, 2)

        combo00s = QComboBox()
        for study in self.studies:
            combo00s.addItem(study)
        grid.addWidget(combo00s, irow, 3)
        combo00s.currentIndexChanged[str].connect(self.changeConfigFile)
        self.combo00s = combo00s

        # line 1
        # ======
        irow += 1
        lbl00a = QLabel('Region:')
        lbl00a.setAlignment(Qt.AlignRight)
        grid.addWidget(lbl00a, irow, 0)

        combo00a= QComboBox()
        for region in self.regions['Region']:
            combo00a.addItem(region)
        combo00a.setFixedWidth(WDGT_SIZE_180)
        grid.addWidget(combo00a, irow, 1)
        combo00a.currentIndexChanged[str].connect(self.changeRegion)
        self.combo00a = combo00a

        lbl00b = QLabel('Crop:')
        lbl00b.setAlignment(Qt.AlignRight)
        grid.addWidget(lbl00b, irow, 2)

        combo00b = QComboBox()
        for crop in self.setup['crops']:
            combo00b.addItem(crop)
        combo00b.setFixedWidth(WDGT_SIZE_100)
        grid.addWidget(combo00b, irow, 3)
        combo00b.currentIndexChanged[str].connect(self.changeCrop)
        self.combo00b = combo00b

        # line 2 - Upper right lon/lat
        # ============================
        irow += 1
        lbl02a = QLabel('Upper right longitude:')
        lbl02a.setAlignment(Qt.AlignRight)
        grid.addWidget(lbl02a, irow, 0)

        w_ur_lon = QLineEdit()
        w_ur_lon.setFixedWidth(WDGT_SIZE_80)
        grid.addWidget(w_ur_lon, irow, 1)
        self.w_ur_lon = w_ur_lon

        lbl02b = QLabel('latitude:')
        lbl02b.setAlignment(Qt.AlignRight)
        grid.addWidget(lbl02b, irow, 2)

        w_ur_lat = QLineEdit()
        w_ur_lat.setFixedWidth(WDGT_SIZE_80)
        grid.addWidget(w_ur_lat, irow, 3)
        self.w_ur_lat = w_ur_lat

        # line 3 Lower left lon/lat
        # =========================
        irow += 1
        lbl01a = QLabel('Lower left longitude:')
        lbl01a.setAlignment(Qt.AlignRight)
        grid.addWidget(lbl01a, irow, 0)

        w_ll_lon = QLineEdit()
        w_ll_lon.setFixedWidth(WDGT_SIZE_80)
        grid.addWidget(w_ll_lon, irow, 1)
        self.w_ll_lon = w_ll_lon

        lbl01b = QLabel('latitude:')
        lbl01b.setAlignment(Qt.AlignRight)
        grid.addWidget(lbl01b, irow, 2)

        w_ll_lat = QLineEdit()
        w_ll_lat.setFixedWidth(WDGT_SIZE_80)
        grid.addWidget(w_ll_lat, irow, 3)
        self.w_ll_lat = w_ll_lat

        # line 4
        # ======
        irow += 1
        lbl03a = QLabel('Study bounding box:')
        # lbl03a.setAlignment(Qt.AlignRight)
        grid.addWidget(lbl03a, irow, 0)
        self.lbl03 = QLabel()
        grid.addWidget(self.lbl03, irow, 1, 1, 4)

        # equilibrium mode
        # ===============
        lbl03b = QLabel('Equilibrium mode:')
        lbl03b.setAlignment(Qt.AlignRight)
        helpText = 'mode of equilibrium run, generally OK with 6'
        lbl03b.setToolTip(helpText)
        grid.addWidget(lbl03b, irow, 5)

        w_equimode = QLineEdit()
        w_equimode.setText('')
        w_equimode.setFixedWidth(WDGT_SIZE_80)
        self.w_equimode = w_equimode
        grid.addWidget(w_equimode, irow, 6)

        # type of run options
        # ===================
        irow += 1
        lbl05 = QLabel('Maximum cells:')
        lbl05.setAlignment(Qt.AlignRight)
        helpText = 'Maximum number of simulation cells to generate for each region'
        lbl05.setToolTip(helpText)
        grid.addWidget(lbl05, irow, 0)

        w_max_cells = QLineEdit()
        w_max_cells.setText('')
        w_max_cells.setFixedWidth(WDGT_SIZE_80)
        self.w_max_cells = w_max_cells
        grid.addWidget(w_max_cells, irow, 1)

        w_all_regions = QCheckBox('All regions')
        helpText = 'Generate across all regions'
        w_all_regions.setToolTip(helpText)
        grid.addWidget(w_all_regions, irow, 2)
        self.w_all_regions = w_all_regions

        w_all_crops = QCheckBox('All crops')
        helpText = 'Generate across all crops'
        w_all_crops.setToolTip(helpText)
        grid.addWidget(w_all_crops, irow, 3)
        self.w_all_crops = w_all_crops

        # simplification options
        # ======================
        w_use_dom_soil = QCheckBox('Use most dominant soil')
        helpText = 'Each HWSD grid cell can have up to 10 soils. Select this option to use most dominant soil and\n' \
                ' discard all others. The the most dominant soil is defined as having the highest percentage coverage '\
                ' of all the soils for that grid cell'
        w_use_dom_soil.setToolTip(helpText)
        grid.addWidget(w_use_dom_soil, irow, 4)
        w_use_dom_soil.setEnabled(False)
        self.w_use_dom_soil = w_use_dom_soil

        w_use_high_cover = QCheckBox('Use highest coverage soil')
        helpText = 'Each meta-cell has one or more HWSD mu global keys with each key associated with a coverage expressed \n'\
                ' as a proportion of the area of the meta cell. Select this option to use the mu global with the highest coverage,\n' \
                ' discard the others and aggregate their coverages to the selected mu global'
        w_use_high_cover.setToolTip(helpText)
        grid.addWidget(w_use_high_cover, irow, 5, 1, 2)
        w_use_high_cover.setEnabled(False)
        self.w_use_high_cover = w_use_high_cover

        # line 6
        # ======
        irow += 1
        lbl06a = QLabel('Year from:')
        lbl06a.setAlignment(Qt.AlignRight)
        helpText = 'Year from which perennial crops are planted or use global N inputs e.g. 220\nset to -1 to disable'
        lbl06a.setToolTip(helpText)
        grid.addWidget(lbl06a, irow, 0)

        w_yr_from = QLineEdit()
        w_yr_from.setText('')
        w_yr_from.setToolTip(helpText)
        w_yr_from.setFixedWidth(WDGT_SIZE_80)
        grid.addWidget(w_yr_from, irow, 1)
        self.w_yr_from = w_yr_from

        w_glbl_n_inpts = QCheckBox('Use global N inputs')
        helpText = 'Use Excel file of mean N application by country and province for China, India and United States'
        w_glbl_n_inpts.setToolTip(helpText)
        grid.addWidget(w_glbl_n_inpts, irow, 2)
        self.w_glbl_n_inpts = w_glbl_n_inpts

        w_use_peren = QCheckBox('Use perennial crops')
        helpText = 'Use perennial crops'
        w_use_peren.setToolTip(helpText)
        grid.addWidget(w_use_peren, irow, 3)
        self.w_use_peren = w_use_peren

        # dormant
        # =======
        w_lbl06b = QLabel('Timestep:')
        w_lbl06b.setAlignment(Qt.AlignRight)
        grid.addWidget(w_lbl06b, irow, 4)

        w_daily = QRadioButton("Daily")
        helpText = 'If this option is selected, then Daily timestep is used'
        w_daily.setToolTip(helpText)
        w_daily.setEnabled(False)
        grid.addWidget(w_daily, irow, 5)
        self.w_daily  = w_daily

        w_mnthly = QRadioButton("Monthly")
        helpText = 'If this option is selected, then Monthly timestep is used'
        w_mnthly.setToolTip(helpText)
        w_mnthly.setEnabled(False)
        grid.addWidget(w_mnthly, irow, 6)
        self.w_mnthly = w_mnthly

        w_timestep_choice = QButtonGroup()
        w_timestep_choice.addButton(w_daily)
        w_timestep_choice.addButton(w_mnthly)
        w_mnthly.setChecked(True)

        # assign check values to radio buttons
        # ====================================
        w_timestep_choice.setId(w_mnthly, 2)
        w_timestep_choice.setId(w_daily, 1)
        self.w_timestep_choice = w_timestep_choice

        # weather resource and simulation period
        # ======================================
        irow = 9
        irow = commonSection(self, grid, irow)
        irow = grid_coarseness(self, grid, irow)

        # actions
        # =======
        irow += 3
        icol = 0
        w_create_files = QPushButton("Create sim files")
        helpText = 'Generate ECOSSE simulation file sets corresponding to ordered HWSD global mapping unit set in CSV file'
        w_create_files.setToolTip(helpText)
        grid.addWidget(w_create_files, irow, icol)
        w_create_files.clicked.connect(self.createSimsClicked)
        self.w_create_files = w_create_files

        icol += 1
        w_auto_run_ec  = QCheckBox('Auto run Ecosse')
        helpText = 'Select this option to automatically run the ECOSSE programme after simulation file generation'
        w_auto_run_ec.setToolTip(helpText)
        grid.addWidget(w_auto_run_ec , irow, icol)
        self.w_auto_run_ec  = w_auto_run_ec

        icol += 1
        w_run_ecosse = QPushButton("Run ECOSSE")
        helpText = 'Create a configuration file for the spec.py script and run it.\n' \
                                                        + 'The spec.py script runs the ECOSSE programme'
        w_run_ecosse.setToolTip(helpText)
        w_run_ecosse.setFixedWidth(WDGT_SIZE_100)
        grid.addWidget(w_run_ecosse, irow, icol)
        w_run_ecosse.clicked.connect(self.runEcosse)
        self.w_run_ecosse = w_run_ecosse

        icol += 3
        w_stop_all = QPushButton('Stop process')
        helpText = 'Stop creation of simulation files or run Ecosse processing'
        w_stop_all.setToolTip(helpText)
        w_stop_all.setEnabled(False)
        w_stop_all.setFixedWidth(WDGT_SIZE_100)
        grid.addWidget(w_stop_all, irow, icol)
        self.w_stop_all = w_stop_all

        icol += 1
        w_save = QPushButton("Save")
        helpText = 'Save configuration and study definition files'
        w_save.setToolTip(helpText)
        w_save.setFixedWidth(WDGT_SIZE_100)
        grid.addWidget(w_save, irow, icol)
        w_save.clicked.connect(self.saveClicked)

        icol += 1
        w_spec = QPushButton("Cancel")
        helpText = 'Leaves GUI without saving configuration and study definition files'
        w_spec.setToolTip(helpText)
        w_spec.setFixedWidth(WDGT_SIZE_100)
        grid.addWidget(w_spec, irow, icol)
        w_spec.clicked.connect(self.cancelClicked)

        icol += 1
        w_exit = QPushButton("Exit", self)
        w_exit.setFixedWidth(WDGT_SIZE_100)
        grid.addWidget(w_exit, irow, icol)
        w_exit.clicked.connect(self.exitClicked)

        # test actions
        # ============
        irow += 1
        icol = 0
        w_wthr_only = QPushButton('Create weather')
        helpText = 'Generate weather only'
        w_wthr_only.setToolTip(helpText)
        w_wthr_only.setEnabled(True)
        grid.addWidget(w_wthr_only, irow, icol)
        w_wthr_only.clicked.connect(self.gnrtWthrClicked)
        self.w_wthr_only = w_wthr_only

        icol += 5
        w_test_fert = QPushButton("Test fertiliser")
        helpText = 'check netCDF4 files making up fertiliser inputs'
        w_test_fert.setToolTip(helpText)
        w_test_fert.setFixedWidth(WDGT_SIZE_100)
        grid.addWidget(w_test_fert, irow, icol)
        w_test_fert.clicked.connect(self.testFertiliserClicked)
        
        icol += 1
        w_mappings = QPushButton("Test Mappings")
        helpText = 'check mappings of states and provinces in the FAO Excel sheet with those' + \
                   ' in the GADM and countries files'
        w_mappings.setToolTip(helpText)
        w_mappings.setFixedWidth(WDGT_SIZE_100)
        grid.addWidget(w_mappings, irow, icol)
        w_mappings.clicked.connect(self.checkMappingsClicked)

        # Layout this window
        # ==================
        rh_vbox.addLayout(grid)     # add grid to RH vertical box
        hbox.addLayout(rh_vbox)     # vertical box goes into horizontal box
        self.setLayout(hbox)        # the horizontal box fits inside the window

        self.setGeometry(300, 300, 690, 250)   # posx, posy, width, height
        self.setWindowTitle('Global Ecosse Site Specific - generate sets of ECOSSE input files based on HWSD grid')

        # reads and set values from last run
        # ==================================
        read_config_file(self)

        self.w_ll_lat.textChanged[str].connect(self.bboxTextChanged)
        self.w_ll_lon.textChanged[str].connect(self.bboxTextChanged)
        self.w_ur_lat.textChanged[str].connect(self.bboxTextChanged)
        self.w_ur_lon.textChanged[str].connect(self.bboxTextChanged)

        self.changeRegion()  # populates lat/long boxes

    def gnrtWthrClicked(self):
        """
        generate weather for all regions, scenarios and GCMs
        """
        generate_all_weather(self)

        return

    def reloadClimScenarios(self):
        """
        determine scenarios for this GCM
        """
        gcm = self.combo10w.currentText()
        scnrs = []
        for wthr_set in self.weather_set_linkages['WrldClim']:
            this_gcm, scnr = wthr_set.split('_')
            if this_gcm == gcm:
                scnrs.append(scnr)

        self.combo10.clear()
        self.combo10.addItems(scnrs)

    def checkMappingsClicked(self):

        check_cntry_prvnc_mappings(self)

    def testFertiliserClicked(self):

        if self.w_all_regions.isChecked():
            all_generate_banded_sims_test(self)
        else:
            region = self.combo00a.currentText()
            crop_name = self.combo00b.currentText()
            generate_banded_sims_test(self, region, crop_name)
            write_study_definition_file(self)

    def saveClicked(self):

        func_name = __prog__ + ' saveClicked'

        # check for spaces
        # ================
        study = self.w_study.text()
        if study == '':
            print('study cannot be blank')
        else:
            if study.find(' ') >= 0:
                print('*** study name must not have spaces ***')
            else:
                save_clicked(self)
                build_and_display_studies(self)

    def resolutionChanged(self):

        calculate_grid_cell(self)

    def changeRegion(self):

        # bounding box set up
        irow = self.combo00a.currentIndex()

        ll_lon, ur_lon, ll_lat, ur_lat, wthr_dir = self.regions.iloc[irow][1:]
        area = calculate_area(list([ll_lon, ll_lat, ur_lon, ur_lat]))
        self.w_ll_lon.setText(str(ll_lon))
        self.w_ll_lat.setText(str(ll_lat))
        self.w_ur_lon.setText(str(ur_lon))
        self.w_ur_lat.setText(str(ur_lat))
        self.lbl03.setText(format_bbox(self.setup['bbox'], area))
        self.setup['region_wthr_dir'] = wthr_dir        # see also def set_region_study

    def bboxTextChanged(self):

        try:
            bbox = list([float(self.w_ll_lon.text()), float(self.w_ll_lat.text()),
                float(self.w_ur_lon.text()), float(self.w_ur_lat.text())])
            area = calculate_area(bbox)
            self.lbl03.setText(format_bbox(bbox, area))
            self.bbox = bbox
        except ValueError as e:
            pass

    def createSimsClicked(self):

        func_name =  __prog__ + ' createSimsClicked'

        hist_start_year = int(self.combo09s.currentText())
        hist_end_year   = int(self.combo09e.currentText())
        if hist_start_year > hist_end_year:
            print('Historic end year must be greater or equal to the start year')
            return

        fut_start_year = int(self.combo11s.currentText())
        fut_end_year   = int(self.combo11e.currentText())
        if fut_start_year > fut_end_year:
            print('Simulation end year must be greater or equal to the start year')
            return

        # overides ECOSSE file creation
        # =============================
        study = self.combo00a.currentText()
        study = study.replace(' ','_')
        self.setup['study'] = study
        calculate_grid_cell(self)

        if self.w_all_regions.isChecked():
            all_generate_banded_sims(self)
        else:
            region = self.combo00a.currentText()
            crop_name = self.combo00b.currentText()
            generate_banded_sims(self, region, crop_name)
            write_study_definition_file(self)

    def runEcosse(self):

        func_name =  __prog__ + ' runEcosse'

        calculate_grid_cell(self)   # assigns value to req_resol_deg
        set_region_study(self)      # sets simulation root directory
        run_ecosse_wrapper(self)

    def fetchCultivJsonFile(self):
        """
        QFileDialog returns a tuple for Python 3.5, 3.6
        """
        fname = self.w_lbl13.text()
        fname, dummy = QFileDialog.getOpenFileName(self, 'Open file', fname, 'JSON files (*.json)')
        if fname != '':
            self.w_lbl13.setText(fname)
            self.w_lbl14.setText(check_cultiv_json_fname(self))

    def fetchCropRotaJsonFile(self):
        """
        QFileDialog returns a tuple for Python 3.5, 3.6
        """
        fname = self.w_lbl16.text()
        fname, dummy = QFileDialog.getOpenFileName(self, 'Open file', fname, 'JSON files (*.json)')
        if fname != '':
            self.w_lbl16.setText(fname)
            self.w_lbl17.setText(check_rotation_json_fname(self))

    def changeConfigFile(self):
        '''
        permits change of configuration file
        '''
        change_config_file(self)

    def cancelClicked(self):

        func_name =  __prog__ + ' cancelClicked'

        exit_clicked(self, write_config_flag = False)

    def exitClicked(self):
        '''
        exit cleanly
        '''
        exit_clicked(self)

    def changeCrop(self):
        '''
        dummy
        '''
        pass

def main():
    """

    """
    app = QApplication(sys.argv)  # create QApplication object
    form = Form() # instantiate form
    # display the GUI and start the event loop if we're not running batch mode
    form.show()             # paint form
    sys.exit(app.exec_())   # start event loop

if __name__ == '__main__':
    main()
