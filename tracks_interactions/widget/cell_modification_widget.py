from qtpy.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class CellModificationWidget(QWidget):
    def __init__(self, napari_viewer, sql_session):
        super().__init__()
        self.setLayout(QVBoxLayout())

        self.viewer = napari_viewer
        self.labels = self.viewer.layers["Labels"]
        self.session = sql_session

        # add shortcuts
        self.init_shortcuts()

        # add track navigation
        self.navigation_row = self.add_modification_control()

    #########################################################
    # shortcuts
    #########################################################

    def init_shortcuts(self):
        """
        Initialize shortcuts for the widget.
        """

    #########################################################
    # modfiy cell
    #########################################################

    def add_modification_control(self):
        """
        Add a set of buttons to navigate position within the track
        """

        cell_row = QWidget()
        cell_row.setLayout(QHBoxLayout())
        cell_row.layout().setContentsMargins(0, 0, 0, 0)

        self.mod_cell_btn = self.add_mod_cell_btn()

        cell_row.layout().addWidget(self.mod_cell_btn)

        self.layout().addWidget(cell_row)

        return cell_row

    def add_mod_cell_btn(self):
        """
        Add a button to trigger storing cell in the database.
        """
        mod_cell_btn = QPushButton("Save")

        mod_cell_btn.clicked.connect(self.mod_cell_function)

        return mod_cell_btn

    def mod_cell_function(self):
        """
        Store the current cell in the database.
        """
        active_cell = self.labels.selected_label
        # cell_properties = self.get_cell_properties()

        # store the cell in the CellDB

        # check if modification of TrackDB is needed
        # and modify

        # trigger update of the graphs

        self.viewer.status = f"Cell {active_cell} saved"

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
