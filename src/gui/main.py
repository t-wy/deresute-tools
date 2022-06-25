from PyQt5.QtCore import QMetaObject, QCoreApplication, Qt
from PyQt5.QtGui import QIcon, QIntValidator, QFontMetrics
from PyQt5.QtWidgets import QWidget, QGridLayout, QVBoxLayout, QHBoxLayout, QTabWidget, QPushButton, QApplication, \
    QMainWindow, QCheckBox, QScrollArea, QLineEdit, QSizePolicy

import customlogger as logger
from chihiro import ROOT_DIR
from gui.events.calculator_view_events import ToggleUnitLockingOptionsVisibilityEvent
from gui.events.chart_viewer_events import PopupChartViewerEvent
from gui.events.service.tips_refresher_service import kill_tip_refresher_service
from gui.events.state_change_events import ShutdownTriggeredEvent, BackupFlagsEvent
from gui.events.utils import eventbus
from gui.viewmodels.card import CardView, CardModel, IconLoaderView, IconLoaderModel
from gui.viewmodels.custom_card import CustomView
from gui.viewmodels.chart_viewer import ChartViewer
from gui.viewmodels.potential import PotentialView, PotentialModel
from gui.viewmodels.quicksearch import QuickSearchView, QuickSearchModel, SongQuickSearchView, SongQuickSearchModel
from gui.viewmodels.simulator.wide_smart import MainView, MainModel
from gui.viewmodels.song import SongView, SongModel
from gui.viewmodels.tips_view import TipView
from gui.viewmodels.unit import UnitView, UnitModel
from logic.profile import profile_manager, unit_storage
from logic.search import indexer, search_engine


