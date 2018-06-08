__author__ = 'labx'

import os, sys, numpy

from PyQt5.QtGui import QPalette, QColor, QFont
from PyQt5.QtWidgets import QMessageBox
from orangewidget import gui
from orangewidget import widget
from orangewidget.settings import Setting
from oasys.widgets import gui as oasysgui
from oasys.widgets import congruence
from oasys.util.oasys_util import EmittingStream
from oasys.util.oasys_util import TriggerIn, TriggerOut

from syned.beamline.beamline import Beamline
from syned.beamline.optical_elements.absorbers.slit import Slit
from syned.storage_ring.light_source import ElectronBeam, LightSource
from syned.widget.widget_decorator import WidgetDecorator
from syned.beamline.shape import Rectangle

from wofrysrw.propagator.wavefront2D.srw_wavefront import WavefrontParameters, WavefrontPrecisionParameters
from wofrysrw.storage_ring.srw_electron_beam import SRWElectronBeam
from wofrysrw.beamline.srw_beamline import SRWBeamline

from orangecontrib.srw.util.srw_util import SRWPlot
from orangecontrib.srw.util.srw_objects import SRWData
from orangecontrib.srw.widgets.gui.ow_srw_wavefront_viewer import SRWWavefrontViewer

class OWSRWSource(SRWWavefrontViewer, WidgetDecorator):

    maintainer = "Luca Rebuffi"
    maintainer_email = "luca.rebuffi(@at@)elettra.eu"
    category = "Sources"
    keywords = ["data", "file", "load", "read"]

    inputs = WidgetDecorator.syned_input_data()
    inputs.append(("SynedData#2", Beamline, "receive_syned_data"))
    inputs.append(("Trigger", TriggerOut, "sendNewWavefront"))

    outputs = [{"name":"SRWData",
                "type":SRWData,
                "doc":"SRW Source Data",
                "id":"data"}]

    want_main_area=1

    source_name = None

    electron_energy_in_GeV = Setting(2.0)
    electron_energy_spread = Setting(0.0007)
    ring_current = Setting(0.4)
    electron_beam_size_h = Setting(5.5453e-05)
    electron_beam_size_v = Setting(2.784e-06)
    electron_beam_divergence_h = Setting(4.5083e-06)
    electron_beam_divergence_v = Setting(8.98e-07)

    moment_x = Setting(0.0)
    moment_y = Setting(0.0)
    moment_z = Setting(0.0)
    moment_xp = Setting(0.0)
    moment_yp = Setting(0.0)

    moment_xx           = Setting((0.05545e-3)**2)
    moment_xxp          = Setting(0.0)
    moment_xpxp         = Setting((4.5083e-06)**2)
    moment_yy           = Setting((2.784e-6)**2)
    moment_yyp          = Setting(0.0)
    moment_ypyp         = Setting((8.98e-07)**2)

    horizontal_emittance = Setting(0.0)
    horizontal_beta = Setting(0.0)
    horizontal_alpha = Setting(0.0)
    horizontal_eta = Setting(0.0)
    horizontal_etap   = Setting(0.0)
    vertical_emittance= Setting(0.0)
    vertical_beta     = Setting(0.0)
    vertical_alpha    = Setting(0.0)
    vertical_eta = Setting(0.0)
    vertical_etap = Setting(0.0)

    type_of_properties = Setting(1)
    type_of_initialization = Setting(0)

    wf_photon_energy = Setting(8000.0)
    wf_h_slit_gap = Setting(0.001)
    wf_v_slit_gap =Setting( 0.001)
    wf_h_slit_points=Setting(100)
    wf_v_slit_points=Setting(100)
    wf_distance = Setting(10.0)

    wf_sr_method = Setting(1)
    wf_relative_precision = Setting(0.01)
    wf_start_integration_longitudinal_position = Setting(0.0) 
    wf_end_integration_longitudinal_position = Setting(0.0) 
    wf_number_of_points_for_trajectory_calculation = Setting(50000)
    wf_use_terminating_terms = Setting(1)
    wf_sampling_factor_for_adjusting_nx_ny = Setting(0.0) 


    TABS_AREA_HEIGHT = 618
    CONTROL_AREA_WIDTH = 405

    def __init__(self, show_automatic_box=False):
        super().__init__(show_automatic_box=show_automatic_box)

        self.runaction = widget.OWAction("Run SRW", self)
        self.runaction.triggered.connect(self.runSRWSource)
        self.addAction(self.runaction)

        self.general_options_box.setVisible(False)

        button_box = oasysgui.widgetBox(self.controlArea, "", addSpace=False, orientation="horizontal")

        button = gui.button(button_box, self, "Run SRW Source", callback=self.runSRWSource)
        font = QFont(button.font())
        font.setBold(True)
        button.setFont(font)
        palette = QPalette(button.palette()) # make a copy of the palette
        palette.setColor(QPalette.ButtonText, QColor('Dark Blue'))
        button.setPalette(palette) # assign new palette
        button.setFixedHeight(45)

        button = gui.button(button_box, self, "Reset Fields", callback=self.callResetSettings)
        font = QFont(button.font())
        font.setItalic(True)
        button.setFont(font)
        palette = QPalette(button.palette()) # make a copy of the palette
        palette.setColor(QPalette.ButtonText, QColor('Dark Red'))
        button.setPalette(palette) # assign new palette
        button.setFixedHeight(45)
        button.setFixedWidth(150)

        gui.separator(self.controlArea)

        self.controlArea.setFixedWidth(self.CONTROL_AREA_WIDTH)

        self.tabs_setting = oasysgui.tabWidget(self.controlArea)
        self.tabs_setting.setFixedHeight(self.TABS_AREA_HEIGHT)
        self.tabs_setting.setFixedWidth(self.CONTROL_AREA_WIDTH-5)

        self.tab_source = oasysgui.createTabPage(self.tabs_setting, "Light Source Setting")

        left_box_1 = oasysgui.widgetBox(self.tab_source, "Electron Beam Parameters", addSpace=True, orientation="vertical", height=380)

        oasysgui.lineEdit(left_box_1, self, "electron_energy_in_GeV", "Energy [GeV]", labelWidth=260, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(left_box_1, self, "electron_energy_spread", "Energy Spread", labelWidth=260, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(left_box_1, self, "ring_current", "Ring Current [A]", labelWidth=260, valueType=float, orientation="horizontal")

        tab_electron = oasysgui.tabWidget(left_box_1)

        tab_beam = oasysgui.createTabPage(tab_electron, "Beam")
        tab_traj = oasysgui.createTabPage(tab_electron, "Trajectory")

        gui.separator(tab_beam)

        gui.comboBox(tab_beam, self, "type_of_properties", label="Electron Beam Properties", labelWidth=350,
                     items=["From 2nd Moments", "From Size/Divergence", "From Twiss"],
                     callback=self.set_TypeOfProperties,
                     sendSelectedValue=False, orientation="horizontal")

        self.left_box_2_1 = oasysgui.widgetBox(tab_beam, "", addSpace=False, orientation="vertical", height=185)

        gui.separator(self.left_box_2_1)

        oasysgui.lineEdit(self.left_box_2_1, self, "moment_xx", "\u03c3x\u22c5\u03c3x   [m\u00b2]", labelWidth=200, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(self.left_box_2_1, self, "moment_xxp", "\u03c3x\u22c5\u03c3x'  [m\u22c5rad]", labelWidth=200, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(self.left_box_2_1, self, "moment_xpxp", "\u03c3x'\u22c5\u03c3x' [rad\u00b2]", labelWidth=200, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(self.left_box_2_1, self, "moment_yy", "\u03c3y\u22c5\u03c3y   [m\u00b2]", labelWidth=200, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(self.left_box_2_1, self, "moment_yyp", "\u03c3y\u22c5\u03c3y'  [m\u22c5rad]", labelWidth=200, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(self.left_box_2_1, self, "moment_ypyp", "\u03c3y'\u22c5\u03c3y' [rad\u00b2]", labelWidth=200, valueType=float, orientation="horizontal")

        self.left_box_2_2 = oasysgui.widgetBox(tab_beam, "", addSpace=False, orientation="vertical", height=185)

        gui.separator(self.left_box_2_2)

        oasysgui.lineEdit(self.left_box_2_2, self, "electron_beam_size_h",       "\u03c3x [m]", labelWidth=200, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(self.left_box_2_2, self, "electron_beam_size_v",       "\u03c3y [m]",  labelWidth=200, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(self.left_box_2_2, self, "electron_beam_divergence_h", "\u03c3x' [rad]", labelWidth=200, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(self.left_box_2_2, self, "electron_beam_divergence_v", "\u03c3y' [rad]", labelWidth=200, valueType=float, orientation="horizontal")

        self.left_box_2_3 = oasysgui.widgetBox(tab_beam, "", addSpace=False, orientation="horizontal", height=185)

        left_box_2_3_l = oasysgui.widgetBox(self.left_box_2_3, "", addSpace=False, orientation="vertical", height=185)
        left_box_2_3_r = oasysgui.widgetBox(self.left_box_2_3, "", addSpace=False, orientation="vertical", height=185)

        gui.separator(left_box_2_3_l)
        gui.separator(left_box_2_3_r)

        oasysgui.lineEdit(left_box_2_3_l, self, "horizontal_emittance", "Emittance x [m]", labelWidth=100, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(left_box_2_3_l, self, "horizontal_beta"     , "\u03B2x [m]"    , labelWidth=100, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(left_box_2_3_l, self, "horizontal_alpha"    , "\u03B1x [rad]"    , labelWidth=100, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(left_box_2_3_l, self, "horizontal_eta"      , "\u03B7x [m]"    , labelWidth=100, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(left_box_2_3_l, self, "horizontal_etap"     , "\u03B7x' [rad]"   , labelWidth=100, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(left_box_2_3_r, self, "vertical_emittance"  , "Emittance y [m]", labelWidth=100, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(left_box_2_3_r, self, "vertical_beta"       , "\u03B2y [m]"    , labelWidth=100, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(left_box_2_3_r, self, "vertical_alpha"      , "\u03B1y [rad]"    , labelWidth=100, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(left_box_2_3_r, self, "vertical_eta"        , "\u03B7y [m]"    , labelWidth=100, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(left_box_2_3_r, self, "vertical_etap"       , "\u03B7y' [rad]"   , labelWidth=100, valueType=float, orientation="horizontal")

        self.set_TypeOfProperties()

        gui.comboBox(tab_traj, self, "type_of_initialization", label="Trajectory Initialization", labelWidth=140,
                     items=["At Zero Point", "At Fixed Position", "Sampled from Phase Space"],
                     callback=self.set_TypeOfInitialization,
                     sendSelectedValue=False, orientation="horizontal")

        self.left_box_3_1 = oasysgui.widgetBox(tab_traj, "", addSpace=False, orientation="vertical", height=160)
        self.left_box_3_2 = oasysgui.widgetBox(tab_traj, "", addSpace=False, orientation="vertical", height=160)

        oasysgui.lineEdit(self.left_box_3_1, self, "moment_x", "x0 [m]", labelWidth=200, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(self.left_box_3_1, self, "moment_y", "y0 [m]", labelWidth=200, valueType=float, orientation="horizontal")

        box = oasysgui.widgetBox(self.left_box_3_1, "", addSpace=False, orientation="horizontal")

        oasysgui.lineEdit(box, self, "moment_z", "z0 [m]", labelWidth=160, valueType=float, orientation="horizontal")
        gui.button(box, self, "Auto", width=35, callback=self.set_z0Default)


        oasysgui.lineEdit(self.left_box_3_1, self, "moment_xp", "xp0 [rad]", labelWidth=200, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(self.left_box_3_1, self, "moment_yp", "yp0 [rad]", labelWidth=200, valueType=float, orientation="horizontal")

        self.set_TypeOfInitialization()

        self.tab_plots = oasysgui.createTabPage(self.tabs_setting, "Wavefront Setting")

        self.tabs_plots_setting = oasysgui.tabWidget(self.tab_plots)
        
        # PROPAGATION -------------------------------------------
        
        tab_wav = oasysgui.createTabPage(self.tabs_plots_setting, "Propagation")

        wav_box = oasysgui.widgetBox(tab_wav, "Wavefront Parameters", addSpace=True, orientation="vertical")

        self.build_wf_photon_energy_box(wav_box)
        oasysgui.lineEdit(wav_box, self, "wf_h_slit_gap", "H Slit Gap [m]", labelWidth=260, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(wav_box, self, "wf_v_slit_gap", "V Slit Gap [m]", labelWidth=260, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(wav_box, self, "wf_h_slit_points", "H Slit Points", labelWidth=260, valueType=int, orientation="horizontal")
        oasysgui.lineEdit(wav_box, self, "wf_v_slit_points", "V Slit Points", labelWidth=260, valueType=int, orientation="horizontal")
        oasysgui.lineEdit(wav_box, self, "wf_distance", "Propagation Distance [m]", labelWidth=260, valueType=float, orientation="horizontal")

        pre_box = oasysgui.widgetBox(tab_wav, "Precision Parameters", addSpace=False, orientation="vertical")

        gui.comboBox(pre_box, self, "wf_sr_method", label="Calculation Method",
                     items=["Manual", "Auto"], labelWidth=260,
                     sendSelectedValue=False, orientation="horizontal")

        oasysgui.lineEdit(pre_box, self, "wf_relative_precision", "Relative Precision", labelWidth=260, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(pre_box, self, "wf_start_integration_longitudinal_position", "Longitudinal position to start integration\n(effective if < zEndInteg) [m]", labelWidth=260, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(pre_box, self, "wf_end_integration_longitudinal_position", "Longitudinal position to finish integration\n(effective if > zStartInteg) [m]", labelWidth=260, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(pre_box, self, "wf_number_of_points_for_trajectory_calculation", "Number of points for trajectory calculation", labelWidth=260, valueType=int, orientation="horizontal")

        gui.comboBox(pre_box, self, "wf_use_terminating_terms", label="Use \"terminating terms\"\n(i.e. asymptotic expansions at zStartInteg\nand zEndInteg) or not",
                     items=["No", "Yes"], labelWidth=260,
                     sendSelectedValue=False, orientation="horizontal")

        oasysgui.lineEdit(pre_box, self, "wf_sampling_factor_for_adjusting_nx_ny", "Sampling factor for adjusting nx/ny\n(effective if > 0)", labelWidth=260, valueType=int, orientation="horizontal")

        gui.rubber(self.controlArea)

    def set_TypeOfProperties(self):
        self.left_box_2_1.setVisible(self.type_of_properties==0)
        self.left_box_2_2.setVisible(self.type_of_properties==1)
        self.left_box_2_3.setVisible(self.type_of_properties==2)

    def set_TypeOfInitialization(self):
        self.left_box_3_1.setVisible(self.type_of_initialization==1)
        self.left_box_3_2.setVisible(self.type_of_initialization!=1)

    def build_wf_photon_energy_box(self, box):
        oasysgui.lineEdit(box, self, "wf_photon_energy", "Photon Energy [eV]", labelWidth=260, valueType=float, orientation="horizontal")

    def runSRWSource(self):
        self.setStatusMessage("")
        self.progressBarInit()

        try:
            self.checkFields()

            srw_source = self.get_srw_source(self.get_electron_beam())
            srw_source.name = self.source_name if not self.source_name is None else self.windowTitle(),

            self.progressBarSet(10)

            self.setStatusMessage("Running SRW")

            sys.stdout = EmittingStream(textWritten=self.writeStdOut)

            self.print_specific_infos(srw_source)

            self.progressBarSet(20)

            self.setStatusMessage("")

            beamline = SRWBeamline(light_source=srw_source)
            wavefront = self.calculate_wavefront_propagation(srw_source)

            tickets = []

            if self.is_do_plots():
                self.setStatusMessage("Plotting Results")

                self.run_calculation_intensity(wavefront, tickets)

                self.plot_results(tickets)

            self.setStatusMessage("")

            self.send("SRWData", SRWData(srw_beamline=beamline, srw_wavefront=wavefront))

        except Exception as exception:
            QMessageBox.critical(self, "Error", str(exception), QMessageBox.Ok)

            #raise exception

        self.progressBarFinished()

    def sendNewWavefront(self, trigger):
        if trigger and trigger.new_object == True:
            self.runSRWSource()

    def get_electron_beam(self):
        if self.type_of_initialization == 2:
            electron_beam = SRWElectronBeam(energy_in_GeV=numpy.random.normal(self.electron_energy_in_GeV,
                                                                              self.electron_energy_spread*self.electron_energy_in_GeV),
                                            energy_spread=self.electron_energy_spread,
                                            current=self.ring_current)
        else:
            electron_beam = SRWElectronBeam(energy_in_GeV=self.electron_energy_in_GeV,
                                            energy_spread=self.electron_energy_spread,
                                            current=self.ring_current)

        if self.type_of_properties == 0:
            electron_beam._moment_xx = self.moment_xx
            electron_beam._moment_xxp = self.moment_xxp
            electron_beam._moment_xpxp = self.moment_xpxp
            electron_beam._moment_yy = self.moment_yy
            electron_beam._moment_yyp = self.moment_yyp
            electron_beam._moment_ypyp = self.moment_ypyp

            x, xp, y, yp = electron_beam.get_sigmas_all()

            self.electron_beam_size_h = x
            self.electron_beam_size_v = y
            self.electron_beam_divergence_h = xp
            self.electron_beam_divergence_v = yp
        elif self.type_of_properties == 1:
            electron_beam.set_sigmas_all(sigma_x=self.electron_beam_size_h,
                                         sigma_y=self.electron_beam_size_v,
                                         sigma_xp=self.electron_beam_divergence_h,
                                         sigma_yp=self.electron_beam_divergence_v)

            self.moment_xx = electron_beam._moment_xx
            self.moment_xpxp = electron_beam._moment_xpxp
            self.moment_yy = electron_beam._moment_yy
            self.moment_ypyp = electron_beam._moment_ypyp

        elif self.type_of_properties == 2:
            electron_beam.set_moments_from_twiss(horizontal_emittance = self.horizontal_emittance,
                                                 horizontal_beta      = self.horizontal_beta,
                                                 horizontal_alpha     = self.horizontal_alpha,
                                                 horizontal_eta       = self.horizontal_eta,
                                                 horizontal_etap      = self.horizontal_etap,
                                                 vertical_emittance   = self.vertical_emittance,
                                                 vertical_beta        = self.vertical_beta,
                                                 vertical_alpha       = self.vertical_alpha,
                                                 vertical_eta         = self.vertical_eta,
                                                 vertical_etap        = self.vertical_etap)

            self.moment_xx = electron_beam._moment_xx
            self.moment_xpxp = electron_beam._moment_xpxp
            self.moment_yy = electron_beam._moment_yy
            self.moment_ypyp = electron_beam._moment_ypyp

            x, xp, y, yp = electron_beam.get_sigmas_all()

            self.electron_beam_size_h = round(x, 9)
            self.electron_beam_size_v = round(y, 9)
            self.electron_beam_divergence_h = round(xp, 10)
            self.electron_beam_divergence_v = round(yp, 10)

        if self.type_of_initialization == 0: # zero
            self.moment_x = 0.0
            self.moment_y = 0.0
            self.moment_z = self.get_default_initial_z()
            self.moment_xp = 0.0
            self.moment_yp = 0.0
        elif self.type_of_initialization == 2: # sampled
            self.moment_x = numpy.random.normal(0.0, self.electron_beam_size_h)
            self.moment_y = numpy.random.normal(0.0, self.electron_beam_size_v)
            self.moment_z = self.get_default_initial_z()
            self.moment_xp = numpy.random.normal(0.0, self.electron_beam_divergence_h)
            self.moment_yp = numpy.random.normal(0.0, self.electron_beam_divergence_v)

        electron_beam._moment_x = self.moment_x
        electron_beam._moment_y = self.moment_y
        electron_beam._moment_z = self.moment_z
        electron_beam._moment_xp = self.moment_xp
        electron_beam._moment_yp = self.moment_yp

        print("\n", "Electron Trajectory Initialization:")
        print("X0: ", electron_beam._moment_x)
        print("Y0: ", electron_beam._moment_y)
        print("Z0: ", electron_beam._moment_z)
        print("XP0: ", electron_beam._moment_xp)
        print("YP0: ", electron_beam._moment_yp)
        print("E0: ", electron_beam._energy_in_GeV, "\n")

        return electron_beam

    def set_z0Default(self):
        self.moment_z = self.get_default_initial_z()

    def get_default_initial_z(self):
        return NotImplementedError()

    def get_srw_source(self, electron_beam=ElectronBeam()):
        raise NotImplementedError()

    def checkFields(self):
        congruence.checkStrictlyPositiveNumber(self.electron_energy_in_GeV, "Energy")
        congruence.checkPositiveNumber(self.electron_energy_spread, "Energy Spread")
        congruence.checkStrictlyPositiveNumber(self.ring_current, "Ring Current")

        if self.type_of_properties == 0:
            congruence.checkPositiveNumber(self.moment_xx   , "Moment xx")
            congruence.checkPositiveNumber(self.moment_xpxp , "Moment xpxp")
            congruence.checkPositiveNumber(self.moment_yy   , "Moment yy")
            congruence.checkPositiveNumber(self.moment_ypyp , "Moment ypyp")
        elif self.type_of_properties == 1:
            congruence.checkPositiveNumber(self.electron_beam_size_h       , "Horizontal Beam Size")
            congruence.checkPositiveNumber(self.electron_beam_divergence_h , "Vertical Beam Size")
            congruence.checkPositiveNumber(self.electron_beam_size_v       , "Horizontal Beam Divergence")
            congruence.checkPositiveNumber(self.electron_beam_divergence_v , "Vertical Beam Divergence")
        elif self.type_of_properties == 2:
            congruence.checkPositiveNumber(self.horizontal_emittance       , "Horizontal Emittance")
            congruence.checkPositiveNumber(self.vertical_emittance         , "Vertical Emittance")

        self.checkLightSourceSpecificFields()

        if self.type_of_initialization == 2:
            congruence.checkNumber(self.moment_x   , "x0")
            congruence.checkNumber(self.moment_xp , "xp0")
            congruence.checkNumber(self.moment_y   , "y0")
            congruence.checkNumber(self.moment_yp , "yp0")
            congruence.checkNumber(self.moment_z , "z0")


        # WAVEFRONT

        self.checkWavefrontPhotonEnergy()

        congruence.checkStrictlyPositiveNumber(self.wf_h_slit_gap, "Wavefront Propagation H Slit Gap")
        congruence.checkStrictlyPositiveNumber(self.wf_v_slit_gap, "Wavefront Propagation V Slit Gap")
        congruence.checkStrictlyPositiveNumber(self.wf_h_slit_points, "Wavefront Propagation H Slit Points")
        congruence.checkStrictlyPositiveNumber(self.wf_v_slit_points, "Wavefront Propagation V Slit Points")
        congruence.checkGreaterOrEqualThan(self.wf_distance, self.get_minimum_propagation_distance(),
                                           "Wavefront Propagation Distance", "Minimum Distance out of the Source: " + str(self.get_minimum_propagation_distance()))

        congruence.checkStrictlyPositiveNumber(self.wf_relative_precision, "Wavefront Propagation Relative Precision")
        congruence.checkStrictlyPositiveNumber(self.wf_number_of_points_for_trajectory_calculation, "Wavefront Propagation Number of points for trajectory calculation")
        congruence.checkPositiveNumber(self.wf_sampling_factor_for_adjusting_nx_ny, "Wavefront Propagation Sampling Factor for adjusting nx/ny")

    def checkLightSourceSpecificFields(self):
        raise NotImplementedError()


    def checkWavefrontPhotonEnergy(self):
        congruence.checkStrictlyPositiveNumber(self.wf_photon_energy, "Wavefront Propagation Photon Energy")


    def run_calculation_intensity(self, srw_wavefront, tickets, progress_bar_value=30):

        e, h, v, i = srw_wavefront.get_intensity(multi_electron=False)

        tickets.append(SRWPlot.get_ticket_2D(h*1000, v*1000, i[int(e.size/2)]))

        self.progressBarSet(progress_bar_value)

        e, h, v, i = srw_wavefront.get_phase()

        tickets.append(SRWPlot.get_ticket_2D(h*1000, v*1000, i[int(e.size/2)]))

        self.progressBarSet(progress_bar_value + 10)

        e, h, v, i = srw_wavefront.get_intensity(multi_electron=True)

        tickets.append(SRWPlot.get_ticket_2D(h*1000, v*1000, i[int(e.size/2)]))

        self.progressBarSet(progress_bar_value + 10)

    def get_automatic_sr_method(self):
        raise NotImplementedError()

    def calculate_wavefront_propagation(self, srw_source):
        photon_energy = self.get_photon_energy_for_wavefront_propagation(srw_source)

        wf_parameters = WavefrontParameters(photon_energy_min = photon_energy,
                                            photon_energy_max = photon_energy,
                                            photon_energy_points=1,
                                            h_slit_gap = self.wf_h_slit_gap,
                                            v_slit_gap = self.wf_v_slit_gap,
                                            h_slit_points=self.wf_h_slit_points,
                                            v_slit_points=self.wf_v_slit_points,
                                            distance = self.wf_distance,
                                            wavefront_precision_parameters=WavefrontPrecisionParameters(sr_method=0 if self.wf_sr_method == 0 else self.get_automatic_sr_method(),
                                                                                                        relative_precision=self.wf_relative_precision,
                                                                                                        start_integration_longitudinal_position=self.wf_start_integration_longitudinal_position,
                                                                                                        end_integration_longitudinal_position=self.wf_end_integration_longitudinal_position,
                                                                                                        number_of_points_for_trajectory_calculation=self.wf_number_of_points_for_trajectory_calculation,
                                                                                                        use_terminating_terms=self.wf_use_terminating_terms,
                                                                                                        sampling_factor_for_adjusting_nx_ny=self.wf_sampling_factor_for_adjusting_nx_ny))

        return srw_source.get_SRW_Wavefront(source_wavefront_parameters=wf_parameters)

    def get_photon_energy_for_wavefront_propagation(self, srw_source):
        return self.wf_photon_energy

    def get_minimum_propagation_distance(self):
        return round(self.get_source_length()*1.01, 6)

    def get_source_length(self):
        raise NotImplementedError()

    def receive_syned_data(self, data):
            if not data is None:
                try:
                    if data.get_beamline_elements_number() > 0:
                        slit_element = data.get_beamline_element_at(0)
                        slit = slit_element.get_optical_element()
                        coordinates = slit_element.get_coordinates()

                        if isinstance(slit, Slit) and isinstance(slit.get_boundary_shape(), Rectangle):
                            rectangle = slit.get_boundary_shape()

                            self.wf_h_slit_gap = rectangle._x_right - rectangle._x_left
                            self.wf_v_slit_gap = rectangle._y_top - rectangle._y_bottom
                            self.wf_distance = coordinates.p()

                            self.int_h_slit_gap = rectangle._x_right - rectangle._x_left
                            self.int_v_slit_gap = rectangle._y_top - rectangle._y_bottom
                            self.int_distance = coordinates.p()

                            self.spe_h_slit_gap = rectangle._x_right - rectangle._x_left
                            self.spe_v_slit_gap = rectangle._y_top - rectangle._y_bottom
                            self.spe_distance = coordinates.p()
                    elif not data._light_source is None and isinstance(data._light_source, LightSource):
                        light_source = data._light_source

                        self.source_name = light_source._name
                        self.electron_energy_in_GeV = light_source._electron_beam._energy_in_GeV
                        self.electron_energy_spread = light_source._electron_beam._energy_spread
                        self.ring_current = light_source._electron_beam._current

                        self.moment_xx = light_source._electron_beam._moment_xx
                        self.moment_xxp = light_source._electron_beam._moment_xxp
                        self.moment_xpxp = light_source._electron_beam._moment_xpxp
                        self.moment_yy = light_source._electron_beam._moment_yy
                        self.moment_yyp = light_source._electron_beam._moment_yyp
                        self.moment_ypyp = light_source._electron_beam._moment_ypyp

                        x, xp, y, yp = light_source._electron_beam.get_sigmas_all()

                        self.electron_beam_size_h = round(x, 9)
                        self.electron_beam_size_v = round(y, 9)
                        self.electron_beam_divergence_h = round(xp, 10)
                        self.electron_beam_divergence_v = round(yp, 10)

                        self.type_of_properties = 0

                        self.set_TypeOfProperties()

                        self.receive_specific_syned_data(data)
                    else:
                        raise ValueError("Syned data not correct")
                except Exception as exception:
                    QMessageBox.critical(self, "Error", str(exception), QMessageBox.Ok)

    def receive_specific_syned_data(self, data):
        raise NotImplementedError()
