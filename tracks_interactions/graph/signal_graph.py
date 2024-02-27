from pyqtgraph import (
    GraphicsLayoutWidget,
    mkPen,
)
from qtpy.QtCore import Qt

from tracks_interactions.db.db_model import CellDB


class SignalGraphWidget(GraphicsLayoutWidget):
    def __init__(self, viewer, session):
        super().__init__()

        self.setContextMenuPolicy(Qt.NoContextMenu)

        self.session = session
        self.viewer = viewer
        self.labels = self.viewer.layers["Labels"]

        # initialize graph
        self.plot_view = self.addPlot(
            title="Signal", labels={"bottom": "Time"}
        )

        self.t_max = self.viewer.dims.range[0][1]
        self.plot_view.setXRange(0, self.t_max)
        self.plot_view.setMouseEnabled(x=True, y=True)
        self.plot_view.setMenuEnabled(False)

        # Connect the plotItem's mouse click event
        # self.plot_view.scene().sigMouseClicked.connect(self.onMouseClick)

        # initialize time line
        pen = mkPen(color=(255, 255, 255), xwidth=1)
        init_position = self.viewer.dims.current_step[0]
        self.time_line = self.plot_view.addLine(x=init_position, pen=pen)

        # connect time slider event
        self.viewer.dims.events.current_step.connect(self.update_family_line)

        # connect label selection event
        self.labels.events.selected_label.connect(self.update_signal_display)

    def onMouseClick(self, event):
        """
        Mouse click event handler.
        Left - selection of a track
        Right - selection of a time point
        """
        vb = self.plot_view.vb
        scene_coords = event.scenePos()

        if self.plot_view.sceneBoundingRect().contains(scene_coords):
            mouse_point = vb.mapSceneToView(scene_coords)
            x_val = mouse_point.x()
            y_val = mouse_point.y()

            # right click - moving in time
            if event.button() == Qt.RightButton:
                pass
                # self.viewer.status = (
                #     f"Right click at {x_val}, {y_val}. Not implemented."
                # )

            # left click - selection of a track
            elif event.button() == Qt.LeftButton:
                # move in time
                self.viewer.dims.set_point(0, round(x_val))
                event.accept()

                # make a track active
                dist = float("inf")
                selected_n = None

                if self.tree is not None:
                    for n in self.tree.traverse():
                        if n.is_root():
                            pass
                        else:
                            # self.viewer.status=f'Clicked on {n.name}, {y_val} of {n.y}, {x_val} from {n.start} to {n.stop}!'
                            if (n.start <= x_val) and (n.stop >= x_val):
                                dist_track = abs(n.y - y_val)
                                if dist_track < dist:
                                    dist = dist_track
                                    selected_n = n

                    # capture if it tries to get attribute from None
                    try:
                        self.viewer.status = (
                            f"Selected track: {selected_n.name}"
                        )
                        self.labels.selected_label = selected_n.name

                        # center the cell
                        self.center_object_core_function()

                    except AttributeError:
                        print(
                            f"Click at {scene_coords.x()},{scene_coords.x()} translated to {x_val}, {y_val}"
                        )

                else:
                    self.viewer.status = "No tree to select from."

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
            self.session.query(CellDB.t, CellDB.signals["ch1_nuc"])
            .filter(CellDB.track_id == active_label)
            .order_by(CellDB.t)
            .all()
        )

        # actions based on finding the label in the database
        if query is not None:
            x_signal = [x[0] for x in query]
            y_signal = [x[1] for x in query]

            self.plot_view.plot(x_signal, y_signal)

        else:
            self.viewer.status = "Error - no such label in the database."
