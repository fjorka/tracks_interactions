import dask.array as da
import numpy as np
import yaml
from qtpy import QtWidgets
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QGridLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import napari


class SettingsWidget(QWidget):
    def __init__(self, viewer, create_widgets_callback=None):

        super().__init__()

        self.viewer = viewer
        self.create_widgets_callback = create_widgets_callback

        self.setStyleSheet(napari.qt.get_stylesheet(theme_id='dark'))

        self.mWidget = self.mainWidget()
        self.mWidget.layout().setAlignment(Qt.AlignTop)

        self.added_widgets = []

        self.setLayout(QVBoxLayout())
        self.layout().setAlignment(Qt.AlignTop)
        self.layout().addWidget(self.mWidget)

    def mainWidget(self):
        """
        widget of a widget
        """

        widget = QWidget()
        widget.setLayout(QGridLayout())

        btn_load = QtWidgets.QPushButton('Open Config File')
        btn_load.clicked.connect(self.openFileDialog)

        widget.layout().addWidget(btn_load, 0, 0)

        self.widget_line = 1

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

            # load config content
            self.loadConfigFile(fileName)

            # remove all previous widgets
            for widget in self.added_widgets:
                widget.hide()
                self.mWidget.layout().removeWidget(widget)
            self.added_widgets = []

            # config_group = QGroupBox()
            # config_group.setLayout(QGridLayout())
            # self.added_widgets.append(config_group)
            # self.mWidget.layout().addWidget(config_group, self.widget_line, 0)
            # self.widget_line += 1

            # # display info of the config file itself
            # l = QLabel("Config File Path:")
            # config_group.layout().addWidget(l, 0, 0)

            # l = QLabel(fileName)
            # config_group.layout().addWidget(l, 1, 0)

            # # horizontal line
            # space = QWidget()
            # space.setFixedHeight(4)
            # self.mWidget.layout().addWidget(space, self.widget_line, 0)
            # self.added_widgets.append(space)
            # self.widget_line += 1

            # display unmutable config content
            # self.displayUnmutableConfig()

            # display load experiment button
            pb = QPushButton('Load Data')
            pb.clicked.connect(self.loadExperiment)
            self.mWidget.layout().addWidget(pb, self.widget_line, 0)
            self.added_widgets.append(pb)
            self.widget_line += 1

            # display mutable config content
            # self.displayMutableConfig()

            # display load widgets button
            pb = QPushButton('Load Tracking')
            pb.clicked.connect(self.loadTracking)
            self.added_widgets.append(pb)
            self.mWidget.layout().addWidget(pb, self.widget_line, 0)
            self.widget_line += 1

    def loadConfigFile(self, filePath):

        with open(filePath) as file:
            config = yaml.safe_load(file)

            self.database_path = config.get('database', {}).get('path', '')
            self.channels_list = config.get('signal_channels', [])
            self.graphs_list = config.get('graphs', [])
            self.cell_tags = config.get('cell_tags', [])

    def displayUnmutableConfig(self):
        """
        display the unmutable config
        """

        # # add database as a group
        # db_group = QGroupBox()
        # db_group.setLayout(QGridLayout())
        # self.added_widgets.append(db_group)
        # self.mWidget.layout().addWidget(db_group, self.widget_line, 0)
        # self.widget_line += 1

        # l = QLabel('Database Path: ')
        # l.setWordWrap(True)
        # db_group.layout().addWidget(l, 0, 0)

        # l = QLabel(self.database_path)
        # db_group.layout().addWidget(l, 1, 0)

        # # add channels as a group
        # channels_group = QGroupBox()
        # channels_group.setLayout(QGridLayout())
        # self.added_widgets.append(channels_group)
        # self.mWidget.layout().addWidget(channels_group, self.widget_line, 0)
        # self.widget_line += 1

        # ind = 0
        # for ch in self.channels_list:
        #     channel_name = ch.get('name', 'Unnamed')
        #     channel_path = ch.get('path', '')

        #     l = QLabel(f'Channel {channel_name}: ')
        #     channels_group.layout().addWidget(l, ind, 0)
        #     ind += 1

        #     l = QLabel(channel_path)
        #     channels_group.layout().addWidget(l, ind, 0)
        #     ind += 1

    def displayMutableConfig(self):
        """
        display the mutable config
        """

        # # add graphs as a group
        # graphs_group = QGroupBox()
        # graphs_group.setLayout(QGridLayout())
        # self.added_widgets.append(graphs_group)
        # self.mWidget.layout().addWidget(graphs_group, self.widget_line, 0)
        # self.widget_line += 1

        # ind = 0
        # for gr in self.graphs_list:
        #     graph_name = gr.get('name', 'Unnamed')
        #     graph_signals = gr.get('signals', [])

        #     l = QLabel(f'Graph {graph_name}: ')
        #     graphs_group.layout().addWidget(l, ind, 0)
        #     ind += 1

        #     for signal in graph_signals:

        #         l = QLabel(signal)
        #         graphs_group.layout().addWidget(l, ind, 0)
        #         ind += 1

    def loadExperiment(self):
        """
        load the experiment
        """

        # remove all previous layers
        for layer in self.viewer.layers.copy():
            self.viewer.layers.remove(layer.name)

        ############################################################################################
        ############################################################################################
        # populate the viewer

        # load images
        self.channels_data_list = []
        for ch in self.channels_list:
            channel_name = ch.get('name', 'Unnamed')
            channel_path = ch.get('path', '')
            channel_lut = ch.get('lut', 'green')

            ch_list = []
            for level in range(1, 5):
                ch_list.append(da.from_zarr(channel_path, level))

            self.viewer.add_image(
                ch_list,
                name=channel_name,
                colormap=channel_lut,
                blending='additive',
                contrast_limits=[0, 2048],
            )
            self.channels_data_list.append(ch_list)

        # create empty labels and add to the viewer
        empty_labels = np.zeros(
            [ch_list[0].shape[1], ch_list[0].shape[2]]
        ).astype(int)
        self.viewer.add_labels(
            empty_labels, name='Labels', metadata={'persistent_label': -1}
        )

        self.viewer.status = 'Experiment loaded'

    def loadTracking(self):
        """
        load the widgets
        """

        # establish connection to the database
        engine = create_engine(f'sqlite:///{self.database_path}')
        self.session = sessionmaker(bind=engine)()

        # Trigger populating of tab2 in the main widget with tracking widgets
        ch_names = [ch.get('name', 'Unnamed') for ch in self.channels_list]
        if self.create_widgets_callback is not None:
            self.create_widgets_callback(
                self.viewer,
                self.session,
                self.channels_data_list,
                ch_names,
                5,
                self.graphs_list,
                self.cell_tags,
            )

        self.viewer.status = 'Tracking loaded'