class CustomMainWindow(QMainWindow):
    def __init__(self, app: QApplication, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.app = app

    def setui(self, ui):
        self.ui = ui

    def keyPressEvent(self, event):
        key = event.key()
        if QApplication.keyboardModifiers() == Qt.ControlModifier and key == Qt.Key_F:
            self.ui.quicksearch_view.focus()
        if QApplication.keyboardModifiers() == (Qt.ShiftModifier | Qt.ControlModifier) and key == Qt.Key_F:
            self.ui.songsearch_view.focus()
        if QApplication.keyboardModifiers() == (Qt.ShiftModifier | Qt.ControlModifier) and key == Qt.Key_H:
            eventbus.eventbus.post(ToggleUnitLockingOptionsVisibilityEvent())
        if QApplication.keyboardModifiers() == Qt.ControlModifier and key == Qt.Key_S:
            logger.info("User data backed up")
            eventbus.eventbus.post(ShutdownTriggeredEvent())
            eventbus.eventbus.post(BackupFlagsEvent())
            unit_storage.clean_all_units(grand=False)
            for r_idx in range(self.ui.user_unit_view1.widget.count()):
                widget = self.ui.user_unit_view1.widget.itemWidget(self.ui.user_unit_view1.widget.item(r_idx))
                widget.update_unit()
            profile_manager.cleanup()

    def closeEvent(self, event):
        eventbus.eventbus.post(ShutdownTriggeredEvent())
        eventbus.eventbus.post(BackupFlagsEvent())
        event.accept()

# noinspection PyAttributeOutsideInit
class UiMainWindow:
    def __init__(self, main):
        self.main = main

    def setup_ui(self):
        logger.info("Initializing UI")
        self.main.resize(1920, 1010)
        qr = self.main.frameGeometry()
        cp = self.main.app.primaryScreen().availableGeometry().topLeft()
        qr.moveTopLeft(cp)
        self.main.move(qr.topLeft())
        self.setup_base()
        self.setup_unit_layout()
        self.setup_simulator_layout()
        self.simulation_calculator_view.setUserID(self.import_text)
        #self.setup_tip_view()
        self.main.setCentralWidget(self.central_widget)
        self.retranslate_ui(self.main)
        QMetaObject.connectSlotsByName(self.main)

    def setup_base(self):
        logger.info("Setting up UI base")

        self.central_widget = QWidget(self.main)
        self.grid_layout = QGridLayout(self.central_widget)
        self.main_layout = QHBoxLayout()
    
    '''
    def setup_tip_view(self):
        self.tip_view = TipView()
        self.grid_layout.addWidget(self.tip_view, 1, 0, 1, 1)
    '''
    
    def setup_unit_layout(self):
        logger.info("Setting up unit layouts")
        
        self.simulator_layout = QVBoxLayout()
        self.simulator = QTabWidget(self.central_widget)
        
        self.unit_widget = QWidget()
        self.unit_layout = QHBoxLayout(self.unit_widget)
        
        self.unit_left_layout = QVBoxLayout()
        
        self.unit_user_unit_custom_layout = QHBoxLayout()
        
        self.user_unit_layout = QVBoxLayout()
        self.user_unit_view1 = UnitView(self.central_widget)
        self.user_unit_view2 = UnitView(self.central_widget)
        self.user_unit_view1.set_copy(self.user_unit_view2)
        self.user_unit_view2.set_copy(self.user_unit_view1)
        self.user_unit_model = UnitModel(self.user_unit_view1, self.user_unit_view2)
        self.user_unit_view1.set_model(self.user_unit_model)
        self.user_unit_view2.set_model(self.user_unit_model)
        self.user_unit_model.initialize_units()
        self.user_unit_layout.addWidget(self.user_unit_view1.widget)
        
        self.add_unit_button = QPushButton()
        self.add_unit_button.setText("Add unit")
        self.add_unit_button.setToolTip(
            "Add an untitled unit. Untitled units are not saved upon exit!\n"
            "Make sure to give your units a name. Unit names must be different.\n"
            "First/Red card is the leader, last/blue card is the guest.")
        self.add_unit_button.clicked.connect(lambda: self.user_unit_view1.add_empty_widget())
        self.add_unit_button.clicked.connect(lambda: self.user_unit_view2.add_empty_widget())
        self.user_unit_layout.addWidget(self.add_unit_button)
        
        self.unit_user_unit_custom_layout.addLayout(self.user_unit_layout, 2)
        
        self.custom_view = CustomView()
        self.custom_view.setup()
        self.custom_view.set_unit_view(self.user_unit_view1)
        self.unit_user_unit_custom_layout.addWidget(self.custom_view.widget, 3)
        self.unit_left_layout.addLayout(self.unit_user_unit_custom_layout)

        self.card_layout = QVBoxLayout()
        self.card_quicksearch_layout = QHBoxLayout()
        self.quicksearch_layout = QHBoxLayout()

        # Set up card MV first
        self.card_view = CardView(self.central_widget)
        self.card_model = CardModel(self.card_view)
        self.card_view.set_model(self.card_model)
        self.card_model.initialize_cards(potential=False)
        self.card_view.initialize_pics()
        self.card_view.connect_cell_change()
        self.card_layout.addWidget(self.card_view.widget)

        # Need card view
        self.quicksearch_view = QuickSearchView(self.central_widget)
        self.quicksearch_model = QuickSearchModel(self.quicksearch_view, self.card_view)
        self.quicksearch_view.set_model(self.quicksearch_model)
        self.card_quicksearch_layout.addLayout(self.quicksearch_layout)
        self.quicksearch_layout.addWidget(self.quicksearch_view.widget)
        self.highlight_checkbox = QCheckBox(self.central_widget)
        self.highlight_checkbox.setText("Highlight Carnival Idols")
        self.highlight_checkbox.clicked.connect(lambda _: self.card_model.highlight_event_cards(_))
        self.quicksearch_layout.addWidget(self.highlight_checkbox)
        self.quicksearch_model.add_options(self.quicksearch_layout, self.central_widget)

        # Then icon loader MV since it makes use of the card model
        self.icon_loader_view = IconLoaderView(self.central_widget)
        self.icon_loader_model = IconLoaderModel(self.icon_loader_view, self.card_model)
        self.icon_loader_view.set_model(self.icon_loader_model)
        self.icon_loader_view.widget.setToolTip("Larger icons require more RAM to run.")
        self.icon_loader_model.load_image(0)
        self.card_quicksearch_layout.addWidget(self.icon_loader_view.widget)
        
        self.import_layout = QHBoxLayout()
        self.import_text = QLineEdit(self.main)
        txt = "999999999"
        self.import_text.setPlaceholderText("User ID")
        self.import_text.setValidator(QIntValidator(0, 999999999, None))  # Only number allowed
        fm = QFontMetrics(self.import_text.font())
        self.import_text.setFixedWidth(fm.width(txt) + 10)
        self.import_button = QPushButton("Import from ID", self.main)
        self.import_button.pressed.connect(lambda: self.import_from_id(self.import_text.text()))
        self.import_button.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.import_layout.addWidget(self.import_text)
        self.import_layout.addWidget(self.import_button)
        self.card_quicksearch_layout.addLayout(self.import_layout)
        
        self.card_layout.addLayout(self.card_quicksearch_layout)
        self.card_layout.setStretch(1, 1)
        
        self.unit_left_layout.addLayout(self.card_layout)
        self.unit_layout.addLayout(self.unit_left_layout, 3)
        
        self.unit_potential_view = PotentialView()
        self.unit_potential_model = PotentialModel(self.unit_potential_view)
        self.unit_potential_view.set_model(self.unit_potential_model)
        self.unit_potential_model.initialize_data()
        self.unit_layout.addWidget(self.unit_potential_view.widget, 1)
        
        self.simulator.addTab(self.unit_widget, "Unit")
    
    def setup_simulator_layout(self):
        logger.info("Setting up simulator layouts")
        
        self.simulation_widget = QWidget()
        self.simulation_layout = QGridLayout(self.simulation_widget)
        
        self.simulation_calculator_view = MainView()
        self.simulation_calculator_model = MainModel(self.simulation_calculator_view)
        self.simulation_calculator_view.set_model(self.simulation_calculator_model)
        self.simulation_calculator_view.setup()
        self.simulation_layout.addWidget(self.simulation_calculator_view.widget, 0, 0, 1, 1)
        self.custom_view.set_calculator_view(self.simulation_calculator_view)
        
        self.simulation_bottom_layout = QHBoxLayout()
        self.simulation_bottom_layout.addWidget(self.user_unit_view2.widget, 4)
        
        self.simulation_song_layout = QVBoxLayout()
        self.simulation_song_view = SongView(self.central_widget)
        self.simulation_song_model = SongModel(self.simulation_song_view)
        self.simulation_song_model.initialize_data()
        self.simulation_song_view.set_model(self.simulation_song_model)
        self.simulation_song_layout.addWidget(self.simulation_song_view.widget)
        self.simulation_songsearch_view = SongQuickSearchView(self.central_widget)
        self.simulation_songsearch_model = SongQuickSearchModel(self.simulation_songsearch_view, self.simulation_song_view)
        self.simulation_songsearch_view.set_model(self.simulation_songsearch_model)
        self.simulation_song_layout.addWidget(self.simulation_songsearch_view.widget)
        self.simulation_bottom_layout.addLayout(self.simulation_song_layout, 7)
        self.simulation_layout.addLayout(self.simulation_bottom_layout, 1, 0, 1, 1)
        
        self.simulation_chart_viewer = ChartViewer(self.main)
        self.simulation_layout.addWidget(self.simulation_chart_viewer.widget, 0, 1, 2, 1)
        
        self.simulator.addTab(self.simulation_widget, "Simulation")
        self.simulator_layout.addWidget(self.simulator)
        self.main_layout.addLayout(self.simulator_layout)
        self.grid_layout.addLayout(self.main_layout, 0, 0, 1, 1)

    def import_from_id(self, game_id):
        self.card_view.disconnect_cell_change()
        updated_card_ids = profile_manager.import_from_gameid(game_id)
        if updated_card_ids is None:
            self.card_view.connect_cell_change()
            return
        indexer.im.initialize_index_db(updated_card_ids)
        indexer.im.reindex(updated_card_ids)
        search_engine.engine.refresh_searcher()
        self.card_model.initialize_cards(updated_card_ids)
        self.card_view.connect_cell_change()

    def retranslate_ui(self, MainWindow):
        _translate = QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("main", "Chihiro"))

    def disable_auto_resize(self):
        self.card_view.toggle_auto_resize(False)


def cleanup():
    logger.info("Waiting for all threads to finish...")
    kill_tip_refresher_service()


def setup_gui(*args):
    app = QApplication(*args)
    app.setApplicationName("Chihiro")
    icon = QIcon(str(ROOT_DIR / 'icon.png'))
    app.setWindowIcon(icon)
    app.lastWindowClosed.connect(lambda: cleanup())
    MainWindow = CustomMainWindow(app)
    ui = UiMainWindow(MainWindow)
    MainWindow.setui(ui)
    ui.setup_ui()
    logger.info("GUI setup successfully")
    return app, MainWindow
