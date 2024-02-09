from qtpy.QtGui import QIcon
from qtpy.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import and_

import tracks_interactions.db.db_functions as fdb
from tracks_interactions.db.db_model import CellDB, TrackDB
from tracks_interactions.widget.track_operations import modify_labels


class TracksWidget(QWidget):
    def __init__(self, napari_viewer, sql_session):
        super().__init__()
        self.setLayout(QVBoxLayout())

        self.viewer = napari_viewer
        self.labels = self.viewer.layers["Labels"]
        self.session = sql_session

        # add shortcuts
        self.init_shortcuts()

        # add track navigation
        self.navigation_row = self.add_navigation_control()

        # add track modification
        self.modification_row = self.add_modification_control()

    #########################################################
    # shortcuts
    #########################################################
    def init_shortcuts(self):
        """
        Initialize shortcuts for the widget.
        """
        # add a shortcut for right click selection
        self.labels.mouse_drag_callbacks.append(self.select_label)

    def select_label(self, layer, event):
        """
        Select a label by right click.
        Works on any layer.
        """
        if event.button == 2:
            # look up cursor position
            x = int(self.viewer.cursor.position[1])
            y = int(self.viewer.cursor.position[2])

            # check which cell was clicked
            myTrackNum = self.labels.data[
                self.viewer.dims.current_step[0], x, y
            ]

            # set track as active
            self.labels.selected_label = int(myTrackNum)

    #########################################################
    # track navigation
    #########################################################
    def add_navigation_control(self):
        """
        Add a set of buttons to navigate position within the track
        """

        navigation_row = QWidget()
        navigation_row.setLayout(QHBoxLayout())
        navigation_row.layout().setContentsMargins(0, 0, 0, 0)

        self.start_track_btn = self.add_start_track_btn()
        self.center_object_btn = self.add_center_object_btn()
        self.end_track_btn = self.add_end_track_btn()

        navigation_row.layout().addWidget(self.start_track_btn)
        navigation_row.layout().addWidget(self.center_object_btn)
        navigation_row.layout().addWidget(self.end_track_btn)

        self.layout().addWidget(navigation_row)

        return navigation_row

    def add_center_object_btn(self):
        """
        Add a button to center the object.
        """
        center_object_btn = QPushButton("<>")

        center_object_btn.clicked.connect(self.center_object_function)

        return center_object_btn

    def center_object_core_function(self):
        """
        Center the object that exists on this frame.
        """
        # orient yourself
        curr_tr = self.labels.selected_label
        curr_fr = self.viewer.dims.current_step[0]

        # find the object
        cell = (
            self.session.query(CellDB)
            .filter(and_(CellDB.track_id == curr_tr, CellDB.t == curr_fr))
            .first()
        )

        if cell is not None:
            # get the position
            x = cell.row
            y = cell.col

            # move the camera
            self.viewer.camera.center = (0, x, y)

        else:
            self.viewer.status = "No object in this frame."

    def center_object_function(self):
        """
        Center the object.
        """

        # orient yourself
        curr_tr = self.labels.selected_label
        curr_fr = self.viewer.dims.current_step[0]

        # find the pathway
        tr = self.session.query(TrackDB).filter_by(track_id=curr_tr).first()

        # move time point if beyond boundary
        if tr.t_begin > curr_fr:
            self.viewer.dims.set_point(0, tr.t_begin)
        elif tr.t_end < curr_fr:
            self.viewer.dims.set_point(0, tr.t_end)

        # center the cell
        self.center_object_core_function()

    def add_start_track_btn(self):
        """
        Add a button to cut tracks.
        """
        start_track_btn = QPushButton("<")

        start_track_btn.clicked.connect(self.start_track_function)

        return start_track_btn

    def start_track_function(self):
        """
        Go to the beginning of the track.
        """
        # find the beginning of a track
        tr = self.labels.selected_label
        t_begin = (
            self.session.query(TrackDB).filter_by(track_id=tr).first().t_begin
        )

        # move to the beginning of a track
        self.viewer.dims.set_point(0, t_begin)

        # center the cell
        self.center_object_core_function()

    def add_end_track_btn(self):
        """
        Add a button to go to the end of the track
        """
        end_track_btn = QPushButton(">")

        end_track_btn.clicked.connect(self.end_track_function)

        return end_track_btn

    def end_track_function(self):
        """
        Go to the last point in the track
        """
        # find the beginning of a track
        tr = self.labels.selected_label
        t_end = (
            self.session.query(TrackDB).filter_by(track_id=tr).first().t_end
        )

        # move to the end of a track
        self.viewer.dims.set_point(0, t_end)

        # center the cell
        self.center_object_core_function()

    #########################################################
    # track modification
    #########################################################
    def add_modification_control(self):
        """
        Add a set of buttons to modify tracks
        """

        modification_row = QWidget()
        modification_row.setLayout(QHBoxLayout())
        modification_row.layout().setContentsMargins(0, 0, 0, 0)

        # create the active tracks
        self.T1_box = self.add_T1_spinbox()
        # self.T2_box = self.add_T2_spinbox()

        # create the buttons
        self.cut_track_btn = self.add_cut_track_btn()
        self.merge_track_btn = self.add_merge_track_btn()
        self.connect_track_btn = self.add_connect_track_btn()

        # add everything to the layout
        modification_row.layout().addWidget(self.T1_box)
        modification_row.layout().addWidget(self.cut_track_btn)
        modification_row.layout().addWidget(self.connect_track_btn)
        modification_row.layout().addWidget(self.merge_track_btn)

        self.layout().addWidget(modification_row)

        return modification_row

    def add_T1_spinbox(self):
        """
        Add a spinbox to select the first track.
        """
        T1_box = QSpinBox()
        T1_box.setMinimum(0)
        T1_box.setMaximum(1000000)
        T1_box.setValue(self.labels.selected_label)

        # connect to the event of changing the track
        self.labels.events.selected_label.connect(self.T1_function)

        return T1_box

    def T1_function(self, event):
        """
        Change the value of T1.
        """
        self.T1_box.setValue(self.labels.selected_label)

    def add_cut_track_btn(self):
        """
        Add a button to cut tracks.
        """
        cut_track_btn = QPushButton("Cut track")

        cut_track_btn.clicked.connect(self.cut_track_function)

        path_to_cut_icon = (
            r"../tracks_interactions/icons/icons8-scissors-50.png"
        )

        icon = QIcon(path_to_cut_icon)
        cut_track_btn.setIcon(icon)
        cut_track_btn.setText(None)

        return cut_track_btn

    def cut_track_function(self):
        """
        Function that performs all the changes after a track is cut.
        """

        ################################################################################################
        # orient yourself - figure what is asked for

        # get the position in time
        current_frame = self.viewer.dims.current_step[0]

        # get my label
        active_label = int(self.viewer.layers["Labels"].selected_label)

        ################################################################################################
        # perform database operations

        # cut trackDB
        mitosis, new_track = fdb.cut_trackDB(
            self.session, active_label, current_frame
        )

        # if cutting from mitosis
        if mitosis:
            # trigger family tree update
            self.viewer.layers["Labels"].selected_label = active_label

        # if cutting in the middle of a track
        elif new_track:
            track_bbox = fdb.modify_track_cellsDB(
                self.session,
                active_label,
                current_frame,
                new_track,
                direction="after",
            )

            # modify labels
            modify_labels(self.viewer, track_bbox, active_label, new_track)

            # trigger family tree update
            self.viewer.layers["Labels"].selected_label = new_track

        # if clicked by mistake
        else:
            pass

        ################################################################################################
        # change viewer status
        self.viewer.status = f"Track {active_label} has been cut."

    def add_merge_track_btn(self):
        """
        Add a button to merge two tracks.
        """
        merge_track_btn = QPushButton("M")

        merge_track_btn.clicked.connect(self.merge_track_function)

        return merge_track_btn

    def merge_track_function(self):
        """
        Function that performs all the changes after a track is merged.
        """
        self.viewer.status = "Merge two tracks."

    def add_connect_track_btn(self):
        """
        Add a button to connect two tracks.
        """
        connect_track_btn = QPushButton("C")

        connect_track_btn.clicked.connect(self.connect_track_function)

        return connect_track_btn

    def connect_track_function(self):
        """
        Function that performs all the changes after a track is connected.
        """
        self.viewer.status = "Connect two tracks."
