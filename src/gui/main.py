from __future__ import annotations

from PyQt5.QtCore import QMetaObject, QCoreApplication, Qt
from PyQt5.QtGui import QIcon, QIntValidator, QFontMetrics
from PyQt5.QtWidgets import QWidget, QGridLayout, QVBoxLayout, QHBoxLayout, QTabWidget, QPushButton, QApplication, \
    QMainWindow, QLineEdit, QSizePolicy, QComboBox, QLabel

import customlogger as logger
from chihiro import ROOT_DIR
from gui.events.calculator_view_events import ToggleUnitLockingOptionsVisibilityEvent
from gui.events.service.tips_refresher_service import kill_tip_refresher_service
from gui.events.state_change_events import ShutdownTriggeredEvent, BackupFlagsEvent
from gui.events.utils import eventbus
from gui.viewmodels.card import CardView, CardModel, CardSmallView, CardSmallModel, IconLoaderView, IconLoaderModel
from gui.viewmodels.chart_viewer import ChartViewer
from gui.viewmodels.custom_card import CustomView, CustomModel
from gui.viewmodels.potential import PotentialView, PotentialModel
from gui.viewmodels.quicksearch import QuickSearchView, QuickSearchModel, SongQuickSearchView, SongQuickSearchModel
from gui.viewmodels.simulator.wide_smart import MainView, MainModel
from gui.viewmodels.song import SongView, SongModel
from gui.viewmodels.tips_view import TipView
from gui.viewmodels.unit import UnitView, UnitModel
from logic.profile import profile_manager, unit_storage
from logic.search import indexer, search_engine
from settings import UPDATE_DATE


