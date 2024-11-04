import dask.array as da
import numpy as np
import yaml
import zarr
from qtpy import QtWidgets
from qtpy.QtCore import Qt
from qtpy.QtGui import QPixmap
from qtpy.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import napari
import tracks_interactions.db.db_functions as fdb
from tracks_interactions.widget.signal_graph_widget import CellGraphWidget
from tracks_interactions.db.config_functions import testConfigFile

class SettingsWidget(QWidget):
    def __init__(
        self, viewer, create_widgets_callback=None, clear_widgets_callback=None
    ):

        super().__init__()

        self.viewer = viewer
        self.create_widgets_callback = create_widgets_callback
        self.clear_widgets_callback = clear_widgets_callback
        self.added_widgets = []

        self.setStyleSheet(napari.qt.get_stylesheet(theme_id='dark'))

        self.mWidget = self.mainWidget()
        self.mWidget.layout().setAlignment(Qt.AlignTop)

        self.setLayout(QVBoxLayout())
        self.layout().setAlignment(Qt.AlignTop)
        self.layout().addWidget(self.mWidget)

    def mainWidget(self):
        """
        widget of a widget
        """

        widget = QWidget()
        widget.setLayout(QGridLayout())
        widget.layout().setAlignment(Qt.AlignTop)

        self.logo_widget = self.createLogoWidget()

        btn_load = QtWidgets.QPushButton('Load Tracking')
        btn_load.clicked.connect(self.openFileDialog)

        widget.layout().addWidget(self.logo_widget, 0, 0)
        widget.layout().addWidget(btn_load, 1, 0)

        self.widget_line = 2

        return widget

    def createLogoWidget(self):
        """
        Creates a logo widget
        """

        # get logo image
        logo_path = r'../tracks_interactions/icons/track_gardener_logo.png'
        logo = QPixmap(logo_path)

        logo_label = QLabel()
        logo_label.setPixmap(logo)
        logo_label.setMaximumHeight(300)
        logo_label.setMaximumWidth(300)
        logo_label.setScaledContents(True)

        sp1 = QWidget()
        sp1.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        sp2 = QWidget()
        sp2.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        widget = QWidget()
        widget.setLayout(QHBoxLayout())
        widget.layout().setAlignment(Qt.AlignTop)
        widget.layout().addWidget(sp1)
        widget.layout().addWidget(logo_label)
        widget.layout().addWidget(sp2)

        return widget

    def openFileDialog(self):
        options = QtWidgets.QFileDialog.Options()
        fileName, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            'QFileDialog.getOpenFileName()',
            '',
            'YAML Files (*.yaml);;All Files (*)',
            options=options,
        )
        if fileName:

            # test if the config file is correct
            self.viewer.status = 'Checking the config file...'
            status, msg = testConfigFile(fileName)

            if status:
                # display a message
                self.viewer.status = 'Config file is correct.'
                
                # load config content
                self.loadConfigFile(fileName)
                
                self.reorganizeWidgets()
            else:
                # display a window with the error message
                msgBox = QtWidgets.QMessageBox(self.viewer.window._qt_window)
                msgBox.setText(msg)
                msgBox.exec()


    def reorganizeWidgets(self):
        """
        reorganize widgets
        """

        # remove all previous widgets
        for widget in self.added_widgets:
            widget.hide()
            self.mWidget.layout().removeWidget(widget)
        self.added_widgets = []

        if self.clear_widgets_callback is not None:
            self.clear_widgets_callback()

        self.loadExperiment()
        self.loadTracking()

        # display load experiment button
        # pb = QPushButton('Save Settings')
        # pb.clicked.connect(self.loadExperiment)
        # self.mWidget.layout().addWidget(pb, self.widget_line, 0)
        # self.added_widgets.append(pb)
        # self.widget_line += 1

        # display load widgets button
        pb = QPushButton('Add graph')
        pb.clicked.connect(self.add_new_graph_widget)
        self.added_widgets.append(pb)
        self.mWidget.layout().addWidget(pb, self.widget_line, 0)
        self.widget_line += 1

    def loadConfigFile(self, filePath):
        """
        Put the content of the yaml file into internal variables.
        """

        with open(filePath) as file:
            config = yaml.safe_load(file)

            exp_settings = config.get('experiment_settings', {})
            self.experiment_name = exp_settings.get(
                'experiment_name', 'Unnamed'
            )
            self.experiment_description = exp_settings.get(
                'experiment_description', ''
            )
            self.database_path = config.get('database', {}).get('path', '')
            self.channels_list = config.get('signal_channels', [])
            self.labels_settings = config.get('labels_settings', {})
            self.graphs_list = config.get('graphs', [])
            self.cell_tags = config.get('cell_tags', [])

    def load_zarr(self, channel_path):
        """
        Function to load data from zarr.
        """

        # try loading if it's a single level
        try:
            data = [da.from_zarr(channel_path)]

        except zarr.errors.ContainsGroupError:

            # check number of levels
            root_group = zarr.open_group(channel_path, mode='r')
            levels_list = [key for key in root_group if key.isdigit()]
            data = []
            for level in levels_list:
                data.append(da.from_zarr(channel_path, level))

        return data

    def loadExperiment(self):
        """
        loads napari layers
        """

        # remove all previous layers

        layers_list = [x.name for x in self.viewer.layers]

        for layer in layers_list:
            self.viewer.layers.remove(layer)

        ############################################################################################
        ############################################################################################
        # populate the viewer

        # load images
        self.channels_data_list = []
        for ch in self.channels_list:
            channel_name = ch.get('name', 'Unnamed')
            channel_path = ch.get('path', '')
            if '.zarr' not in channel_path:
                self.viewer.status = 'Only zarr files are supported'
                return
            channel_lut = ch.get('lut', 'green')
            channel_contrast_limits = ch.get('contrast_limits', [0, 4095])

            # get data from zarr
            # a list of arrays
            # multiple arrays if multiscale
            data = self.load_zarr(channel_path)

            # necessary to send to the modification widget
            # to recalculate signals when object changes
            self.channels_data_list.append(data[0])

            # because napari cannot accept a single array within a list
            data_viewer = data[0] if len(data) == 1 else data

            self.viewer.add_image(
                data_viewer,
                name=channel_name,
                colormap=channel_lut,
                blending='additive',
                contrast_limits=channel_contrast_limits,
            )

        # add labels to the viewer
        empty_labels = np.zeros([data[0].shape[1], data[0].shape[2]]).astype(
            int
        )
        labels_layer = self.viewer.add_labels(
            empty_labels, name='Labels', metadata={'persistent_label': -1}
        )

        # set labels settings
        labels_layer.selected_label = 0
        labels_layer.brush_size = self.labels_settings.get('brush_size', 10)

        # set viewer status
        self.viewer.status = 'Experiment loaded'

    def loadTracking(self):
        """
        load the widgets
        """

        # establish connection to the database
        engine = create_engine(f'sqlite:///{self.database_path}')
        self.session = sessionmaker(bind=engine)()

        # get a list of signals
        self.signal_list = fdb.get_signals(self.session)

        # Trigger populating of tab2 in the main widget with tracking widgets
        ch_names = [ch.get('name', 'Unnamed') for ch in self.channels_list]
        if self.create_widgets_callback is not None:
            self.create_widgets_callback(
                self.viewer,
                self.session,
                self.channels_data_list,
                ch_names,
                5,
                self.signal_list,
                self.graphs_list,
                self.cell_tags,
            )

        self.viewer.status = 'Tracking loaded'

    def add_new_graph_widget(self):

        graph_widget = CellGraphWidget(
            self.viewer,
            self.session,
            self.signal_list,
            tag_dictionary=self.cell_tags,
        )

        self.viewer.window.add_dock_widget(
            graph_widget, area='bottom', name='New Graph'
        )
        self.napari_widgets.append(graph_widget)
