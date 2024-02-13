from qtpy.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import and_

from tracks_interactions.db.db_model import CellDB, TrackDB


class TrackNavigationWidget(QWidget):
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

        # add checkbox for following the object
        self.follow_object_checkbox = self.add_follow_object_checkbox()

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
        curr_tr = int(
            self.labels.selected_label
        )  # because numpy.int64 is not accepted by the database
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
        curr_tr = int(
            self.labels.selected_label
        )  # because numpy.int64 is not accepted by the database
        curr_fr = self.viewer.dims.current_step[0]

        # find the pathway
        tr = self.session.query(TrackDB).filter_by(track_id=curr_tr).first()

        print(f"object {curr_tr} of {type(curr_tr)} found as {tr}")

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
    # cell following
    #########################################################

    def add_follow_object_checkbox(self):
        """
        Add a checkbox to follow the object.
        """
        follow_object_checkbox = QCheckBox("Follow track")

        follow_object_checkbox.stateChanged.connect(
            self.followBoxStateChanged_function
        )

        self.layout().addWidget(follow_object_checkbox)

        return follow_object_checkbox

    def followBoxStateChanged_function(self):
        """
        Follow the object if the checkbox is checked.
        """
        if self.follow_object_checkbox.isChecked():
            self.viewer.status = "Following the object is turned on."

            # center the cell (as at the beginning no slider is triggered)
            self.center_object_core_function()

            # connect centering to slider movement
            self.viewer.dims.events.current_step.connect(
                self.center_object_core_function
            )

            # connect centering to label selection
            self.labels.events.selected_label.connect(
                self.center_object_core_function
            )

        else:
            self.viewer.status = "Following the object is turned off."

            # disconnect from slider movement
            self.viewer.dims.events.current_step.disconnect(
                self.center_object_core_function
            )

            # disconnect from label selection
            self.labels.events.selected_label.disconnect(
                self.center_object_core_function
            )
