import numpy as np
import pandas as pd
import pyqtgraph as pg
from ete3 import Tree
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from napari import Viewer
from tracks_interactions.db.db_model import TrackDB

viewer = Viewer()
engine = create_engine("sqlite:///:memory:")
# plot_widget


def add_children(node, df, n=2):
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
        child_node.add_features(num=n, start=row["t_begin"], stop=row["t_end"])

        n += 1

        n = add_children(child_node, df, n)

    return n


def build_Newick_tree(engine, root_id):
    """
    input:
        - root_id
        - engine
    output:
        - Newick tree to construct a graph
    """

    # get info about the family from the database
    with Session(engine) as session:
        query = session.query(TrackDB).filter(TrackDB.root == root_id)
        df = pd.read_sql(query.statement, engine)

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
    )

    # add children
    add_children(trunk, df)

    # return tree
    return tree


def add_y_rendering(t, t_rendering):
    """
    Helper function for rendering of a tree.
    For convenience to keep y values in the tree.
    Helpful while generating vertical lines.
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


def render_tree_view(plot_view, t, viewer):
    """
    Input:
    plot_view - from plot_widget
    t - tree object
    viewer - general napari viewer (to get label colors)
    Output:
    plot_view - a plot with the tree rendered on it.
    """

    labels_layer = viewer.layers["Labels"]

    y_max = 1

    # render the tree
    t_rendering = t.render(".")

    # add position of y to the rendering
    t = add_y_rendering(t, t_rendering)

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

            label_color = labels_layer.get_color(node_name)
            pen = pg.mkPen(
                color=pg.mkColor((label_color * 255).astype(int)), width=5
            )

            plot_view.plot(x_signal, y_signal, pen=pen)

            text_item = pg.TextItem(str(node_name), anchor=(1, 1))
            text_item.setPos(x2, n.y)
            plot_view.addItem(text_item)

            # check if children are present
            if len(n.children) > 0:
                for child in n.children:
                    x_signal = [x2, x2]
                    y_signal = [n.y, child.y]
                    plot_view.plot(x_signal, y_signal, pen=pen)

    # set limits on axis
    t_max = viewer.dims.range[0][1]
    plot_view.setXRange(0, t_max)
    plot_view.setYRange(0, 1.1 * y_max)

    return plot_view


def build_lineage_widget(t_max):
    """
    Builds pyqt widget to display lineage tree.
    """

    global plot_widget

    plot_widget = pg.GraphicsLayoutWidget()
    plot_view = plot_widget.addPlot(
        title="Lineage tree", labels={"bottom": "Time"}
    )
    plot_view.hideAxis("left")
    plot_view.setXRange(0, t_max)

    return plot_widget


def update_lineage_display(event):
    global plot_widget  # it may be possible to extract from napari, at the moment a global thing
    # global viewer
    # global time_line

    # clear the widget
    plot_view = plot_widget.getItem(0, 0)
    plot_view.clear()

    # get an active label
    active_label = int(viewer.layers["Labels"].selected_label)

    # check if the label is in the database
    with Session(engine) as session:
        query = (
            session.query(TrackDB)
            .filter(TrackDB.track_id == active_label)
            .first()
        )

    # actions based on finding the label in the database
    if query is not None:
        # get the root value
        root = query.root

        # update viewer status
        viewer.status = f"Family of track number {root}."

        # buid the tree
        tree = build_Newick_tree(engine, root)

        # update the widget with the tree
        plot_view = render_tree_view(plot_view, tree, viewer)

    else:
        viewer.status = "Error - no such label in the database."
