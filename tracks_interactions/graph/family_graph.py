import numpy as np
import pandas as pd
from ete3 import Tree
from pyqtgraph import (
    GraphicsLayoutWidget,
    TextItem,
    mkColor,
    mkPen,
)
from qtpy.QtCore import Qt

from tracks_interactions.db.db_model import TrackDB


class FamilyGraphWidget(GraphicsLayoutWidget):
    def __init__(self, viewer, session):
        super().__init__()

        self.setContextMenuPolicy(Qt.NoContextMenu)

        self.session = session
        self.viewer = viewer
        self.labels = self.viewer.layers["Labels"]

        # initialize graph
        self.plot_view = self.addPlot(
            title="Lineage tree", labels={"bottom": "Time"}
        )
        self.plot_view.hideAxis("left")
        self.t_max = self.viewer.dims.range[0][1]
        self.plot_view.setXRange(0, self.t_max)
        self.plot_view.setMouseEnabled(x=True, y=True)
        self.plot_view.setMenuEnabled(False)

        # Connect the plotItem's mouse click event
        self.plot_view.scene().sigMouseClicked.connect(self.onMouseClick)

        # initialize time line
        pen = mkPen(color=(255, 255, 255), xwidth=1)
        init_position = self.viewer.dims.current_step[0]
        self.time_line = self.plot_view.addLine(x=init_position, pen=pen)

        # connect time slider event
        self.viewer.dims.events.current_step.connect(self.update_family_line)

        # connect label selection event
        self.labels.events.selected_label.connect(self.update_lineage_display)

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

            ############################################################
            # find which track was selected
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
            ############################################################

            if event.button() == Qt.LeftButton:
                # move in time
                self.viewer.dims.set_point(0, round(x_val))

                # capture if it tries to get attribute from None
                try:
                    self.viewer.status = f"Selected track: {selected_n.name}"
                    self.labels.selected_label = selected_n.name

                except AttributeError:
                    print(
                        f"Click at {scene_coords.x()},{scene_coords.x()} translated to {x_val}, {y_val}"
                    )

            # right click - change of status
            elif event.button() == Qt.RightButton:
                if selected_n is not None:
                    # flip the status
                    track = (
                        self.session.query(TrackDB)
                        .filter(TrackDB.track_id == selected_n.name)
                        .first()
                    )
                    track.accepted_tag = not track.accepted_tag
                    self.session.commit()

                    # update the tree
                    self.update_lineage_display()

                    # update viewer status
                    self.viewer.status = f"Track {selected_n.name} accepted status: {track.accepted_tag}."

        else:
            self.viewer.status = "No tree to select from."

    def update_family_line(self):
        """
        Update of the family line when slider position is moved.
        """
        # line_position = event.value # that emitts warning for reasons that I don't understand
        line_position = self.viewer.dims.current_step[0]
        self.time_line.setValue(line_position)

    def update_lineage_display(self):
        """
        Update of the lineage display when a new label is selected.
        """

        # Clear all elements except the time line
        items_to_remove = self.plot_view.items[
            1:
        ]  # Get all items except the time line
        for item in items_to_remove:
            self.plot_view.removeItem(item)

        # get an active label
        active_label = int(self.labels.selected_label)

        # check if the label is in the database
        query = (
            self.session.query(TrackDB)
            .filter(TrackDB.track_id == active_label)
            .first()
        )

        # actions based on finding the label in the database
        if query is not None:
            # get the root value
            root = query.root

            # update viewer status
            self.viewer.status = f"Family of track number {root}."

            # buid the tree
            self.tree = build_Newick_tree(self.session, root)

            # update the widget with the tree
            self.render_tree_view(self.tree)

        else:
            self.viewer.status = "Error - no such label in the database."

    def render_tree_view(self, t):
        """
        Create a new family tree when the update is called.
        """

        y_max = 1
        active_label = int(self.labels.selected_label)

        # render the tree
        t_rendering = t.render(".")

        # add position of y to the rendering
        t = _add_y_rendering(t, t_rendering)

        for n in t.traverse():
            if n.is_root():
                pass
            else:
                node_name = n.name

                # get position in time
                x1 = n.start
                x2 = n.stop
                x_signal = [x1, x2]

                # get rendered position (y axis)
                y_signal = n.y.repeat(2)
                y_max = np.max([n.y, y_max])

                label_color = self.labels.get_color(node_name)

                if n.name == active_label:
                    pen_color = mkColor((label_color * 255).astype(int))
                    pen = mkPen(color=pen_color, width=4)
                else:
                    label_color[-1] = 0.4
                    pen_color = mkColor((label_color * 255).astype(int))
                    pen = mkPen(color=pen_color, width=2)

                if n.accepted is False:
                    pen.setStyle(Qt.DotLine)

                self.plot_view.plot(x_signal, y_signal, pen=pen)

                # add text
                if n.accepted is True:
                    text_item = TextItem(
                        str(node_name), anchor=(1, 1), color="green"
                    )

                else:
                    text_item = TextItem(str(node_name), anchor=(1, 1))

                text_item.setPos(x2, n.y)
                self.plot_view.addItem(text_item)

                # check if children are present
                if len(n.children) > 0:
                    for child in n.children:
                        x_signal = [x2, x2]
                        y_signal = [n.y, child.y]
                        self.plot_view.plot(x_signal, y_signal, pen=pen)

        # set limits on axis
        self.plot_view.setXRange(0, self.t_max)
        self.plot_view.setYRange(0, 1.1 * y_max)


def _add_children(node, df, n=2):
    """
    Helper function for build_Newick_tree
    Recursively adds children to the tree from a dataframe.
    Modifies the tree in place.

    input:
        node - ete3.TreeNode
        df - dataframe with info about children
        n - number of the first child
    output:
        None
    """

    # get a df with the info about children
    children = df.loc[df.parent_track_id == node.name, :]

    for _, row in children.iterrows():
        child_node = node.add_child(name=row["track_id"])
        child_node.add_features(
            num=n,
            start=row["t_begin"],
            stop=row["t_end"],
            accepted=row["accepted_tag"],
        )

        n += 1

        n = _add_children(child_node, df, n)

    return n


def _add_y_rendering(t, t_rendering):
    """
    Helper function for rendering of a tree.
    For convenience to keep y values in the tree.
    Helpful while generating vertical lines.
    t -
    t_rendering -
    """

    for n in t.traverse(strategy="preorder"):
        if n.is_root():
            pass
        else:
            y = np.mean(
                [
                    t_rendering["node_areas"][n.num][1],
                    t_rendering["node_areas"][n.num][3],
                ]
            )
            n.add_feature("y", y)

    return t


def build_Newick_tree(session, root_id):
    """
    input:
        - root_id
        - session
    output:
        - Newick tree to construct a graph
    """

    # get info about the family from the database
    query = session.query(TrackDB).filter(TrackDB.root == root_id)
    df = pd.read_sql(query.statement, session.bind)

    # make sure that the root of this id exists
    assert len(df) > 0, "No data for this root_id"

    # create tree
    tree = Tree(name=root_id)

    # add trunk
    trunk_row = df.loc[df.track_id == root_id, :]

    trunk = tree.add_child(name=root_id)
    trunk.add_features(
        num=1,
        start=trunk_row["t_begin"].values[0],
        stop=trunk_row["t_end"].values[0],
        accepted=bool(trunk_row["accepted_tag"].values[0]),
    )

    # add children
    _add_children(trunk, df)

    # return tree
    return tree
