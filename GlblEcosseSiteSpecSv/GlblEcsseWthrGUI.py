# -------------------------------------------------------------------------------
# Name:
# Purpose:     Creates a GUI with five adminstrative levels plus country
# Author:      Mike Martin
# Created:     11/12/2015
# Licence:     <your licence>
# -------------------------------------------------------------------------------
#
__prog__ = 'GlblEcsseWthrGUI.py'
__version__ = '0.0.1'
__author__ = 's03mm5'

import sys
from os.path import join, isdir
from os import listdir

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (QLabel, QWidget, QApplication, QHBoxLayout, QVBoxLayout, QGridLayout, QLineEdit,
                                                            QComboBox, QRadioButton,  QPushButton, QCheckBox)

from initialise_funcs import (read_wthr_config_file, initiation, write_wthr_config_file, build_and_display_studies)
from commonCmpntsGUI import exit_clicked, commonSection, grid_coarseness, calculate_grid_cell
from glbl_ecss_cmmn_funcs import write_study_definition_file
from shape_funcs import format_bbox, calculate_area

from wthr_generation_fns import generate_all_weather, write_avemet_files
from wthr_generation_rothc_fns import generate_banded_rothc_wthr

WARNING_STR = '*** Warning *** '

WDGT_SIZE_80 = 80
WDGT_SIZE_100 = 100
WDGT_SIZE_120 = 120
WDGT_SIZE_180 = 180
WTHR_FLAG = True

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

        # right hand box consists of w_combo boxes, labels and buttons
        # ==========================================================
        rh_vbox = QVBoxLayout()

        # The layout is done with the QGridLayout
        grid = QGridLayout()
        grid.setSpacing(10)	# set spacing between widgets
        irow = 0

        # line 1
        # ======
        irow += 1
        lbl00a = QLabel('Region:')
        lbl00a.setAlignment(Qt.AlignRight)
        grid.addWidget(lbl00a, irow, 0)

        w_combo00a= QComboBox()
        for region in self.regions:
            w_combo00a.addItem(region)
        w_combo00a.setFixedWidth(WDGT_SIZE_180)
        grid.addWidget(w_combo00a, irow, 1)
        w_combo00a.currentIndexChanged[str].connect(self.changeRegion)
        self.w_combo00a = w_combo00a

        w_combo00b = QComboBox()        # Crop
        self.w_combo00b = w_combo00b

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

        w_equimode = QLineEdit()       # equilibrium mode
        self.w_equimode = w_equimode

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

        w_all_regions = QCheckBox('All studies')
        self.w_all_regions = w_all_regions

        w_all_crops = QCheckBox('All crops')
        self.w_all_crops = w_all_crops

        # simplification options
        # ======================
        w_use_dom_soil = QCheckBox('Use most dominant soil')
        self.w_use_dom_soil = w_use_dom_soil

        w_use_high_cover = QCheckBox('Use highest coverage soil')
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
        self.w_glbl_n_inpts = w_glbl_n_inpts

        w_use_peren = QCheckBox('Use perennial crops')
        self.w_use_peren = w_use_peren

        # dormant
        # =======
        w_daily = QRadioButton("Daily")
        self.w_daily  = w_daily

        w_mnthly = QRadioButton("Monthly")
        self.w_mnthly = w_mnthly

        # weather resource and simulation period
        # ======================================
        irow = 9
        irow = commonSection(self, grid, irow, WTHR_FLAG)
        irow = grid_coarseness(self, grid, irow)

        # actions
        # =======
        irow += 3
        icol = 0
        w_auto_run_ec  = QCheckBox('Auto run Ecosse')
        self.w_auto_run_ec  = w_auto_run_ec
        icol += 5

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

        icol += 3
        w_rothc_wthr = QPushButton("RothC wthr")
        helpText = 'Generate RothC weathrer'
        w_rothc_wthr.setToolTip(helpText)
        w_rothc_wthr.setFixedWidth(WDGT_SIZE_100)
        w_rothc_wthr.setEnabled(True)
        grid.addWidget(w_rothc_wthr, irow, icol)
        w_rothc_wthr.clicked.connect(self.gnrtRthCwthrClicked)

        icol += 4
        w_chck_wthr = QPushButton("Check Weather")
        helpText = 'Check weather'
        w_chck_wthr.setToolTip(helpText)
        w_chck_wthr.setFixedWidth(WDGT_SIZE_100)
        grid.addWidget(w_chck_wthr, irow, icol)
        w_chck_wthr.clicked.connect(self.checkWthrClicked)

        # Layout this window
        # ==================
        rh_vbox.addLayout(grid)     # add grid to RH vertical box
        hbox.addLayout(rh_vbox)     # vertical box goes into horizontal box
        self.setLayout(hbox)        # the horizontal box fits inside the window

        self.setGeometry(300, 300, 690, 250)   # posx, posy, width, height
        self.setWindowTitle('Global Ecosse Site Specific - generate sets of ECOSSE input files based on HWSD grid')

        # reads and set values from last run
        # ==================================
        read_wthr_config_file(self)

        self.w_ll_lat.textChanged[str].connect(self.bboxTextChanged)
        self.w_ll_lon.textChanged[str].connect(self.bboxTextChanged)
        self.w_ur_lat.textChanged[str].connect(self.bboxTextChanged)
        self.w_ur_lon.textChanged[str].connect(self.bboxTextChanged)

        self.changeRegion()  # populates lat/long boxes

    def gnrtRthCwthrClicked(self):
        """
        generate weather for all regions, scenarios and GCMs
        """
        generate_banded_rothc_wthr(self)

        return

    def checkWthrClicked(self):
        """
        C
        """
        wthr_scenarios = self.wthr_scenarios
        sims_dir = self.setup['sims_dir']

        fs_dirs = listdir(sims_dir)
        for fn in fs_dirs:
            this_dir = join(sims_dir, fn)
            if isdir(this_dir):
                res = fn.split('_')
                if len(res) == 2:
                    if res[1] in wthr_scenarios:
                        print('\tentities in ' + fn + ' ' + str(len(listdir(this_dir))))

        return

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
        gcm = self.w_combo10w.currentText()
        scnrs = []
        for wthr_set in self.weather_set_linkages['WrldClim']:
            this_gcm, scnr = wthr_set.split('_')
            if this_gcm == gcm:
                scnrs.append(scnr)

        self.w_combo10.clear()
        self.w_combo10.addItems(scnrs)

    def saveClicked(self):
        """
        validate user input by checking for spaces and blankness
        """
        study = self.w_study.text()
        if study == '':
            print('study cannot be blank')
        else:
            if study.find(' ') >= 0:
                print('*** study name must not have spaces ***')
            else:
                # write last GUI selections
                write_wthr_config_file(self)
                write_study_definition_file(self)
                build_and_display_studies(self)

    def resolutionChanged(self):
        """

        """
        calculate_grid_cell(self)

    def changeRegion(self):
        """

        """
        # bounding box set up
        irow = self.w_combo00a.currentIndex()

        ll_lon, ur_lon, ll_lat, ur_lat, wthr_dir = self.regions_df.iloc[irow][1:]
        area = calculate_area(list([ll_lon, ll_lat, ur_lon, ur_lat]))
        self.w_ll_lon.setText(str(ll_lon))
        self.w_ll_lat.setText(str(ll_lat))
        self.w_ur_lon.setText(str(ur_lon))
        self.w_ur_lat.setText(str(ur_lat))
        self.lbl03.setText(format_bbox(self.setup['bbox'], area))
        self.setup['region_wthr_dir'] = wthr_dir        # see also def set_region_study

    def bboxTextChanged(self):
        """

        """
        try:
            bbox = list([float(self.w_ll_lon.text()), float(self.w_ll_lat.text()),
                float(self.w_ur_lon.text()), float(self.w_ur_lat.text())])
            area = calculate_area(bbox)
            self.lbl03.setText(format_bbox(bbox, area))
            self.bbox = bbox
        except ValueError as e:
            pass

    def cancelClicked(self):
        """

        """
        exit_clicked(self, write_config_flag = False)

    def exitClicked(self):
        """
        exit cleanly
        """
        exit_clicked(self, wthr_only_flag = True)

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