class CustomMainWindow(QMainWindow):
    ui: UiMainWindow

    def __init__(self, app: QApplication, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.app = app

    def setui(self, ui):
        self.ui = ui

    def keyPressEvent(self, event):
        key = event.key()
        if QApplication.keyboardModifiers() == Qt.ControlModifier and key == Qt.Key_F:
            if self.ui.main_widget.currentIndex() == 0:
                self.ui.quicksearch_view.focus()
            elif self.ui.main_widget.currentIndex() == 1:
                self.ui.quicksearch_small_view.focus()
        if QApplication.keyboardModifiers() == (Qt.ShiftModifier | Qt.ControlModifier) and key == Qt.Key_F:
            self.ui.songsearch_view.focus()
        if QApplication.keyboardModifiers() == (Qt.ShiftModifier | Qt.ControlModifier) and key == Qt.Key_H:
            eventbus.eventbus.post(ToggleUnitLockingOptionsVisibilityEvent())
        if QApplication.keyboardModifiers() == Qt.ControlModifier and key == Qt.Key_S:
            logger.info("User data backed up")
            eventbus.eventbus.post(ShutdownTriggeredEvent())
            eventbus.eventbus.post(BackupFlagsEvent())
            for r_idx in range(self.ui.unit_storage_view.widget.count()):
                widget = self.ui.unit_storage_view.widget.itemWidget(self.ui.unit_storage_view.widget.item(r_idx))
                if widget is not None:
                    widget.update_unit()
            profile_manager.cleanup()

    def closeEvent(self, event):
        eventbus.eventbus.post(ShutdownTriggeredEvent())
        eventbus.eventbus.post(BackupFlagsEvent())
        event.accept()


# noinspection PyAttributeOutsideInit
class UiMainWindow:
    main: CustomMainWindow

    def __init__(self, main: CustomMainWindow):
        self.main = main

    def setup_ui(self):
        logger.info("Initializing UI")
        self.main.resize(1920, 1005)
        qr = self.main.frameGeometry()
        cp = self.main.app.primaryScreen().availableGeometry().topLeft()
        qr.moveTopLeft(cp)
        self.main.move(qr.topLeft())
        self.setup_base()
        self.setup_unit_layout()
        self.setup_simulator_layout()
        self.calculator_view.setUserID(self.import_text)
        self.setup_tip_view()
        self.main.setCentralWidget(self.central_widget)
        self.retranslate_ui(self.main)
        QMetaObject.connectSlotsByName(self.main)

    def setup_base(self):
        logger.info("Setting up UI base")

        self.central_widget = QWidget(self.main)
        self.central_layout = QVBoxLayout(self.central_widget)
        margin = self.central_layout.contentsMargins()
        self.central_layout.setContentsMargins(margin.left(), margin.top(), margin.right(), margin.bottom() - 2)

        self.main_widget = QTabWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.main_widget)
        self.central_layout.addWidget(self.main_widget)

    def setup_unit_layout(self):
        logger.info("Setting up Unit Tab")

        self.unit_widget = QWidget()
        self.unit_layout = QGridLayout(self.unit_widget)
        self.main_widget.addTab(self.unit_widget, "Unit")

        self.unit_storage_layout = QVBoxLayout()
        self.unit_layout.addLayout(self.unit_storage_layout, 0, 0)
        self.unit_layout.setColumnStretch(0, 6)

        self.unit_storage_view = UnitView(self.central_widget, 1)
        self.unit_storage_model = UnitModel(self.unit_storage_view)
        self.unit_storage_view.set_model(self.unit_storage_model)
        self.unit_storage_layout.addWidget(self.unit_storage_view.widget)

        self.unit_add_button = QPushButton()
        self.unit_add_button.setText("Add unit")
        self.unit_add_button.setToolTip(
            "Add an untitled unit. Untitled units are not saved upon exit!\n"
            "Make sure to give your units a name. Unit names must be different.\n"
            "First/Red card is the leader, last/blue card is the guest.")
        self.unit_add_button.clicked.connect(lambda: self.unit_storage_view.add_empty_widget())
        self.unit_storage_layout.addWidget(self.unit_add_button)

        self.custom_view = CustomView()
        self.custom_model = CustomModel(self.custom_view)
        self.custom_view.set_model(self.custom_model)
        self.unit_layout.addWidget(self.custom_view.widget, 0, 1)
        self.unit_layout.setColumnStretch(1, 9)

        self.card_layout = QVBoxLayout()
        self.unit_layout.addLayout(self.card_layout, 1, 0, 1, 2)

        self.card_view = CardView(self.central_widget)
        self.card_model = CardModel(self.card_view, 1)
        self.card_view.set_model(self.card_model)
        self.card_model.initialize_cards(potential=False)
        self.card_view.initialize_pics()
        self.card_view.connect_cell_change()
        self.card_layout.addWidget(self.card_view.widget)

        self.card_bottom_layout = QHBoxLayout()
        self.card_layout.addLayout(self.card_bottom_layout)
        self.card_layout.setStretch(1, 1)

        self.quicksearch_layout = QHBoxLayout()
        self.card_bottom_layout.addLayout(self.quicksearch_layout)

        self.quicksearch_view = QuickSearchView(self.central_widget)
        self.quicksearch_model = QuickSearchModel(self.quicksearch_view, self.card_view)
        self.quicksearch_view.set_model(self.quicksearch_model)
        self.quicksearch_view.set_model_id(1)
        self.quicksearch_layout.addWidget(self.quicksearch_view.widget)
        self.quicksearch_model.add_options(self.quicksearch_layout, self.central_widget)

        self.icon_loader_view = IconLoaderView(self.central_widget)
        self.icon_loader_model = IconLoaderModel(self.icon_loader_view, self.card_model)
        self.icon_loader_view.set_model(self.icon_loader_model)
        self.icon_loader_view.widget.setToolTip("Larger icons require more RAM to run.")
        self.icon_loader_model.load_image(0)
        self.card_bottom_layout.addWidget(self.icon_loader_view.widget)

        self.import_layout = QHBoxLayout()
        self.card_bottom_layout.addLayout(self.import_layout)

        self.import_text = QLineEdit(self.main)
        self.import_text.setPlaceholderText("User ID")
        self.import_text.setValidator(QIntValidator(0, 999999999, None))  # Only number allowed
        self.import_text.setFixedWidth(QFontMetrics(self.import_text.font()).width("999999999") + 10)
        self.import_layout.addWidget(self.import_text)

        self.import_button = QPushButton("Import from ID", self.main)
        self.import_button.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.import_layout.addWidget(self.import_button)

        self.import_setting = QComboBox(self.main)
        for option in ["SSR+ only", "1SSR", "AllSR", "1SSR / AllSR", "AllSR↓", "1SSR / AllSR↓", "Clear"]:
            self.import_setting.addItem(option)
        self.import_setting.setToolTip(
            "SSR+ only : Sets owned value of SSR+ cards only.\n"
            "1SSR : If you have same n(>1) SSRs, set owned value of SSR to 1 and SSR+ to n-1.\n"
            "AllSR : Set owned value of all SR+ and SR cards to 1.\n"
            "AllSR↓ : Set owned value of all cards with the rarity lower than SR+ to 1.\n"
            "Clear : Set owned value of all cards to 0.")
        self.import_setting.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.import_layout.addWidget(self.import_setting)

        self.import_button.pressed.connect(lambda: self.import_from_id(self.import_text.text(),
                                                                       self.import_setting.currentIndex()))

        self.potential_view = PotentialView()
        self.potential_model = PotentialModel(self.potential_view)
        self.potential_view.set_model(self.potential_model)
        self.potential_model.initialize_data()
        self.unit_layout.addWidget(self.potential_view.widget, 0, 2, 2, 1)
        self.unit_layout.setColumnStretch(2, 5)

    def setup_simulator_layout(self):
        logger.info("Setting up Simulator Tab")

        self.simulation_widget = QWidget()
        self.simulation_layout = QGridLayout(self.simulation_widget)
        self.main_widget.addTab(self.simulation_widget, "Simulation")

        self.calculator_view = MainView()
        self.calculator_model = MainModel(self.calculator_view)
        self.calculator_view.set_model(self.calculator_model)
        self.calculator_view.setup()
        self.simulation_layout.addWidget(self.calculator_view.widget, 0, 0, 1, 1)

        self.simulation_setting_layout = QGridLayout()
        self.simulation_layout.addLayout(self.simulation_setting_layout, 1, 0, 1, 1)

        self.card_small_layout = QVBoxLayout()
        self.simulation_setting_layout.addLayout(self.card_small_layout, 0, 0)
        self.simulation_setting_layout.setColumnStretch(0, 13)

        self.card_small_view = CardSmallView(self.central_widget)
        self.card_small_model = CardSmallModel(self.card_small_view, 2)
        self.card_small_view.set_model(self.card_small_model)
        self.card_small_model.initialize_cards(potential=False)
        self.card_small_view.initialize_pics()
        self.card_small_view.connect_cell_change()
        self.card_small_layout.addWidget(self.card_small_view.widget)

        self.quicksearch_small_layout = QHBoxLayout()
        self.card_small_layout.addLayout(self.quicksearch_small_layout)

        self.quicksearch_small_view = QuickSearchView(self.central_widget)
        self.quicksearch_small_model = QuickSearchModel(self.quicksearch_small_view, self.card_small_view)
        self.quicksearch_small_view.set_model(self.quicksearch_small_model)
        self.quicksearch_small_view.set_model_id(2)
        self.quicksearch_small_layout.addWidget(self.quicksearch_small_view.widget)
        self.quicksearch_small_model.add_options(self.quicksearch_small_layout, self.central_widget)

        self.song_layout = QVBoxLayout()
        self.simulation_setting_layout.addLayout(self.song_layout, 1, 0, 1, 1)

        self.song_view = SongView(self.central_widget)
        self.song_model = SongModel(self.song_view)
        self.song_view.set_model(self.song_model)
        self.song_model.initialize_data()
        self.song_layout.addWidget(self.song_view.widget)

        self.songsearch_view = SongQuickSearchView(self.central_widget)
        self.songsearch_model = SongQuickSearchModel(self.songsearch_view, self.song_view)
        self.songsearch_view.set_model(self.songsearch_model)
        self.song_layout.addWidget(self.songsearch_view.widget)

        self.unit_storage_small_view = UnitView(self.central_widget, 2)
        self.unit_storage_small_model = UnitModel(self.unit_storage_small_view)
        self.unit_storage_small_view.set_model(self.unit_storage_small_model)
        self.unit_storage_small_model.initialize_units()
        self.simulation_setting_layout.addWidget(self.unit_storage_small_view.widget, 0, 1, 2, 1)

        self.chart_viewer = ChartViewer(self.main)
        self.simulation_layout.addWidget(self.chart_viewer.widget, 0, 1, 2, 1)
        self.simulation_setting_layout.setColumnStretch(1, 7)

    def setup_tip_view(self):
        self.tip_layout = QHBoxLayout()
        self.central_layout.addLayout(self.tip_layout)

        self.tip_layout.addSpacing(4)

        self.tip_view = TipView()
        self.tip_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.tip_layout.addWidget(self.tip_view)

        text = "Deresute-tools modified by @oayimikagakat with features added by @t-wy" + " " * 8
        self.credit_label = QLabel(text)
        self.credit_label.setAlignment(Qt.AlignRight)
        self.tip_layout.addWidget(self.credit_label)

        self.update_label = QLabel("Update Date : " + UPDATE_DATE.strftime('%m/%d/%Y') + " " * 2)
        self.update_label.setAlignment(Qt.AlignRight)
        self.tip_layout.addWidget(self.update_label)

    def import_from_id(self, game_id: str, option: int):
        self.card_view.disconnect_cell_change()
        updated_card_ids = profile_manager.import_from_gameid(game_id, option)
        if updated_card_ids is None:
            self.card_view.connect_cell_change()
            return
        indexer.im.initialize_index_db(updated_card_ids)
        indexer.im.reindex(updated_card_ids)
        search_engine.engine.refresh_searcher()
        self.card_model.initialize_cards(updated_card_ids)
        self.card_view.connect_cell_change()

    @staticmethod
    def retranslate_ui(main_window: CustomMainWindow):
        _translate = QCoreApplication.translate
        main_window.setWindowTitle(_translate("main", "Chihiro"))


def cleanup():
    logger.info("Waiting for all threads to finish...")
    kill_tip_refresher_service()


def setup_gui(*args):
    app = QApplication(*args)
    app.setApplicationName("Chihiro")
    icon = QIcon(str(ROOT_DIR / 'icon.png'))
    app.setWindowIcon(icon)
    app.lastWindowClosed.connect(lambda: cleanup())
    main_window = CustomMainWindow(app)
    ui = UiMainWindow(main_window)
    main_window.setui(ui)
    ui.setup_ui()
    logger.info("GUI setup successfully")
    return app, main_window
