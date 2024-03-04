from qtpy.QtWidgets import (
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from tracks_interactions.db.db_functions import (
    add_CellDB_to_DB,
    calculate_cell_signals,
    cut_trackDB,
)
from tracks_interactions.db.db_model import NO_PARENT, CellDB, TrackDB


class CellModificationWidget(QWidget):
    def __init__(
        self,
        napari_viewer,
        sql_session,
        ch_list=None,
        ch_names=None,
        ring_width=5,
    ):
        super().__init__()
        self.setLayout(QVBoxLayout())

        self.viewer = napari_viewer
        self.labels = self.viewer.layers["Labels"]
        self.session = sql_session
        self.ch_list = ch_list
        self.ch_names = ch_names
        self.ring_width = ring_width

        self.mod_cell_btn = self.add_mod_cell_btn()
        self.layout().addWidget(self.mod_cell_btn)

        # add a keyboard shortcut for label modification
        self.viewer.bind_key(
            "Shift-Enter", self.mod_cell_function, overwrite=True
        )

    def add_mod_cell_btn(self):
        """
        Add a button to trigger storing cell in the database.
        """
        mod_cell_btn = QPushButton("Save")

        mod_cell_btn.clicked.connect(self.mod_cell_function)

        return mod_cell_btn

    def mod_cell_function(self, viewer=None):
        """
        Store the current cell in the database.
        """

        # orient yourself
        active_cell = self.labels.selected_label
        frame = self.viewer.dims.current_step[0]

        cell_list = (
            self.session.query(CellDB)
            .filter(CellDB.t == frame)
            .filter(CellDB.track_id == active_cell)
            .all()
        )

        # adding new cell
        if len(cell_list) == 0:
            #  create CellDB
            new_cell = add_CellDB_to_DB(self.viewer)
            new_signals = calculate_cell_signals(
                new_cell,
                ch_list=self.ch_list,
                ch_names=self.ch_names,
                ring_width=self.ring_width,
            )
            new_cell.signals = new_signals
            self.session.add(new_cell)
            self.session.commit()

            # introduce TrackDB changes
            track = (
                self.session.query(TrackDB)
                .filter(TrackDB.track_id == active_cell)
                .first()
            )
            if track is not None:
                if track.t_begin > frame:
                    track.t_begin = frame
                    track.parent_track_id = NO_PARENT
                    track.root = active_cell
                if track.t_end < frame:
                    track.t_end = frame

                    # find children
                    children = (
                        self.session.query(TrackDB)
                        .filter(TrackDB.parent_track_id == active_cell)
                        .all()
                    )
                    # cut off children
                    for child in children:
                        _, _ = cut_trackDB(
                            self.session, child.track_id, child.t_begin
                        )
                        self.session.commit()

                self.session.commit()
            else:
                new_track = TrackDB(
                    track_id=active_cell,
                    parent_track_id=NO_PARENT,
                    root=active_cell,
                    t_begin=frame,
                    t_end=frame,
                )
                self.session.add(new_track)
                self.session.commit()

        # cell modification
        elif len(cell_list) == 1:
            cell = cell_list[0]
            new_cell = add_CellDB_to_DB(self.viewer)
            properties = [
                "track_id",
                "t",
                "row",
                "col",
                "bbox_0",
                "bbox_1",
                "bbox_2",
                "bbox_3",
                "mask",
                "tags",
            ]
            self.viewer.status = f"Modifying cell {active_cell} at {frame}."
            for prop in properties:
                setattr(cell, prop, getattr(new_cell, prop))
            new_signals = calculate_cell_signals(cell, ch_list=self.ch_list)
            cell.signals = new_signals

            # add tag
            cell.tags = {"modified": "True"}
            self.session.commit()

        else:
            self.viewer.status = (
                f"Error - Multiple cells found for {active_cell} at {frame}."
            )

        self.viewer.status = f"Cell {active_cell} from frame {frame} saved."

        # force graph update
        self.viewer.layers["Labels"].selected_label = 0
        self.viewer.layers["Labels"].selected_label = active_cell

    def get_cell_properties(self):
        """
        Get the properties of the current cell.
        """
        active_cell = self.labels.selected_label
        frame = self.viewer.dims.current_step[0]

        # get the current view
        # get coordinates of visible part
        coord_view = self.labels.corner_pixels.T
        r_start = coord_view[1, 0]
        r_end = coord_view[1, 1]
        c_start = coord_view[2, 0]
        c_end = coord_view[2, 1]

        labels_cropped = (
            self.labels[frame, r_start:r_end, c_start:c_end] == active_cell
        )

        # find the object
        return labels_cropped
