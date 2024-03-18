import numpy as np
from qtpy.QtGui import QColor
from qtpy.QtWidgets import (
    QComboBox,
    QHBoxLayout,
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
    def __init__(
        self,
        napari_viewer,
        sql_session,
        signal_list,
        signal_sel_list=None,
        color_sel_list=None,
    ):
        super().__init__()

        self.setLayout(QVBoxLayout())

        self.viewer = napari_viewer
        self.session = sql_session
        self.signal_list = signal_list
        self.signal_sel_list = signal_sel_list
        self.color_sel_list = color_sel_list

        # account for incorrect signal and color list
        if self.signal_sel_list is not None and (
            len(self.signal_sel_list) != len(self.color_sel_list)
        ):
            self.viewer.status = (
                "Signal list and color list have different lengths."
            )
            self.signal_sel_list = None
            self.color_sel_list = None

        # add graph
        self.graph = self.add_signal_graph()

        # add matching
        if self.signal_sel_list is None:
            self.addRowButton()
        else:
            for ind in range(len(self.signal_sel_list)):
                status = "-" if (ind < len(self.signal_sel_list) - 1) else "+"
                self.addRowButton(
                    status, self.signal_sel_list[ind], self.color_sel_list[ind]
                )

            self.graph.update_signal_display()

    def addRowButton(self, status="+", signal=None, color=None):
        # Create a new row
        rowLayout = QHBoxLayout()

        comboBox = self.createSignalComboBox(signal)

        button = QPushButton(status)
        button.clicked.connect(lambda: self.handleButtonClick(button))

        rowLayout.addWidget(comboBox)
        rowLayout.addWidget(button)

        self.layout().addLayout(rowLayout)

    def createSignalComboBox(self, signal=None):
        comboBox = QComboBox()
        for sig in self.signal_list:
            comboBox.addItem(sig)

        if signal is not None:
            comboBox.setCurrentText(signal)

        comboBox.activated[str].connect(self.onSelection)

        return comboBox

    def onSelection(self):
        # update list of signals and colors
        signal_sel_list = []
        for i in range(1, self.layout().count()):
            signal = self.layout().itemAt(i).itemAt(0).widget().currentText()
            signal_sel_list.append(signal)
        self.graph.signal_list = signal_sel_list
        self.graph.color_list = generate_n_qcolors(len(signal_sel_list))
        # update graph
        self.graph.update_signal_display()

    def handleButtonClick(self, button):
        if button.text() == "+":
            self.addRowButton()
            button.setText("-")
        else:  # The button is a '-' button
            self.removeRowButton(button)

        self.onSelection()

    def removeRowButton(self, button):
        # Find the layout that contains the button and remove it
        for i in range(1, self.layout().count()):
            layout = self.layout().itemAt(i)
            # Check if this is the layout to be removed
            if layout.layout().indexOf(button) != -1:
                self.clearLayout(layout.layout())
                self.layout().removeItem(layout)
                break

    def clearLayout(self, layout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

    def add_signal_graph(self):
        """
        Add a signal graph
        """
        graph_widget = SignalGraph(
            self.viewer,
            self.session,
            legend_on=False,
            selected_signals=self.signal_sel_list,
            color_list=self.color_sel_list,
        )
        self.layout().addWidget(graph_widget)

        return graph_widget


def generate_n_qcolors(n):
    colors = []
    for i in np.linspace(0, 1, n, endpoint=False):
        hue = int(i * 360)
        color = QColor.fromHsv(hue, 255, 255)
        colors.append(color)
    return colors
