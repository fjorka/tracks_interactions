from pyqtgraph import (
    GraphicsLayoutWidget,
    LegendItem,
    mkPen,
)
from qtpy.QtCore import Qt

from tracks_interactions.db.db_model import CellDB


class SignalGraph(GraphicsLayoutWidget):
    def __init__(
        self,
        viewer,
        session,
        legend_on=True,
        selected_signals=None,
        color_list=None,
    ):
        super().__init__()

        self.setContextMenuPolicy(Qt.NoContextMenu)

        self.session = session
        self.viewer = viewer
        self.labels = self.viewer.layers["Labels"]
        self.legend_on = legend_on
        self.signal_list = selected_signals
        self.color_list = color_list

        # initialize graph
        self.plot_view = self.addPlot(
            title="Signal", labels={"bottom": "Time"}
        )

        self.t_max = self.viewer.dims.range[0][1]
        self.plot_view.setXRange(0, self.t_max)
        self.plot_view.setMouseEnabled(x=True, y=True)
        self.plot_view.setMenuEnabled(False)

        # Connect the plotItem's mouse click event
        self.plot_view.scene().sigMouseClicked.connect(self.onMouseClick)

        # add time line
        self.time_line = self.add_time_line()

        # connect time slider event
        self.viewer.dims.events.current_step.connect(self.update_family_line)

        # connect label selection event
        self.labels.events.selected_label.connect(self.update_signal_display)

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

    def update_family_line(self):
        """
        Update of the family line when slider position is moved.
        """
        # line_position = event.value # that emitts warning for reasons that I don't understand
        line_position = self.viewer.dims.current_step[0]
        self.time_line.setValue(line_position)

    def update_signal_display(self):
        """
        Update of the signal display when a new label is selected.
        """

        # Clear all elements except the time line
        items_to_remove = self.plot_view.items[
            1:
        ]  # Get all items except the time line
        for item in items_to_remove:
            self.plot_view.removeItem(item)

        # get an active label
        active_label = int(self.viewer.layers["Labels"].selected_label)

        # check if the label is in the database
        query = (
            self.session.query(CellDB.t, CellDB.signals)
            .filter(CellDB.track_id == active_label)
            .order_by(CellDB.t)
            .all()
        )
        if query is not None:
            x_signal = [x[0] for x in query]

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
                y_signal = [x[1][sig] for x in query]
                pl = self.plot_view.plot(
                    x_signal, y_signal, pen=mkPen(color=col, width=2), name=sig
                )
                if self.legend_on:
                    legend.addItem(pl, sig)

        else:
            self.viewer.status = "Error - no such label in the database."
