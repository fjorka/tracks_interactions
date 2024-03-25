from qtpy.QtCore import Qt
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import (
    QGridLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

import tracks_interactions.db.db_functions as fdb
from tracks_interactions.widget.track_operations import modify_labels


class TrackModificationWidget(QWidget):
    def __init__(self, napari_viewer, sql_session):
        super().__init__()
        self.setLayout(QVBoxLayout())

        self.viewer = napari_viewer
        self.labels = self.viewer.layers["Labels"]
        self.session = sql_session

        # add track modification
        self.modification_row = self.add_modification_control()

    #########################################################
    # track modification
    #########################################################

    def add_modification_control(self):
        """
        Add a set of buttons to modify tracks
        """

        modification_row = QWidget()

        # Create the grid layout
        modification_row.setLayout(QGridLayout())

        # Create the first row widgets
        labelT2 = QLabel("active")
        self.T2_box = self.add_T_spinbox(self.labels.selected_label)
        arrowLabel = QLabel(
            "→", alignment=Qt.AlignCenter
        )  # Big arrow label, centered
        arrowLabel.setStyleSheet("font-size: 24px;")  # Making the arrow bigger
        labelT1 = QLabel("to")
        self.T1_box = self.add_T_spinbox(self.labels.selected_label)

        # connect spinboxed to the event of changing the track
        self.labels.events.selected_label.connect(self.T_function)
        # connect change of T2 to change of active label
        # self.T2_box.valueChanged.connect(self.T2_change_function)
        self.T2_box.editingFinished.connect(self.T2_change_function)

        # Add first row widgets to the layout
        modification_row.layout().addWidget(labelT2, 0, 0)  # Row 0, Column 0
        modification_row.layout().addWidget(
            self.T2_box, 0, 1
        )  # Row 0, Column 1
        modification_row.layout().addWidget(
            arrowLabel, 0, 2
        )  # Row 0, Column 2
        modification_row.layout().addWidget(labelT1, 0, 3)  # Row 0, Column 3
        modification_row.layout().addWidget(
            self.T1_box, 0, 4
        )  # Row 0, Column 4

        # create the buttons
        self.cut_track_btn = self.add_cut_track_btn()
        self.merge_track_btn = self.add_merge_track_btn()
        self.connect_track_btn = self.add_connect_track_btn()
        self.del_track_btn = self.add_del_track_btn()
        self.new_track_btn = self.add_new_track_btn()

        # Add second row widgets to the layout
        modification_row.layout().addWidget(self.cut_track_btn, 1, 0)
        modification_row.layout().addWidget(self.merge_track_btn, 1, 1)
        modification_row.layout().addWidget(self.connect_track_btn, 1, 2)
        modification_row.layout().addWidget(self.del_track_btn, 1, 3)
        modification_row.layout().addWidget(self.new_track_btn, 1, 4)

        self.layout().addWidget(modification_row)

        return modification_row

    def add_T_spinbox(self, value):
        """
        Add a spinbox for track selection
        """
        T_box = QSpinBox()
        T_box.setMinimum(0)
        T_box.setMaximum(1000000)
        T_box.setValue(value)

        return T_box

    def T_function(self, event):
        """
        Change the values of T1 and T2 spinboxes.
        """
        prev_tr = self.T2_box.value()
        self.T2_box.setValue(self.labels.selected_label)
        self.T1_box.setValue(prev_tr)

    def T2_change_function(self):
        """
        Change the value of the active label.
        """
        self.labels.selected_label = self.T2_box.value()

    ################################################################################################
    ################################################################################################
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

        ############################################################################################
        # orient yourself - figure what is asked for

        # get the position in time
        current_frame = self.viewer.dims.current_step[0]

        # get my label
        active_label = int(self.labels.selected_label)

        ############################################################################################
        # perform database operations

        # cut trackDB
        mitosis, new_track = fdb.cut_trackDB(
            self.session, active_label, current_frame
        )

        # if cutting from mitosis
        if mitosis:
            # trigger family tree update
            self.labels.selected_label = 0
            self.labels.selected_label = active_label

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

        ############################################################################################
        # change viewer status
        self.viewer.status = f"Track {active_label} has been cut."

    ################################################################################################
    ################################################################################################
    def add_del_track_btn(self):
        """
        Add a button to cut tracks.
        """
        del_track_btn = QPushButton("Delete track")

        del_track_btn.clicked.connect(self.del_track_function)

        path_to_del_icon = r"../tracks_interactions/icons/icons8-delete-48.png"

        icon = QIcon(path_to_del_icon)
        del_track_btn.setIcon(icon)
        del_track_btn.setText(None)

        return del_track_btn

    def del_track_function(self):
        """
        Function that performs all the changes after a track is deleted
        """

        ############################################################################################
        # orient yourself - figure what is asked for

        # get my label
        active_label = int(self.labels.selected_label)

        # get yourself

        ############################################################################################
        # perform database operations

        # delete trackDB
        status = fdb.delete_trackDB(self.session, active_label)

        if status != "Track not found":
            track_bbox = fdb.modify_track_cellsDB(
                self.session,
                active_label,
                current_frame=None,
                new_track=None,
                direction="all",
            )

            # modify labels
            modify_labels(self.viewer, track_bbox, active_label, 0)

            # trigger family tree update
            self.labels.selected_label = 0

        self.viewer.status = status

    ################################################################################################
    ################################################################################################
    def add_merge_track_btn(self):
        """
        Add a button to merge two tracks.
        """
        merge_track_btn = QPushButton("M")

        merge_track_btn.clicked.connect(self.merge_track_function)

        path_to_merge_icon = r"../tracks_interactions/icons/icons8-link-50.png"

        icon = QIcon(path_to_merge_icon)
        merge_track_btn.setIcon(icon)
        merge_track_btn.setText(None)

        return merge_track_btn

    def merge_track_function(self):
        """
        Function that performs all the changes after a track is merged.
        Track T2 is merged to track T1.
        """

        curr_fr = self.viewer.dims.current_step[0]

        t2 = self.T2_box.value()
        t1 = self.T1_box.value()

        ################################################################################################
        # check if the request is possible
        if t1 == t2:
            self.viewer.status = "Error - cannot merge a track with itself."
            return

        ################################################################################################
        # perform database operations

        # cut trackDB
        t1_after, _ = fdb.integrate_trackDB(
            self.session, "merge", t1, t2, curr_fr
        )

        if t1_after == -1:
            self.viewer.status = (
                "Error - cannot merge to a track that hasn't started yet."
            )
            return

        if t1_after is not None:
            # modify cellsDB of t1
            track_bbox_t1 = fdb.modify_track_cellsDB(
                self.session, t1, curr_fr, t1_after, direction="after"
            )

            # modify labels of t1
            modify_labels(self.viewer, track_bbox_t1, t1, t1_after)

        # modify cellsDB of t2
        track_bbox_t2 = fdb.modify_track_cellsDB(
            self.session, t2, curr_fr, t1, direction="after"
        )

        # modify labels of t2
        modify_labels(self.viewer, track_bbox_t2, t2, t1)

        ################################################################################################
        # change viewer status
        self.T2_box.setValue(t1)
        self.T1_box.setValue(t2)
        self.viewer.status = f"Track {t2} has been merged to {t1}. Track {t1_after} has been created."

        # trigger updates
        self.labels.selected_label = t1

    ################################################################################################
    ################################################################################################
    def add_connect_track_btn(self):
        """
        Add a button to connect two tracks.
        """
        connect_track_btn = QPushButton("C")

        connect_track_btn.clicked.connect(self.connect_track_function)

        path_to_con_icon = (
            r"../tracks_interactions/icons/icons8-connect-50.png"
        )

        icon = QIcon(path_to_con_icon)
        connect_track_btn.setIcon(icon)
        connect_track_btn.setText(None)

        return connect_track_btn

    def connect_track_function(self):
        """
        Function that performs all the changes after a track is connected.
        Track
        """

        # get the position in time
        curr_fr = self.viewer.dims.current_step[0]

        # get the tracks to interact with
        t2 = self.T2_box.value()
        t1 = self.T1_box.value()

        ################################################################################################
        # check if the request is possible
        if t1 == t2:
            self.viewer.status = "Error - cannot connect a track with itself."
            return

        ################################################################################################
        # perform database operations

        # cut trackDB
        t1_after, t2_before = fdb.integrate_trackDB(
            self.session, "connect", t1, t2, curr_fr
        )

        if t1_after == -1:
            self.viewer.status = (
                "Error - cannot connect to a track that hasn't started yet."
            )
            return

        if t1_after is not None:
            # modify cellsDB of t1_after
            track_bbox_t1 = fdb.modify_track_cellsDB(
                self.session, t1, curr_fr, t1_after, direction="after"
            )

            # modify labels of t1_after
            modify_labels(self.viewer, track_bbox_t1, t1, t1_after)

            # change viewer status
            self.viewer.status = f"Track {t2} has been connected to {t1}. Track {t1_after} has been created."

        if t2_before is not None:
            # modify cellsDB of t2
            track_bbox_t2 = fdb.modify_track_cellsDB(
                self.session, t2, curr_fr, t2_before, direction="before"
            )

            # modify labels of t2_before
            modify_labels(self.viewer, track_bbox_t2, t2, t2_before)

            # change viewer status
            self.viewer.status = f"Track {t2} has been connected to {t1}. Track {t2_before} has been created."

        # account for different both and none new tracks in viewer status
        if t1_after is not None and t2_before is not None:
            self.viewer.status = f"Track {t2} has been connected to {t1}. Tracks {t1_after} and {t2_before} have been created."

        elif t1_after is None or t2_before is None:
            self.viewer.status = f"Track {t2} has been connected to {t1}."

        # trigger family tree update
        self.labels.selected_label = 0
        self.labels.selected_label = t2

        # set T1 and T1
        self.T2_box.setValue(t2)
        self.T1_box.setValue(t1)

    ################################################################################################
    ################################################################################################
    def add_new_track_btn(self):
        """
        Add a button to connect two tracks.
        """
        new_track_btn = QPushButton("N")

        new_track_btn.clicked.connect(self.new_track_function)

        path_to_new_icon = r"../tracks_interactions/icons/icons8-add-64.png"

        icon = QIcon(path_to_new_icon)
        new_track_btn.setIcon(icon)
        new_track_btn.setText(None)

        return new_track_btn

    def new_track_function(self):
        """
        Function that performs all the changes after a track is connected.
        Track
        """

        new_track = fdb.newTrack_number(self.session)
        self.labels.selected_label = new_track

        self.viewer.status = f"You can start track {new_track}."
