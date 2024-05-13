import numpy as np
from pyqtgraph import GraphicsLayoutWidget, LegendItem, TextItem, mkPen
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QGraphicsPixmapItem, QDialog, QTextEdit, QVBoxLayout, QPushButton
from qtpy.QtGui import QPixmap

from tracks_interactions.db.db_model import CellDB


class SignalGraph(GraphicsLayoutWidget):
    def __init__(
        self,
        viewer,
        session,
        legend_on=True,
        selected_signals=None,
        color_list=None,
        tag_dictionary=None,
    ):
        super().__init__()

        self.setContextMenuPolicy(Qt.NoContextMenu)

        self.session = session
        self.viewer = viewer
        self.labels = self.viewer.layers['Labels']
        self.legend_on = legend_on
        self.signal_list = selected_signals
        self.color_list = color_list
        if tag_dictionary is None:
            self.tag_dictionary = {}
        else:
            self.tag_dictionary = tag_dictionary

        # initialize graph
        self.plot_view = self.addPlot(title='', labels={'bottom': 'Time'})

        self.t_max = self.viewer.dims.range[0][1]
        self.plot_view.setXRange(0, self.t_max)
        self.plot_view.setMouseEnabled(x=True, y=True)
        self.plot_view.setMenuEnabled(False)

        # Connect the plotItem's mouse click event
        self.plot_view.scene().sigMouseClicked.connect(self.onMouseClick)

        # add time line
        self.time_line = self.add_time_line()

        # connect time slider event
        self.viewer.dims.events.current_step.connect(self.update_time_line)

        # connect label selection event
        self.labels.events.selected_label.connect(self.update_graph_all)

    def add_time_line(self):
        """
        Add a line to the graph that follows the time slider.
        """
        pen = mkPen(color=(255, 255, 255), xwidth=1)
        init_position = self.viewer.dims.current_step[0]
        time_line = self.plot_view.addLine(x=init_position, pen=pen)

        return time_line

    def onMouseClick(self, event):
        """
        Mouse click event handler.
        Left - selection of a time point in the movie.
        """
        vb = self.plot_view.vb
        scene_coords = event.scenePos()

        if self.plot_view.sceneBoundingRect().contains(scene_coords):
            mouse_point = vb.mapSceneToView(scene_coords)
            x_val = mouse_point.x()

            # left click - moving in time
            if event.button() == Qt.LeftButton:
                # move in time
                self.viewer.dims.set_point(0, round(x_val))

    def update_time_line(self):
        """
        Update of the time line when slider position is moved.
        """
        # line_position = event.value # that emitts warning for reasons that I don't understand
        line_position = self.viewer.dims.current_step[0]
        self.time_line.setValue(line_position)

    def get_db_info(self):
        """
        Get information about the cell from the database.
        """
        # get a label or a persistent label
        if self.viewer.layers['Labels'].selected_label > 0:
            self.active_label = int(self.labels.selected_label)
        else:
            self.active_label = int(self.labels.metadata['persistent_label'])

        # get the info
        self.query = (
            self.session.query(CellDB.t, CellDB.signals, CellDB.tags)
            .filter(CellDB.track_id == self.active_label)
            .order_by(CellDB.t)
            .all()
        )

    def redraw_tags(self):
        """
        Function that updates taggs on the graph.
        """

        # remove previous tags
        items_to_remove = [
            x for x in self.plot_view.items if isinstance(x, TextItem)
        ]
        for item in items_to_remove:
            self.plot_view.removeItem(item)

        # reset view
        self.plot_view.enableAutoRange(
            self.plot_view.getViewBox().XYAxes, True
        )

        y_view_range = self.plot_view.viewRange()[1]
        y_range = y_view_range[1] - y_view_range[0]
        row_height = 0.1 * y_range

        # add tags
        if len(self.query) > 0:
            if len(self.tag_dictionary) > 0:
                sorted_tags = self.tag_dictionary.items()
                for index, (tag, tag_mark) in enumerate(sorted_tags):
                    x_list = [
                        item[0]
                        for item in self.query
                        if (
                            item[2].get(tag) == 'True'
                            or item[2].get(tag) is True
                        )
                    ]
                    if x_list:
                        y = y_view_range[1] + (index * row_height)
                        for x in x_list:
                            text = TextItem(text=tag_mark, anchor=(0.5, 0))
                            self.plot_view.addItem(text)
                            text.setPos(x, y)
            else:
                self.viewer.status = 'No tags to display.'

        else:
            self.viewer.status = 'Error - no such label in the database.'

    def redraw_signals(self):
        """
        Function that updates signals on the graph.
        """

        # remove previous signals
        items_to_remove = self.plot_view.items[1:]
        for item in items_to_remove:
            self.plot_view.removeItem(item)

        if len(self.query) > 0:
            x_signal = [x[0] for x in self.query]
            full_x_range = list(range(min(x_signal), max(x_signal) + 1))

            y_signals = {
                sig: [np.nan] * len(full_x_range) for sig in self.signal_list
            }

            for t, signals, _ in self.query:
                index = full_x_range.index(t)
                for sig in self.signal_list:
                    if sig in signals:
                        y_signals[sig][index] = signals[sig]

            # reset view
            self.plot_view.enableAutoRange(
                self.plot_view.getViewBox().XYAxes, True
            )

            if self.legend_on:
                legend = LegendItem(
                    offset=(70, 30)
                )  # Offset for the position of the legend in the view
                legend.setParentItem(self.plot_view.graphicsItem())

            for sig, col in zip(self.signal_list, self.color_list):
                if sig is not None:
                    y_signal_with_gaps = y_signals[sig]
                    pl = self.plot_view.plot(
                        full_x_range,
                        y_signal_with_gaps,
                        pen=mkPen(color=col, width=2),
                        name=sig,
                    )
                    if self.legend_on:
                        legend.addItem(pl, sig)
        else:
            self.viewer.status = 'Error - no such label in the database.'

    def update_tags(self):
        """
        Update of the tags on the graph.
        """
        self.get_db_info()
        self.redraw_tags()

    def update_signals(self):
        """
        Update of the signals on the graph.
        """
        self.get_db_info()
        self.redraw_signals()

    def update_graph_all(self):
        """
        Update of the signal display when a new label is selected.
        """
        if self.labels.selected_label != 0:
            self.get_db_info()
            self.redraw_signals()
            self.redraw_tags()
