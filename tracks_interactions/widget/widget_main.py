from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QGridLayout,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import napari
from tracks_interactions.graph.family_graph import FamilyGraphWidget
from tracks_interactions.widget.signal_graph_widget import CellGraphWidget
from tracks_interactions.widget.widget_modifications import ModificationWidget
from tracks_interactions.widget.widget_navigation import TrackNavigationWidget
from tracks_interactions.widget.widget_settings import SettingsWidget


class TrackGardener(QWidget):

    def __init__(self, viewer: napari.Viewer = None):
        """
        Parameters
        ----------
        viewer : Viewer
            The Napari viewer instance
        """

        super().__init__()
        viewer = napari.current_viewer() if viewer is None else viewer
        self.viewer = viewer

        self.setStyleSheet(napari.qt.get_stylesheet(theme_id='dark'))
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)

        widget = QWidget()
        widget.setLayout(QGridLayout())
        widget.layout().setContentsMargins(0, 0, 0, 0)

        # QTabwidget
        self.tabwidget = QTabWidget()

        # 1st tab
        self.settings_window = SettingsWidget(viewer, self.create_widgets)
        self.tabwidget.addTab(self.settings_window, 'Settings')

        # 2nd tab (initially empty)
        self.tab2 = QWidget()
        self.tab2.setLayout(QGridLayout())
        self.tab2.layout().setAlignment(Qt.AlignTop)
        self.tab2.layout().setContentsMargins(0, 0, 0, 0)
        self.tabwidget.addTab(self.tab2, 'Curating')

        # add tab widget to the layout
        widget.layout().addWidget(self.tabwidget, 0, 0)

        # Scrollarea allows content to be larger than the assigned space (small monitor)
        scroll_area = QScrollArea()
        scroll_area.setWidget(widget)
        scroll_area.setWidgetResizable(True)

        self.layout().addWidget(scroll_area)

    def create_widgets(
        self,
        viewer,
        session,
        ch_list,
        ch_names,
        ring_width,
        graph_list,
        cell_tags,
    ):
        """
        Callback to create widgets in the second tab.
        """

        # add lineage graph
        fam_plot_widget = FamilyGraphWidget(self.viewer, session)
        self.viewer.window.add_dock_widget(fam_plot_widget, area='bottom')

        # add navigation widget
        self.navigation_widget = TrackNavigationWidget(viewer, session)
        self.tab2.layout().addWidget(self.navigation_widget, 0, 0)

        # add modification widget
        self.modification_widget = ModificationWidget(
            viewer,
            session,
            ch_list=ch_list,
            ch_names=ch_names,
            ring_width=ring_width,
        )
        self.tab2.layout().addWidget(self.modification_widget, 1, 0)

        # add graph widgets
        # get this from the database
        signal_list = ['area', 'ch0_nuc', 'ch0_cyto', 'ch1_nuc', 'ch1_cyto']

        for gr in graph_list:
            graph_name = gr.get('name', 'Unnamed')
            graph_signals = gr.get('signals', [])
            graph_colors = gr.get('colors', [])
            graph_widget = CellGraphWidget(
                viewer,
                session,
                signal_list,
                signal_sel_list=graph_signals,
                color_sel_list=graph_colors,
                tag_dictionary=cell_tags,
            )
            # self.tab2.layout().addWidget(graph_widget, ind, 0)
            # ind += 1
            self.viewer.window.add_dock_widget(
                graph_widget, area='right', name=graph_name
            )

        # switch to the second tab
        self.tabwidget.setCurrentIndex(1)
