from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QGridLayout,
    QTabWidget,
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

        self.napari_widgets = []
        self.navigation_widget = None
        self.modification_widget = None

        self.setStyleSheet(napari.qt.get_stylesheet(theme_id='dark'))
        self.setLayout(QGridLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)

        # QTabwidget
        self.tabwidget = QTabWidget()

        # 1st tab
        self.settings_window = SettingsWidget(
            viewer, self.create_widgets, self.clear_widgets
        )
        self.tabwidget.addTab(self.settings_window, 'settings')

        # 2nd tab (initially empty)
        self.tab2 = QWidget()
        self.tab2.setLayout(QGridLayout())
        self.tab2.layout().setAlignment(Qt.AlignTop)
        self.tab2.layout().setContentsMargins(0, 0, 0, 0)
        self.tab2.setMinimumWidth(500)
        self.tabwidget.addTab(self.tab2, 'interact')

        # add tab widget to the layout
        self.layout().addWidget(self.tabwidget, 0, 0)

    def clear_widgets(self):
        """
        Remove all widgets from the second tab.
        """

        # remove graph widgets
        if len(self.napari_widgets) > 0:
            for widget in self.napari_widgets:
                self.viewer.window.remove_dock_widget(widget)
            self.napari_widgets = []

            # disconnect labels connections
            self.viewer.camera.events.zoom.disconnect(
                self.navigation_widget.build_labels
            )
            self.viewer.camera.events.center.disconnect(
                self.navigation_widget.build_labels
            )
            self.viewer.layers['Labels'].events.visible.disconnect(
                self.navigation_widget.build_labels
            )

        # remove widgets from tab2
        if self.navigation_widget is not None:
            self.navigation_widget.setParent(None)
            self.navigation_widget.deleteLater()

        if self.modification_widget is not None:
            self.modification_widget.setParent(None)
            self.modification_widget.deleteLater()

    def create_widgets(
        self,
        viewer,
        session,
        ch_list,
        ch_names,
        signal_list,
        graph_list,
        cell_tags,
        signal_function,
    ):
        """
        Callback to create widgets in the second tab.
        """

        # remember general thing
        self.cell_tags = cell_tags

        # add lineage graph
        fam_plot_widget = FamilyGraphWidget(self.viewer, session)
        self.viewer.window.add_dock_widget(fam_plot_widget, area='bottom')
        self.napari_widgets.append(fam_plot_widget)

        # add navigation widget
        self.navigation_widget = TrackNavigationWidget(viewer, session)
        self.tab2.layout().addWidget(self.navigation_widget, 0, 0)

        # add modification widget
        self.modification_widget = ModificationWidget(
            viewer,
            session,
            ch_list=ch_list,
            ch_names=ch_names,
            tag_dictionary=cell_tags,
            signal_function=signal_function,
        )
        self.tab2.layout().addWidget(self.modification_widget, 1, 0)

        # add graph widgets

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
                graph_widget, area='bottom', name=graph_name
            )
            self.napari_widgets.append(graph_widget)

        # switch to the second tab
        self.tabwidget.setCurrentIndex(1)
