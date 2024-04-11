from qtpy.QtWidgets import (
    QColorDialog,
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

        add_list_graph_btn = QPushButton('+')
        add_list_graph_btn.clicked.connect(self.add_graph_with_list)
        self.layout().addWidget(add_list_graph_btn)

    def add_graph_with_list(self):
        """
        Add a signal graph with a list of signals.
        """
        if self.signal_list is None:
            self.viewer.status = 'No signal list provided.'
        else:
            list_graph_widget = CellGraphWidget(
                self.viewer, self.session, signal_list=self.signal_list
            )
            self.viewer.window.add_dock_widget(list_graph_widget, area='right')


class CellGraphWidget(QWidget):
    def __init__(
        self,
        napari_viewer,
        sql_session,
        signal_list,
        signal_sel_list=None,
        color_sel_list=None,
        tag_dictionary=None,
    ):
        super().__init__()

        if tag_dictionary is None:
            tag_dictionary = {}

        self.setLayout(QVBoxLayout())

        self.viewer = napari_viewer
        self.labels = self.viewer.layers['Labels']
        self.session = sql_session
        self.signal_list = [None] + signal_list
        self.signal_sel_list = signal_sel_list
        self.color_sel_list = color_sel_list
        self.tag_dictionary = tag_dictionary
        self.btn_offset = 1

        # account for incorrect signal and color list
        if self.signal_sel_list is not None and (
            len(self.signal_sel_list) != len(self.color_sel_list)
        ):
            self.viewer.status = (
                'Signal list and color list have different lengths.'
            )
            self.signal_sel_list = None
            self.color_sel_list = None

        # add graph
        self.graph = self.add_signal_graph()

        # add matching buttons
        if (self.signal_sel_list is None) or (len(self.signal_sel_list) == 0):
            self.addRowButton()
        else:
            for ind in range(len(self.signal_sel_list)):
                self.addRowButton(
                    button=None,
                    signal=self.signal_sel_list[ind],
                    color=self.color_sel_list[ind],
                )

            # trigger graph update
            self.graph.update_graph_all()

    def addRowButton(self, button=None, signal=None, color=None):

        # Create a new row
        rowLayout = QHBoxLayout()

        comboBox = self.createSignalComboBox(signal)
        colorButton = self.createColorButton(color)

        add_button = QPushButton('+')
        add_button.setMaximumWidth(30)
        add_button.clicked.connect(
            lambda: self.handleAddButtonClick(add_button)
        )

        min_button = QPushButton('-')
        min_button.setMaximumWidth(30)
        min_button.clicked.connect(
            lambda: self.handleMinButtonClick(min_button)
        )

        rowLayout.addWidget(comboBox)
        rowLayout.addWidget(colorButton)
        rowLayout.addWidget(add_button)
        rowLayout.addWidget(min_button)

        # when it's added by click on the button
        if button is not None:

            for i in range(1, self.layout().count()):
                layout = self.layout().itemAt(i)
                if layout.layout().indexOf(button) != -1:

                    self.layout().insertLayout(i + 1, rowLayout)
        else:
            self.layout().addLayout(rowLayout)

        # in case we just added the second signal
        if self.layout().count() == 3:
            last_row = self.layout().itemAt(1)
            last_row.itemAt(3).widget().setEnabled(True)

    def createSignalComboBox(self, signal=None):
        comboBox = QComboBox()
        for sig in self.signal_list:
            comboBox.addItem(sig)

        if signal is not None:
            comboBox.setCurrentText(signal)

        comboBox.activated[str].connect(self.onSelection)

        return comboBox

    def createColorButton(self, color=None):
        colorButton = QPushButton()
        colorButton.setMaximumWidth(30)  # Keep the button small
        if color:
            colorButton.setStyleSheet(f'background-color: {color}')
        else:
            colorButton.setStyleSheet('background-color: white')
        colorButton.clicked.connect(lambda: self.selectColor(colorButton))

        return colorButton

    def selectColor(self, button):
        # Open a color dialog and set the selected color as the button's background
        color = QColorDialog.getColor()
        if color.isValid():
            button.setStyleSheet(f'background-color: {color.name()}')
            self.onSelection()

    def onSelection(self):
        # update list of signals and colors
        signal_sel_list = []
        color_sel_list = []

        # get info about selected signals
        for i in range(self.btn_offset, self.layout().count()):
            self.viewer.status = 'Selection changed'
            signal = self.layout().itemAt(i).itemAt(0).widget().currentText()
            signal_sel_list.append(signal)
            color = (
                self.layout()
                .itemAt(i)
                .itemAt(1)
                .widget()
                .palette()
                .button()
                .color()
                .name()
            )
            color_sel_list.append(color)
        self.viewer.status = 'Selection changed'
        self.graph.signal_list = signal_sel_list
        self.graph.color_list = color_sel_list

        self.viewer.status = f'Selected signals: {signal_sel_list} with colors: {color_sel_list}'

        # update graph
        self.graph.update_graph_all()

    def handleAddButtonClick(self, button):

        self.addRowButton(button)

    def handleMinButtonClick(self, button):

        self.removeRowButton(button)

    def removeRowButton(self, button):
        # Find the layout that contains the button and remove it
        for i in range(1, self.layout().count()):
            layout = self.layout().itemAt(i)
            # Check if this is the layout to be removed
            if layout.layout().indexOf(button) != -1:
                self.clearLayout(layout.layout())
                self.layout().removeItem(layout)
                break

        # if only one row left
        if self.layout().count() == 2:
            last_row = self.layout().itemAt(1)
            last_row.itemAt(3).widget().setEnabled(False)

        # update what is displayed
        self.onSelection()

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
            tag_dictionary=self.tag_dictionary,
        )

        self.layout().addWidget(graph_widget)

        return graph_widget
