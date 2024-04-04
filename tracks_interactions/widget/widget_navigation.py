from qtpy.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QGroupBox,
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
        self.labels = self.viewer.layers['Labels']
        self.session = sql_session
        self.query_lim = 500

        # add shortcuts
        self.init_shortcuts()

        widget = QWidget()
        widget.setLayout(QGridLayout())
        widget.layout().setContentsMargins(0, 0, 0, 0)
        navigation_group = QGroupBox()
        navigation_group.setLayout(QGridLayout())
        navigation_group.layout().setContentsMargins(0, 0, 0, 0)

        # add track navigation
        self.navigation_row = self.add_navigation_control()
        navigation_group.layout().addWidget(self.navigation_row, 0, 0)

        # add checkbox for following the object
        self.follow_object_checkbox = self.add_follow_object_checkbox()
        navigation_group.layout().addWidget(self.follow_object_checkbox, 1, 0)
        # set initial the default status to checked
        self.follow_object_checkbox.setChecked(True)

        widget.layout().addWidget(navigation_group)
        self.layout().addWidget(widget)

        # build labels layer
        self.build_labels()

        # connect building labels to the viewer
        self.viewer.camera.events.zoom.connect(self.build_labels)
        self.viewer.camera.events.center.connect(self.build_labels)
        self.labels.events.visible.connect(self.build_labels)

    #########################################################
    # shortcuts
    #########################################################

    def init_shortcuts(self):
        """
        Initialize shortcuts for the widget.
        """
        # add a shortcut for right click selection
        self.viewer.mouse_drag_callbacks.append(self.select_label)

    def select_label(self, viewer, event):
        """
        Select a label by right click.
        Works on any layer.
        """
        if event.button == 2:
            # look up cursor position
            position = tuple([int(x) for x in self.viewer.cursor.position])

            # check which cell was clicked
            myTrackNum = self.labels.data[position[1], position[2]]

            # set track as active
            self.labels.selected_label = int(myTrackNum)

    #########################################################
    # labels_layer_update
    #########################################################

    def build_labels(self):
        """
        Function to build the labels layer based on db content
        """

        if self.viewer.layers['Labels'].visible:
            current_frame = self.viewer.dims.current_step[0]

            # clear labels
            self.viewer.layers['Labels'].data[:] = 0

            # get the corner pixels of the viewer - for magnification
            corner_pixels = self.labels.corner_pixels

            r_rad = (corner_pixels[1, 0] - corner_pixels[0, 0]) / 2
            c_rad = (corner_pixels[1, 1] - corner_pixels[0, 1]) / 2

            # get the center position of the viewer
            r = self.viewer.camera.center[1]
            c = self.viewer.camera.center[2]

            # calculate labels extent
            r_start = r - r_rad
            r_stop = r + r_rad
            c_start = c - c_rad
            c_stop = c + c_rad

            # query the database
            query = (
                self.session.query(CellDB)
                .filter(CellDB.t == current_frame)
                .filter(CellDB.bbox_0 < int(r_stop))
                .filter(CellDB.bbox_1 < int(c_stop))
                .filter(CellDB.bbox_2 > int(r_start))
                .filter(CellDB.bbox_3 > int(c_start))
                .limit(self.query_lim)
                .all()
            )

            if len(query) < self.query_lim:
                frame = self.viewer.layers['Labels'].data

                for cell in query:
                    frame[
                        cell.bbox_0 : cell.bbox_2, cell.bbox_1 : cell.bbox_3
                    ] += (cell.mask.astype(int) * cell.track_id)

                self.viewer.layers['Labels'].data = frame
                self.viewer.status = f'Found {len(query)} cells in the field.'

                # store the query with the layer
                self.labels.metadata['query'] = query

            else:
                self.viewer.layers['Labels'].refresh()
                self.viewer.status = f'More than {self.query_lim} in the field - zoom in to display labels.'

    #########################################################
    # track navigation
    #########################################################

    def add_navigation_control(self):
        """
        Add a set of buttons to navigate position within the track
        """

        navigation_row = QWidget()
        navigation_row.setLayout(QGridLayout())

        self.start_track_btn = self.add_start_track_btn()
        self.center_object_btn = self.add_center_object_btn()
        self.end_track_btn = self.add_end_track_btn()

        navigation_row.layout().addWidget(self.start_track_btn, 0, 0)
        navigation_row.layout().addWidget(self.center_object_btn, 0, 1)
        navigation_row.layout().addWidget(self.end_track_btn, 0, 2)

        return navigation_row

    def add_center_object_btn(self):
        """
        Add a button to center the object.
        """
        center_object_btn = QPushButton('<>')

        center_object_btn.clicked.connect(self.center_object_function)

        return center_object_btn

    def center_object_core_function(self):
        """
        Center the object that exists on this frame.
        """
        # orient yourself
        track_id = int(
            self.labels.selected_label
        )  # because numpy.int64 is not accepted by the database
        current_frame = self.viewer.dims.current_step[0]

        if track_id != 0:
            # find the object
            cell = (
                self.session.query(CellDB)
                .filter(
                    and_(
                        CellDB.track_id == track_id, CellDB.t == current_frame
                    )
                )
                .first()
            )

            if cell is not None:
                # get the position
                r = cell.row
                c = cell.col

                # check if there is movement
                _, x, y = self.viewer.camera.center

                if x == r and y == c:
                    # trigger rebuilding of labels
                    self.build_labels()
                else:
                    # move the camera
                    self.viewer.camera.center = (0, r, c)

            else:
                self.viewer.status = 'No object in this frame.'
                self.build_labels()

        else:
            self.viewer.status = 'No object selected.'
            self.build_labels()

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
        start_track_btn = QPushButton('<')

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
        end_track_btn = QPushButton('>')

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
        follow_object_checkbox = QCheckBox('Follow track')

        follow_object_checkbox.stateChanged.connect(
            self.followBoxStateChanged_function
        )

        return follow_object_checkbox

    def followBoxStateChanged_function(self):
        """
        Follow the object if the checkbox is checked.
        """
        if self.follow_object_checkbox.isChecked():
            self.viewer.status = 'Following the object is turned on.'

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

            # disconnect building labels from the slider
            self.viewer.dims.events.current_step.disconnect(self.build_labels)

        else:
            self.viewer.status = 'Following the object is turned off.'

            # disconnect from slider movement
            self.viewer.dims.events.current_step.disconnect(
                self.center_object_core_function
            )

            # disconnect from label selection
            self.labels.events.selected_label.disconnect(
                self.center_object_core_function
            )

            # connect building labels to the slider
            self.viewer.dims.events.current_step.connect(self.build_labels)
