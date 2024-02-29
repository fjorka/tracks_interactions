from qtpy.QtWidgets import (
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from tracks_interactions.graph.signal_graph import SignalGraph


class AddListGraphWidget(QWidget):
    def __init__(self, napari_viewer, sql_session, signal_list=None):
        super().__init__()

        self.setLayout(QVBoxLayout())

        self.viewer = napari_viewer
        self.session = sql_session
        self.signal_list = signal_list

        add_list_graph_btn = QPushButton("+")
        add_list_graph_btn.clicked.connect(self.add_graph_with_list)
        self.layout().addWidget(add_list_graph_btn)

    def add_graph_with_list(self):
        """
        Add a signal graph with a list of signals.
        """
        if self.signal_list is None:
            self.viewer.status = "No signal list provided."
        else:
            list_graph_widget = ListGraphWidget(
                self.viewer, self.session, signal_list=self.signal_list
            )
            self.viewer.window.add_dock_widget(list_graph_widget, area="right")


class ListGraphWidget(QWidget):
    def __init__(self, napari_viewer, sql_session, signal_list=None):
        super().__init__()

        self.setLayout(QVBoxLayout())

        self.viewer = napari_viewer
        self.session = sql_session
        self.signal_list = signal_list

        self.list_widget = self.add_signal_list()

        self.graph = self.add_signal_graph()

    def add_signal_list(self):
        """
        Add a list of signals to be displayed.
        """
        list_widget = QListWidget()
        # Set selection mode to allow multiple items to be selected
        list_widget.setSelectionMode(QListWidget.MultiSelection)

        # Add items to the list
        for sig in self.signal_list:  # Example items
            list_widget.addItem(sig)

        list_widget.selectionModel().selectionChanged.connect(
            self.onSelectionChanged
        )

        list_widget.setFixedHeight(20)
        self.layout().addWidget(list_widget)

        return list_widget

    def onSelectionChanged(self, selected, deselected):
        """
        Event handler for the selectionChanged signal.
        """
        # get what is selected and change the graph
        self.graph.signal_list = [
            item.text() for item in self.list_widget.selectedItems()
        ]
        self.graph.update_signal_display()

    def add_signal_graph(self):
        """
        Add a signal graph
        """
        graph_widget = SignalGraph(self.viewer, self.session)
        self.layout().addWidget(graph_widget)

        return graph_widget
